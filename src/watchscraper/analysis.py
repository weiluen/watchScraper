"""Dataset assembly, categorization, and cleaning for price analysis.

Turns raw price_records into an analysis-ready DataFrame:
  1. Categorize every record into (brand, family) from its search query,
     linked reference watch, or listing title.
  2. Flag junk listings (straps, bezels, box/papers-only, parts, MoonSwatch).
  3. Flag price outliers with family-relative bounds + MAD-based trimming.
  4. Assign price tiers from family median prices.

Records are flagged, never deleted — every exclusion carries a reason so the
cleaning is auditable.
"""

import re

import numpy as np
import pandas as pd
from sqlalchemy import text

# Ordered: more specific families must precede their parents
# (Royal Oak Offshore before Royal Oak, Planet Ocean before Seamaster).
FAMILY_PATTERNS: list[tuple[str, str, str]] = [
    ("Rolex", "Submariner", r"submariner"),
    ("Rolex", "Daytona", r"daytona"),
    ("Rolex", "GMT-Master II", r"gmt[- ]?master"),
    ("Rolex", "Datejust", r"datejust"),
    ("Rolex", "Explorer", r"explorer"),
    ("Rolex", "Sky-Dweller", r"sky[- ]?dweller"),
    ("Audemars Piguet", "Royal Oak Offshore", r"royal\s+oak\s+offshore|offshore"),
    ("Audemars Piguet", "Royal Oak", r"royal\s+oak"),
    ("Patek Philippe", "Nautilus", r"nautilus"),
    ("Patek Philippe", "Aquanaut", r"aquanaut"),
    ("Patek Philippe", "Calatrava", r"calatrava"),
    ("Omega", "Speedmaster", r"speedmaster"),
    ("Omega", "Planet Ocean", r"planet\s+ocean"),
    ("Omega", "Aqua Terra", r"aqua\s+terra"),
    ("Omega", "Seamaster 300M", r"seamaster"),
    ("Vacheron Constantin", "Overseas", r"overseas"),
    ("Vacheron Constantin", "Patrimony", r"patrimony"),
    ("Vacheron Constantin", "Traditionnelle", r"traditionnelle"),
    ("Vacheron Constantin", "Fiftysix", r"fifty\s?six"),
    ("IWC", "Big Pilot", r"big\s+pilot"),
    ("IWC", "Portugieser", r"portugieser|portuguese"),
    ("IWC", "Pilot Mark", r"pilot.*mark|mark\s+x{0,2}v?i{0,3}"),
    ("IWC", "Aquatimer", r"aquatimer"),
    ("Jaeger-LeCoultre", "Reverso", r"reverso"),
    ("Jaeger-LeCoultre", "Master Ultra Thin", r"master\s+ultra\s+thin"),
    ("Jaeger-LeCoultre", "Polaris", r"polaris"),
    ("A. Lange & Söhne", "Datograph", r"datograph"),
    ("A. Lange & Söhne", "Lange 1", r"lange\s*1(?!8)"),
    ("A. Lange & Söhne", "Saxonia", r"saxonia"),
    ("A. Lange & Söhne", "1815", r"\b1815\b"),
    ("Cartier", "Santos", r"santos"),
    ("Cartier", "Tank", r"\btank\b"),
    ("Cartier", "Ballon Bleu", r"ballon\s+bleu"),
    ("Cartier", "Pasha", r"pasha"),
]

BRAND_PATTERNS: list[tuple[str, str]] = [
    ("Rolex", r"rolex"),
    ("Audemars Piguet", r"audemars|piguet"),
    ("Patek Philippe", r"patek"),
    ("Omega", r"omega"),
    ("Vacheron Constantin", r"vacheron"),
    ("IWC", r"\biwc\b"),
    ("Jaeger-LeCoultre", r"jaeger|lecoultre|\bjlc\b"),
    ("A. Lange & Söhne", r"lange"),
    ("Cartier", r"cartier"),
]

