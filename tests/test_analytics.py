import pandas as pd
import pytest

from smart_business_analytics.analytics import (
    DataValidationError,
    calculate_line_metrics,
    create_demo_data,
    detect_daily_revenue_anomalies,
    filter_by_period,
    normalise_sales_data,
    recommendations_for,
    summary_metrics,
)


def sample_sales() -> pd.DataFrame:
    return normalise_sales_data(
        pd.DataFrame(
            {
                "sale_date": ["2025-01-01", "2025-01-02", "2025-01-03"],
                "item": ["Mouse", "Keyboard", "Mouse"],
                "product_category": ["Accessories", "Accessories", "Accessories"],
                "qty": [2, 1, 3],
                "price": [20, 50, 20],
                "cost": [12, 65, 12],
            }
        )
    )


def test_normalise_supports_common_column_aliases():
    result = sample_sales()
    assert {"date", "product", "category", "quantity", "unit_price", "unit_cost"}.issubset(result.columns)
    assert result.loc[0, "product"] == "Mouse"


def test_normalise_rejects_missing_required_columns():
    with pytest.raises(DataValidationError, match="unit_cost"):
        normalise_sales_data(pd.DataFrame({"date": ["2025-01-01"], "product": ["Mouse"], "quantity": [1], "price": [20]}))


def test_profit_margin_and_period_filter_are_calculated_correctly():
    sales = calculate_line_metrics(sample_sales())
    filtered = filter_by_period(sales, "2025-01-01", "2025-01-02")
    metrics = summary_metrics(filtered)
    assert metrics["revenue"] == 90
    assert metrics["gross_profit"] == 1
    assert round(metrics["gross_margin_pct"], 2) == 1.11


def test_anomaly_detection_finds_large_revenue_spike():
    raw = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=20, freq="D"),
            "product": ["Widget"] * 20,
            "quantity": [1] * 19 + [20],
            "unit_price": [10] * 20,
            "unit_cost": [5] * 20,
        }
    )
    anomalies = detect_daily_revenue_anomalies(calculate_line_metrics(normalise_sales_data(raw)))
    assert list(anomalies["date"].dt.strftime("%Y-%m-%d")) == ["2025-01-20"]
    assert anomalies.loc[0, "direction"] == "Higher than usual"


def test_recommendations_explain_loss_making_product():
    sales = calculate_line_metrics(sample_sales())
    recommendations = recommendations_for(sales)
    assert any(item["title"] == "Review Keyboard" for item in recommendations)


def test_demo_data_is_repeatable_and_has_expected_schema():
    first = create_demo_data()
    second = create_demo_data()
    assert first.equals(second)
    assert len(first) == 1800
    assert {"date", "product", "category", "quantity", "unit_price", "unit_cost"} == set(first.columns)
