"""Core calculations for the Smart Business Analytics dashboard."""

from .analytics import (
    DataValidationError,
    calculate_line_metrics,
    category_performance,
    create_demo_data,
    detect_daily_revenue_anomalies,
    filter_by_period,
    load_sales_file,
    monthly_performance,
    normalise_sales_data,
    product_performance,
    recommendations_for,
    summary_metrics,
)

__all__ = [
    "DataValidationError",
    "calculate_line_metrics",
    "category_performance",
    "create_demo_data",
    "detect_daily_revenue_anomalies",
    "filter_by_period",
    "load_sales_file",
    "monthly_performance",
    "normalise_sales_data",
    "product_performance",
    "recommendations_for",
    "summary_metrics",
]