# A listing matching any of these is not a wristwatch sale.
JUNK_PATTERNS: list[str] = [
    r"\b(?:box(?:\s*(?:and|&|\+)\s*papers?)?|papers?|booklet|manual|tags?|card|bezel|dial|hands?|crystal|movement|case(?:back)?|link|strap|band|bracelet|buckle|clasp)\s+only\b",
    r"\bonly\s+(?:box|papers?|bezel|dial|strap|band|bracelet)\b",
    r"\bpaper\s*work\s+only\b",
    r"\b(?:strap|band|bracelet|buckle|clasp|bezel\s+insert|insert|crystal|movement|winder|holder|travel\s+case|watch\s+roll|pouch)\b\s+(?:for|fits?|compatible)\b",
    r"\b(?:for|fits?)\s+(?:rolex|omega|cartier|iwc|patek|audemars|vacheron|jaeger|lange)\b",
    r"^(?:genuine|oem|aftermarket|custom|new)?\s*(?:rubber|leather|nato|silicone|steel)\s+(?:strap|band|bracelet)\b",
    r"\bwatch\s*band\b",
    r"\bbezel\s+insert\b",
    r"\b(?:parts|repair|not\s+working|as[- ]?is|broken|no\s+movement)\b",
    r"\bswatch\b",  # Omega/AP x Swatch collabs are a different market
    r"\b(?:empty|display)\s+box\b",
    r"\bwarranty\s+card\b",
    r"\bservice\s+(?:papers?|booklet|manual)\b",
    r"\b(?:winder|safe|display\s+case)\b",
]

_JUNK_RE = re.compile("|".join(f"(?:{p})" for p in JUNK_PATTERNS), re.IGNORECASE)

# Family-relative price sanity bounds (fraction of family median).
REL_LOWER = 0.15
REL_UPPER = 8.0
MAD_Z_CUTOFF = 3.5

TIER_BOUNDS_USD = [
    ("entry", 0, 5_000),
    ("mid", 5_000, 15_000),
    ("high", 15_000, 40_000),
    ("ultra", 40_000, float("inf")),
]

DATASET_SQL = text("""
    SELECT
        pr.id,
        s.name AS source,
        pr.price_usd / 100.0 AS price,
        pr.price_type,
        pr.condition,
        pr.title,
        pr.reference_parsed,
        pr.watch_id,
        pr.match_method,
        pr.match_confidence,
        pr.parsed_year,
        pr.observed_at,
        pr.scraped_at,
        pr.raw_data->>'query' AS query,
        b.name AS linked_brand,
        w.model_name AS linked_model,
        w.reference_number AS linked_ref,
        w.family AS linked_family,
        w.production_start_year,
        w.production_end_year,
        w.retail_price_usd / 100.0 AS retail_price
    FROM price_records pr
    JOIN sources s ON s.id = pr.source_id
    LEFT JOIN watches w ON w.id = pr.watch_id
    LEFT JOIN brands b ON b.id = w.brand_id
""")


def load_dataset(engine) -> pd.DataFrame:
    """Load all price records with linked-watch context."""
    df = pd.read_sql(DATASET_SQL, engine)
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], utc=True)
    # Effective event date: sale date for sold records, scrape date for asking.
    df["event_date"] = df["observed_at"].fillna(df["scraped_at"])
    return df


def _match_family(text_value: str) -> tuple[str | None, str | None]:
    if not text_value:
        return None, None
    for brand, family, pattern in FAMILY_PATTERNS:
        if re.search(pattern, text_value, re.IGNORECASE):
            return brand, family
    return None, None


def categorize(df: pd.DataFrame) -> pd.DataFrame:
    """Assign (brand, family) to every record.

    Priority: the linked reference's catalog family (authoritative — the
    matcher put it there), then the search query (it produced the listing),
    then the title. Brand falls back to title keywords.
    """
    linked_families = (
        df["linked_family"] if "linked_family" in df else pd.Series(None, index=df.index)
    )
    linked_brands = (
        df["linked_brand"] if "linked_brand" in df else pd.Series(None, index=df.index)
    )

    brands: list[str | None] = []
    families: list[str | None] = []
    for query, title, linked_family, linked_brand in zip(
        df["query"].fillna(""),
        df["title"].fillna(""),
        linked_families,
        linked_brands,
    ):
        brand, family = _match_family(query or "")
        if family is None:
            brand, family = _match_family(title or "")
        if isinstance(linked_family, str) and linked_family:
            family = linked_family
            if isinstance(linked_brand, str) and linked_brand:
                brand = linked_brand
        if brand is None:
            for b, pattern in BRAND_PATTERNS:
                if re.search(pattern, f"{query or ''} {title or ''}", re.IGNORECASE):
                    brand = b
                    break
        brands.append(brand)
        families.append(family)
    out = df.copy()
    out["brand"] = brands
    out["family"] = families
    return out


