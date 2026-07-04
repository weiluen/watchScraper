"""Hierarchical valuation engine: smooth market values from sparse sales.

The first-principles model. Every sale is one noisy observation of a latent
value:

    log(price) = node_offset + family_trend(t) + config_effects + noise

  - The NODE is the watch identity: dial variant when known, else the
    reference, else the (family, material) generic. Its offset (the
    variant's premium over the family base) is stable and estimable from
    few sales — this is how a 3-sale John Mayer gets a trustworthy value.
  - The TREND is shared across the family and estimated from ALL its sales
    after removing each sale's node offset, smoothed with a kernel-weighted
    median. Weekly medians of whichever watches happened to sell that week
    are composition noise; the offset-adjusted pooled trend is not.
  - CONFIG effects (full set / box & papers, bracelet type, condition) are
    hedonic multipliers estimated from within-node contrasts and pooled
    globally — a full-set premium is a property of the market, not of one
    reference. Sales are standardized to "full set, good condition" before
    entering the level/trend fit; a specific listing or holding is valued
    by putting its own configuration back.

Offsets are shrunk empirical-Bayes style (kappa = n / (n + K)) toward the
family base, so thin nodes lean on their parent instead of their own noise.

Forecasts extrapolate the smoothed trend's recent slope, heavily damped —
grey-market drift is slow, and wiggles must not be extrapolated.
"""

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

TREND_BANDWIDTH_DAYS = 21.0
OFFSET_SHRINK_K = 2.0
N_ITER = 3
MIN_FAMILY_OBS = 12
MIN_HEDONIC_CELL = 6

_FULL_SET_RE = re.compile(
    r"\bfull\s+set\b|\bbox\s*(?:&|and|\+|/)\s*papers?\b|\bb\s*&\s*p\b|\bbox/papers\b"
    r"|\bwith\s+box\s+and\s+papers\b|\bcomplete\s+set\b",
    re.IGNORECASE,
)


def parse_full_set(title: str | None) -> bool:
    return bool(_FULL_SET_RE.search(title or ""))


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cw = np.cumsum(w)
    if cw[-1] <= 0:
        return float(np.median(v))
    return float(v[np.searchsorted(cw, 0.5 * cw[-1])])


def kernel_median_smoother(
    t: np.ndarray, y: np.ndarray, grid: np.ndarray, bandwidth: float
) -> np.ndarray:
    """Gaussian-kernel weighted median of y over time, evaluated on grid.

    Robust (a $6k parts-lot slipping the filters cannot bend the line) and
    smooth (no weekly sawtooth). Falls back to widening windows where data
    is locally thin.
    """
    out = np.empty(len(grid))
    for i, g in enumerate(grid):
        bw = bandwidth
        for _ in range(4):
            w = np.exp(-0.5 * ((t - g) / bw) ** 2)
            if w.sum() >= 3.0:  # effective sample size guard
                break
            bw *= 1.8
        out[i] = _weighted_median(y, w)
    return out


@dataclass
class NodeValue:
    node_type: str  # "variant" | "ref" | "family_material"
    brand: str | None
    ref: str | None
    dial_variant: str | None
    family: str
    material: str | None
    n: int
    offset: float  # log premium over family base (shrunk)
    value: float  # standardized config: full set, good condition
    ci_lo: float
    ci_hi: float
    chg_1m_pct: float | None
    chg_3m_pct: float | None


@dataclass
class FamilyModel:
    family: str
    base: float  # family median log price (standardized config)
    grid: pd.DatetimeIndex
    trend: np.ndarray  # log deviation from base over grid
    trend_se: np.ndarray
    n_obs: int


