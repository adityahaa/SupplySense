# Zero-cost deployment

Target repository: https://github.com/adityahaa/SupplySense

Use Streamlit Community Cloud at https://share.streamlit.io/ with the repository above, branch `main`, main file `app.py`, and Python **3.12** in advanced settings. Keep app visibility public so visitors do not need GitHub authentication. No secrets or API keys are required. Do not enable billing, add a payment method, use Render or purchase a fallback.

Streamlit's [official Community Cloud documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud) describes the service as free. Its [resource documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) states that inactive apps sleep after 12 hours and viewers can wake them. Resource allocations may change; cold starts and throttling are possible. No uptime or latency guarantee is made.

Deploy only the reviewed public source export, not the entire local release. The original M5 files stay local pending redistribution verification. The public app automatically selects its saved UCI bundle and does not require training, customer data, a paid API or file uploads.

Deployment status: pending live verification. A repository URL alone does not prove an app is deployed. After deployment, record the actual public URL and confirm anonymous loading, all seven pages, a changed budget, a scenario control, and desktop/mobile-sized rendering. If sign-in, terms or account authorization is needed, the account owner must complete it; do not create alternate paid infrastructure.
