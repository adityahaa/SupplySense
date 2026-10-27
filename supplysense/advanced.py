"""Direct 28-day forecasts using a snapshot of all information at each origin."""
import numpy as np
import pandas as pd

CATS = ['series_code', 'store_code', 'category_code', 'department_code', 'item_code']
SNAPSHOT = ['origin', 'last_sales', 'mean_7', 'mean_28', 'mean_56', 'mean_84',
            'mean_180', 'mean_365', 'std_28', 'zero_28', 'zero_84', 'days_since_sale',
            'trend_7_28', 'trend_28_84', 'latest_price', 'price_ratio_28']
FEATURES = CATS + SNAPSHOT + ['horizon', 'day', 'dow', 'month', 'year',
    'day_of_month', 'day_of_year', 'snap', 'event_1', 'event_2',
    'weekday_last', 'weekday_mean_4w']


def mappings_for(data):
    return {col: {str(v): i for i, v in enumerate(sorted(data[col].unique()))}
            for col in ['id', 'store_id', 'cat_id', 'dept_id', 'item_id']}


def make_anchors(data, origins, mappings):
    """Calculate trailing statistics, then retain only forecast-origin snapshots."""
    cols = ['id','store_id','cat_id','dept_id','item_id','state_id','day','sales','sell_price']
    f = data[cols].sort_values(['id','day']).copy()
    if f.duplicated(['id','day']).any() or not f.groupby('id').day.diff().dropna().eq(1).all():
        raise ValueError('Need one consecutive daily row per product-store.')
    g = f.groupby('id', sort=False)
    for raw, enc in zip(['id','store_id','cat_id','dept_id','item_id'], CATS):
        f[enc] = f[raw].map(mappings[raw]).astype('int32')
    f['last_sales'] = f.sales
    for w in [7,28,56,84,180,365]:
        f[f'mean_{w}'] = g.sales.transform(lambda s: s.rolling(w,min_periods=1).mean()).astype('float32')
    f['std_28'] = g.sales.transform(lambda s: s.rolling(28,min_periods=1).std(ddof=0)).astype('float32')
    for w in [28,84]:
        f[f'zero_{w}'] = g.sales.transform(lambda s: s.eq(0).astype(float).rolling(w,min_periods=1).mean()).astype('float32')
    last_sale_day = f.day.where(f.sales.gt(0)).groupby(f.id,sort=False).ffill()
    f['days_since_sale'] = f.day - last_sale_day
    f['trend_7_28'] = (f.mean_7+1)/(f.mean_28+1)
    f['trend_28_84'] = (f.mean_28+1)/(f.mean_84+1)
    f['latest_price'] = g.sell_price.ffill()
    pmean = f.latest_price.groupby(f.id,sort=False).transform(lambda s:s.rolling(28,min_periods=1).mean())
    f['price_ratio_28'] = f.latest_price/pmean
    for offset in range(7):
        f[f'weekday_last_{offset}'] = g.sales.shift(offset)
        f[f'weekday_mean_{offset}'] = sum(g.sales.shift(offset+7*j) for j in range(4))/4
    f = f[f.day.isin(origins)].rename(columns={'day':'origin'})
    keep = ['id','state_id'] + CATS + SNAPSHOT + [f'weekday_{kind}_{o}' for kind in ['last','mean'] for o in range(7)]
    out = f[keep].copy()
    for col in out:
        if col not in ['id','state_id']:
            out[col] = out[col].astype('float32')
    return out.reset_index(drop=True)


def make_design(anchors, calendar, actuals=None):
    """Expand each origin to 28 days; labels are an optional separate join."""
    f = anchors.loc[anchors.index.repeat(28)].reset_index(drop=True)
    f['horizon'] = np.tile(np.arange(1,29), len(anchors))
    f['day'] = f.origin.astype(int)+f.horizon
    cal = calendar.copy()
    cal['date'] = pd.to_datetime(cal.date)
    cal['day'] = (cal.date-pd.Timestamp('2011-01-29')).dt.days+1
    cal = cal.set_index('day')
    target = cal.reindex(f.day).reset_index(drop=True)
    if target.date.isna().any():
        raise ValueError('Calendar misses forecast days.')
    for c, values in [('dow',target.date.dt.dayofweek), ('month',target.date.dt.month),
                      ('year',target.date.dt.year), ('day_of_month',target.date.dt.day),
                      ('day_of_year',target.date.dt.dayofyear)]:
        f[c] = values.to_numpy()
    f['snap'] = np.select([f.state_id.eq(s) for s in ['CA','TX','WI']],
                         [target[f'snap_{s}'].to_numpy() for s in ['CA','TX','WI']])
    f['event_1'] = target.event_name_1.notna().to_numpy().astype(int)
    f['event_2'] = target.event_name_2.notna().to_numpy().astype(int)
    offset = (-f.horizon.to_numpy()) % 7
    for kind, name in [('last','weekday_last'), ('mean','weekday_mean_4w')]:
        vals = f[[f'weekday_{kind}_{o}' for o in range(7)]].to_numpy()
        f[name] = vals[np.arange(len(f)), offset]
    f = f[['id']+FEATURES]
    if actuals is not None:
        f = f.merge(actuals[['id','day','sales']],on=['id','day'],validate='many_to_one',how='left')
        if f.sales.isna().any():
            raise ValueError('Training labels must be observed.')
    f[FEATURES] = f[FEATURES].astype('float32')
    return f


def prediction_frame(design, predictions, manifest):
    p = design[['id','origin','horizon','day']].copy()
    p[['origin','horizon','day']] = p[['origin','horizon','day']].astype(int)
    p = p.merge(manifest[['id','item_id','store_id','cat_id']],on='id',validate='many_to_one')
    p['date'] = pd.Timestamp('2011-01-29')+pd.to_timedelta(p.day-1,unit='D')
    p['prediction'] = np.maximum(0,np.asarray(predictions,dtype=float))
    return p