@dataclass
class ValuationModel:
    hedonics: dict[str, float] = field(default_factory=dict)  # log multipliers
    families: dict[str, FamilyModel] = field(default_factory=dict)
    nodes: pd.DataFrame = field(default_factory=pd.DataFrame)

    # -- lookups ----------------------------------------------------------

    def node_row(
        self, brand: str, ref: str | None, dial: str | None, family: str | None = None
    ) -> pd.Series | None:
        if self.nodes.empty:
            return None
        df = self.nodes
        if ref:
            hit = df[
                (df["brand"] == brand)
                & (df["ref"] == ref)
                & (df["dial_variant"].fillna("") == (dial or ""))
            ]
            if len(hit):
                return hit.iloc[0]
            hit = df[(df["brand"] == brand) & (df["ref"] == ref)]
            if len(hit):
                return hit.iloc[0]
        if family:
            hit = df[(df["node_type"] == "family_material") & (df["family"] == family)]
            if len(hit):  # dominant = largest n
                return hit.sort_values("n", ascending=False).iloc[0]
        return None

    def value_series(self, row: pd.Series) -> pd.Series:
        """Smooth market-value series for a node (standard configuration)."""
        fam = self.families.get(row["family"])
        if fam is None:
            return pd.Series(dtype=float)
        levels = np.exp(fam.base + row["offset"] + fam.trend)
        return pd.Series(levels, index=fam.grid)

    def value_band(self, row: pd.Series) -> tuple[pd.Series, pd.Series]:
        fam = self.families.get(row["family"])
        if fam is None:
            empty = pd.Series(dtype=float)
            return empty, empty
        se = np.sqrt(fam.trend_se**2 + row["offset_se"] ** 2)
        lo = np.exp(fam.base + row["offset"] + fam.trend - 1.96 * se)
        hi = np.exp(fam.base + row["offset"] + fam.trend + 1.96 * se)
        return pd.Series(lo, index=fam.grid), pd.Series(hi, index=fam.grid)

    def configure_value(
        self, base_value: float, full_set: bool = True, bracelet: str | None = None
    ) -> float:
        """Re-apply configuration effects to a standardized value."""
        v = np.log(base_value)
        if not full_set:
            v -= self.hedonics.get("full_set", 0.0)
        if bracelet and f"bracelet_{bracelet}" in self.hedonics:
            v += self.hedonics[f"bracelet_{bracelet}"]
        return float(np.exp(v))

    def forecast_trend(
        self, family: str, horizon_weeks: int = 8, damp: float = 0.4
    ) -> pd.DataFrame | None:
        """Damped extrapolation of the SMOOTHED trend with honest bands."""
        fam = self.families.get(family)
        if fam is None or len(fam.grid) < 6:
            return None
        # Slope from the last ~10 weeks of the smoothed trend
        tail = min(10, len(fam.grid))
        x = np.arange(tail, dtype=float)
        slope, _, _, _ = stats.theilslopes(fam.trend[-tail:], x, 0.90)
        slope *= damp
        # Uncertainty from historical increments of the smoothed trend
        increments = np.diff(fam.trend)
        inc_scale = float(np.median(np.abs(increments)) * 1.4826) if len(increments) else 0.02
        last = fam.trend[-1]
        rng = np.random.default_rng(11)
        steps = rng.normal(slope, max(inc_scale, 1e-4), size=(2000, horizon_weeks))
        paths = last + np.cumsum(steps, axis=1)
        week = pd.Timedelta(weeks=1)
        rows = []
        for h in range(horizon_weeks):
            rows.append(
                {
                    "week": fam.grid[-1] + week * (h + 1),
                    "trend": last + slope * (h + 1),
                    "p05": np.percentile(paths[:, h], 5),
                    "p95": np.percentile(paths[:, h], 95),
                }
            )
        return pd.DataFrame(rows)


# ── Estimation ────────────────────────────────────────────────────────────


MIN_SIZE_SPLIT = 15  # a size band becomes its own atom only if this dense


def _size_band(size_mm) -> str | None:
    """Coarse case-size bands. Ladies'/mid/full trade as distinct markets;
    the band is only used to split a family-generic atom where dense."""
    if size_mm is None or (isinstance(size_mm, float) and np.isnan(size_mm)):
        return None
    s = float(size_mm)
    if s < 34:
        return "sub34"
    if s < 38:
        return "34-37"
    if s < 42:
        return "38-41"
    return "42+"


def _row_size(row) -> float | None:
    for col in ("parsed_size", "linked_size_mm"):
        v = row.get(col)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            return v
    return None


