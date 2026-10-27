"""Historical lost-sales simulation. All economic inputs are explicit assumptions."""
from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Assumptions:
    starting_stock: int = 20  # per selected series
    unit_cost: float = 2.0  # assumed acquisition cost, NOT observed selling price
    holding_cost: float = .05  # per unit at day end
    shortage_penalty: float = 5.0  # per unfulfilled unit; no revenue/profit claim
    order_fee: float = 1.0  # per nonempty SKU order
    budget: float = 3000.0  # shared cash for new orders over entire horizon
    lead_days: int = 3
    review_days: int = 7
    safety_weight: float = 0.0  # point + weight * (upper - point); heuristic, not service probability
    demand_multiplier: float = 1.0


def simulate(predictions, assumptions=Assumptions()):
    a = assumptions
    values = asdict(a)
    try:
        valid = all(np.isfinite(v) and v >= 0 for v in values.values())
    except TypeError:
        valid = False
    if not valid:
        raise ValueError('Assumptions must be finite and nonnegative.')
    if a.unit_cost <= 0 or a.lead_days < 1 or a.review_days < 1 or a.safety_weight > 1:
        raise ValueError('Positive unit cost, lead/review >=1, safety weight <=1 required.')
    for v in [a.starting_stock, a.lead_days, a.review_days]:
        if int(v) != v:
            raise ValueError('Stock, lead days and review days must be integers.')
    required = ['id', 'date', 'prediction', 'sales']
    if predictions.empty or not set(required).issubset(predictions):
        raise ValueError('Need nonempty evaluated predictions with actual sales.')
    p = predictions.copy()
    p['date'] = pd.to_datetime(p.date, errors='coerce')
    if p.id.isna().any() or p.date.isna().any():
        raise ValueError('Every row needs a series identifier and a valid date.')
    if p.duplicated(['id', 'date']).any() or ('model' in p and p.model.nunique() != 1):
        raise ValueError('Select a single model with unique series/date rows.')
    p = p.sort_values(['date', 'id'])
    for col in ['prediction', 'sales']:
        p[col] = pd.to_numeric(p[col], errors='coerce')
    if not np.isfinite(p[['prediction','sales']].to_numpy()).all() or (p[['prediction','sales']] < 0).any().any():
        raise ValueError('Forecasts and sales must be finite, complete and nonnegative.')
    if a.safety_weight > 0:
        if 'upper' not in p:
            raise ValueError('Safety-stock adjustment requires available upper prediction bounds.')
        p['upper'] = pd.to_numeric(p.upper, errors='coerce')
        if not np.isfinite(p.upper).all() or p.upper.lt(p.prediction).any():
            raise ValueError('Safety-stock adjustment requires finite upper bounds at or above forecasts.')
    else:
        # Point-policy experiments on development forecasts need no invented intervals.
        p['upper'] = p.prediction
    ids = sorted(p.id.unique()); dates = sorted(p.date.unique())
    if len(p) != len(ids) * len(dates):
        raise ValueError('Each series must cover the same dates.')
    if not pd.DatetimeIndex(dates).equals(pd.date_range(dates[0], periods=len(dates), freq='D')):
        raise ValueError('Simulation requires consecutive daily dates; lead times are measured in days.')
    stock = {i: float(a.starting_stock) for i in ids}
    pipeline = []
    demand = p.pivot(index='date', columns='id', values='sales').reindex(index=dates, columns=ids)
    p['target_rate'] = p.prediction + a.safety_weight * (p.upper - p.prediction)
    forecasts = p.pivot(index='date', columns='id', values='target_rate').reindex(index=dates, columns=ids)
    cash = a.budget; rows = []
    for t, date in enumerate(dates):
        arriving = {i: 0 for i in ids}
        for due, i, qty in pipeline:
            if due == t:
                stock[i] += qty; arriving[i] += qty
        pipeline = [order for order in pipeline if order[0] > t]
        day_rows = {}
        for i in ids:
            need = float(demand.loc[date, i]) * a.demand_multiplier
            sold = min(stock[i], need); stock[i] -= sold
            day_rows[i] = {'date': date, 'id': i, 'demand': need, 'fulfilled': sold,
                'lost_units': need - sold, 'ending_stock': stock[i], 'arrivals': arriving[i],
                'ordered_units': 0, 'procurement_spend': 0., 'order_fees': 0.,
                'holding_cost': stock[i] * a.holding_cost,
                'shortage_cost': (need - sold) * a.shortage_penalty,
                'stockout': bool(need > sold), 'expected_arrival_date': pd.NaT}
        if t % a.review_days == 0 and t + a.lead_days < len(dates):
            requests = []
            for i in ids:
                target = forecasts[i].iloc[t + 1:min(len(dates), t + a.lead_days + a.review_days + 1)].sum()
                position = stock[i] + sum(q for _, sku, q in pipeline if sku == i)
                qty = max(0, math.ceil(target - position))
                requests.append((qty, i))
            # Explicit reproducible allocation rule, not an optimization claim.
            for qty, i in sorted(requests, key=lambda v: (-v[0], v[1])):
                affordable = max(0, math.floor((cash - a.order_fee + 1e-9) / a.unit_cost))
                qty = min(qty, affordable)
                if qty:
                    spend = qty * a.unit_cost
                    cash -= spend + a.order_fee
                    pipeline.append((t + a.lead_days, i, qty))
                    day_rows[i].update(ordered_units=qty, procurement_spend=spend, order_fees=a.order_fee,
                                       expected_arrival_date=pd.Timestamp(dates[t + a.lead_days]))
        for i in ids:
            day_rows[i]['outstanding_order_units'] = sum(q for _, sku, q in pipeline if sku == i)
            day_rows[i]['inventory_position'] = stock[i] + day_rows[i]['outstanding_order_units']
        rows.extend(day_rows.values())
    trace = pd.DataFrame(rows)
    totals = trace[['demand', 'fulfilled', 'lost_units', 'procurement_spend', 'order_fees',
                    'holding_cost', 'shortage_cost']].sum().to_dict()
    totals['fill_rate'] = totals['fulfilled'] / totals['demand'] if totals['demand'] else None
    totals['simulated_total_cost'] = sum(totals[k] for k in ['procurement_spend','order_fees','holding_cost','shortage_cost'])
    totals['budget_remaining'] = max(0., cash)
    totals['ending_stock'] = sum(stock.values())
    totals['starting_stock_value_excluded'] = len(ids) * a.starting_stock * a.unit_cost
    totals['stockout_series_days'] = int(trace.stockout.sum())
    totals['stockout_day_rate'] = float(trace.stockout.mean())
    totals['holding_plus_shortage_cost'] = totals['holding_cost'] + totals['shortage_cost']
    return trace, totals
