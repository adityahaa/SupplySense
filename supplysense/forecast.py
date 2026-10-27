"""Fixed-origin 28-day forecasts: every sales/price feature is at least 28 days old."""
import math
import numpy as np
import pandas as pd

HORIZON = 28
FEATURES = ['series_code', 'store_code', 'category_code', 'day', 'dow', 'month',
            'year', 'snap', 'event_1', 'event_2', 'lag_28', 'lag_35', 'lag_56',
            'mean_7_at_28', 'mean_28_at_28', 'std_28_at_28', 'zero_28_at_28',
            'price_at_28', 'price_missing_at_28']
CATEGORICAL = ['series_code', 'store_code', 'category_code']
CANDIDATES = {
    'lgbm_small': {'n_estimators': 200, 'num_leaves': 15, 'min_child_samples': 50},
    'lgbm_medium': {'n_estimators': 400, 'num_leaves': 31, 'min_child_samples': 50},
}


def make_features(data, mappings=None):
    frame = data.sort_values(['id', 'day']).copy()
    if frame.duplicated(['id', 'day']).any():
        raise ValueError('Duplicate series/day rows.')
    if not frame.groupby('id').day.diff().dropna().eq(1).all():
        raise ValueError('Missing daily rows would invalidate positional lag features.')
    if mappings is None:
        mappings = {col: {v: i for i, v in enumerate(sorted(frame[col].unique()))}
                    for col in ['id', 'store_id', 'cat_id']}
    for raw, encoded in [('id', 'series_code'), ('store_id', 'store_code'), ('cat_id', 'category_code')]:
        frame[encoded] = frame[raw].map(mappings[raw]).fillna(-1).astype(int)
    frame['dow'] = pd.to_datetime(frame.date).dt.dayofweek
    frame['snap'] = [row[f'snap_{row["state_id"]}'] for row in frame.to_dict('records')]
    frame['event_1'] = frame.event_name_1.notna().astype(int)
    frame['event_2'] = frame.event_name_2.notna().astype(int)
    groups = frame.groupby('id', sort=False)
    for lag in [28, 35, 56]:
        frame[f'lag_{lag}'] = groups.sales.shift(lag)
    for window in [7, 28]:
        frame[f'mean_{window}_at_28'] = groups.sales.transform(
            lambda s: s.shift(28).rolling(window, min_periods=window).mean())
    frame['std_28_at_28'] = groups.sales.transform(lambda s: s.shift(28).rolling(28).std(ddof=0))
    frame['zero_28_at_28'] = groups.sales.transform(
        lambda s: s.eq(0).astype(float).where(s.notna()).shift(28).rolling(28).mean())
    # Never backfill a launch-period missing price; never use the target-week price.
    frame['price_at_28'] = groups.sell_price.transform(lambda s: s.ffill().shift(28))
    frame['price_missing_at_28'] = frame.price_at_28.isna().astype(int)
    return frame, mappings


def block(data, origin, horizon=HORIZON):
    return data[data.day.between(origin + 1, origin + horizon)].copy()


def predict_block(model, features, origin):
    target = block(features, origin)
    expected = features.id.nunique() * HORIZON
    if len(target) != expected:
        raise ValueError(f'Need {expected} rows for a complete forecast block.')
    # The prediction path never passes target sales to a model.
    result = target[['id', 'item_id', 'store_id', 'cat_id', 'date', 'day']].copy()
    result['origin'] = origin
    result['horizon'] = result.day - origin
    if model is None:
        history = features[features.day.between(origin - 6, origin)].set_index(['id', 'day']).sales
        source_days = origin - 6 + (result.horizon.to_numpy() - 1) % 7
        result['prediction'] = [float(history.loc[(i, d)]) for i, d in zip(result.id, source_days)]
    else:
        result['prediction'] = np.maximum(0, model.predict(target[FEATURES]))
    return result.reset_index(drop=True)


def attach_actuals(predictions, data):
    return predictions.merge(data[['id', 'day', 'sales']], on=['id', 'day'], validate='one_to_one')


def point_metrics(predictions):
    if predictions.empty:
        return {'MAE': None, 'RMSE': None, 'WAPE': None, 'bias_units_per_day': None, 'rows': 0}
    y = predictions.sales.to_numpy(float)
    error = predictions.prediction.to_numpy(float) - y
    if not np.isfinite(y).all() or not np.isfinite(error).all() or (y < 0).any():
        raise ValueError('Forecast metrics require finite predictions and nonnegative finite actuals.')
    return {'MAE': float(np.abs(error).mean()), 'RMSE': float(np.sqrt((error ** 2).mean())),
            'WAPE': float(np.abs(error).sum() / y.sum()) if y.sum() else None,
            'bias_units_per_day': float(error.mean()), 'rows': len(y)}


def training_scales(features, train_end):
    # Normalization for residual pooling, not an M5 RMSSE denominator.
    return (features[features.day <= train_end].groupby('id').sales.mean() + 1).to_dict()


def calibrate(predictions, scales, alpha=0.10):
    p = predictions.copy()
    p['score'] = (p.sales - p.prediction).abs() / p.id.map(scales)
    radii = {}
    for horizon, rows in p.groupby('horizon'):
        scores = np.sort(rows.score.to_numpy())
        rank = math.ceil((len(scores) + 1) * (1 - alpha))
        if rank > len(scores):
            raise ValueError('Insufficient calibration scores for the requested interval level.')
        radii[str(int(horizon))] = float(scores[rank - 1])
    return {'alpha': alpha, 'radii_by_horizon': radii, 'scales_by_series': scales,
            'method': 'Pooled scale-normalized absolute residual quantile by horizon',
            'guarantee': 'Nominal 90%; no distribution-free coverage claim for dependent M5 series.'}


def add_intervals(predictions, calibration):
    p = predictions.copy()
    radius = p.horizon.astype(str).map(calibration['radii_by_horizon']) * p.id.map(calibration['scales_by_series'])
    if radius.isna().any():
        raise ValueError('Calibration does not cover these horizons or series.')
    p['lower'] = np.maximum(0, p.prediction - radius)
    p['upper'] = p.prediction + radius
    return p


def interval_metrics(p, alpha=0.10):
    if not 0 < alpha < 1:
        raise ValueError('Interval alpha must be strictly between zero and one.')
    unavailable = {'coverage': None, 'mean_width': None, 'mean_interval_score': None}
    if p.empty or not {'lower', 'upper', 'sales'}.issubset(p):
        return unavailable
    # Do not silently compute coverage on a smaller population than the point metrics.
    if p[['lower', 'upper', 'sales']].isna().any().any():
        return unavailable
    if not np.isfinite(p[['lower','upper','sales']].to_numpy(float)).all() or p.lower.gt(p.upper).any():
        raise ValueError('Interval metrics require finite ordered bounds.')
    width = p.upper - p.lower
    score = width + 2 / alpha * (p.lower - p.sales).clip(lower=0) + 2 / alpha * (p.sales - p.upper).clip(lower=0)
    return {'coverage': float(p.sales.between(p.lower, p.upper).mean()),
            'mean_width': float(width.mean()), 'mean_interval_score': float(score.mean())}
