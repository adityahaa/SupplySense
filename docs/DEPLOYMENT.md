# Zero-cost deployment

Target repository: https://github.com/adityahaa/SupplySense

Use Streamlit Community Cloud at https://share.streamlit.io/ with the repository above, branch `main`, main file `app.py`, and Python **3.12** in advanced settings. Keep app visibility public so visitors do not need GitHub authentication. No secrets or API keys are required. Do not enable billing, add a payment method, use Render or purchase a fallback.

Streamlit's [official Community Cloud documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud) describes the service as free. Its [resource documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) states that inactive apps sleep after 12 hours and viewers can wake them. Resource allocations may change; cold starts and throttling are possible. No uptime or latency guarantee is made.

Deploy only the reviewed public source export, not the entire local release. The original M5 files stay local pending redistribution verification. The public app automatically selects its saved UCI bundle and does not require training, customer data, a paid API or file uploads.

Deployment verified 28 October 2026: **https://supplysense-adityahaa.streamlit.app/**. All seven pages rendered on the live site, changed budget and demand-scenario controls recalculated, and desktop/mobile-sized checks were performed. A fresh unauthenticated HTTP session received the app and healthy server response. See `PUBLIC_VERIFICATION.md` for exact coverage and remaining limits. Visitors open the public URL directly; no installation or GitHub sign-in is needed. The Streamlit toolbar's Deploy button is hidden to avoid suggesting that visitors need to deploy their own copy.

Maintenance: review changes in the public export, commit and push normally to `main`; Community Cloud automatically updates the app. Never upload the complete local release. `.gitattributes` preserves artifact bytes across platforms. Keep original M5 bundles and full independent checkpoints in the local project. No secrets are required by this app.
