# Smart Business Analytics

A small, transparent Streamlit dashboard for analysing sales exports. Upload a CSV or Excel file to track revenue, gross profit, margin, product and category performance, unusual sales days, and practical recommendations.

This is a portfolio project designed for small-business sales data. It is not an accounting system, investment adviser, or autonomous AI agent.

## Features

- Import CSV, XLS, and XLSX sales exports.
- Validate the data before calculations.
- Calculate revenue, cost of goods, gross profit, and gross margin.
- Filter by date range and product category; compare core metrics with the preceding period.
- Show monthly performance and product/category profitability.
- Flag unusually high or low daily revenue using a documented statistical rule.
- Provide recommendations linked to the displayed calculations.
- Run safely with deterministic synthetic demo data — no customer data is included.

## Quick start

```bash
git clone https://github.com/ptripaka-max/smart-business-analytics.git
cd smart-business-analytics
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install dependencies and start the dashboard:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Select **Demo data** to explore it immediately.

## Input schema

The app needs one row per sales line. The required fields are:

| Column | Description | Example |
| --- | --- | --- |
| `date` | Date of the sale | `2025-01-31` |
| `product` | Product or service name | `Wireless Mouse` |
| `quantity` | Units sold; must be greater than zero | `2` |
| `unit_price` | Selling price per unit | `29.99` |
| `unit_cost` | Direct cost per unit | `12.50` |

`category` is optional and defaults to `Uncategorized`.

For convenience, common aliases are recognised: `sale_date`, `order_date`, `item`, `qty`, `units_sold`, `price`, `selling_price`, `cost`, and `cost_price`.

### Example CSV

```csv
date,product,category,quantity,unit_price,unit_cost
2025-01-31,Wireless Mouse,Electronics,2,23.00,11.00
2025-01-31,Notebook Set,Stationery,5,12.00,4.00
```

## How the analysis works

For every sales row:

- **Revenue** = `quantity × unit_price`
- **Cost of goods** = `quantity × unit_cost`
- **Gross profit** = `revenue − cost of goods`
- **Gross margin** = `gross profit ÷ revenue × 100`

Anomaly detection groups revenue by day and flags a day when it is at least **two standard deviations** above or below the selected period's average daily revenue. It is a signal to investigate, not proof of a problem.

Recommendations are rules based on the same data visible in the dashboard: loss-making products, low overall margin, and unusually low sales days. They are intentionally explainable and do not make financial decisions.

## Tests

```bash
pytest -q
```

The test suite covers column mapping, validation, financial formulas, date filtering, anomaly detection, recommendations, and reproducible demo data. GitHub Actions runs it on every push and pull request.

## Project structure

```text
.
├── app.py                         # Streamlit interface
├── smart_business_analytics/
│   └── analytics.py               # Validation and analysis functions
├── tests/
│   └── test_analytics.py
└── .github/workflows/tests.yml    # Continuous integration
```

## Privacy and limitations

- Do not commit real customer exports, credentials, or Streamlit secrets.
- Gross profit uses the direct `unit_cost` supplied in the upload. It does not include rent, salaries, tax, refunds, marketing, or other overhead.
- Validate the inputs and use professional accounting advice before taking material business decisions.

## License

Released under the [MIT License](LICENSE).
