"""Shared presentation components. Calculations live in forecast, inventory and research."""
from dataclasses import asdict
from html import escape
import json
import math

import plotly.express as px
import streamlit as st

from supplysense.inventory import Assumptions

PALETTE = ['#087f8c', '#e9a23b', '#6174b5', '#d06072', '#729543', '#8c6bb1', '#8c7c65']


def setup_style():
    px.defaults.template = 'plotly_white'
    px.defaults.color_discrete_sequence = PALETTE
    st.markdown('''<style>
    html,body,[data-testid="stApp"] {font-family:"Segoe UI",Arial,sans-serif;}
    [data-testid="stAppViewContainer"] {background:#f4f7fb;}
    [data-testid="stHeader"] {background:rgba(244,247,251,.95);}
    [data-testid="stSidebar"] {background:#11263d;border-right:1px solid #234058;}
    [data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#e2edf5;}
    [data-testid="stSidebar"] [data-baseweb="select"] * {color:#1a334b;}
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {color:#1a334b;}
    [data-testid="stSidebar"] hr {border-color:#2e465d;}
    .block-container {padding-top:3.3rem;padding-bottom:3rem;max-width:1520px;}
    h1 {letter-spacing:-1.1px;color:#102b44;font-weight:750;}
    h2,h3 {color:#173950;letter-spacing:-.3px;}
    [data-testid="stMetric"] {background:#fff;border:1px solid #dce6ee;border-radius:13px;padding:17px 19px;}
    [data-testid="stMetricLabel"] {color:#52657b;white-space:normal;}
    [data-testid="stMetricLabel"] p {white-space:normal;overflow:visible;text-overflow:clip;}
    [data-testid="stMetricValue"] {color:#153650;font-size:1.9rem;}
    [data-testid="stExpander"] {background:white;border-color:#dce6ee;border-radius:12px;}
    [data-testid="stDataFrame"] {border:1px solid #dce6ee;border-radius:10px;}
    [data-testid="stMarkdownContainer"] table {display:block;max-width:100%;overflow-x:auto;}
    [data-testid="stMarkdownContainer"] code {overflow-wrap:anywhere;}
    .ss-brand {font-size:1.7rem;font-weight:750;letter-spacing:-.8px;color:#fff;margin-top:0;}
    .ss-tagline {font-size:.82rem;line-height:1.5;color:#afc9dc;margin:4px 0 25px;}
    .ss-kicker {font-size:.72rem;font-weight:700;letter-spacing:1.5px;color:#087f8c;text-transform:uppercase;}
    .ss-subtitle {font-size:1.05rem;line-height:1.6;color:#566c81;margin:-.3rem 0 1.1rem;max-width:980px;}
    .ss-note {background:#e8f4f3;border-left:4px solid #087f8c;border-radius:0 10px 10px 0;padding:16px 20px;color:#173f4a;margin:12px 0 20px;}
    .ss-note strong {display:block;margin-bottom:5px;}
    .ss-badge {display:inline-block;background:#e4f2f2;color:#12636d;border-radius:5px;padding:4px 9px;margin-right:6px;font-size:.75rem;font-weight:650;}
    .ss-footer {border-top:1px solid #dce6ee;padding-top:20px;margin-top:30px;color:#607589;font-size:.8rem;}
    @media(max-width:760px) {.block-container {padding:3rem 1rem 2rem;}h1 {font-size:2rem;}[data-testid="stMetricValue"] {font-size:1.5rem;}
    [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}[data-testid="column"],[data-testid="stColumn"] {min-width:min(100%,260px);flex:1 1 260px;}}
    </style>''', unsafe_allow_html=True)


