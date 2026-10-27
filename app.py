from dataclasses import asdict, replace
from pathlib import Path
import json
import os
import zipfile
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from supplysense.artifacts import load_bundle
from supplysense.forecast import point_metrics, interval_metrics
from supplysense.inventory import Assumptions, simulate

st.set_page_config(page_title='SupplySense | Forecast to decision', page_icon='◈', layout='wide')
from supplysense.ui import setup_style, chart, csv_download, assumption_controls, simulation_summary, assumptions_caption, cost_summary, policy_explanation, fmt
from supplysense.pages import scenario_page, decision_page, methodology_page, simulation, comparison
setup_style()
st.sidebar.markdown('## ◈ SupplySense')
st.sidebar.caption('From Forecasts to Better Inventory Decisions')
page = st.sidebar.radio('Workspace', ['Overview', 'Forecast explorer', 'Inventory planner',
                                     'Scenario simulator', 'Model comparison', 'Business impact', 'Research & methodology'])
uploaded = st.sidebar.file_uploader('Import another results ZIP (optional)', type=['zip'])
result_dir = Path(__file__).parent / 'results'
available = {label:name for label,name in [('Improved experiment','improved_results.zip'),
             ('Original pilot','trained_results.zip'),('Independent UCI replication','public_results.zip')]
             if (result_dir/name).is_file()}
result_choice = st.sidebar.radio('Saved experiment', list(available) or ['Improved experiment'])
default_bundle = result_dir / available.get(result_choice, 'improved_results.zip')
if not default_bundle.is_file():
    st.sidebar.warning('Selected bundle is missing. Trying the original pilot; the actual loaded dates appear below.')
    default_bundle = Path(__file__).parent / 'results' / 'trained_results.zip'
payload = uploaded.getvalue() if uploaded is not None else (
    default_bundle.read_bytes() if default_bundle.is_file() and
    os.environ.get('SUPPLYSENSE_NO_BUNDLED_RESULTS') != '1' else None)

st.sidebar.caption('Historical evaluation · Simulated inventory · No real orders')

@st.cache_data(show_spinner=False, max_entries=4)
def read_results(payload):
    return load_bundle(payload)

