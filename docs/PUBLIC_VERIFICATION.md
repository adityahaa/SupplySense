# Public release verification

27 October 2026. The changed artifact loader, UI, independent feature construction and fixed experiment outputs were checked locally. **27 tests passed** in 21.96 seconds, including all seven pages with the independent bundle, all original tests, no-future-data feature regression, baseline arithmetic, output hashes, matching observations and zero-budget controls. The validation-selected 28-day mean is retained despite the different test winner.

The original M5 bundles and saved research output files are preserved. The public export uses an explicit allowlist and scans source and ZIP members for local machine paths, known token/private-key patterns and local identity strings. It excludes raw datasets, invoice/customer-level data, local handoff, logs and XML host metadata. The public model bundle contains selected daily UCI aggregates with CC BY 4.0 attribution. Full original M5 bundles are not uploaded.

## Live deployment verified 28 October 2026

Public app: https://supplysense-adityahaa.streamlit.app/  
Reviewed repository: https://github.com/adityahaa/SupplySense  
Host: Streamlit Community Cloud, branch `main`, entry point `app.py`, Python 3.12. No billing, card or paid service was activated.

All seven pages were opened on the live site: Overview, Forecast explorer, Inventory planner, Scenario simulator, Model comparison, Business impact, and Research & methodology. Historical dates, observed/forecast chart, model rankings, simulation labels and executed research tables loaded without application exceptions. Desktop viewport was measured at 1440 × 900; a separate mobile-sized browser viewport was measured at 390 × 844. Overview, navigation and Research were visually inspected at mobile size. This is browser emulation, not a physical-phone or exhaustive cross-browser test.

Executed public control checks with the last-origin mean_28 forecast, 90 products and default assumptions:

- Setting shared budget from 3,000 CU to zero changed simulated fill from 10.4% to 4.9%, procurement to 0.00 CU and remaining budget to 0.00 CU; total simulated cost became 132,595.25 CU.
- Increased-demand preset changed the demand multiplier from 1 to 1.25, simulated fill to 8.3% and simulated cost to 162,914.98 CU (+34,441.78 CU versus default). These are simulated stress results, not additional forecast measurements.
- Research displayed both-origin metrics, 216 policy comparisons, interval undercoverage and the absent frequent-demand group. A wide-table mobile overflow defect was found and fixed: the deployed table now has a 319-pixel viewport with `overflow-x:auto` for 767 pixels of content. Wide tables intentionally scroll horizontally.

Anonymous access was checked with a fresh HTTP cookie jar containing no account credentials: public page, inner Streamlit app and health endpoint returned 200; health returned `ok`. The browser checks used the account owner's existing browser session, so this HTTP check is the separate anonymous-access evidence. A first HTTP attempt without cookie handling entered the host's session redirects; allowing fresh anonymous session cookies resolved it.

The public-only exported directory independently passed seven-page AppTest and a zero-budget interaction. Its first run had a sandbox temporary-directory cleanup warning after assertions passed. After the CSS fix, the existing independent-bundle/all-pages test was rerun with workspace TEMP/TMP and passed (1 test, `public_css_smoke.xml` locally). This is a focused rerun of an existing test, not a 28th unique test; the full-suite count remains 27. No experiments were repeated for these UI checks.

Screenshots are retained locally in `docs/screenshots/public_*.png`; selected reviewed screenshots accompany the public README. The public exporter checks an allowlist and ZIP CRC/member hashes. `.gitattributes` disables line-ending conversion so Git preserves the research files' exact bytes. Raw data, original M5 bundles, credentials, machine paths, private logs and environments are excluded.

Still unverified: fresh-machine Explorer setup, Python 3.11 execution, real mobile hardware/touch, every browser and control combination, public download round-trips, long-duration uptime, concurrent-user capacity and wake-up latency after actual hibernation. Python 3.12 and Windows scripts were tested locally in the earlier release. Shared free hosting can sleep and has no uptime guarantee.

The research protocol was frozen locally before execution, not externally preregistered. All final periods are now inspected. Software tests, forecasting metrics and simulated inventory outcomes are separate kinds of evidence. No real financial gains, causal impact, significance, research novelty or publication acceptance is established.