def flag_junk(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["is_junk"] = out["title"].fillna("").str.contains(_JUNK_RE)
    return out


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Two-stage family-relative outlier flagging on non-junk records.

    Stage 1: hard relative bounds around the family median (catches parts
    priced like accessories and bundle/typo prices).
    Stage 2: modified z-score (median absolute deviation) within
    (family, price_type); |z| > 3.5 is an outlier. MAD is the standard
    robust scale estimator — one crazy listing can't drag the cutoff.
    """
    out = df.copy()
    out["outlier_reason"] = None
    # Suspects (anchor-flagged fakes) must already be excluded here, or they
    # drag the family median down and genuine sales get flagged instead.
    usable = ~out["is_junk"] & ~out["is_suspect"] & out["family"].notna()

    for (family, price_type), grp in out[usable].groupby(["family", "price_type"]):
        med = grp["price"].median()
        rel_bad = grp.index[(grp["price"] < med * REL_LOWER) | (grp["price"] > med * REL_UPPER)]
        out.loc[rel_bad, "outlier_reason"] = "relative_bounds"

        survivors = grp.drop(rel_bad)
        if len(survivors) >= 8:
            mad = (survivors["price"] - survivors["price"].median()).abs().median()
            if mad > 0:
                z = 0.6745 * (survivors["price"] - survivors["price"].median()) / mad
                out.loc[survivors.index[z.abs() > MAD_Z_CUTOFF], "outlier_reason"] = "mad_z"

    out["is_outlier"] = out["outlier_reason"].notna()
    return out



# A sold price this far below the dealer-ask / retail anchor is presumed to be
# a counterfeit, homage, heavily-damaged, or parts listing that slipped the
# keyword net. eBay sold pools for halo models (Nautilus, Lange 1) are
# dominated by fakes at plausible-looking price points, so within-source
# statistics cannot catch them — only a cross-source anchor can.
ANCHOR_FLOOR = 0.35


def flag_suspect(df: pd.DataFrame) -> pd.DataFrame:
    """Flag sold records implausibly far below independent price anchors.

    Anchor priority: Chrono24 dealer asking median for the family (dealers
    rarely list fakes), falling back to the family's median retail price from
    the seeded reference watches.
    """
    out = df.copy()
    usable = ~out["is_junk"] & out["family"].notna()

    ask_anchor = (
        out[usable & (out["price_type"] == "asking")]
        .groupby("family")["price"]
        .median()
    )
    retail_anchor = (
        out[out["family"].notna() & out["retail_price"].notna()]
        .groupby("family")["retail_price"]
        .median()
    )
    anchor = ask_anchor.combine_first(retail_anchor)

    out["anchor_price"] = out["family"].map(anchor)
    out["is_suspect"] = (
        usable
        & (out["price_type"] == "sold")
        & out["anchor_price"].notna()
        & (out["price"] < out["anchor_price"] * ANCHOR_FLOOR)
    )
    return out


def assign_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Tier each family by its median clean sold price (asking as fallback)."""
    out = df.copy()
    clean = out[out["clean"]]
    sold = clean[clean["price_type"] == "sold"]
    family_median = sold.groupby("family")["price"].median()
    # Families with no sold data fall back to asking medians
    asking_median = clean[clean["price_type"] == "asking"].groupby("family")["price"].median()
    family_median = family_median.combine_first(asking_median)

    def tier_of(family):
        med = family_median.get(family)
        if med is None or pd.isna(med):
            return None
        for name, lo, hi in TIER_BOUNDS_USD:
            if lo <= med < hi:
                return name
        return None

    out["tier"] = out["family"].map(tier_of)
    out["family_median"] = out["family"].map(family_median)
    return out


def build_clean_dataset(engine) -> pd.DataFrame:
    """Full pipeline: load → categorize → junk filter → outlier filter → tiers.

    Returns every record with flags; downstream analysis should select
    df[df['clean']].
    """
    df = load_dataset(engine)
    df = categorize(df)
    df = flag_junk(df)
    df = flag_suspect(df)
    df = flag_outliers(df)
    df["clean"] = (
        ~df["is_junk"] & ~df["is_outlier"] & ~df["is_suspect"] & df["family"].notna()
    )
    df = assign_tiers(df)
    return df


def weekly_medians(df: pd.DataFrame, min_n: int = 5) -> pd.DataFrame:
    """Weekly median price per (brand, family, price_type).

    Buckets with fewer than min_n observations are dropped — a median of
    three sales is noise, not signal.
    """
    clean = df[df["clean"]].copy()
    clean["week"] = (
        clean["event_date"].dt.tz_convert("UTC").dt.tz_localize(None)
        .dt.to_period("W-SUN").dt.start_time
    )
    agg = (
        clean.groupby(["brand", "family", "price_type", "week"])
        .agg(
            n=("price", "size"),
            median=("price", "median"),
            p25=("price", lambda s: s.quantile(0.25)),
            p75=("price", lambda s: s.quantile(0.75)),
            mean=("price", "mean"),
            std=("price", "std"),
        )
        .reset_index()
    )
    return agg[agg["n"] >= min_n].reset_index(drop=True)


# Records below this match confidence don't price a specific reference —
# they still price the family. 0.65 = attributes-narrowed and better.
REF_VALUE_MIN_CONFIDENCE = 0.65


def reference_values(df: pd.DataFrame, min_n: int = 3) -> pd.DataFrame:
    """Market value per reference (the variant is the reference).

    Only clean sold records matched at REF_VALUE_MIN_CONFIDENCE or better
    contribute: a nickname-default-generation guess (0.55) is good enough to
    place a listing in a family, not to price a specific variant.
    """
    clean = df[
        df["clean"]
        & (df["price_type"] == "sold")
        & df["linked_ref"].notna()
        & (df["match_confidence"].fillna(0) >= REF_VALUE_MIN_CONFIDENCE)
    ]
    if clean.empty:
        return pd.DataFrame()

    rows = []
    for (brand, ref), grp in clean.groupby(["linked_brand", "linked_ref"]):
        if len(grp) < min_n:
            continue
        prices = grp["price"].values
        retail = grp["retail_price"].dropna()
        retail_v = float(retail.iloc[0]) if len(retail) else None
        median = float(np.median(prices))
        rows.append(
            {
                "brand": brand,
                "ref": ref,
                "model": grp["linked_model"].iloc[0],
                "family": grp["family"].iloc[0],
                "start_year": grp["production_start_year"].iloc[0],
                "end_year": grp["production_end_year"].iloc[0],
                "n_sold": len(grp),
                "median_usd": median,
                "p25_usd": float(np.percentile(prices, 25)),
                "p75_usd": float(np.percentile(prices, 75)),
                "retail_usd": retail_v,
                "premium_to_retail_pct": (
                    (median / retail_v - 1) * 100 if retail_v else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("median_usd", ascending=False)


def store_snapshots(engine, weekly: pd.DataFrame) -> int:
    """Upsert weekly medians into price_snapshots; returns rows written."""
    if weekly.empty:
        return 0
    rows = [
        {
            "snapshot_date": r["week"].date(),
            "brand": r["brand"],
            "family": r["family"],
            "price_type": r["price_type"],
            "n": int(r["n"]),
            "median_usd": float(r["median"]),
            "p25_usd": float(r["p25"]),
            "p75_usd": float(r["p75"]),
            "mean_usd": float(r["mean"]),
            "std_usd": float(r["std"]) if pd.notna(r["std"]) else None,
        }
        for _, r in weekly.iterrows()
    ]
    from sqlalchemy import text as sa_text

    with engine.begin() as conn:
        conn.execute(
            sa_text("""
                INSERT INTO price_snapshots
                    (snapshot_date, brand, family, price_type, n,
                     median_usd, p25_usd, p75_usd, mean_usd, std_usd)
                VALUES
                    (:snapshot_date, :brand, :family, :price_type, :n,
                     :median_usd, :p25_usd, :p75_usd, :mean_usd, :std_usd)
                ON CONFLICT ON CONSTRAINT uq_snapshot_week_family_type
                DO UPDATE SET
                    n = EXCLUDED.n,
                    median_usd = EXCLUDED.median_usd,
                    p25_usd = EXCLUDED.p25_usd,
                    p75_usd = EXCLUDED.p75_usd,
                    mean_usd = EXCLUDED.mean_usd,
                    std_usd = EXCLUDED.std_usd
            """),
            rows,
        )
    return len(rows)


def cleaning_report(df: pd.DataFrame) -> dict:
    """Summary counts for the audit trail."""
    return {
        "total": len(df),
        "junk": int(df["is_junk"].sum()),
        "outliers": int(df["is_outlier"].sum()),
        "suspect": int(df["is_suspect"].sum()),
        "uncategorized": int(df["family"].isna().sum()),
        "clean": int(df["clean"].sum()),
        "clean_pct": round(100.0 * df["clean"].mean(), 1),
    }
