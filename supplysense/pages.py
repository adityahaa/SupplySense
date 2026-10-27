"""Decision-lab and methodology pages built on the existing verified calculators."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import hashlib
import pandas as pd
import plotly.express as px
import streamlit as st
from .inventory import Assumptions, simulate
from .research import compare_models, run_sensitivity, rank_reversals, forecast_summary
from .ui import (chart, note, assumption_controls, assumptions_caption, csv_download,
                 json_download, simulation_summary, cost_summary, policy_explanation, fmt)

@st.cache_data(show_spinner=False,max_entries=16)
def comparison(p,a):
    return compare_models(p,a)

@st.cache_data(show_spinner=False,max_entries=32)
def simulation(p,a):
    return simulate(p,a)

@st.cache_data(show_spinner=False,max_entries=4)
def sensitivity(p):
    return run_sensitivity(p)

def scenario_page(p,context):
    st.info('SIMULATED · Changes stress historical demand and operating assumptions. Forecasts stay fixed.')
    base=assumption_controls('scenario_',intervals=p.upper.notna().all())
    presets=['Normal demand','Increased demand','Reduced demand','Longer lead time','Higher shortage penalty','Budget constrained','Custom']
    preset=st.selectbox('Scenario preset',presets)
    factors={'Normal demand':(1.,0,1.,1.),'Increased demand':(1.25,0,1.,1.),
             'Reduced demand':(.75,0,1.,1.),'Longer lead time':(1.,4,1.,1.),
             'Higher shortage penalty':(1.,0,2.,1.),'Budget constrained':(1.,0,1.,.5),'Custom':(1.25,3,1.,1.)}
    demand,delay,penalty,budget=factors[preset]
    a,b=st.columns(2)
    demand=a.slider('Scenario demand multiplier',0.,2.,demand,.05,key='demand_'+preset)
    delay=b.slider('Additional replenishment delay (days)',0,28,delay,key='delay_'+preset)
    a,b=st.columns(2)
    penalty=a.slider('Shortage penalty multiplier',0.,5.,penalty,.25,key='penalty_'+preset)
    budget=b.slider('Purchasing budget multiplier',0.,2.,budget,.1,key='budget_'+preset)
    stress=replace(base,demand_multiplier=demand,lead_days=base.lead_days+delay,
                   shortage_penalty=base.shortage_penalty*penalty,budget=base.budget*budget)
    _,normal=simulation(p,base); trace,total=simulation(p,stress)
    simulation_summary(total); assumptions_caption(stress)
    table=pd.DataFrame([{'scenario':'Baseline assumptions',**normal},{'scenario':preset,**total}])
    if normal['fill_rate'] is not None and total['fill_rate'] is not None:
        st.write(f"Fill-rate change: **{100*(total['fill_rate']-normal['fill_rate']):+.2f} percentage points**. Simulated cost change: **{total['simulated_total_cost']-normal['simulated_total_cost']:+,.2f} CU**.")
    chart(px.bar(table,x='scenario',y=['procurement_spend','order_fees','holding_cost','shortage_cost'],title='Simulated cost composition',labels={'value':'Assumed CU'}))
    st.dataframe(table[['scenario','fill_rate','lost_units','simulated_total_cost','ending_stock']],hide_index=True,use_container_width=True)
    csv_download(table,'Download scenario comparison','scenario_comparison.csv')
    json_download({'scope':context,'baseline':asdict(base),'scenario':asdict(stress)},'Download scenario assumptions','scenario_assumptions.json')
    policy_explanation()

def decision_page(scope,bundle,root,context):
    st.write('Does a more accurate demand forecast always produce a better inventory decision? Compare each saved model under the same policy, population and initial conditions.')
    if 'seasonal_naive' not in set(scope.model):
        st.warning('This bundle has no seasonal-naive baseline. Use Model comparison for measured scores or import the supplied result bundle for the decision lab.')
        return
    a=assumption_controls('lab_',intervals=scope.upper.notna().all(),expanded=False)
    assumptions_caption(a)
    with st.spinner('Comparing saved forecasts under identical operating assumptions…'):
        result=comparison(scope,a)
    winner=result.sort_values(['MAE','model']).iloc[0]
    cheapest=result.sort_values(['simulated_total_cost','model']).iloc[0]
    note('Product Management Insight',f"Under these assumptions, {winner.model} has the lowest measured MAE ({winner.MAE:.3f}), while {cheapest.model} has the lowest simulated cost ({cheapest.simulated_total_cost:,.2f} CU). Select models against the operating objective and service constraint; this scenario does not establish a universally best model.")
    l,r=st.columns(2)
    with l: chart(px.scatter(result,x='MAE',y='simulated_total_cost',color='model',hover_data=['fill_rate','bias_units_per_day'],title='Forecast error versus simulated cost',labels={'MAE':'MAE (units/series/day)','simulated_total_cost':'Cost (CU)'}))
    with r: chart(px.bar(result,x='model',y='fill_rate',title='Simulated unit fill rate by model'))
    l,r=st.columns(2)
    with l: chart(px.scatter(result,x='holding_cost',y='shortage_cost',color='model',title='Holding–shortage trade-off (CU)'))
    with r: chart(px.scatter(result,x='simulated_total_cost',y='fill_rate',color='model',symbol='is_pareto',title='Cost–service Pareto comparison'))
    chart(px.bar(result,x='model',y=['mae_rank','cost_rank'],barmode='group',title='Technical ranking versus business ranking · 1 is lowest'))
    cols=['model','MAE','bias_units_per_day','simulated_total_cost','fill_rate','lost_units','holding_cost','shortage_cost','procurement_spend','simulated_total_cost_delta_vs_baseline','cost_rank','mae_rank','is_pareto']
    st.dataframe(result[cols],hide_index=True,use_container_width=True)
    st.caption('Cost differences use seasonal naive as the baseline. Pareto points are not dominated on both cost and fill rate within this scenario. Lower cost can reflect lower procurement or service; inspect all components.')
    reversals=rank_reversals(result)
    if len(reversals):
        st.write(f'{len(reversals)} model pairs show lower MAE but higher simulated cost under the current assumptions.')
        with st.expander('Inspect supported ranking reversals'): st.dataframe(reversals,hide_index=True,use_container_width=True)
    else: st.info('No strict MAE/cost ranking reversal occurs in this selection.')
    csv_download(result,'Download decision comparison','decision_comparison.csv')
    json_download({'scope':context,'assumptions':asdict(a)},'Download decision assumptions','decision_assumptions.json')
    st.subheader('Sensitivity analysis')
    st.caption('34 fixed scenarios: lead times 1/3/7 days × shortage penalties 1/5/10 CU × safety weights 0/0.5/1, plus holding-cost, review-frequency and budget checks. These reset to documented defaults independently of the controls above.')
    saved=root/'results'/'research'
    matching=False
    if (saved/'protocol.json').is_file():
        try:
            checksums=json.loads((saved/'checksums.json').read_text())
            for name in ['protocol.json','sensitivity_results.csv']:
                if hashlib.sha256((saved/name).read_bytes()).hexdigest()!=checksums.get(name):
                    raise ValueError('Research checksum mismatch')
            protocol=json.loads((saved/'protocol.json').read_text())
            current_code=all(hashlib.sha256((root/'supplysense'/name).read_bytes()).hexdigest()==expected for name,expected in protocol['code_sha256'].items())
            matching=current_code and protocol['source_bundle_sha256']==bundle['bundle_sha256'] and scope.id.nunique()==bundle['test_predictions'].id.nunique()
        except (OSError,ValueError,KeyError,TypeError):
            st.warning('Saved sensitivity files are missing or invalid. Recalculate below or run scripts/run_business_research.py to regenerate them.')
    data=None
    if matching and (saved/'sensitivity_results.csv').is_file():
        data=pd.read_csv(saved/'sensitivity_results.csv')
        st.success('Executed full-population sensitivity results loaded for this exact experiment bundle.')
    elif scope.upper.notna().all():
        if st.button('Run 34 scenarios for current selection',type='primary'):
            with st.spinner('Running bounded sensitivity simulations…'): data=sensitivity(scope)
            st.session_state['sensitivity_selection']=(context,data)
        cached=st.session_state.get('sensitivity_selection')
        if cached and cached[0]==context: data=cached[1]
    else: st.info('This sensitivity design requires intervals. Point-policy comparisons above remain available.')
    if data is not None:
        grid=data[data.family.eq('factorial')]
        l,r=st.columns(2)
        with l: chart(px.line(grid[grid.shortage_penalty.eq(5)&grid.safety_weight.eq(0)].sort_values('lead_days'),x='lead_days',y='simulated_total_cost',color='model',markers=True,title='Lead-time sensitivity · penalty 5, safety 0'))
        with r: chart(px.line(grid[grid.lead_days.eq(3)&grid.safety_weight.eq(0)].sort_values('shortage_penalty'),x='shortage_penalty',y='simulated_total_cost',color='model',markers=True,title='Shortage sensitivity · lead 3, safety 0'))
        selected=st.selectbox('Inspect an executed scenario',data.scenario_id.unique())
        st.dataframe(data[data.scenario_id.eq(selected)],hide_index=True,use_container_width=True)
        csv_download(data,'Download sensitivity results','sensitivity_results.csv')
        if matching: json_download(protocol,'Download sensitivity protocol','sensitivity_protocol.json')
        else:
            from .research import default_scenarios
            json_download({'scope':context,'scenarios':[{'id':s['scenario_id'],'assumptions':asdict(s['assumptions'])} for s in default_scenarios()]},'Download sensitivity protocol','sensitivity_protocol.json')
    policy_explanation()

def methodology_page(bundle,root):
    if bundle['settings'].get('schema_version') == 3:
        st.subheader('Independent replication: forecasting, intermittency and constrained inventory')
        note('Evidence boundaries','The original M5 findings and this UCI replication are separate. All inventory outcomes are simulated. Both final evaluation windows are now inspected; no further tuning may treat them as untouched.')
        for label,name in [('Replication findings','INDEPENDENT_RESULTS.md'),('Literature and contribution','RESEARCH_EXTENSION.md'),('Data attribution','PUBLIC_DATA_NOTICE.md')]:
            path=root/'docs'/name
            if path.is_file():
                with st.expander(label,expanded=label=='Replication findings'): st.markdown(path.read_text(encoding='utf-8'))
        with st.expander('Frozen independent protocol'):
            st.json(json.loads((root/'docs/INDEPENDENT_PROTOCOL.json').read_text()))
        output=root/'results/independent'
        for label,name in [('Both test origins','test_origin_metrics.csv'),('Conditional MAE uncertainty','mae_cluster_intervals.csv'),('Budget, lead time and shortage-cost scenarios','sensitivity_results.csv'),('Intermittency groups within the shared budget','intermittency_results.csv')]:
            path=output/name
            if path.is_file():
                with st.expander(label):
                    frame=pd.read_csv(path);st.dataframe(frame,hide_index=True,use_container_width=True)
                    csv_download(frame,'Download '+label,name)
        return
    st.subheader('From Forecast Accuracy to Business Value: Evaluating AI-Driven Inventory Planning Decisions')
    st.write('**Research question:** To what extent do improvements in demand forecasting accuracy translate into improved simulated inventory performance?')
    note('Evidence boundaries','Forecast errors are measured against historical sales. Inventory costs and service are simulated. The saved test has already been inspected; the new policy sensitivities are descriptive, not an independent forecasting test.')
    sections=[('Research overview','research_overview.md'),('Research paper draft','research_paper_draft.md'),('Inventory methodology','inventory_method.md'),('Existing forecasting protocol','v2_method.md'),('References','references.md')]
    for label,name in sections:
        path=root/'docs'/name
        if path.is_file():
            with st.expander(label,expanded=label=='Research overview'):
                st.markdown(path.read_text(encoding='utf-8'))
    val=bundle.get('validation_predictions',pd.DataFrame())
    if not val.empty:
        st.subheader('Existing development windows')
        st.caption('Previously used for model development. These are not new independent tests. Only models actually saved in these windows are shown.')
        origins=sorted(val.origin.unique()) if 'origin' in val else [bundle['settings']['validation_origin']]
        origin=st.selectbox('Development forecast origin',origins)
        g=val[val.origin.eq(origin)].copy() if 'origin' in val else val.copy()
        if 'date' not in g: g['date']=pd.Timestamp('2011-01-29')+pd.to_timedelta(g.day-1,unit='D')
        st.dataframe(forecast_summary(g),hide_index=True,use_container_width=True)
        with st.expander('Development window: default point-policy comparison'):
            st.dataframe(comparison(g,Assumptions()),hide_index=True,use_container_width=True)
            st.caption('Stock and budget reset at each origin. Safety weight is zero because these saved validation forecasts have no calibrated bounds.')
    with st.expander('Source settings and provenance'):
        st.json(bundle['settings']); st.write('Imported result SHA256:',bundle['bundle_sha256'])