def _node_key(row, dense_size_cells: set | None = None) -> tuple:
    """(node_type, brand, ref, dial, family, material, size_band) identity.

    The pricing atom. Matched watches key on reference (+dial variant);
    material and size are fixed by the reference so they are not split
    dimensions there. Unmatched (family-generic) atoms key on
    (family, material, size-band) — material is the dominant price driver
    and size a secondary one, but size only splits the atom where the
    (family, material, band) cell is dense enough to estimate; otherwise it
    folds back to (family, material). This is the adaptive-granularity rule.
    """
    conf = row.get("match_confidence") or 0
    if isinstance(row.get("linked_ref"), str) and conf >= 0.65:
        dial = row.get("linked_dial")
        dial = dial if isinstance(dial, str) else None
        if dial:
            return ("variant", row["linked_brand"], row["linked_ref"], dial,
                    row["family"], row["material"], "")
        return ("ref", row["linked_brand"], row["linked_ref"], None,
                row["family"], row["material"], "")

    band = _size_band(_row_size(row))
    if dense_size_cells is not None and band is not None:
        cell = (row["family"], row["material"], band)
        band = band if cell in dense_size_cells else ""
    else:
        band = band or ""
    return ("family_material", row.get("brand"), None, None,
            row["family"], row["material"], band)


def _estimate_hedonics(df: pd.DataFrame) -> dict[str, float]:
    """Pooled log premia for configuration factors via within-cell contrasts."""
    hedonics: dict[str, float] = {}
    cells = df.groupby(["family", "material"])

    def pooled_contrast(flag_col: str) -> float | None:
        diffs, weights = [], []
        for _, cell in cells:
            a = cell[cell[flag_col]]["log_price"]
            b = cell[~cell[flag_col]]["log_price"]
            if len(a) >= MIN_HEDONIC_CELL and len(b) >= MIN_HEDONIC_CELL:
                diffs.append(a.median() - b.median())
                weights.append(min(len(a), len(b)))
        if not diffs:
            return None
        return _weighted_median(np.array(diffs), np.array(weights, dtype=float))

    fs = pooled_contrast("full_set")
    if fs is not None:
        # Bound to sanity: the full-set premium is real but not 2x
        hedonics["full_set"] = float(np.clip(fs, 0.0, 0.25))

    for bracelet in ("jubilee",):
        df["_flag"] = df["bracelet"] == bracelet
        contrast = pooled_contrast("_flag")
        if contrast is not None:
            hedonics[f"bracelet_{bracelet}"] = float(np.clip(contrast, -0.15, 0.15))
    df.drop(columns="_flag", errors="ignore", inplace=True)
    return hedonics


