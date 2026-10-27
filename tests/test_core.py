"""Small correctness fixtures only: no M5 training or claimed experiment results."""
from dataclasses import replace
import math
import numpy as np
import pandas as pd
import pytest
from supplysense.forecast import (make_features, FEATURES, predict_block, calibrate,
    add_intervals, point_metrics, interval_metrics)
from supplysense.inventory import Assumptions, simulate


def synthetic_history():
    frames=[]
    for i in range(2):
        d=np.arange(1,151)
        frames.append(pd.DataFrame({'id':f'item{i}_CA_1','item_id':f'item{i}',
            'store_id':'CA_1','cat_id':'FOODS','state_id':'CA','day':d,
            'date':pd.Timestamp('2011-01-29')+pd.to_timedelta(d-1,unit='D'),
            'month':1,'year':2011,'sales':(d % 7 + i).astype(float),'sell_price':2.,
            'snap_CA':0,'snap_TX':0,'snap_WI':0,'event_name_1':None,'event_name_2':None}))
    return pd.concat(frames,ignore_index=True)


def test_all_horizon_features_ignore_future_sales_and_prices():
    data=synthetic_history(); origin=100
    before,mappings=make_features(data)
    poisoned=data.copy()
    poisoned.loc[poisoned.day>origin,['sales','sell_price']]=999999
    after,_=make_features(poisoned,mappings)
    mask=before.day.between(origin+1,origin+28)
    pd.testing.assert_frame_equal(before.loc[mask,FEATURES],after.loc[mask,FEATURES])
    pd.testing.assert_frame_equal(predict_block(None,before,origin),predict_block(None,after,origin))


def test_seasonal_forecast_repeats_last_week():
    data,_=make_features(synthetic_history())
    p=predict_block(None,data,100)
    s=p[p.id.eq('item0_CA_1')].prediction.to_numpy()
    np.testing.assert_array_equal(s,np.tile(np.arange(94,101)%7,4))


def test_calibration_rank_and_metrics():
    p=pd.DataFrame({'id':['x']*20,'horizon':[1]*20,'prediction':[0.]*20,'sales':np.arange(20)})
    c=calibrate(p,{'x':1.},alpha=.1)
    assert c['radii_by_horizon']['1']==18 # ceil(21*.9)=19th sorted score
    scored=add_intervals(p,c)
    assert interval_metrics(scored)['coverage']==.95
    assert point_metrics(p)['MAE']==9.5
    assert point_metrics(p.assign(sales=0))['WAPE'] is None


def inventory_fixture(n=5):
    return pd.DataFrame({'id':['x']*n,'date':pd.date_range('2016-04-25',periods=n),
                         'prediction':[1.]*n,'upper':[2.]*n,'sales':[1.]*n})


def test_inventory_arrival_and_cash_conservation():
    a=Assumptions(starting_stock=0,unit_cost=2.,order_fee=1.,budget=5.,lead_days=2,review_days=1)
    trace,t=simulate(inventory_fixture(),a)
    assert trace.ordered_units.tolist()==[2,0,0,0,0]
    assert trace.arrivals.tolist()==[0,0,2,0,0]
    assert trace.fulfilled.tolist()==[0,0,1,1,0]
    assert t['fill_rate']==.4 and t['budget_remaining']==0
    assert t['procurement_spend']+t['order_fees']==5
    assert t['fulfilled']+t['lost_units']==t['demand']
    assert trace.arrivals.sum()+a.starting_stock-trace.fulfilled.sum()==t['ending_stock']


def test_zero_budget_no_demand_and_long_lead():
    _,t=simulate(inventory_fixture(),Assumptions(starting_stock=0,budget=0))
    assert t['lost_units']==5 and t['procurement_spend']==0
    trace,t=simulate(inventory_fixture().assign(sales=0,prediction=0,upper=0))
    assert t['fill_rate'] is None and trace.ordered_units.sum()==0
    trace,t=simulate(inventory_fixture(),Assumptions(starting_stock=0,lead_days=28))
    assert trace.ordered_units.sum()==0 and t['lost_units']==5


def test_no_negative_stock_or_budget_for_shared_orders():
    p=pd.concat([inventory_fixture().assign(id='x'),inventory_fixture().assign(id='y')])
    trace,t=simulate(p,Assumptions(starting_stock=0,budget=7,lead_days=1))
    assert trace.ending_stock.ge(0).all() and t['budget_remaining']>=0
    assert trace.procurement_spend.sum()+trace.order_fees.sum()<=7
    with pytest.raises(ValueError):
        simulate(pd.concat([p,p]))
