"""Streamlit entry point for Smart Business Analytics."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from smart_business_analytics.analytics import (
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


st.set_page_config(page_title="Smart Business Analytics", page_icon="📊", layout="wide")


def money(value: float) -> str:
    return f"${value:,.0f}"


def percent_change(current: float, previous: float) -> str | None:
    if previous == 0:
        return None
    return f"{(current / previous - 1) * 100:+.1f}% vs previous period"


@st.cache_data
def demo_data() -> pd.DataFrame:
    return create_demo_data()


st.title("Smart Business Analytics")
st.caption("A transparent sales and profitability dashboard for small businesses. All recommendations are based on the metrics shown below.")

with st.sidebar:
    st.header("Data source")
    source_choice = st.radio("Choose data", ["Demo data", "Upload file"], label_visibility="collapsed")
    uploaded_file = None
    if source_choice == "Upload file":
        uploaded_file = st.file_uploader("CSV or Excel sales export", type=["csv", "xlsx", "xls"])
        with st.expander("Expected file columns"):
            st.code("date, product, category, quantity, unit_price, unit_cost", language="text")
            st.caption("Category is optional. Common alternatives such as `sale_date`, `qty`, `price`, and `cost` are recognised.")

try:
    if source_choice == "Demo data":
        raw_data = demo_data()
        data_label = "Synthetic demo data"
    elif uploaded_file is None:
        st.info("Upload a CSV or Excel sales export to begin, or switch to demo data.")
        st.stop()
    else:
        raw_data = load_sales_file(BytesIO(uploaded_file.getvalue()), uploaded_file.name)
        data_label = uploaded_file.name
    sales = calculate_line_metrics(normalise_sales_data(raw_data))
except (DataValidationError, UnicodeDecodeError, ValueError) as error:
    st.error(f"Could not analyse this file: {error}")
    st.stop()

min_date = sales["date"].min().date()
max_date = sales["date"].max().date()
with st.sidebar:
    st.header("Filters")
    selected_dates = st.date_input("Period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    selected_categories = st.multiselect("Categories", sorted(sales["category"].unique()), default=sorted(sales["category"].unique()))

if not isinstance(selected_dates, tuple) or len(selected_dates) != 2:
    st.warning("Choose both a start and an end date.")
    st.stop()

filtered = filter_by_period(sales, selected_dates[0], selected_dates[1], selected_categories)
if filtered.empty:
    st.warning("No sales match these filters. Try another period or category.")
    st.stop()

metrics = summary_metrics(filtered)
period_days = (pd.Timestamp(selected_dates[1]) - pd.Timestamp(selected_dates[0])).days + 1
previous_start = pd.Timestamp(selected_dates[0]) - pd.Timedelta(days=period_days)
previous_end = pd.Timestamp(selected_dates[0]) - pd.Timedelta(days=1)
previous = filter_by_period(sales, previous_start, previous_end, selected_categories)
previous_metrics = summary_metrics(previous) if not previous.empty else None

st.caption(f"Source: {data_label} · {len(filtered):,} sales records in the selected period")
first, second, third, fourth = st.columns(4)
first.metric("Revenue", money(metrics["revenue"]), percent_change(metrics["revenue"], previous_metrics["revenue"]) if previous_metrics else None)
second.metric("Gross profit", money(metrics["gross_profit"]), percent_change(metrics["gross_profit"], previous_metrics["gross_profit"]) if previous_metrics else None)
third.metric("Gross margin", f"{metrics['gross_margin_pct']:.1f}%")
fourth.metric("Units sold", f"{metrics['units_sold']:,.0f}")

st.subheader("Sales over time")
monthly = monthly_performance(filtered).set_index("month")
st.line_chart(monthly[["revenue", "gross_profit"]], use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("Most profitable products")
    products = product_performance(filtered)
    st.bar_chart(products.head(10).set_index("product")[["gross_profit"]], use_container_width=True)
    st.dataframe(
        products[["product", "revenue", "gross_profit", "gross_margin_pct", "units_sold"]],
        column_config={
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
            "gross_profit": st.column_config.NumberColumn("Gross profit", format="$%.0f"),
            "gross_margin_pct": st.column_config.NumberColumn("Margin", format="%.1f%%"),
            "units_sold": st.column_config.NumberColumn("Units", format="%.0f"),
        },
        hide_index=True,
        use_container_width=True,
    )
with right:
    st.subheader("Category performance")
    categories = category_performance(filtered)
    st.bar_chart(categories.set_index("category")[["revenue"]], use_container_width=True)
    st.dataframe(
        categories[["category", "revenue", "gross_profit", "gross_margin_pct", "units_sold"]],
        column_config={
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
            "gross_profit": st.column_config.NumberColumn("Gross profit", format="$%.0f"),
            "gross_margin_pct": st.column_config.NumberColumn("Margin", format="%.1f%%"),
            "units_sold": st.column_config.NumberColumn("Units", format="%.0f"),
        },
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Unusual revenue days")
anomalies = detect_daily_revenue_anomalies(filtered)
if anomalies.empty:
    st.info("No unusual daily revenue pattern was found. At least seven distinct sales days are needed for this check.")
else:
    st.caption("A day is flagged when revenue is at least two standard deviations from the average daily revenue in the selected period.")
    st.dataframe(
        anomalies,
        column_config={
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
            "z_score": st.column_config.NumberColumn("Distance from average", format="%.2f SD"),
        },
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Recommended next actions")
for recommendation in recommendations_for(filtered, anomalies):
    with st.expander(f"{recommendation['priority']} priority — {recommendation['title']}", expanded=True):
        st.write(recommendation["evidence"])
        st.write(f"**Suggested action:** {recommendation['action']}")

with st.expander("Inspect calculated sales data"):
    st.dataframe(filtered, hide_index=True, use_container_width=True)
