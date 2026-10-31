# SupplySense technical report

## Problem and architecture

SupplySense studies how forecast errors relate to inventory choices under stated simulated costs and constraints. Streamlit presents saved historical results; it does not train on refresh or place orders. app.py handles navigation, supplysense/artifacts.py validates bounded artifacts, forecast.py computes forecast metrics, inventory.py simulates ordering, and research.py compares matched methods and scenarios.

## Data and experiment

The public case study uses an attributed UCI Online Retail subset, distinct from the excluded original M5 material. Cleaning retains 478,836 positive UK product transactions after declared filtering. Training-only seeded selection chooses 90 products from 2,181 eligible products. All 90 are intermittent under the frozen definition. See [data notice](PUBLIC_DATA_NOTICE.md), [protocol](INDEPENDENT_PROTOCOL.json), and [executed results](INDEPENDENT_RESULTS.md).

Four methods (seasonal naive, 28-day mean, Croston SBA, direct LightGBM) use validation/calibration windows preceding two nonoverlapping 28-day final origins. Pooled evaluation has 5,040 observations per model. Validation selected mean_28; test inspection does not change the default. The public bundle contains compact saved results, not every training checkpoint.

## Results and comparisons

Recorded test MAE is 11.387500 for seasonal naive, 11.301219 for mean_28, 11.018639 for SBA, and 9.992816 for LightGBM. The recorded LightGBM MAE reduction versus seasonal naive is 12.2475%. Its 86.09% interval coverage is below nominal 90%; seasonal naive reaches 90.04% with wider bands. These are existing executed artifact results, not a newly rerun training experiment.

The 216 recorded inventory comparisons cross four methods, two origins, three budgets, three lead times, and three shortage penalties. Rankings depend on scenario: SBA has lowest reference-cell cost at the first origin and LightGBM at the second. No universal operational winner or real savings is established. MAE/RMSE/WAPE, signed bias, interval coverage/width, simulated cost, and fill rate measure distinct properties.

## Limitations and reproduction

One retailer, 90 selected intermittent products, two inspected final windows, positive-sales demand proxies, assumed costs, and budget-coupled decisions limit generalization. Cluster intervals do not capture common product shocks. Forecast intervals have no temporal-dependence coverage guarantee. No novelty, causal effect, or publication claim is made.

Use the root README to run the saved-artifact app and core/research tests. Full experiment reproduction requires obtaining the attributed UCI ZIP and running scripts/run_independent_retail.py --data PATH_TO_UCI_ZIP in a fresh copy; existing checkpoints are not overwritten. See [original public verification](PUBLIC_VERIFICATION.md) and [verification record](VERIFICATION.md) for the current review's checks.
