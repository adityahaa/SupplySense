import numpy as np
import pandas as pd
import pytest
from supplysense.inventory import Assumptions, simulate
from supplysense.research import compare_models, default_scenarios, pareto_front, rank_reversals, validate_comparison

def sample():
    p=pd.DataFrame({'id':['x']*5,'date':pd.date_range('2016-05-23',periods=5),'sales':[1.]*5,'prediction':[1.]*5})
    return pd.concat([p.assign(model='seasonal_naive'),p.assign(model='alternative',prediction=2.)],ignore_index=True)

def test_matching_observations_and_baseline():
    p=sample(); p.loc[0,'sales']=2
    with pytest.raises(ValueError,match='identical'): validate_comparison(p)
    with pytest.raises(ValueError,match='Baseline'): compare_models(sample().query("model=='alternative'"))

def test_point_only_and_zero_demand():
    r=compare_models(sample(),Assumptions(starting_stock=0,budget=0))
    assert r.simulated_total_cost.eq(25).all()
    assert r.fill_rate.eq(0).all()
    with pytest.raises(ValueError,match='upper bounds'): compare_models(sample(),Assumptions(safety_weight=.5))
    zero=compare_models(sample().assign(sales=0,prediction=0),Assumptions(starting_stock=0))
    assert zero.fill_rate.isna().all() and zero.WAPE.isna().all()

def test_pareto_and_rank_reversals():
    f=pd.DataFrame({'simulated_total_cost':[10,10,12,8],'fill_rate':[.9,.9,.8,.7]})
    assert pareto_front(f).is_pareto.tolist()==[True,True,False,True]
    r=compare_models(sample(),Assumptions(starting_stock=0,budget=30,lead_days=1,review_days=1))
    assert np.allclose(r.simulated_total_cost,r.procurement_spend+r.order_fees+r.holding_cost+r.shortage_cost)
    assert len(default_scenarios())==34
    assert len({s['scenario_id'] for s in default_scenarios()})==34

def test_simulator_rejects_infinite_and_irregular_dates():
    p=sample().query("model=='seasonal_naive'").copy()
    with pytest.raises(ValueError,match='finite'): simulate(p.assign(prediction=np.inf))
    p.loc[p.index[-1],'date']+=pd.Timedelta(days=1)
    with pytest.raises(ValueError,match='consecutive'): simulate(p)

def test_orders_cannot_see_future_actual_demand():
    p=sample().query("model=='seasonal_naive'").copy()
    a=Assumptions(starting_stock=0,budget=30,lead_days=1,review_days=1)
    t,_=simulate(p,a)
    changed=p.copy(); changed.loc[changed.index>=2,'sales']=10000
    altered,_=simulate(changed,a)
    pd.testing.assert_frame_equal(t.iloc[:2],altered.iloc[:2])
