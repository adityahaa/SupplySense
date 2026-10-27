# Independent Online Retail replication: executed results

Executed 27 October 2026 under the locally frozen protocol. This dataset is independent of M5, but this is a small historical replication, not a prospective business trial. All inventory outcomes are simulated.

## Population and chronology

The source contains 541,909 transaction rows. The declared cleaning removes 5,270 duplicate rows in the six used columns and retains 478,836 UK positive-sales product transactions. Customer fields are not read. Among 2,181 training-eligible products, 90 are selected by a seeded hash. Daily zeros are assumed absent recorded positive sales, not proof of no unconstrained demand. The training zero fraction is 74.76%.

Weights and selection eligibility stop on 26 May 2011. Validation origins: 23 June and 21 July; calibration: 18 August and 15 September; final test: 13 October and 10 November. Each forecast spans the next 28 days. The final intervals end 10 November and 8 December respectively. Features use only information available at each origin. The public forecast explorer shows the last origin; tables below pool both origins (5,040 observations per model).

**Validation selected mean_28 by MAE. It remains the dashboard default even though LightGBM performs best on the inspected test.** No test-based champion switch or parameter search was performed.

## Measured forecasting results

| model | MAE | RMSE | WAPE | bias_units_per_day | coverage | mean_width |
|---|---|---|---|---|---|---|
| croston_sba | 11.018639 | 75.737169 | 1.008296 | -1.553307 | 0.871230 | 22.603352 |
| lightgbm_direct | 9.992816 | 74.894111 | 0.914425 | -2.534363 | 0.860913 | 25.222034 |
| mean_28 | 11.301219 | 76.308135 | 1.034155 | -1.367857 | 0.820040 | 22.076389 |
| seasonal_naive | 11.387500 | 77.494940 | 1.042050 | -1.654960 | 0.900397 | 38.073016 |

WAPE and coverage are ratios. MAE and width are units per product-day. LightGBM's pooled test MAE is 12.2475% below seasonal naive: `(11.3875 - 9.99281620589674) / 11.3875 × 100`. This does not prove universal superiority. LightGBM's 86.09% empirical coverage falls below the nominal 90% target; seasonal naive reaches 90.04% with wider bands. Retain this undercoverage finding. Coverage is not accuracy.

## Conditional uncertainty

| model | MAE_difference_vs_seasonal | conditional_95_low | conditional_95_high | clusters | replicates |
|---|---|---|---|---|---|
| croston_sba | -0.368861 | -1.447301 | 0.893741 | 90 | 2000 |
| lightgbm_direct | -1.394684 | -2.739134 | -0.124793 | 90 | 2000 |
| mean_28 | -0.086281 | -1.322455 | 1.398229 | 90 | 2000 |
| seasonal_naive | 0.000000 | 0.000000 | 0.000000 | 90 | 2000 |

Intervals use 2,000 paired resamples of 90 complete product paths, retaining both origins and all horizons within each product. They quantify variation conditional on these two windows and sampled products. They do not capture cross-product common shocks, dataset selection uncertainty or generalize to other businesses; no significance claim is made. Forecast bands separately use per-product/model calibration residuals from 56 days and do not have a temporal-dependence coverage guarantee.

## Simulated operational results

The study executed 27 policy combinations × four models × two origins = **216 comparisons**. Lead times are 1/3/7 days, shortage penalties 1/5/10 CU, and shared budgets are 0.5/1/2 times 33,277.288136 CU. The reference budget comes from training-only expected 28-day sales × assumed acquisition cost. It is not based on test demand.

Initial stock is 20 units per product, acquisition 2 CU/unit, holding 0.05 CU/unit/day, order fee 1 CU/SKU order, review every 7 days and safety weight 0. Stock/budget reset per origin; one shared budget covers all 90 products. Initial-stock acquisition value is excluded, no terminal salvage is credited, and unmet proxy demand is lost. Fixed-origin forecasts drive the existing order-up-to rule; allocation is largest unit shortfall then ID, not an optimized allocation policy.

At reference budget, lead 3 and shortage penalty 5:

| origin | model | simulated_total_cost | fill_rate |
|---|---|---|---|
| 317 | croston_sba | 94310.200000 | 0.581595 |
| 317 | mean_28 | 94798.250000 | 0.593870 |
| 317 | lightgbm_direct | 97961.400000 | 0.519563 |
| 317 | seasonal_naive | 101362.700000 | 0.525810 |
| 345 | lightgbm_direct | 89036.000000 | 0.627779 |
| 345 | croston_sba | 89960.600000 | 0.633049 |
| 345 | seasonal_naive | 91298.450000 | 0.620199 |
| 345 | mean_28 | 94893.300000 | 0.600996 |

Origin 317 is 13 October; origin 345 is 10 November. At the first origin, SBA has the lowest simulated cost while mean_28 has the highest fill rate among these four. At the second, LightGBM has lowest cost while SBA has highest fill. Thus the best measured error does not select a universally best cost/service policy. These numbers use the research budget; the interactive planner's default 3,000 CU is a different scenario.

Across the 54 origin/scenario cells, lowest-cost counts are LightGBM 32, mean_28 11, SBA 10 and seasonal naive 1. These counts are over a chosen grid, not win probabilities. Keep seasonal naive's winning cell and all negative outcomes in the CSV. Report origin-level results/ranges rather than a confidence interval that incorrectly treats budget-coupled products as independent inventory experiments.

## Intermittency gap and remaining limitations

All 90 selected products have training ADI >1.32; there are no frequent products. Group traces are correctly taken from the same full-population shared-budget simulation, but **no frequent-versus-intermittent comparison is supported**. A future stratified sample needs a new frozen protocol and independent evaluation, not post-test cherry-picking.

The retailer includes wholesale and exceptional transactions; large errors remain (RMSE around 75). Positive-sales filtering excludes returns; availability, genuine lost demand and real costs are unknown. The short horizon and initial stock influence rankings. The previously inspected M5 results remain exploratory and separate. These UCI tests are also now inspected. No real savings, causal impact, significance or novelty is established.

Reproduction: install requirements-dev.txt plus openpyxl, download the attributed UCI ZIP, and run `python scripts/run_independent_retail.py --data PATH_TO_UCI_ZIP` in a fresh copy without results/independent. The script intentionally refuses to overwrite existing checkpoints. Raw data and customer records are not published. Machine-readable results and protocol hashes accompany the public demo; complete all-origin predictions and the model checkpoint remain in the local project.
