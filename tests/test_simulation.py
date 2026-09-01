from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.metrics import build_sku_recommendations
from arknights_merch_analytics.simulation import simulate_erp


def test_simulation_is_reproducible_and_labeled() -> None:
    heat = pd.DataFrame([{"operator": "望", "heat_score": 88.0}])
    categories = pd.DataFrame(
        [
            {
                "category": "徽章",
                "reference_price": 18,
                "unit_cost_rate": 0.3,
                "live_fit": 0.9,
                "production_risk": 0.15,
            }
        ]
    )
    first = simulate_erp(heat, categories, seed=7)
    second = simulate_erp(heat, categories, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert first["is_simulated"].all()
    assert (first["sold_units"] <= first["launch_inventory"]).all()


def test_recommendation_metrics_are_valid() -> None:
    erp = pd.DataFrame(
        [
            {
                "sku_id": "望-徽章",
                "operator": "望",
                "category": "徽章",
                "heat_score": 90,
                "price": 18,
                "unit_cost": 5,
                "live_fit": 0.9,
                "production_risk": 0.2,
                "page_views": 1000,
                "orders": 100,
                "launch_inventory": 130,
                "sold_units": 120,
                "return_units": 2,
                "is_simulated": True,
                "simulation_seed": 1,
            }
        ]
    )
    output = build_sku_recommendations(erp)
    assert 0 <= output.iloc[0]["sell_through_rate"] <= 1
    assert output.iloc[0]["gmv"] == 2160