st.markdown('<div class="ss-kicker">SupplySense · From Forecasts to Better Inventory Decisions</div>', unsafe_allow_html=True)
st.title(page)
if payload is None:
    st.markdown('<p class="intro">Turn retail sales forecasts into transparent inventory decisions.</p>', unsafe_allow_html=True)
    st.markdown('<div class="welcome"><h2>Saved results are missing</h2>'
                '<p>Restore the results folder from the supplied project ZIP, or import a valid results ZIP in the sidebar. '
                'The delivered application includes trained results and requires no new training.</p></div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    c1.metric('Planned series', '90'); c2.metric('Forecast horizon', '28 days'); c3.metric('Experiment status', 'Not run')
    st.info('No model results have been imported. Forecast accuracy and business outcomes are not yet available.')
    st.markdown('Expected file: `results/improved_results.zip` (preferred) or `results/trained_results.zip`. '
                'Optional reproduction notebooks are in `notebooks/`.')
    audit_path = Path(__file__).parent / 'docs' / 'dataset_audit.json'
    if audit_path.exists():
        with st.expander('Verified source-file inspection'):
            audit = json.loads(audit_path.read_text())
            st.write(f"{audit['sales']['rows']:,} source series, {audit['sales']['days']:,} sales days; "
                     f"{audit['sales']['zero_fraction']:.1%} zero sales entries.")
            st.caption('Source audit only. This does not establish forecast performance.')
    st.stop()

try:
    bundle = read_results(payload)
except (ValueError, KeyError, OSError, TypeError, zipfile.BadZipFile) as exc:
    st.error(f'Cannot load results: {exc}'); st.stop()
st.sidebar.success('Saved results validated and loaded')
settings = bundle['settings']; all_predictions = bundle['test_predictions']
st.caption('Dataset: ' + settings.get('dataset', 'M5 retail sales') +
           ' · Explore forecast errors, then compare inventory decisions under assumptions.')
if settings.get('schema_version') == 3:
    st.info('Public research demo · UCI Online Retail (CC BY 4.0). This is a separate replication, not the original M5 experiment. '
            'Store = one UK online retailer; category = a group defined by training-period sales frequency.')
    st.caption('Free hosting can sleep after inactivity. If a sleeping page appears, use its wake-up button; startup may take time.')
test_start = all_predictions.date.min().strftime('%d %b %Y')
test_end = all_predictions.date.max().strftime('%d %b %Y')
st.caption(f"Run {settings['run_id']} · historical holdout: {test_start}–{test_end} · intervals shown only where saved")
stores = st.sidebar.multiselect('Stores', sorted(all_predictions.store_id.unique()), default=sorted(all_predictions.store_id.unique()))
categories = st.sidebar.multiselect('Categories', sorted(all_predictions.cat_id.unique()), default=sorted(all_predictions.cat_id.unique()))
scope = all_predictions[all_predictions.store_id.isin(stores) & all_predictions.cat_id.isin(categories)]
if scope.empty:
    st.info('Select at least one store and category.'); st.stop()
models = list(scope.model.unique())
champion = settings['validation_champion']
model = st.sidebar.selectbox('Forecast model', models, index=models.index(champion))
p = scope[scope.model.eq(model)].copy()
st.sidebar.caption(f"Validation MAE champion: {champion}. Filters do not reselect the model.")

context={'run_id':settings['run_id'],'bundle_sha256':bundle['bundle_sha256'],'stores':stores,'categories':categories,'model':model,'start':test_start,'end':test_end}
root=Path(__file__).parent

if page == 'Overview':
    st.markdown('<p class="intro">A measured view of forecast performance before inventory decisions.</p>', unsafe_allow_html=True)
    m = point_metrics(p); intervals = interval_metrics(p)
    a,b,c,d = st.columns(4)
    a.metric('Product-store series', p.id.nunique()); b.metric('Holdout MAE (units/day)', f"{m['MAE']:.3f}")
    c.metric('Daily interval coverage', fmt(intervals['coverage'],1,True)); d.metric('Recorded holdout sales', f'{p.sales.sum():,.0f}')
    aggregate = p.groupby('date')[['sales','prediction']].sum().reset_index()
    chart(px.line(aggregate, x='date', y=['sales','prediction'], markers=True,
                  labels={'value':'Units / day','date':'Date','variable':'Series'}, title='Recorded sales and forecast · selected population'))
    st.caption('Aggregate point forecasts only. Summed daily bounds are not a valid aggregate prediction interval.')
    st.metric('Measured bias (units / series / day)',fmt(m['bias_units_per_day'],3))
    st.subheader('Inventory decision snapshot')
    assumptions_caption(Assumptions())
    _,overview_totals=simulation(p,Assumptions())
    simulation_summary(overview_totals)
    st.caption('Explore configurable assumptions in Inventory planner and compare all methods in Business impact. The lowest forecast error need not yield the lowest simulated cost under a particular policy.')
    left,right = st.columns([1.1,1])
    with left:
        totals = p.groupby('cat_id')[['sales','prediction']].sum().reset_index()
        chart(px.bar(totals,x='cat_id',y=['sales','prediction'],barmode='group',
                     title='Holdout sales by category',labels={'value':'Units','cat_id':'Category'}))
    with right:
        st.subheader('What this run can establish')
        st.write('This view compares one historical 28-day evaluation for 90 series. '
                 'The champion was chosen using validation MAE before final testing.')
        st.warning('Recorded sales are a demand proxy. Actual stock availability, procurement costs and true lost demand are unavailable.')
        st.caption('No official hierarchical WRMSSE score or generalization to current retail demand is claimed.')

elif page == 'Forecast explorer':
    series = st.selectbox('Product-store combination', sorted(p.id.unique()))
    single = p[p.id.eq(series)].sort_values('date')
    history = bundle['history']; history = history[history.id.eq(series)].tail(84)
    fig = go.Figure()
    has_bands=single[['lower','upper']].notna().all().all()
    if has_bands:
        fig.add_trace(go.Scatter(x=single.date,y=single.upper,line=dict(width=0),name='Upper 90% bound'))
        fig.add_trace(go.Scatter(x=single.date,y=single.lower,fill='tonexty',fillcolor='rgba(17,139,135,.18)',line=dict(width=0),name='Lower 90% bound'))
    fig.add_trace(go.Scatter(x=history.date,y=history.sales,name='Observed history',line=dict(color='#9ba9b8')))
    fig.add_trace(go.Scatter(x=single.date,y=single.sales,name='Holdout actual',line=dict(color='#eb9f45',dash='dot')))
    fig.add_trace(go.Scatter(x=single.date,y=single.prediction,name='Forecast',line=dict(color='#118b87')))
    fig.update_layout(title=series,yaxis_title='Units / day',xaxis_title='Date'); chart(fig)
    st.caption('Nominal 90% marginal daily bands from separate calibration blocks. Coverage is empirical; these are not simultaneous path guarantees.' if has_bands else 'Prediction intervals are unavailable for this model; point forecasts are shown.')
    st.dataframe(single[['date','sales','prediction','lower','upper']],use_container_width=True,hide_index=True)
    errors=single.assign(error=single.prediction-single.sales)
    chart(px.bar(errors,x='date',y='error',title='Signed forecast error · forecast minus recorded sales',labels={'error':'Units'}))
    csv_download(errors,'Download selected forecast','forecast.csv')

elif page == 'Inventory planner':
    st.info('SIMULATED · Fixed-origin order-up-to planning using historical sales as demand. No real orders are placed.')
    a = assumption_controls('planner_', intervals=p.upper.notna().all())
    trace,totals = simulation(p,a); simulation_summary(totals)
    cost_summary(totals); assumptions_caption(a)
    daily = trace.groupby('date')[['ending_stock','lost_units','arrivals','ordered_units']].sum().reset_index()
    chart(px.line(daily,x='date',y=['ending_stock','lost_units','arrivals'],markers=True,
                  title='Simulated stock flow · selected population',labels={'value':'Units','date':'Date'}))
    st.subheader('Order schedule')
    orders = trace[trace.ordered_units.gt(0)][['date','expected_arrival_date','id','ordered_units','procurement_spend','order_fees']]
    st.dataframe(orders,use_container_width=True,hide_index=True)
    st.caption('Orders placed at day end arrive at the start of day t + lead time. Budget pays acquisition plus order fees. '
               'Requests are allocated by largest unit shortfall, then identifier. No backorders, expiry or terminal salvage. '
               'Initial stock acquisition value is excluded from cost. Forecast bounds summed for safety are a heuristic, not a service-level guarantee.')
    csv_download(trace,'Download simulated daily ledger','inventory_ledger.csv')
    st.download_button('Download assumptions',json.dumps({'scope':context,'assumptions':asdict(a)},indent=2),'assumptions.json')
    policy_explanation()

elif page == 'Scenario simulator':
    scenario_page(p,context)

elif page == 'Model comparison':
    st.subheader('Final holdout · current store/category filters')
    if settings.get('schema_version') == 2:
        st.info(f"MAE champion: {settings['validation_champion']}. RMSE champion: {settings['volume_champion']}. Both were selected on validation.")
        st.caption('original_snapshot retains the delivered pilot model weights. original_recipe_refit retrains the original method through the same cutoff as the new models. Compare models within this period; v1 used different dates.')
    metrics = pd.DataFrame([{'model':name,**point_metrics(g),**interval_metrics(g)} for name,g in scope.groupby('model')])
    chart(px.bar(metrics,x='model',y='MAE',title='Final holdout MAE · lower is better',labels={'MAE':'Units / day','model':'Model'}))
    baseline_mae=metrics.set_index('model').loc['seasonal_naive','MAE'] if 'seasonal_naive' in set(metrics.model) else 0
    metrics['MAE improvement vs seasonal (%)']=(100*(baseline_mae-metrics.MAE)/baseline_mae) if baseline_mae else float('nan')
    metrics['MAE rank']=metrics.MAE.rank(method='min')
    st.dataframe(metrics.sort_values('MAE'),hide_index=True,use_container_width=True)
    lines=scope.groupby(['model','date'],as_index=False).prediction.sum()
    chart(px.line(lines,x='date',y='prediction',color='model',title='Model forecast comparison · same dates and population',labels={'prediction':'Units / day'}))
    st.caption('WAPE is a ratio (0.20 means 20%); undefined for all-zero actuals. Coverage is a ratio; target 0.90. '
               'Mean interval score penalizes wide intervals and misses; lower is better. Metrics are at the product-store/day level.')
    st.subheader('Model selection record · full validation population')
    st.dataframe(bundle['metrics'][bundle['metrics'].split.eq('validation')],hide_index=True,use_container_width=True)
    st.caption('Validation scores are intentionally unfiltered: they document the original model-selection decision. '
               'Do not change the champion based on the test ranking.')
    csv_download(metrics,'Download filtered holdout metrics','model_comparison.csv')
    with st.expander('Experiment settings and provenance'):
        st.json(settings); st.json(bundle['audit'])

elif page == 'Business impact':
    decision_page(scope,bundle,root,context)

elif page == 'Research & methodology':
    methodology_page(bundle,root)
