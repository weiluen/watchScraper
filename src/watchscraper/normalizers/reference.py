import re

# Brand-specific normalization rules.
# Strip common prefixes/suffixes, collapse whitespace, uppercase.

_STRIP_PREFIXES = re.compile(r"^(ref\.?\s*|reference\s*)", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

# Rolex: 5-6 digits + optional letter suffix
# 6-digit: 126610LN, 116500LN, 124060 (current models)
# 5-digit: 16610, 16520, 14270 (older models)
_ROLEX_REF_6 = re.compile(r"(?<!\d)(1[12]\d{4})([A-Z]{0,6})(?!\d)")
_ROLEX_REF_5 = re.compile(r"(?<!\d)(1[4-9]\d{3})([A-Z]{0,6})(?!\d)")

# Patek: 4-5 digits, slash, variant (5711/1A, 5167A)
_PATEK_REF = re.compile(r"(5\d{3}[A-Z]?)(/\d[A-Z]+)?")

# AP Royal Oak: 15xxx or 26xxx + 2-letter suffix (must not be preceded by a digit)
_AP_REF = re.compile(r"(?<!\d)([12][56]\d{3})([A-Z]{2})")

# Omega: dotted format like 310.30.42.50.01.001
_OMEGA_REF = re.compile(r"(\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3})")

# Vacheron Constantin: format like 4500V/110A-B128 or 47040/000A-9008
_VC_REF = re.compile(r"(\d{4,5}[A-Z]?/\d{3}[A-Z]-[A-Z0-9]{4,5})")

# IWC: "IW" prefix + 6 digits (IW371605, IW500710)
_IWC_REF = re.compile(r"(IW\d{6})", re.IGNORECASE)

# Jaeger-LeCoultre: "Q" prefix + 7 digits (Q3858520)
_JLC_REF = re.compile(r"(Q\d{7})", re.IGNORECASE)

# A. Lange & Söhne: 3 digits + dot + 3 digits (191.032, 403.035)
_LANGE_REF = re.compile(r"(?<!\d)(\d{3}\.\d{3})(?!\d)")

# Cartier: "W" prefix + alphanumeric (WSSA0029, WSBB0046, CRWSTA0016)
_CARTIER_REF = re.compile(r"((?:CR)?W[A-Z]{2,4}\d{4})", re.IGNORECASE)


def normalize_reference(raw: str, brand_slug: str | None = None) -> str:
    """Normalize a watch reference number to canonical form.

    Examples:
        "Ref. 126710 BLNR" → "126710BLNR"
        "5711/1A-010" → "5711/1A"
        "15500ST.OO.1220ST.01" → "15500ST"
        "310.30.42.50.01.001" → "310.30.42.50.01.001"
        "4500V/110A-B128" → "4500V/110A-B128"
    """
    text = raw.strip()
    text = _STRIP_PREFIXES.sub("", text)
    text = _WHITESPACE.sub("", text)

    if brand_slug == "rolex":
        return _normalize_rolex(text)
    elif brand_slug == "patek-philippe":
        return _normalize_patek(text)
    elif brand_slug in ("audemars-piguet", "ap"):
        return _normalize_ap(text)
    elif brand_slug == "omega":
        return _normalize_omega(text)
    elif brand_slug in ("vacheron-constantin", "vc"):
        return _normalize_vc(text)
    elif brand_slug == "iwc":
        return _normalize_iwc(text)
    elif brand_slug in ("jaeger-lecoultre", "jlc"):
        return _normalize_jlc(text)
    elif brand_slug in ("a-lange-sohne", "lange"):
        return _normalize_lange(text)
    elif brand_slug == "cartier":
        return _normalize_cartier(text)

    # Generic: try each regex directly (order matters — specific patterns first)
    pattern_normalizer_pairs = [
        (_OMEGA_REF, _normalize_omega),
        (_VC_REF, _normalize_vc),
        (_IWC_REF, _normalize_iwc),
        (_JLC_REF, _normalize_jlc),
        (_LANGE_REF, _normalize_lange),
        (_CARTIER_REF, _normalize_cartier),
        (_ROLEX_REF_6, _normalize_rolex),
        (_ROLEX_REF_5, _normalize_rolex),
        (_AP_REF, _normalize_ap),
        (_PATEK_REF, _normalize_patek),
    ]
    for pattern, normalizer in pattern_normalizer_pairs:
        if pattern.search(text.upper()):
            return normalizer(text)

    return text.upper()


def _normalize_rolex(text: str) -> str:
    # Try 6-digit refs first (current models), then 5-digit (older)
    m = _ROLEX_REF_6.search(text.upper())
    if m:
        return m.group(1) + m.group(2)
    m = _ROLEX_REF_5.search(text.upper())
    if m:
        return m.group(1) + m.group(2)
    return text.upper()


def _normalize_patek(text: str) -> str:
    m = _PATEK_REF.search(text.upper())
    if m:
        base = m.group(1)
        variant = m.group(2) or ""
        return base + variant
    return text.upper()


def _normalize_ap(text: str) -> str:
    m = _AP_REF.search(text.upper())
    if m:
        return m.group(1) + m.group(2)
    return text.upper()


def _normalize_omega(text: str) -> str:
    # Omega refs are dotted numbers — preserve as-is if matched
    m = _OMEGA_REF.search(text)
    if m:
        return m.group(1)
    return text.upper()


def _normalize_vc(text: str) -> str:
    # Vacheron refs like 4500V/110A-B128 — preserve case
    m = _VC_REF.search(text)
    if m:
        return m.group(1)
    return text.upper()


def _normalize_iwc(text: str) -> str:
    m = _IWC_REF.search(text)
    if m:
        return m.group(1).upper()
    return text.upper()


def _normalize_jlc(text: str) -> str:
    m = _JLC_REF.search(text)
    if m:
        return m.group(1).upper()
    return text.upper()


def _normalize_lange(text: str) -> str:
    m = _LANGE_REF.search(text)
    if m:
        return m.group(1)
    return text.upper()


def _normalize_cartier(text: str) -> str:
    m = _CARTIER_REF.search(text)
    if m:
        return m.group(1).upper()
    return text.upper()


# Alias mapping for common variant strings
KNOWN_ALIASES: dict[str, list[str]] = {
    # Rolex Submariner Date
    "126610LN": ["126610 LN", "Ref.126610LN", "Sub Date Black"],
    "126610LV": ["126610 LV", "Starbucks", "Sub Date Green"],
    # Rolex GMT-Master II
    "126710BLNR": ["126710 BLNR", "Batman", "GMT Batman"],
    "126710BLRO": ["126710 BLRO", "Pepsi", "GMT Pepsi"],
    # Rolex Daytona
    "116500LN": ["116500 LN", "Daytona Ceramic"],
    # Patek Nautilus
    "5711/1A": ["5711/1A-010", "5711/1A-014", "Nautilus Blue", "5711"],
    # AP Royal Oak
    "15500ST": ["15500ST.OO.1220ST", "RO 15500"],
    "15202ST": ["15202ST.OO.1240ST", "Jumbo"],
}


def resolve_alias(text: str) -> str | None:
    """Try to resolve a reference string to a canonical reference via known aliases."""
    normalized = normalize_reference(text)

    # Direct match
    if normalized in KNOWN_ALIASES:
        return normalized

    # Search alias lists
    for canonical, aliases in KNOWN_ALIASES.items():
        for alias in aliases:
            alias_norm = normalize_reference(alias)
            if normalized == alias_norm or text.strip().lower() == alias.lower():
                return canonical

    return None