def build_valuation(clean_sold: pd.DataFrame) -> ValuationModel:
    """Fit the full model from clean sold records.

    clean_sold needs: price, event_date, family, material, title,
    linked_brand/linked_ref/linked_dial, match_confidence, parsed_attributes
    (for bracelet), retail_price.
    """
    df = clean_sold.copy()
    df = df[df["family"].notna() & (df["price"] > 0)].copy()
    if df.empty:
        return ValuationModel()

    df["log_price"] = np.log(df["price"])
    df["full_set"] = df["title"].map(parse_full_set)
    df["bracelet"] = (
        df["parsed_bracelet"] if "parsed_bracelet" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    df["t_days"] = (
        df["event_date"].dt.tz_convert("UTC").dt.tz_localize(None)
        - pd.Timestamp("2026-01-01")
    ).dt.total_seconds() / 86400.0

    hedonics = _estimate_hedonics(df)

    # Standardize every sale to full-set / base-bracelet configuration
    df["y"] = df["log_price"]
    if "full_set" in hedonics:
        df.loc[~df["full_set"], "y"] += hedonics["full_set"]
    for name, premium in hedonics.items():
        if name.startswith("bracelet_"):
            b = name.split("_", 1)[1]
            df.loc[df["bracelet"] == b, "y"] -= premium

    # Adaptive size splitting: a (family, material, size-band) cell earns its
    # own atom only when dense; otherwise size folds into the material atom.
    fam_level = df[~(df["linked_ref"].notna() & (df["match_confidence"].fillna(0) >= 0.65))].copy()
    if not fam_level.empty:
        fam_level["_band"] = fam_level.apply(lambda r: _size_band(_row_size(r)), axis=1)
        cell_counts = (
            fam_level.dropna(subset=["_band"])
            .groupby(["family", "material", "_band"]).size()
        )
        dense_size_cells = {idx for idx, n in cell_counts.items() if n >= MIN_SIZE_SPLIT}
    else:
        dense_size_cells = set()

    df["node"] = df.apply(lambda r: _node_key(r, dense_size_cells), axis=1)

    families: dict[str, FamilyModel] = {}
    node_rows: list[dict] = []

    for family, fam_df in df.groupby("family"):
        if len(fam_df) < MIN_FAMILY_OBS:
            continue
        base = float(fam_df["y"].median())
        t = fam_df["t_days"].values.astype(float)
        y = fam_df["y"].values - base

        # Grid spans where the data is dense — a single vintage sale from
        # years back must not stretch a flat pseudo-history behind the trend
        naive_dates = fam_df["event_date"].dt.tz_convert("UTC").dt.tz_localize(None)
        end = naive_dates.max().normalize()
        start = max(
            naive_dates.quantile(0.05).normalize(),
            end - pd.Timedelta(weeks=60),
        )
        grid_dates = pd.date_range(start, end, freq="W-MON")
        if len(grid_dates) < 2:
            continue
        grid_t = (
            (grid_dates - pd.Timestamp("2026-01-01")).total_seconds().values / 86400.0
        )

        # Iterate: offsets given trend, trend given offsets.
        # IDENTIFICATION uses UNSHRUNK node medians (fixed-effects style):
        # any shrinkage here leaves a level residue that leaks into the
        # trend exactly where the sales mix is unbalanced — the composition
        # artifact this model exists to kill. Shrinkage is applied only to
        # the REPORTED offsets afterwards, as a prior for thin nodes.
        node_groups = {
            node: fam_df.index.get_indexer(idx)
            for node, idx in fam_df.groupby("node").groups.items()
        }
        offsets = {
            node: float(np.median(y[pos])) for node, pos in node_groups.items()
        }
        trend = np.zeros(len(grid_t))
        for _ in range(N_ITER):
            node_off = fam_df["node"].map(offsets).values
            trend = kernel_median_smoother(
                t, y - node_off, grid_t, TREND_BANDWIDTH_DAYS
            )
            trend_at_obs = np.interp(t, grid_t, trend)
            resid = y - trend_at_obs
            for node, pos in node_groups.items():
                offsets[node] = float(np.median(resid[pos]))

        # Reporting offsets: hierarchical empirical-Bayes shrinkage.
        # A variant shrinks toward its REFERENCE's pooled level (a 3-sale
        # John Mayer's prior is "a gold Daytona 116508", not "a Daytona");
        # references and generics shrink toward the family base.
        trend_at_obs = np.interp(t, grid_t, trend)
        resid_all = y - trend_at_obs

        # Anchors for hierarchical shrinkage: a dial variant shrinks toward
        # its reference's level; a size sub-atom shrinks toward its
        # (family, material) parent.
        ref_anchor: dict[tuple, list] = {}
        mat_anchor: dict[tuple, list] = {}
        for node, pos in node_groups.items():
            node_type_key, brand_key, ref_key = node[0], node[1], node[2]
            fam_key, mat_key = node[4], node[5]
            if ref_key:
                ref_anchor.setdefault((brand_key, ref_key), []).extend(resid_all[pos])
            if node_type_key == "family_material":
                mat_anchor.setdefault((fam_key, mat_key), []).extend(resid_all[pos])
        ref_anchor = {k: float(np.median(v)) for k, v in ref_anchor.items() if v}
        mat_anchor = {k: float(np.median(v)) for k, v in mat_anchor.items() if v}

        report_offsets = {}
        for node, pos in node_groups.items():
            node_type_key, brand_key, ref_key = node[0], node[1], node[2]
            fam_key, mat_key, band_key = node[4], node[5], node[6]
            node_med = float(np.median(resid_all[pos]))
            kappa = len(pos) / (len(pos) + OFFSET_SHRINK_K)
            if node_type_key == "variant" and (brand_key, ref_key) in ref_anchor:
                anchor = ref_anchor[(brand_key, ref_key)]
                report_offsets[node] = anchor + kappa * (node_med - anchor)
            elif node_type_key == "family_material" and band_key and (fam_key, mat_key) in mat_anchor:
                anchor = mat_anchor[(fam_key, mat_key)]
                report_offsets[node] = anchor + kappa * (node_med - anchor)
            else:
                report_offsets[node] = kappa * node_med

        # Residual scale for uncertainty
        node_off = fam_df["node"].map(offsets).values
        final_resid = y - node_off - np.interp(t, grid_t, trend)
        sigma = float(np.median(np.abs(final_resid)) * 1.4826) or 0.05
        # Effective n per grid point → trend standard error
        w_sums = np.array([
            np.exp(-0.5 * ((t - g) / TREND_BANDWIDTH_DAYS) ** 2).sum() for g in grid_t
        ])
        trend_se = sigma / np.sqrt(np.maximum(w_sums, 1.0))

        families[family] = FamilyModel(
            family=family, base=base, grid=grid_dates,
            trend=trend, trend_se=trend_se, n_obs=len(fam_df),
        )

        # Month-over-month changes measured on the SMOOTH trend
        def _chg(weeks_back: int) -> float | None:
            if len(trend) <= weeks_back:
                return None
            return float((np.exp(trend[-1] - trend[-1 - weeks_back]) - 1) * 100)

        chg1, chg3 = _chg(4), _chg(12)

        for node, grp in fam_df.groupby("node"):
            node_type, brand, ref, dial, fam_name, material, size_band = node
            n = len(grp)
            offset = report_offsets[node]
            offset_se = sigma / np.sqrt(n) if n else sigma
            value = float(np.exp(base + offset + trend[-1]))
            node_rows.append(
                {
                    "node_type": node_type,
                    "brand": brand,
                    "ref": ref,
                    "dial_variant": dial,
                    "family": fam_name,
                    "material": material,
                    "size_band": size_band or None,
                    "n": n,
                    "offset": offset,
                    "offset_se": offset_se,
                    "value": value,
                    "ci_lo": float(np.exp(np.log(value) - 1.96 * np.sqrt(
                        offset_se**2 + trend_se[-1] ** 2))),
                    "ci_hi": float(np.exp(np.log(value) + 1.96 * np.sqrt(
                        offset_se**2 + trend_se[-1] ** 2))),
                    "chg_1m_pct": chg1,
                    "chg_3m_pct": chg3,
                }
            )

    nodes = pd.DataFrame(node_rows)
    return ValuationModel(hedonics=hedonics, families=families, nodes=nodes)


def market_index_from_trends(model: ValuationModel) -> pd.Series:
    """Smooth market index: median family trend, rebased to 100.

    Every family trend is composition- and configuration-adjusted by
    construction, so this cannot register mix shifts as price moves.
    """
    if not model.families:
        return pd.Series(dtype=float)
    frames, weights = [], []
    for fam in model.families.values():
        if fam.n_obs >= 30:
            frames.append(pd.Series(fam.trend, index=fam.grid, name=fam.family))
            weights.append(np.sqrt(fam.n_obs))
    if not frames:
        return pd.Series(dtype=float)
    panel = pd.concat(frames, axis=1)
    w = np.array(weights)

    # Chain weekly returns (families present in BOTH weeks), never level an
    # unbalanced panel — a family entering mid-window must not move the index
    diffs = panel.diff()
    steps = []
    for _, row in diffs.iloc[1:].iterrows():
        mask = row.notna().values
        if mask.any():
            steps.append(_weighted_median(row.values[mask].astype(float), w[mask]))
        else:
            steps.append(0.0)
    level = np.concatenate([[0.0], np.cumsum(steps)])
    return pd.Series(
        100.0 * np.exp(level), index=panel.index, name="index"
    )
