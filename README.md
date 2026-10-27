# SupplySense

**From Forecasts to Better Inventory Decisions**

A seven-page Streamlit portfolio application connecting historical sales forecasts to transparent, simulated inventory decisions. Intended for retail analysts and Engineering Management reviewers. It never places real orders.

## Public demo

Hosting: Streamlit Community Cloud. Deployment URL will be recorded after successful verification; no live deployment is claimed by this placeholder.

The public demo uses an independently evaluated, attributed **UCI Online Retail** subset. It is separate from the original local M5 experiment. Public artifacts contain 90 selected product series and saved predictions; visitors need no dataset upload, Python installation or GitHub sign-in once the public app is deployed. No model trains when a page refreshes.

Free Community Cloud apps can sleep after 12 hours without traffic. Anyone with access can use the wake-up button; cold starts can take time. Shared resources can throttle and no always-on performance is promised. No paid API, payment method or billing activation is required by this project. See [official hosting limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).

## Walkthrough

1. **Overview:** check the dataset and historical evaluation dates.
2. **Forecast explorer:** choose a product/model; inspect actuals, prediction bands and signed errors; download CSV.
3. **Model comparison:** compare measured MAE, RMSE, WAPE, bias and coverage. Coverage is not accuracy.
4. **Inventory planner:** change stock, cash, delays and costs to recalculate simulated orders, cost and fill rate.
5. **Scenario simulator:** stress demand or budget under explicit assumptions.
6. **Business impact:** compare forecast-error and simulated cost/service rankings under the same conditions.
7. **Research & methodology:** read the frozen protocol, all-origin findings, uncertainty and limitations.

On narrow screens, use the upper-left arrow to open navigation. Store means one UK online retailer; category means the training-defined demand-frequency group. All 90 selected products are intermittent under the frozen definition; no frequent-demand comparison is supported.

## Verified research, with negative findings

Two nonoverlapping 28-day test origins yield 5,040 observations per method. Test MAE: LightGBM 9.992816, SBA 11.018639, 28-day mean 11.301219, seasonal naive 11.387500. LightGBM reduces MAE by 12.25% versus seasonal naive. **Validation selected the 28-day mean**, which remains the display default; the inspected test does not reselect it.

LightGBM interval coverage is 86.09%, below the nominal 90%; seasonal naive is 90.04% with wider bands. In 216 simulated comparisons, cost/service rankings vary across budgets, lead times, penalties and origins. Under the reference-budget/3-day-lead/5-CU-penalty cell, SBA has lowest cost at the first origin and LightGBM at the second. No universal winner or actual financial savings is claimed.

See [executed results](docs/INDEPENDENT_RESULTS.md), [literature positioning](docs/RESEARCH_EXTENSION.md), [protocol](docs/INDEPENDENT_PROTOCOL.json) and [data attribution](docs/PUBLIC_DATA_NOTICE.md). The research question has substantial prior overlap. This is a reproducible case study, not a novelty or publication-readiness claim. Both final windows are now inspected.

## Run on Windows

Download the repository ZIP and **Extract All**. Install 64-bit Python 3.12, enabling **Add Python to PATH**. In the extracted folder, double-click `setup_windows.bat` once; it creates `.venv`, installs requirements and starts the app. Later, double-click `start_windows.bat`. Open http://localhost:8501 and keep the terminal open. Press Ctrl+C to stop. No PowerShell activation or execution-policy change is needed.

Manual fallback from Command Prompt in that folder:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\launch.py
```

## Architecture and reproduction

`app.py` handles navigation; `supplysense/ui.py` presentation; `pages.py` decision/research views; `artifacts.py` bounded checksum-validated loading; `forecast.py` scoring; `inventory.py` simulation; `research.py` matched comparisons. Application dependencies are NumPy, Pandas, Plotly and Streamlit. Optional training dependencies are separate.

The original M5 bundles remain unchanged locally and are excluded here pending redistribution verification; do not publish the complete local ZIP. This public release uses `results/public_results.zip` with selected aggregated CC BY 4.0 data. Raw invoices and customer identifiers are excluded. [Attribution and changes](docs/PUBLIC_DATA_NOTICE.md).

For replication install `requirements-dev.txt` and `openpyxl`, obtain the UCI download linked in the protocol, and run `python scripts/run_independent_retail.py --data PATH_TO_UCI_ZIP` in a fresh copy without `results/independent/`. Existing experiment directories are never overwritten. This fits ordinary local CPU compute; Colab is optional. Local complete checkpoints are retained separately from the compact public reports.

Run public core tests with `python -m pytest tests/test_core.py tests/test_research.py -q` after installing development dependencies. Full local verification and public-site smoke checks are documented in `docs/PUBLIC_VERIFICATION.md`.

Limits: one retailer, only intermittent products in the fixed sample, two final origins, censored positive-sales proxy, assumed costs, finite-horizon policies and daily residual bands without a dependence-aware coverage guarantee. Product-cluster bootstrap intervals do not capture cross-product shocks. Shared-budget simulations do not have independent-product confidence intervals. No causal effect, real savings or current-demand forecasts are claimed.
