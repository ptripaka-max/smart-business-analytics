"""Validation and transparent financial calculations used by the dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    """Raised when an uploaded sales file cannot support reliable calculations."""


_ALIASES = {
    "date": {"date", "sale_date", "order_date", "transaction_date"},
    "product": {"product", "product_name", "item", "item_name"},
    "category": {"category", "product_category"},
    "quantity": {"quantity", "qty", "units", "units_sold"},
    "unit_price": {"unit_price", "price", "selling_price", "sale_price"},
    "unit_cost": {"unit_cost", "cost", "cost_price", "purchase_price"},
}
_REQUIRED_COLUMNS = {"date", "product", "quantity", "unit_price", "unit_cost"}


def _clean_column_name(name: object) -> str:
    return "_".join(str(name).strip().lower().replace("-", " ").split())


def load_sales_file(source: BinaryIO | bytes | Path, filename: str) -> pd.DataFrame:
    """Read a CSV or XLSX file selected by the dashboard user."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(source)
    raise DataValidationError("Please upload a CSV, XLS, or XLSX file.")


def normalise_sales_data(raw: pd.DataFrame) -> pd.DataFrame:
    """Map common column names to the required sales schema and validate it."""
    if raw.empty:
        raise DataValidationError("The uploaded file has no rows.")

    columns_by_clean_name = {_clean_column_name(column): column for column in raw.columns}
    rename_map: dict[object, str] = {}
    for canonical_name, aliases in _ALIASES.items():
        source_name = next((columns_by_clean_name[name] for name in aliases if name in columns_by_clean_name), None)
        if source_name is not None:
            rename_map[source_name] = canonical_name

    data = raw.rename(columns=rename_map).copy()
    if data.columns.duplicated().any():
        raise DataValidationError("The file contains duplicate column names after normalisation.")

    missing = sorted(_REQUIRED_COLUMNS - set(data.columns))
    if missing:
        raise DataValidationError(
            "Missing required columns: " + ", ".join(missing) + ". See the expected schema in the dashboard."
        )

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    invalid_dates = int(data["date"].isna().sum())
    if invalid_dates:
        raise DataValidationError(f"{invalid_dates} row(s) have an invalid date.")

    for column in ("quantity", "unit_price", "unit_cost"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
        invalid_values = int(data[column].isna().sum())
        if invalid_values:
            raise DataValidationError(f"{invalid_values} row(s) have an invalid {column} value.")
        if (data[column] < 0).any():
            raise DataValidationError(f"{column} cannot contain negative values.")

    if (data["quantity"] == 0).any():
        raise DataValidationError("quantity must be greater than zero.")
    if data["product"].isna().any() or data["product"].astype(str).str.strip().eq("").any():
        raise DataValidationError("Every row must include a product name.")

    data["product"] = data["product"].astype(str).str.strip()
    if "category" not in data:
        data["category"] = "Uncategorized"
    data["category"] = data["category"].fillna("Uncategorized").astype(str).str.strip()
    data.loc[data["category"].eq(""), "category"] = "Uncategorized"
    data["date"] = data["date"].dt.normalize()
    return data.sort_values("date").reset_index(drop=True)


def calculate_line_metrics(data: pd.DataFrame) -> pd.DataFrame:
    """Add revenue, cost of goods sold, gross profit, and gross margin per row."""
    result = data.copy()
    result["revenue"] = result["quantity"] * result["unit_price"]
    result["cost_of_goods"] = result["quantity"] * result["unit_cost"]
    result["gross_profit"] = result["revenue"] - result["cost_of_goods"]
    result["gross_margin_pct"] = np.where(
        result["revenue"].gt(0), result["gross_profit"] / result["revenue"] * 100, 0.0
    )
    return result


def summary_metrics(data: pd.DataFrame) -> dict[str, float]:
    """Return aggregate measures calculated from the selected sales rows."""
    revenue = float(data["revenue"].sum())
    cost_of_goods = float(data["cost_of_goods"].sum())
    gross_profit = float(data["gross_profit"].sum())
    return {
        "revenue": revenue,
        "cost_of_goods": cost_of_goods,
        "gross_profit": gross_profit,
        "gross_margin_pct": gross_profit / revenue * 100 if revenue else 0.0,
        "units_sold": float(data["quantity"].sum()),
    }


def filter_by_period(data: pd.DataFrame, start: object, end: object, categories: list[str] | None = None) -> pd.DataFrame:
    """Filter sales inclusively by date and optionally by product category."""
    start_date = pd.Timestamp(start).normalize()
    end_date = pd.Timestamp(end).normalize()
    if start_date > end_date:
        raise ValueError("The start date must not be after the end date.")
    filtered = data.loc[data["date"].between(start_date, end_date)].copy()
    if categories is not None:
        filtered = filtered.loc[filtered["category"].isin(categories)].copy()
    return filtered


def _grouped_performance(data: pd.DataFrame, column: str) -> pd.DataFrame:
    grouped = data.groupby(column, as_index=False).agg(
        revenue=("revenue", "sum"),
        cost_of_goods=("cost_of_goods", "sum"),
        gross_profit=("gross_profit", "sum"),
        units_sold=("quantity", "sum"),
    )
    grouped["gross_margin_pct"] = np.where(
        grouped["revenue"].gt(0), grouped["gross_profit"] / grouped["revenue"] * 100, 0.0
    )
    return grouped.sort_values("gross_profit", ascending=False).reset_index(drop=True)


def product_performance(data: pd.DataFrame) -> pd.DataFrame:
    return _grouped_performance(data, "product")


def category_performance(data: pd.DataFrame) -> pd.DataFrame:
    return _grouped_performance(data, "category")


def monthly_performance(data: pd.DataFrame) -> pd.DataFrame:
    monthly = data.assign(month=data["date"].dt.to_period("M").dt.to_timestamp())
    return _grouped_performance(monthly, "month").sort_values("month").reset_index(drop=True)


def detect_daily_revenue_anomalies(data: pd.DataFrame, z_threshold: float = 2.0) -> pd.DataFrame:
    """Flag daily revenue unusually far from the average for the selected period."""
    daily = data.groupby("date", as_index=False).agg(revenue=("revenue", "sum"))
    daily = daily.sort_values("date").reset_index(drop=True)
    if len(daily) < 7 or daily["revenue"].std(ddof=0) == 0:
        return pd.DataFrame(columns=["date", "revenue", "z_score", "direction"])

    mean_revenue = daily["revenue"].mean()
    std_revenue = daily["revenue"].std(ddof=0)
    daily["z_score"] = (daily["revenue"] - mean_revenue) / std_revenue
    anomalies = daily.loc[daily["z_score"].abs() >= z_threshold].copy()
    anomalies["direction"] = np.where(anomalies["z_score"] > 0, "Higher than usual", "Lower than usual")
    return anomalies.sort_values("z_score", key=lambda values: values.abs(), ascending=False).reset_index(drop=True)


def recommendations_for(data: pd.DataFrame, anomalies: pd.DataFrame | None = None) -> list[dict[str, str]]:
    """Create action-oriented recommendations using only displayed calculations."""
    metrics = summary_metrics(data)
    products = product_performance(data)
    items: list[dict[str, str]] = []

    loss_makers = products.loc[products["gross_profit"] < 0].head(3)
    for _, row in loss_makers.iterrows():
        items.append(
            {
                "priority": "High",
                "title": f"Review {row['product']}",
                "evidence": f"It generated ${abs(row['gross_profit']):,.0f} in gross losses at a {row['gross_margin_pct']:.1f}% margin.",
                "action": "Check supplier cost, selling price, discounts, and whether the product should remain in the range.",
            }
        )

    if metrics["gross_margin_pct"] < 20:
        items.append(
            {
                "priority": "Medium",
                "title": "Protect overall margin",
                "evidence": f"Gross margin is {metrics['gross_margin_pct']:.1f}% for the selected period.",
                "action": "Prioritise higher-margin products and test price or purchasing changes before increasing sales spend.",
            }
        )

    anomalies = anomalies if anomalies is not None else detect_daily_revenue_anomalies(data)
    negative_anomalies = anomalies.loc[anomalies["z_score"] < 0].head(2)
    average_daily_revenue = data.groupby("date")["revenue"].sum().mean()
    for _, row in negative_anomalies.iterrows():
        difference = (row["revenue"] / average_daily_revenue - 1) * 100
        items.append(
            {
                "priority": "Medium",
                "title": f"Investigate sales dip on {row['date']:%b %d, %Y}",
                "evidence": f"Revenue was ${row['revenue']:,.0f}, {abs(difference):.0f}% below the period's average daily revenue.",
                "action": "Check stock availability, campaigns, channel performance, and any operational events from that day.",
            }
        )

    if not items:
        items.append(
            {
                "priority": "Info",
                "title": "No urgent profitability issue found",
                "evidence": f"All products have non-negative gross profit and overall margin is {metrics['gross_margin_pct']:.1f}%.",
                "action": "Use the product and category tables to focus growth activity on the most profitable areas.",
            }
        )
    return items


def create_demo_data(seed: int = 42) -> pd.DataFrame:
    """Build deterministic, synthetic sales data for a safe dashboard demonstration."""
    catalog = [
        ("Wireless Mouse", "Electronics", 11.0, 23.0, 5.0),
        ("USB-C Hub", "Electronics", 20.0, 39.0, 3.0),
        ("Desk Lamp", "Home Office", 18.0, 35.0, 2.5),
        ("Notebook Set", "Stationery", 4.0, 12.0, 8.0),
        ("Ergonomic Chair", "Furniture", 115.0, 199.0, 0.7),
        ("Laptop Stand", "Home Office", 16.0, 32.0, 3.5),
        ("Webcam", "Electronics", 26.0, 49.0, 2.0),
        ("Pen Pack", "Stationery", 3.0, 9.0, 7.0),
        ("Monitor Arm", "Furniture", 42.0, 75.0, 1.3),
        ("Cable Organiser", "Accessories", 3.5, 8.0, 6.0),
    ]
    generator = np.random.default_rng(seed)
    records: list[dict[str, object]] = []
    for date in pd.date_range("2025-01-01", periods=180, freq="D"):
        seasonal_factor = 1 + 0.18 * np.sin(date.dayofyear / 18)
        if date.weekday() >= 5:
            seasonal_factor *= 0.8
        if date == pd.Timestamp("2025-03-22"):
            seasonal_factor *= 0.35
        if date == pd.Timestamp("2025-05-16"):
            seasonal_factor *= 2.7
        for product, category, cost, price, typical_quantity in catalog:
            quantity = max(1, int(round(generator.poisson(typical_quantity * seasonal_factor))))
            records.append(
                {
                    "date": date,
                    "product": product,
                    "category": category,
                    "quantity": quantity,
                    "unit_price": round(price * generator.uniform(0.96, 1.04), 2),
                    "unit_cost": cost,
                }
            )
    return pd.DataFrame.from_records(records)