def heading(title, subtitle):
    st.markdown('<div class="ss-kicker">SupplySense · Decision intelligence</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="ss-subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)


def note(title, body):
    st.markdown(f'<div class="ss-note"><strong>{escape(title)}</strong>{escape(body)}</div>', unsafe_allow_html=True)


def fmt(value, digits=2, percent=False):
    if value is None or not math.isfinite(float(value)):
        return 'N/A'
    return f'{value:.{digits}%}' if percent else f'{value:,.{digits}f}'


def chart(fig, key=None, height=380):
    # Keep multi-model legends below the plot so they do not collide with titles.
    many_series = len(fig.data) > 2
    fig.update_layout(margin=dict(l=12, r=15, t=65, b=125 if many_series else 80), height=height + (100 if many_series else 40),
                      font=dict(family='Segoe UI, Arial', color='#30465e', size=12),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='white',
                      legend=dict(orientation='h', y=-.28, yanchor='top', x=0, title_text='', font=dict(size=10)),
                      hoverlabel=dict(bgcolor='white'), title_font_size=17)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#edf1f5', zerolinecolor='#d7e0e9')
    st.plotly_chart(fig, use_container_width=True, key=key,
                    config={'displaylogo': False, 'toImageButtonOptions': {'format': 'png', 'scale': 2}})


def csv_download(frame, label, filename, key=None):
    st.download_button(label, frame.to_csv(index=False).encode('utf-8'), filename,
                       'text/csv', key=key)


def json_download(value, label, filename, key=None):
    st.download_button(label, json.dumps(value, indent=2, default=str, allow_nan=False), filename,
                       'application/json', key=key)


def assumption_controls(prefix, intervals=True, expanded=True):
    with st.expander('Operating assumptions · configurable', expanded=expanded):
        st.caption('Costs use assumed currency units (CU). Stock is per product-store; the purchasing budget is shared across the selected population for this entire evaluation period.')
        a, b, c, d = st.columns(4)
        stock = a.number_input('Starting units per series', min_value=0, max_value=1000000, value=20, step=1, key=prefix+'stock')
        unit = b.number_input('Acquisition CU / unit', min_value=.01, max_value=1000000., value=2., key=prefix+'unit')
        hold = c.number_input('Holding CU / unit / day', min_value=0., max_value=1000000., value=.05, format='%.2f', key=prefix+'hold')
        shortage = d.number_input('Penalty CU / lost unit', min_value=0., max_value=1000000., value=5., key=prefix+'short')
        a, b, c, d = st.columns(4)
        fee = a.number_input('Fixed CU / SKU order', min_value=0., max_value=1000000., value=1., key=prefix+'fee')
        budget = b.number_input('Shared order budget (CU)', min_value=0., max_value=1000000000., value=3000., key=prefix+'budget')
        lead = c.number_input('Replenishment delay (days)', min_value=1, max_value=28, value=3, key=prefix+'lead')
        review = d.number_input('Review every (days)', min_value=1, max_value=28, value=7, key=prefix+'review')
        safety = st.slider('Safety weight: point forecast → upper daily bound', 0., 1., 0., .1,
                           key=prefix+'safety', disabled=not intervals)
        if not intervals:
            st.caption('Intervals are unavailable for this selection. Safety weight is fixed at zero.')
            safety = 0.
        if budget < unit + fee:
            st.info('This budget cannot fund one new unit plus its order fee. Only starting inventory will serve demand.')
        if lead >= 28:
            st.info('A 28-day lead time means new orders cannot arrive within this 28-day evaluation.')
    return Assumptions(stock, unit, hold, shortage, fee, budget, lead, review, safety)


def assumptions_caption(a):
    st.caption(f'SIMULATED · {a.starting_stock} starting units / series · acquisition {a.unit_cost:g} CU / unit · '
               f'holding {a.holding_cost:g} CU / unit / day · shortage {a.shortage_penalty:g} CU / lost unit · '
               f'order fee {a.order_fee:g} CU · lead {a.lead_days} days · review {a.review_days} days · '
               f'budget {a.budget:,.0f} CU · safety weight {a.safety_weight:g} · demand ×{a.demand_multiplier:g}')


def simulation_summary(totals):
    a, b, c, d = st.columns(4)
    a.metric('Simulated fill rate', fmt(totals['fill_rate'], 1, True))
    b.metric('Unmet simulated demand', fmt(totals['lost_units'], 1))
    c.metric('Simulated total cost (CU)', fmt(totals['simulated_total_cost']))
    d.metric('Budget remaining (CU)', fmt(totals['budget_remaining']))


def cost_summary(totals):
    a, b, c, d = st.columns(4)
    a.metric('Procurement (CU)', fmt(totals['procurement_spend']))
    b.metric('Holding cost (CU)', fmt(totals['holding_cost']))
    c.metric('Shortage cost (CU)', fmt(totals['shortage_cost']))
    d.metric('Order fees (CU)', fmt(totals['order_fees']))


def policy_explanation():
    with st.expander('How the replenishment policy works'):
        st.markdown('On review days, SupplySense sums the fixed forecast over the next **lead time + review period**, '
                    'adds the configured uncertainty buffer, subtracts on-hand stock and incoming orders, and rounds '
                    'positive shortfalls up to whole units. Orders are limited by the remaining shared budget.')
        st.markdown('Orders are placed at day end and arrive at the start of day **t + lead time**. '
                    'Larger unit shortfalls get budget priority, with product identifier breaking ties. '
                    'Actual sales for future days are never used to place an order.')
        st.caption('Historical recorded sales stand in for demand. Unfulfilled units are lost sales, not backorders. '
                   'Initial stock acquisition is excluded; procurement, order fees, end-of-day holding and shortage '
                   'penalties are included. There is no terminal salvage, expiry, capacity constraint or profit model. '
                   'Summed daily interval bounds are a safety heuristic, not a guaranteed service level.')
