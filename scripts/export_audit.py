"""Audit export: one line per watch, then the data points behind each value.

  data/audit_watches.csv   — ONE ROW = ONE WATCH (a sellable identity):
      every dial variant, plus every single-dial reference. Internal
      pricing buckets (unresolved-dial parents, family generics) are NOT
      watches and live in audit_internals.csv instead.

  data/audit_evidence.csv  — the data points that compose each value:
      every clean sale attributed to each watch (its offset evidence),
      with the raw price, detected configuration, the standardized price
      the model actually used, and its deviation from the final value.
      A watch's value = its offset evidence + the family trend; the trend's
      corpus size and span are columns on the watch row.

  data/audit_internals.csv — unresolved-dial parent buckets and
      family-generic nodes with their values, so nothing is hidden.

  data/audit_sales.csv     — the full sold corpus with match assignments
      and cleaning flags (junk/suspect/outlier), for tracing exclusions.
"""

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sqlalchemy import text

from watchscraper.analysis import REF_VALUE_MIN_CONFIDENCE, build_clean_dataset, reference_values
from watchscraper.database import engine
from watchscraper.valuation import build_valuation, parse_full_set
from watchscraper.web.services import ref_slug

BASE_URL = "https://watchscraper-worker-production.up.railway.app"
OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    df = build_clean_dataset(engine)
    clean_sold = df[df["clean"] & (df["price_type"] == "sold")].copy()
    model = build_valuation(clean_sold)
    ref_vals = reference_values(df)

    catalog = pd.read_sql(
        text("""
            SELECT b.name AS brand, w.reference_number AS ref, w.dial_variant,
                   w.model_name, w.family, w.case_material, w.dial_color,
                   w.bezel, w.bracelet, w.case_size_mm,
                   w.production_start_year, w.production_end_year,
                   w.retail_price_usd / 100.0 AS retail_usd,
                   (SELECT string_agg(n.nickname, ' | ')
                    FROM watch_nicknames n WHERE n.watch_id = w.id) AS nicknames,
                   EXISTS (SELECT 1 FROM watches w2
                           WHERE w2.brand_id = w.brand_id
                             AND w2.reference_number = w.reference_number
                             AND w2.dial_variant IS NOT NULL) AS ref_has_variants
            FROM watches w JOIN brands b ON b.id = w.brand_id
            ORDER BY b.name, w.reference_number, w.dial_variant NULLS FIRST
        """),
        engine,
    )

    nodes = model.nodes
    comps_idx = (
        ref_vals.set_index(["brand", "ref", ref_vals["dial_variant"].fillna("")])
        if not ref_vals.empty
        else None
    )

    static_refs = (
        Path(__file__).resolve().parent.parent
        / "src" / "watchscraper" / "web" / "static" / "img" / "refs"
    )

    def node_for(brand: str, ref: str, dial: str | None):
        if nodes.empty:
            return None
        hit = nodes[
            (nodes["brand"] == brand)
            & (nodes["ref"] == ref)
            & (nodes["dial_variant"].fillna("") == (dial or ""))
        ]
        return hit.iloc[0] if len(hit) else None

    watch_rows, internal_rows = [], []
    for _, w in catalog.iterrows():
        dial = w["dial_variant"] if pd.notna(w["dial_variant"]) else None
        is_watch = dial is not None or not w["ref_has_variants"]
        node = node_for(w["brand"], w["ref"], dial)
        fam_model = model.families.get(w["family"]) if pd.notna(w["family"]) else None
        slug = ref_slug(w["brand"], w["ref"], dial)

        comp_med = comp_n = None
        if comps_idx is not None:
            key = (w["brand"], w["ref"], dial or "")
            if key in comps_idx.index:
                comp = comps_idx.loc[key]
                comp_med = float(comp["median_usd"])
                comp_n = int(comp["n_sold"])

        value = float(node["value"]) if node is not None else None
        retail = float(w["retail_usd"]) if pd.notna(w["retail_usd"]) else None

        row = {
            "watch_key": f"{w['brand']}|{w['ref']}|{dial or ''}",
            "brand": w["brand"],
            "reference": w["ref"],
            "dial_variant": dial or "",
            "model_name": w["model_name"],
            "family": w["family"],
            "case_material": w["case_material"],
            "dial_color": dial or w["dial_color"],
            "bezel": w["bezel"],
            "bracelet": w["bracelet"],
            "case_size_mm": w["case_size_mm"],
            "prod_start": w["production_start_year"],
            "prod_end": w["production_end_year"],
            "nicknames": w["nicknames"] or "",
            "retail_usd": retail,
            "model_value_usd": round(value, 0) if value else None,
            "value_ci_lo": round(float(node["ci_lo"]), 0) if node is not None else None,
            "value_ci_hi": round(float(node["ci_hi"]), 0) if node is not None else None,
            "n_own_sales": int(node["n"]) if node is not None else 0,
            "offset_log": round(float(node["offset"]), 4) if node is not None else None,
            "family_trend_sales_n": fam_model.n_obs if fam_model else 0,
            "value_composition": (
                f"offset from {int(node['n'])} own sales + {w['family']} trend "
                f"({fam_model.n_obs} sales)"
                if node is not None and fam_model
                else "no cleared sales — not valued"
            ),
            "chg_1m_pct": round(float(node["chg_1m_pct"]), 2)
            if node is not None and pd.notna(node["chg_1m_pct"]) else None,
            "comps_median_usd": comp_med,
            "comps_n": comp_n,
            "premium_vs_retail_pct": round((value / retail - 1) * 100, 1)
            if (value and retail) else None,
            "has_ui_page": comp_med is not None,
            "ui_url": f"{BASE_URL}/refs/{slug}" if comp_med is not None else "",
            "has_own_image": (static_refs / f"{slug}.jpg").exists(),
        }
        if is_watch:
            watch_rows.append(row)
        else:
            internal_rows.append(
                {**row, "row_kind": "unresolved_dial_bucket",
                 "note": "internal: sales of this ref with unknown dial; never displayed, never prices a variant"}
            )

    if not nodes.empty:
        for _, node in nodes[nodes["node_type"] == "family_material"].iterrows():
            internal_rows.append(
                {
                    "watch_key": f"generic|{node['family']}|{node['material']}",
                    "brand": node["brand"] or "",
                    "family": node["family"],
                    "case_material": node["material"],
                    "model_value_usd": round(float(node["value"]), 0),
                    "value_ci_lo": round(float(node["ci_lo"]), 0),
                    "value_ci_hi": round(float(node["ci_hi"]), 0),
                    "n_own_sales": int(node["n"]),
                    "row_kind": "family_generic",
                    "note": "internal: values listings not matched to any reference",
                }
            )

    watches_df = pd.DataFrame(watch_rows)
    internals_df = pd.DataFrame(internal_rows)

    # ── Evidence: the data points composing each watch's value ──────────
    ev = clean_sold[
        clean_sold["linked_ref"].notna()
        & (clean_sold["match_confidence"].fillna(0) >= REF_VALUE_MIN_CONFIDENCE)
    ].copy()
    ev["dial"] = ev["linked_dial"].fillna("")
    ev["watch_key"] = ev["linked_brand"] + "|" + ev["linked_ref"] + "|" + ev["dial"]
    ev["full_set"] = ev["title"].map(parse_full_set)
    fs_mult = float(np.exp(model.hedonics.get("full_set", 0.0)))
    ev["standardized_price_usd"] = np.where(
        ev["full_set"], ev["price"], ev["price"] * fs_mult
    ).round(0)

    value_by_key = {r["watch_key"]: r["model_value_usd"] for r in watch_rows}
    value_by_key.update(
        {r["watch_key"]: r.get("model_value_usd") for r in internal_rows}
    )
    ev["vs_final_value_pct"] = [
        round((sp / value_by_key[k] - 1) * 100, 1)
        if value_by_key.get(k) else None
        for sp, k in zip(ev["standardized_price_usd"], ev["watch_key"])
    ]

    evidence = ev[
        ["watch_key", "event_date", "price", "full_set",
         "standardized_price_usd", "vs_final_value_pct", "match_method",
         "match_confidence", "source", "title"]
    ].rename(columns={"price": "raw_price_usd"}).copy()
    evidence["event_date"] = evidence["event_date"].dt.strftime("%Y-%m-%d")
    evidence["title"] = evidence["title"].str.slice(0, 140)
    evidence = evidence.sort_values(["watch_key", "event_date"])

    # ── Full corpus with flags ───────────────────────────────────────────
    sold = df[df["price_type"] == "sold"].copy()
    sales = pd.DataFrame(
        {
            "event_date": sold["event_date"].dt.strftime("%Y-%m-%d"),
            "price_usd": sold["price"],
            "title": sold["title"].str.slice(0, 140),
            "source": sold["source"],
            "matched_brand": sold["linked_brand"],
            "matched_ref": sold["linked_ref"],
            "matched_dial": sold["linked_dial"],
            "family": sold["family"],
            "material_bucket": sold["material"],
            "match_method": sold["match_method"],
            "match_confidence": sold["match_confidence"],
            "prices_a_watch": (
                sold["linked_ref"].notna()
                & (sold["match_confidence"].fillna(0) >= REF_VALUE_MIN_CONFIDENCE)
                & sold["clean"]
            ),
            "flag_junk": sold["is_junk"],
            "flag_suspect": sold["is_suspect"],
            "flag_outlier": sold["is_outlier"],
            "clean": sold["clean"],
        }
    ).sort_values(["matched_brand", "matched_ref", "matched_dial", "event_date"])

    OUT_DIR.mkdir(exist_ok=True)
    watches_df.to_csv(OUT_DIR / "audit_watches.csv", index=False)
    evidence.to_csv(OUT_DIR / "audit_evidence.csv", index=False)
    internals_df.to_csv(OUT_DIR / "audit_internals.csv", index=False)
    sales.to_csv(OUT_DIR / "audit_sales.csv", index=False)

    # Excel workbook: same data as sheets ("subsequent pages")
    try:
        with pd.ExcelWriter(OUT_DIR / "audit.xlsx", engine="openpyxl") as xl:
            watches_df.to_excel(xl, sheet_name="Watches", index=False)
            evidence.to_excel(xl, sheet_name="Value evidence", index=False)
            internals_df.to_excel(xl, sheet_name="Internal buckets", index=False)
            sales.to_excel(xl, sheet_name="All sales + flags", index=False)
        xlsx = True
    except Exception:
        xlsx = False

    print(f"audit_watches.csv:   {len(watches_df)} watches "
          f"(valued: {watches_df.model_value_usd.notna().sum()})")
    print(f"audit_evidence.csv:  {len(evidence)} data points across "
          f"{evidence.watch_key.nunique()} watches/buckets")
    print(f"audit_internals.csv: {len(internals_df)} internal buckets")
    print(f"audit_sales.csv:     {len(sales)} sold records")
    if xlsx:
        print(f"audit.xlsx:          all four as sheets")


if __name__ == "__main__":
    main()
