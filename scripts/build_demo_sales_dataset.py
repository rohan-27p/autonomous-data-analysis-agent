"""Generate a clean, demo-friendly sales dataset for the Autonomous Data Analysis Agent.

Reproducible (fixed seed). Produces a single flat table that exercises every
analysis capability: aggregation, grouping, trend, ranking, correlation,
distribution, segmentation, filtering/lookup, anomaly detection, and data-quality
profiling (a few intentional nulls + outliers).

Run:
    python scripts/build_demo_sales_dataset.py

Outputs:
    docs/demo_sales_dataset.csv
    docs/demo_sales_dataset.xlsx
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 20260625
OUT_DIR = Path(__file__).resolve().parent.parent / "docs"
N_ROWS = 320
START = date(2025, 1, 1)
END = date(2025, 12, 31)

# Region market size weights (West/East are the big markets) and a units multiplier.
REGIONS = {
    "West": (0.30, 1.25),
    "East": (0.26, 1.15),
    "North": (0.18, 0.95),
    "South": (0.16, 0.90),
    "Central": (0.10, 0.80),
}
COUNTRY_BY_REGION = {
    "West": "USA",
    "East": "USA",
    "North": "Canada",
    "South": "Mexico",
    "Central": "USA",
}
# category -> (unit_price, cost_ratio, popularity weight)
CATEGORIES = {
    "Widgets": (20.0, 0.60, 0.34),
    "Gadgets": (52.0, 0.55, 0.27),
    "Gizmos": (125.0, 0.50, 0.18),
    "Accessories": (12.0, 0.70, 0.21),
}
PRODUCTS = {
    "Widgets": ["Widget Mini", "Widget Pro", "Widget Max"],
    "Gadgets": ["Gadget Air", "Gadget Plus", "Gadget Ultra"],
    "Gizmos": ["Gizmo One", "Gizmo Studio", "Gizmo Enterprise"],
    "Accessories": ["Cable Pack", "Travel Case", "Mount Kit"],
}
SEGMENTS = {"Consumer": 0.5, "SMB": 0.32, "Corporate": 0.18}
CHANNELS = {"Online": 0.55, "Retail": 0.30, "Partner": 0.15}


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def region_weights() -> dict[str, float]:
    return {name: share for name, (share, _) in REGIONS.items()}


def category_weights() -> dict[str, float]:
    return {name: w for name, (_, _, w) in CATEGORIES.items()}


def seasonal_multiplier(d: date) -> float:
    # Gentle growth through the year with a Q4 holiday spike.
    base = 1.0 + (d.month - 1) * 0.03
    if d.month in (11, 12):
        base *= 1.45
    return base


def build_rows(rng: random.Random) -> list[dict]:
    span_days = (END - START).days
    rows: list[dict] = []
    for i in range(N_ROWS):
        order_date = START + timedelta(days=rng.randint(0, span_days))
        region = weighted_choice(rng, region_weights())
        _, units_mult = REGIONS[region]
        category = weighted_choice(rng, category_weights())
        unit_price, cost_ratio, _ = CATEGORIES[category]
        product = rng.choice(PRODUCTS[category])
        segment = weighted_choice(rng, SEGMENTS)
        channel = weighted_choice(rng, CHANNELS)

        seg_mult = {"Consumer": 1.0, "SMB": 1.6, "Corporate": 2.4}[segment]
        base_units = rng.randint(1, 18)
        raw_units = base_units * units_mult * seg_mult * seasonal_multiplier(order_date) / 1.5
        units = max(1, round(raw_units))

        # Discounts cluster low; corporate/partner deals get deeper discounts.
        discount = round(min(0.30, max(0.0, rng.gauss(0.08, 0.06)
                        + (0.06 if segment == "Corporate" else 0)
                        + (0.04 if channel == "Partner" else 0))), 2)

        unit_cost = round(unit_price * cost_ratio, 2)
        revenue = round(units * unit_price * (1 - discount), 2)
        cost = round(units * unit_cost, 2)
        profit = round(revenue - cost, 2)

        # Satisfaction skews positive; ~8% missing to demo data-quality profiling.
        if rng.random() < 0.08:
            satisfaction = None
        else:
            satisfaction = rng.choices([5, 4, 3, 2, 1], weights=[40, 32, 18, 7, 3], k=1)[0]

        rows.append(
            {
                "order_id": 100001 + i,
                "order_date": order_date.isoformat(),
                "region": region,
                "country": COUNTRY_BY_REGION[region],
                "product_category": category,
                "product": product,
                "customer_segment": segment,
                "sales_channel": channel,
                "units": units,
                "unit_price": unit_price,
                "discount": discount,
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
                "customer_satisfaction": satisfaction,
            }
        )
    return rows


def inject_anomalies(rng: random.Random, rows: list[dict]) -> None:
    # Two clear bulk orders (revenue outliers) and one loss-making deep-discount order,
    # so anomaly-detection / "find unusual orders" questions have something to surface.
    bulk_idx = rng.sample(range(len(rows)), 2)
    for idx in bulk_idx:
        r = rows[idx]
        r["customer_segment"] = "Corporate"
        r["units"] = rng.randint(450, 600)
        r["discount"] = 0.05
        r["revenue"] = round(r["units"] * r["unit_price"] * (1 - r["discount"]), 2)
        r["cost"] = round(r["units"] * r["unit_price"] * CATEGORIES[r["product_category"]][1], 2)
        r["profit"] = round(r["revenue"] - r["cost"], 2)

    loss_idx = rng.choice([i for i in range(len(rows)) if i not in bulk_idx])
    r = rows[loss_idx]
    r["discount"] = 0.62  # unusually deep discount -> negative margin
    r["revenue"] = round(r["units"] * r["unit_price"] * (1 - r["discount"]), 2)
    r["profit"] = round(r["revenue"] - r["cost"], 2)


def main() -> None:
    rng = random.Random(SEED)
    rows = build_rows(rng)
    inject_anomalies(rng, rows)
    df = pd.DataFrame(rows).sort_values("order_date").reset_index(drop=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "demo_sales_dataset.csv"
    xlsx_path = OUT_DIR / "demo_sales_dataset.xlsx"
    df.to_csv(csv_path, index=False)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sales")

    print(f"Wrote {len(df)} rows x {len(df.columns)} cols")
    print(f"  {csv_path}")
    print(f"  {xlsx_path}")
    print("Totals -> revenue:", round(df["revenue"].sum(), 2),
          "profit:", round(df["profit"].sum(), 2))
    print("Nulls in customer_satisfaction:", int(df["customer_satisfaction"].isna().sum()))


if __name__ == "__main__":
    main()
