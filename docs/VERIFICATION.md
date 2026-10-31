# Verification record

Review date: 1 November 2026 (Asia/Kolkata).

- Passed: `python -m pytest tests/test_core.py tests/test_research.py -q`: 11 tests in 6.03 seconds. Python 3.11.9, pytest 8.3.5, NumPy 2.2.6, pandas 2.2.3, LightGBM 4.6.0.
- Passed: `load_bundle(Path('results/public_results.zip').read_bytes())`, including member/checksum validation and schema checks. Four methods and 90 series load successfully. The stored metrics table matches the documented pooled test metrics (5,040 rows/method).
- Important distinction: compact test_predictions.csv contains only the final origin (2,520 rows/method). Recomputed final-origin MAE is 10.6494680802 (SBA), 9.4081494461 (LightGBM), 10.9763321995 (mean_28), and 10.9587301587 (seasonal naive). These must not be confused with the two-origin pooled values. This review did not regenerate the excluded full all-origin checkpoints or retrain models.
- Public URL returned HTTP 200 with cookies enabled and a Streamlit application shell. A cookie-free request entered a redirect loop. Current interactive page behavior was not rechecked; historical browser evidence remains in PUBLIC_VERIFICATION.md.
- Not rerun: raw-UCI training, the 216 full all-origin inventory comparisons, or browser checks. Existing measured research is explicitly attributed to the saved experiment rather than described as newly executed.

Reproduce the core checks with the root README commands. Obtain UCI data separately to rerun the full experiment; raw customer records are not included.
