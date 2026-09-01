from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_erp(
    operator_heat: pd.DataFrame,
    categories: pd.DataFrame,
    seed: int = 20260901,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for _, operator in operator_heat.iterrows():
        heat_factor = 0.65 + float(operator["heat_score"]) / 100
        for _, category in categories.iterrows():
            price = float(category["reference_price"])
            cost_rate = float(category["unit_cost_rate"])
            live_fit = float(category["live_fit"])
            production_risk = float(category["production_risk"])
            page_views = max(300, int(rng.normal(5200 * heat_factor * live_fit, 500)))
            base_conversion = 0.018 + 0.045 * live_fit + 0.02 * heat_factor
            orders = max(1, int(page_views * np.clip(rng.normal(base_conversion, 0.006), 0.01, 0.18)))
            units_per_order = np.clip(rng.normal(1.18, 0.08), 1.0, 1.6)
            demand_units = max(1, int(orders * units_per_order))
            inventory_buffer = 1.10 + production_risk * 0.35
            launch_inventory = max(demand_units, int(demand_units * inventory_buffer))
            sold_units = min(launch_inventory, demand_units)
            return_rate = np.clip(0.015 + production_risk * 0.08 + rng.normal(0, 0.006), 0, 0.15)
            return_units = int(round(sold_units * return_rate))
            rows.append(
                {
                    "sku_id": f"{operator['operator']}-{category['category']}",
                    "operator": operator["operator"],
                    "category": category["category"],
                    "heat_score": round(float(operator["heat_score"]), 4),
                    "price": round(price, 2),
                    "unit_cost": round(price * cost_rate, 2),
                    "live_fit": live_fit,
                    "production_risk": production_risk,
                    "page_views": page_views,
                    "orders": orders,
                    "launch_inventory": launch_inventory,
                    "sold_units": sold_units,
                    "return_units": return_units,
                    "is_simulated": True,
                    "simulation_seed": seed,
                }
            )
    return pd.DataFrame(rows)

