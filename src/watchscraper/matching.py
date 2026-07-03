"""The listing→reference matching rules engine.

Every listing is resolved to a specific reference number (the atomic watch)
through ordered rules, each with a confidence and a recorded method:

  1. exact_ref  (0.95)  Explicit reference in the title, validated against
                         the catalog. A stated year outside the reference's
                         production window flags a conflict and downgrades
                         to 0.80 — the reference still wins over the year,
                         because sellers type years loosely (service years,
                         purchase years) but rarely invent reference numbers.
  2. alias      (0.90)  Alternate spellings that map 1:1 to a reference
                         (long-form AP refs, Patek dash suffixes).
  3. nickname   (0.80)  Community names ("Hulk", "Batman", "Pepsi") resolved
                         through the nickname table. Where a nickname spans
                         generations, the stated year picks the reference;
                         with no year, bracelet/attribute hints are tried,
                         then the current-production generation wins at
                         reduced confidence (0.55) — most listings are the
                         newer watch.
  4. attributes (0.65)  No ref, no nickname: the family plus extracted
                         attributes (size, material class, dial, bezel,
                         date/no-date, year window) must narrow the family's
                         candidates to exactly one reference.
  5. family     (0.30)  Only the family (collection) is knowable. watch_id
                         stays NULL; the analysis layer prices these at
                         family level.

Values derive from variants: because each reference IS a variant
(color/material/combo), pricing per reference prices the variant.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchscraper.analysis import BRAND_PATTERNS, _match_family
from watchscraper.normalizers.reference import normalize_reference

CURRENT_YEAR = 2026


# ── Attribute extraction ──────────────────────────────────────────────────

_YEAR_RE = re.compile(r"(?<![\d.])(19[4-9]\d|20[0-4]\d)(?![\d.])")
_SIZE_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\s?mm\b", re.IGNORECASE)
_DIAL_RE = re.compile(
    r"\b(mother of pearl|ice blue|black|white|blue|green|grey|gray|silver|"
    r"champagne|chocolate|brown|salmon|olive|golden|gold|rhodium|slate|"
    r"meteorite|panda|cream|tiffany|pink|rose|ivory|sundust|turquoise|steel)"
    r"\s+(?:colou?r\s+)?(?:index\s+)?dial",
    re.IGNORECASE,
)
_BEZEL_RE = re.compile(
    r"\b(black|blue|green|red|brown|grey|gray|ceramic|fluted|smooth)"
    r"(?:\s*(?:&|/|and|-)\s*(black|blue|green|red|brown|grey|gray))?\s+bezel",
    re.IGNORECASE,
)
_NO_DATE_RE = re.compile(r"\bno[\s-]?date\b", re.IGNORECASE)

_MATERIAL_CLASSES: list[tuple[str, str]] = [
    ("two-tone", r"two[\s-]?tone|rolesor|steel\s*(?:&|/|and)\s*(?:18k\s*)?(?:yellow\s+|rose\s+|everose\s+)?gold|18k/ss|gold/steel"),
    ("rose-gold", r"rose\s+gold|everose|pink\s+gold|sedna"),
    ("white-gold", r"white\s+gold"),
    ("yellow-gold", r"yellow\s+gold|18k\s+gold(?!\s*/)|solid\s+gold"),
    ("platinum", r"\bplatinum\b"),
    ("titanium", r"\btitanium\b"),
    ("ceramic", r"\bceramic\b(?!\s+bezel)"),
    ("steel", r"stainless|oystersteel|\bsteel\b(?!\s*(?:&|/|and)\s*gold)"),
]

_BRACELETS: list[tuple[str, str]] = [
    ("jubilee", r"\bjubilee\b"),
    ("oysterflex", r"\boysterflex\b"),
    ("president", r"\bpresident\b"),
    ("oyster", r"\boyster\s+(?:bracelet|band)\b|\bon\s+oyster\b"),
    ("leather", r"\bleather\b"),
    ("rubber", r"\brubber\b"),
    ("nato", r"\bnato\b"),
    ("mesh", r"\bmesh\b"),
]

_DIAL_SYNONYMS = {
    "gray": "grey",
    "golden": "gold",
    "panda": "white",  # a "panda dial" Daytona is the white-dial variant
}

# Reference-candidate patterns, most specific first. These run against the
# raw title (word boundaries intact); each hit is then normalized and looked
# up in the catalog. An optional space is tolerated between digits and a
# letter suffix ("126610 LN").
_REF_CANDIDATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3}"),           # Omega
    re.compile(r"\d{4,5}[A-Z]?/\d{3}[A-Z]-[A-Z0-9]{4,5}", re.I),      # VC
    re.compile(r"\bIW\d{6}\b", re.I),                                  # IWC
    re.compile(r"\bQ\d{7}\b", re.I),                                   # JLC
    re.compile(r"(?<!\d)\d{3}\.\d{3}(?!\d)"),                          # Lange
    re.compile(r"\b(?:CR)?W[A-Z]{2,4}\d{4}\b", re.I),                  # Cartier
    re.compile(r"(?<![\d.])[12][56]\d{3} ?[A-Z]{2}\b", re.I),          # AP
    re.compile(r"\b5\d{3}[A-Z]?(?:/\d[A-Z]+(?:-\d{3})?)?\b", re.I),    # Patek
    re.compile(r"(?<![\d.])1[12]\d{4}(?: ?[A-Z]{2,6})?(?![\d.])", re.I),  # Rolex 6-digit
    re.compile(r"(?<![\d.])1[4-9]\d{3}(?: ?[A-Z]{1,6})?(?![\d.])", re.I),  # Rolex 5-digit
    # Rolex 4-digit vintage refs — enumerated, since generic 4-digit patterns
    # collide with years and sizes
    re.compile(r"(?<![\d.])(?:1675|1016|5513|5512|1601|1603|6263|6265|1665|1680)(?![\d.])"),
]


def extract_ref_candidates(title: str, brand_slug: str | None = None) -> list[str]:
    """Normalized reference candidates found in a raw title, specific-first.

    Rolex candidates with a space-joined letter suffix also yield their bare
    digits as a fallback ("16610 SERVICED" must still find 16610).
    """
    candidates: list[str] = []
    fallbacks: list[str] = []

    def add(value: str, pool: list[str]) -> None:
        if value and value not in candidates and value not in fallbacks:
            pool.append(value)

    for pattern in _REF_CANDIDATE_PATTERNS:
        for m in pattern.finditer(title):
            raw = m.group(0)
            cleaned = re.sub(r"\s+", "", raw).upper()
            normalized = normalize_reference(raw, brand_slug).upper()
            # The un-normalized form first: a Patek dash suffix (5711/1A-014)
            # pins the exact dial variant and must win over the bare ref.
            if cleaned != normalized:
                add(cleaned, candidates)
            add(normalized, candidates)
            if " " in raw:
                digits = re.match(r"1\d{4,5}", raw)
                if digits:
                    add(digits.group(0), fallbacks)
    return candidates + fallbacks


def extract_attributes(title: str) -> dict:
    """Structured attributes from a listing title.

    Scrapers call this at ingest time so every listing lands with its
    variant signals (year, size, material, dial, bezel, bracelet, date)
    already parsed.
    """
    text = title or ""
    attrs: dict = {}

    years = [int(y) for y in _YEAR_RE.findall(text)]
    years = [y for y in years if y <= CURRENT_YEAR + 1]
    if years:
        # The latest plausible year is the watch year more often than not
        # ("1990s style, 2021 card" → 2021 is what dates the watch).
        attrs["year"] = max(years)

    m = _SIZE_RE.search(text)
    if m:
        size = float(m.group(1))
        if 20 <= size <= 55:
            attrs["size_mm"] = size

    m = _DIAL_RE.search(text)
    if m:
        color = m.group(1).lower()
        attrs["dial"] = _DIAL_SYNONYMS.get(color, color)

    m = _BEZEL_RE.search(text)
    if m:
        parts = [p.lower() for p in m.groups() if p]
        attrs["bezel"] = "/".join(_DIAL_SYNONYMS.get(p, p) for p in parts)

    for cls, pattern in _MATERIAL_CLASSES:
        if re.search(pattern, text, re.IGNORECASE):
            attrs["material"] = cls
            break

    for name, pattern in _BRACELETS:
        if re.search(pattern, text, re.IGNORECASE):
            attrs["bracelet"] = name
            break

    if _NO_DATE_RE.search(text):
        attrs["no_date"] = True

    return attrs


# ── Catalog snapshot ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class CatalogEntry:
    watch_id: int
    brand_slug: str
    ref: str
    family: str | None
    start: int | None
    end: int | None
    dial: str | None
    material_class: str | None
    size_mm: float | None
    bezel: str | None
    bracelet: str | None
    has_date: bool | None
    dial_variant: str | None = None  # set = this entry IS a dial variant

    def year_ok(self, year: int, tolerance: int = 1) -> bool:
        if self.start is not None and year < self.start - tolerance:
            return False
        if self.end is not None and year > self.end + tolerance:
            return False
        return True

    def has_window(self) -> bool:
        return self.start is not None

    def is_current(self) -> bool:
        return self.start is not None and self.end is None


def _classify_material(raw: str | None) -> str | None:
    if not raw:
        return None
    for cls, pattern in _MATERIAL_CLASSES:
        if re.search(pattern, raw, re.IGNORECASE):
            return cls
    return None


@dataclass
class MatchResult:
    watch_id: int | None
    method: str
    confidence: float
    family: str | None = None
    attributes: dict = field(default_factory=dict)


class Matcher:
    """In-memory catalog + the ordered matching rules."""

    def __init__(
        self,
        entries: list[CatalogEntry],
        aliases: dict[str, int],
        nicknames: dict[str, list[int]],
        dial_terms: dict[tuple[str, str, str], str] | None = None,
    ) -> None:
        self.entries = entries
        self.by_id = {e.watch_id: e for e in entries}
        self.by_ref: dict[str, list[CatalogEntry]] = {}
        for e in entries:
            self.by_ref.setdefault(e.ref.upper(), []).append(e)
        # (brand_slug, REF, listing dial term) -> canonical variant dial
        if dial_terms is None:
            from watchscraper.catalog import REF_VARIANTS

            dial_terms = {}
            for (slug, ref), variants in REF_VARIANTS.items():
                for v in variants:
                    for term in (v.dial, *v.match_terms):
                        dial_terms[(slug, ref.upper(), term.lower())] = v.dial
        self.dial_terms = dial_terms
        # Alias keys keep their raw (whitespace-stripped) form too, because
        # a Patek dash suffix pins the dial variant and normalization would
        # strip it: 5711/1A-014 must stay findable.
        self.aliases = {}
        for a, wid in aliases.items():
            self.aliases[normalize_reference(a).upper()] = wid
            self.aliases[re.sub(r"\s+", "", a).upper()] = wid
        self.nicknames = {n.lower(): wids for n, wids in nicknames.items()}
        self._nickname_re = (
            re.compile(
                r"\b(" + "|".join(
                    re.escape(n) for n in sorted(self.nicknames, key=len, reverse=True)
                ) + r")\b",
                re.IGNORECASE,
            )
            if self.nicknames
            else None
        )

    # -- construction -----------------------------------------------------

    @classmethod
    def from_session(cls, session: Session) -> "Matcher":
        from watchscraper.models import Brand, Watch, WatchAlias, WatchNickname

        rows = session.execute(
            select(Watch, Brand.slug).join(Brand, Brand.id == Watch.brand_id)
        ).all()
        entries = [
            CatalogEntry(
                watch_id=w.id,
                brand_slug=slug,
                ref=w.reference_number,
                family=w.family,
                start=w.production_start_year,
                end=w.production_end_year,
                dial=(w.dial_color or "").lower() or None,
                material_class=_classify_material(w.case_material),
                size_mm=w.case_size_mm,
                bezel=(w.bezel or "").lower() or None,
                bracelet=(w.bracelet or "").lower() or None,
                has_date=w.has_date,
                dial_variant=w.dial_variant,
            )
            for w, slug in rows
        ]
        aliases = {
            a.alias: a.watch_id
            for a in session.execute(select(WatchAlias)).scalars()
        }
        nicknames: dict[str, list[int]] = {}
        for n in session.execute(select(WatchNickname)).scalars():
            nicknames.setdefault(n.nickname, []).append(n.watch_id)
        return cls(entries, aliases, nicknames)

    # -- rules ------------------------------------------------------------

    def match(self, title: str, query: str | None = None) -> MatchResult:
        text = f"{query or ''} {title or ''}"
        attrs = extract_attributes(title or "")
        year = attrs.get("year")
        brand_slug = self._detect_brand(text)
        _, family = _match_family(query or "")
        if family is None:
            _, family = _match_family(title or "")

        # Rule 1+2: explicit reference or alias
        result = self._match_ref(title or "", brand_slug, year, attrs)
        if result:
            result.family = self.by_id[result.watch_id].family or family
            result.attributes = attrs
            return result

        # Rule 3: nickname
        result = self._match_nickname(text, brand_slug, year, attrs)
        if result:
            result.family = self.by_id[result.watch_id].family or family
            result.attributes = attrs
            return result

        # Rule 4: attribute narrowing within the family
        if family:
            result = self._match_attributes(family, brand_slug, year, attrs)
            if result:
                result.family = family
                result.attributes = attrs
                return result

        # Rule 5: family only
        return MatchResult(
            watch_id=None,
            method="family" if family else "none",
            confidence=0.3 if family else 0.0,
            family=family,
            attributes=attrs,
        )

    def _detect_brand(self, text: str) -> str | None:
        slug_map = {
            "Rolex": "rolex",
            "Audemars Piguet": "audemars-piguet",
            "Patek Philippe": "patek-philippe",
            "Omega": "omega",
            "Vacheron Constantin": "vacheron-constantin",
            "IWC": "iwc",
            "Jaeger-LeCoultre": "jaeger-lecoultre",
            "A. Lange & Söhne": "a-lange-sohne",
            "Cartier": "cartier",
        }
        for brand, pattern in BRAND_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return slug_map.get(brand)
        return None

    def _match_ref(
        self, title: str, brand_slug: str | None, year: int | None, attrs: dict
    ) -> MatchResult | None:
        for normalized in extract_ref_candidates(title, brand_slug):
            entries = self.by_ref.get(normalized, [])
            if brand_slug:
                brand_matches = [e for e in entries if e.brand_slug == brand_slug]
                entries = brand_matches or entries

            entry = None
            confidence = 0.95
            if len(entries) == 1:
                entry = entries[0]
            elif len(entries) > 1 and len({e.brand_slug for e in entries}) == 1:
                entry, confidence = self._resolve_dial_variant(entries, title, attrs)

            if entry is not None:
                if year and entry.has_window() and not entry.year_ok(year):
                    attrs["year_conflict"] = True
                    return MatchResult(entry.watch_id, "exact_ref", min(confidence, 0.80))
                return MatchResult(entry.watch_id, "exact_ref", confidence)

            watch_id = self.aliases.get(normalized)
            if watch_id:
                return MatchResult(watch_id, "alias", 0.90)
        return None

    def _resolve_dial_variant(
        self, entries: list[CatalogEntry], title: str, attrs: dict
    ) -> tuple[CatalogEntry | None, float]:
        """Pick the dial variant of a multi-dial reference.

        A variant nickname in the title ("John Mayer") is decisive; then the
        parsed dial term; otherwise the parent bucket takes the record at
        reduced confidence — a 116508 of unknown dial is still a 116508, but
        it must never price a specific variant.
        """
        parent = next((e for e in entries if e.dial_variant is None), None)
        children = [e for e in entries if e.dial_variant is not None]
        if not children:
            return (parent, 0.95) if parent else (None, 0.0)

        if self._nickname_re:
            m = self._nickname_re.search(title)
            if m:
                ids = set(self.nicknames.get(m.group(1).lower(), []))
                named = [c for c in children if c.watch_id in ids]
                if len(named) == 1:
                    return named[0], 0.95

        dial = attrs.get("dial")
        if dial:
            key_brand = children[0].brand_slug
            key_ref = children[0].ref.upper()
            canonical = self.dial_terms.get((key_brand, key_ref, dial.lower()))
            if canonical:
                for c in children:
                    if c.dial_variant == canonical:
                        return c, 0.92
            # A dial was stated but matches no known variant of this ref —
            # park it on the parent rather than guess.
            attrs["dial_unrecognized"] = dial

        attrs["dial_unresolved"] = True
        return parent, 0.85

    def _match_nickname(
        self, text: str, brand_slug: str | None, year: int | None, attrs: dict
    ) -> MatchResult | None:
        if not self._nickname_re:
            return None
        m = self._nickname_re.search(text)
        if not m:
            return None

        candidates = [
            self.by_id[wid]
            for wid in self.nicknames[m.group(1).lower()]
            if wid in self.by_id
        ]
        if brand_slug:
            # A nickname never crosses brands: "panda dial" on an Omega
            # must not match the Rolex Daytona Panda.
            candidates = [e for e in candidates if e.brand_slug == brand_slug]
        if not candidates:
            return None
        if len(candidates) == 1:
            return MatchResult(candidates[0].watch_id, "nickname", 0.80)

        # Generation disambiguation: the stated year picks the window
        if year:
            in_window = [e for e in candidates if e.year_ok(year)]
            if len(in_window) == 1:
                return MatchResult(in_window[0].watch_id, "nickname", 0.80)
            if not in_window:
                # The year falls outside every known generation (e.g. a 1969
                # "Pepsi" when the catalog starts at 1981) — matching any
                # candidate would misprice a vintage watch. Family fallback.
                return None
            candidates = in_window

        # Bracelet hint (e.g. jubilee Batman = 126710BLNR)
        bracelet = attrs.get("bracelet")
        if bracelet:
            with_bracelet = [
                e for e in candidates if e.bracelet and bracelet in e.bracelet
            ]
            if len(with_bracelet) == 1:
                return MatchResult(with_bracelet[0].watch_id, "nickname", 0.75)

        # Default: the current-production generation, at reduced confidence
        current = [e for e in candidates if e.is_current()]
        if len(current) == 1:
            return MatchResult(current[0].watch_id, "nickname_default_gen", 0.55)
        return MatchResult(candidates[0].watch_id, "nickname_ambiguous", 0.45)

    def _match_attributes(
        self, family: str, brand_slug: str | None, year: int | None, attrs: dict
    ) -> MatchResult | None:
        candidates = [e for e in self.entries if e.family == family]
        if brand_slug:
            candidates = [e for e in candidates if e.brand_slug == brand_slug]
        if not candidates:
            return None

        def narrow(pool, pred):
            survivors = [e for e in pool if pred(e)]
            return survivors or pool  # a filter that kills everyone is ignored

        if year is not None:
            with_windows = [e for e in candidates if e.has_window()]
            if with_windows:
                survivors = [e for e in with_windows if e.year_ok(year)]
                if survivors:
                    candidates = survivors

        size = attrs.get("size_mm")
        if size is not None:
            candidates = narrow(
                candidates,
                lambda e: e.size_mm is not None and abs(e.size_mm - size) <= 0.75,
            )

        material = attrs.get("material")
        if material:
            candidates = narrow(
                candidates,
                lambda e: e.material_class is not None and e.material_class == material,
            )

        dial = attrs.get("dial")
        if dial:
            candidates = narrow(
                candidates, lambda e: e.dial is not None and dial in e.dial
            )

        bezel = attrs.get("bezel")
        if bezel:
            first = bezel.split("/")[0]
            candidates = narrow(
                candidates, lambda e: e.bezel is not None and first in e.bezel
            )

        if attrs.get("no_date"):
            candidates = narrow(candidates, lambda e: e.has_date is False)

        if len(candidates) == 1:
            return MatchResult(candidates[0].watch_id, "attributes", 0.65)
        return None
