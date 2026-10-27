# Research extension and literature positioning

Reviewed 27 October 2026. Focused primary-source review, not a systematic review.

Question: **When does better forecast accuracy lead to better inventory decisions across demand intermittency, budgets, lead times and shortage-cost conditions?**

The broad question substantially overlaps existing research. Theodorou, Spiliotis and Assimakopoulos (2025), *Forecast accuracy and inventory performance: Insights on their relationship from the M5 competition data*, EJOR 322(2), 414–426, [DOI](https://doi.org/10.1016/j.ejor.2024.12.033), directly studies this relationship. Its publisher page was access-blocked during this session; we do not claim to have re-read the full journal article. The authors' [2023 ISF presentation](https://www.researchgate.net/publication/372101000_Forecasting_accuracy_and_inventory_performance_Evidence_on_their_relationship_from_the_M5_competition_data), DOI 10.13140/RG.2.2.14988.28808, was accessible as author-uploaded primary material. It describes rolling M5 simulations, multiple forecasting methods and order-up-to settings, and shows that inventory component rankings can differ from forecast-error rankings. It also discusses demand characteristics. This directly prevents a novelty claim based on merely adding these comparisons to M5.

Syntetos, Boylan and Croston (2005), *On the categorization of demand patterns*, JORS 56, 495–503, DOI 10.1057/palgrave.jors.2601841, links demand patterns and forecasting-method performance. Kostenko and Hyndman's [author-hosted note](https://robjhyndman.com/papers/idcat.pdf) revisits those boundaries. SupplySense uses the historical ADI threshold 1.32 only as a declared descriptive grouping, not a claim of optimal classification or causal effect.

Zaffran et al. (2022), [Adaptive Conformal Predictions for Time Series](https://proceedings.mlr.press/v162/zaffran22a.html), PMLR 162, 25834–25866, explains why temporal dependence matters for conformal uncertainty. SupplySense does not implement their adaptive procedure. Its calibrated bands are empirically evaluated, without an exchangeability guarantee.

The defensible contribution here is a **transparent engineering replication on a separately sourced, explicitly licensed retailer dataset**, with a finite shared purchasing budget, a fixed allocation rule, preserved negative findings and inspectable decision outputs. This is useful portfolio/reproducibility work. It is not established as a novel algorithm, novel research question or publication-ready contribution. A wider literature review would be necessary before claiming that the budget interaction is new.

## Protocol and evidence status

`INDEPENDENT_PROTOCOL.json` was saved before downloading or evaluating UCI data. Its SHA256 and execution start were captured in `results/independent/freeze.json`; parameters and selection were fixed before test scoring. This is a local protocol freeze, not external preregistration. Two validation, two calibration and two nonoverlapping final origins use chronological boundaries. Only one small pooled LightGBM model was trained; original M5 weights and results were not retrained or modified.

The resulting UCI sample contains **90 intermittent and zero frequent products** under the frozen grouping. Do not change selection after inspecting tests merely to obtain the desired contrast. The current evidence cannot answer the between-group part of the question. Both UCI test windows have now been inspected; like the earlier M5 windows, they cannot be reused as untouched tests for further tuning.

See `INDEPENDENT_RESULTS.md` for executed findings. Pending: a new, prospectively specified stratified replication on genuinely independent data, broader literature coverage, more temporal origins, and uncertainty that addresses common demand shocks and budget coupling. No causal business effect, real savings, statistical significance or publication acceptance is claimed.
