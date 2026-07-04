"""The pricing atom: the right granularity for valuation.

The unit of valuation is NOT the reference number — it is the *market-distinct
configuration*: the finest grouping of physical attributes that (a) the market
treats as a separate good (buyers pay systematically differently across groups)
and (b) has enough transactions to estimate. The reference number is a proxy
for this, usually reliable, but it fails two ways: one reference sold with
several dials that trade apart (116508 green vs champagne), and family-level
listings where the reference is unknown but the material still moves price.

Every price-relevant attribute is one of two kinds:

  IDENTITY  — factory-fixed, immutable, market-distinct. Defines the atom and
              can SPLIT it into sub-atoms when the data supports it:
                case material, dial, bezel, case size, movement generation.
              (For most modern references, material/bezel are already encoded
              in the reference number; the live within-reference split is
              almost always the DIAL.)

  CONFIG    — the state of a specific example. NEVER splits the atom; applied
              as a pooled hedonic multiplier on the atom's value:
                condition, completeness (box & papers), swappable bracelet,
                minor age effects.

Granularity is ADAPTIVE. A reference is split along an identity attribute only
when each candidate sub-group clears a density floor AND the price gap between
groups is real (a rank test, beyond what a hedonic could explain). Below that
bar, the attribute is left aggregated and carried by a hedonic — a 2-sale rare
dial does not get its own free-floating market, it borrows its reference's.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

IDENTITY_ATTRS = ("case_material", "dial", "bezel", "case_size", "movement_gen")
CONFIG_ATTRS = ("condition", "full_set", "bracelet")

# A split must have at least this many clean sales in EACH sub-group, and the
# group medians must span at least this ratio, and a Kruskal-Wallis rank test
# must reject "same distribution" at this level.
MIN_PER_GROUP = 5
MIN_SPREAD_RATIO = 1.18  # ≥18% gap between cheapest and priciest sub-group
SPLIT_ALPHA = 0.05


@dataclass(frozen=True)
class AtomKey:
    """Canonical pricing-atom signature. dial is the live split dimension;
    material/bezel/size are usually fixed by the reference."""

    brand: str
    reference: str | None  # None = family-generic atom
    dial: str | None = None
    material: str | None = None  # for family-generic atoms where ref is unknown
    family: str | None = None

    def label(self) -> str:
        if self.reference:
            return (
                f"{self.brand} {self.reference}"
                + (f" · {self.dial} dial" if self.dial else "")
            )
        return f"{self.brand} {self.family} · {self.material or 'unknown'}"


@dataclass
class SplitFinding:
    brand: str
    reference: str
    attribute: str            # which identity attr splits it (usually "dial")
    n_total: int
    groups: list[dict]        # [{value, n, median, share}]
    spread_ratio: float
    p_value: float
    recommend_split: bool
    reason: str


def _dial_from(row) -> str | None:
    """Best dial signal for a sold record: matched variant, else parsed."""
    d = row.get("linked_dial")
    if isinstance(d, str) and d:
        return d
    attrs = row.get("parsed_attributes")
    if isinstance(attrs, dict):
        dv = attrs.get("dial")
        if isinstance(dv, str) and dv:
            return dv.title()
    return None


def analyze_reference_granularity(
    clean_sold: pd.DataFrame,
    min_per_group: int = MIN_PER_GROUP,
    spread_ratio: float = MIN_SPREAD_RATIO,
    alpha: float = SPLIT_ALPHA,
) -> list[SplitFinding]:
    """Data-driven: for every reference with enough sales, decide whether the
    DIAL warrants splitting it into separate pricing atoms.

    Returns a finding per reference (split or not) with the evidence, so the
    granularity decision is auditable rather than hand-guessed.
    """
    df = clean_sold[
        clean_sold["linked_ref"].notna()
        & (clean_sold["match_confidence"].fillna(0) >= 0.65)
    ].copy()
    if df.empty:
        return []
    df["dial_signal"] = df.apply(_dial_from, axis=1)

    findings: list[SplitFinding] = []
    for (brand, ref), grp in df.groupby(["linked_brand", "linked_ref"]):
        dialed = grp[grp["dial_signal"].notna()]
        if len(dialed) < 2 * min_per_group:
            continue
        counts = dialed.groupby("dial_signal")["price"].agg(["size", "median"])
        eligible = counts[counts["size"] >= min_per_group]
        if len(eligible) < 2:
            continue

        groups = [
            {
                "value": dial,
                "n": int(row["size"]),
                "median": float(row["median"]),
                "share": round(int(row["size"]) / len(dialed), 2),
            }
            for dial, row in eligible.sort_values("median", ascending=False).iterrows()
        ]
        meds = [g["median"] for g in groups]
        ratio = max(meds) / min(meds) if min(meds) > 0 else float("inf")

        samples = [
            dialed[dialed["dial_signal"] == g["value"]]["price"].values
            for g in groups
        ]
        try:
            _, p = stats.kruskal(*samples)
        except ValueError:
            p = 1.0

        split = bool(ratio >= spread_ratio and p < alpha)
        if split:
            reason = (
                f"{len(groups)} dials each ≥{min_per_group} sales span "
                f"{(ratio-1)*100:.0f}% (p={p:.3f}) — separate markets"
            )
        elif ratio < spread_ratio:
            reason = f"dial gap only {(ratio-1)*100:.0f}% — one market, dial is hedonic"
        else:
            reason = f"gap {(ratio-1)*100:.0f}% not significant (p={p:.2f}) — insufficient evidence"

        findings.append(
            SplitFinding(
                brand=brand, reference=ref, attribute="dial",
                n_total=len(grp), groups=groups, spread_ratio=round(ratio, 3),
                p_value=round(float(p), 4), recommend_split=split, reason=reason,
            )
        )
    return findings


def reconcile_with_catalog(
    findings: list[SplitFinding], catalog_variant_refs: set[str]
) -> dict:
    """Compare data-driven split recommendations to hand-curated REF_VARIANTS.

    Surfaces: MISSED (data says split, catalog doesn't) and UNSUPPORTED
    (catalog splits, data too thin to confirm) — the audit the user wants.
    """
    data_split = {f.reference for f in findings if f.recommend_split}
    missed = sorted(data_split - catalog_variant_refs)
    confirmed = sorted(data_split & catalog_variant_refs)
    unconfirmed = sorted(catalog_variant_refs - {f.reference for f in findings})
    return {
        "confirmed_by_data": confirmed,
        "missed_by_catalog": missed,       # data says split, we don't — add these
        "curated_but_thin": unconfirmed,    # we split, data can't yet confirm
    }
