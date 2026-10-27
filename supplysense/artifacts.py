"""Read a bounded result bundle without extracting or executing uploaded code."""
import hashlib
import io
import json
import zipfile
import numpy as np
import pandas as pd

REQUIRED = ['experiment.json', 'test_predictions.csv', 'history.csv', 'metrics.csv',
            'subset_manifest.csv', 'data_audit.json', 'checksums.json']


def load_bundle(payload):
    if len(payload) > 100 * 1024 * 1024:
        raise ValueError('Result bundle exceeds 100 MB; upload the Colab results ZIP, not the dataset ZIP.')
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:
            raise ValueError('Expanded result bundle exceeds 200 MB.')
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate ZIP member names.')
        missing = set(REQUIRED) - set(z.namelist())
        if missing:
            raise ValueError(f'Missing result files: {sorted(missing)}. Upload the exported Colab results ZIP.')
        checksums = json.loads(z.read('checksums.json'))
        if not isinstance(checksums, dict):
            raise ValueError('Malformed artifact checksum manifest.')
        for name in set(REQUIRED[:-1]) | set(checksums):
            if name not in z.namelist() or hashlib.sha256(z.read(name)).hexdigest() != checksums.get(name):
                raise ValueError(f'Checksum mismatch for {name}. Re-export the result bundle.')
        settings = json.loads(z.read('experiment.json'))
        if settings.get('schema_version') not in [1,2,3] or settings.get('status') != 'complete' or not settings.get('test_evaluated'):
            raise ValueError('Need a completed SupplySense schema-v1 or schema-v2 experiment.')
        result = {'settings': settings, 'audit': json.loads(z.read('data_audit.json')),
                  'bundle_sha256': hashlib.sha256(payload).hexdigest()}
        for name in ['test_predictions', 'history', 'metrics', 'subset_manifest']:
            result[name] = pd.read_csv(io.BytesIO(z.read(name + '.csv')), float_precision='round_trip')
        p = result['test_predictions']
        required_columns = {'id','model','date','store_id','cat_id','sales','prediction','day','horizon','origin'}
        if not required_columns.issubset(p):
            raise ValueError('Prediction columns do not match the artifact contract.')
        if p.duplicated(['model','id','day']).any():
            raise ValueError('Duplicate predictions.')
        if p[list(required_columns)].isna().any().any():
            raise ValueError('Prediction identifiers, actuals and dates must be complete.')
        nums = p[['sales','prediction']].to_numpy(float)
        if not np.isfinite(nums).all() or (nums < 0).any():
            raise ValueError('Invalid finite, nonnegative prediction counts.')
        if ('lower' in p) != ('upper' in p):
            raise ValueError('Both lower and upper bounds are needed when intervals are supplied.')
        if 'lower' not in p:
            p['lower'] = np.nan; p['upper'] = np.nan
        result['has_intervals_by_model'] = {}
        for name, group in p.groupby('model'):
            bounds = group[['lower', 'upper']]
            if bounds.isna().all().all():
                result['has_intervals_by_model'][name] = False
            elif bounds.isna().any().any() or not np.isfinite(bounds.to_numpy(float)).all() or group.lower.lt(0).any() or group.lower.gt(group.prediction).any() or group.prediction.gt(group.upper).any():
                raise ValueError('Invalid or partially missing interval bounds.')
            else:
                result['has_intervals_by_model'][name] = True
        result['has_intervals'] = all(result['has_intervals_by_model'].values())
        if result['subset_manifest'].id.isna().any() or result['subset_manifest'].id.duplicated().any():
            raise ValueError('The evaluation manifest must contain unique nonmissing identifiers.')
        ids = set(result['subset_manifest'].id)
        models = set(settings['models']) if settings.get('schema_version') in [2,3] else {'seasonal_naive', settings['selected_booster']}
        if set(p.model) != models or set(p.id) != ids or len(ids) != 90:
            raise ValueError('Unexpected model or series coverage.')
        origin = settings.get('test_origin', 1913)
        independent = settings.get('schema_version') == 3
        if independent and (settings.get('dataset') != 'UCI Online Retail' or settings.get('date_base') != '2010-12-01'
                            or settings.get('evaluation_series') != 90 or origin != 345):
            raise ValueError('Unsupported independent evaluation contract.')
        date_base = pd.Timestamp('2010-12-01' if independent else '2011-01-29')
        if not independent and origin not in [1913,1941]:
            raise ValueError('Unsupported M5 evaluation origin.')
        if not p.origin.eq(origin).all() or not p.day.eq(p.horizon + origin).all():
            raise ValueError('Unexpected forecast origin.')
        for _, g in p.groupby(['model','id']):
            if sorted(g.horizon.tolist()) != list(range(1,29)):
                raise ValueError('Incomplete 28-day prediction horizon.')
        # Equal counts alone do not establish comparable model populations or labels.
        reference = None
        for _, g in p.groupby('model'):
            if set(g.id) != ids:
                raise ValueError('Models must cover the same evaluation series.')
            obs = g.sort_values(['id','day'])[['id','day','sales','store_id','cat_id']].reset_index(drop=True)
            if reference is not None and not obs.equals(reference):
                raise ValueError('Models must share identical observations, actual sales and metadata.')
            reference = obs
        if settings.get('validation_champion') not in models:
            raise ValueError('The declared validation champion is unavailable in the saved predictions.')
        p['date'] = pd.to_datetime(p.date)
        expected_dates = date_base + pd.to_timedelta(p.day - 1, unit='D')
        if not p.date.eq(expected_dates).all():
            raise ValueError('Forecast dates disagree with M5 day indices.')
        h = result['history']
        if not {'id','day','date','sales'}.issubset(h):
            raise ValueError('Historical observations are missing required columns.')
        h['date'] = pd.to_datetime(h.date, errors='coerce')
        if h[['id','day','date','sales']].isna().any().any() or h.duplicated(['id','day']).any():
            raise ValueError('Historical observations contain missing values or duplicate keys.')
        if not set(h.id).issubset(ids) or h.day.gt(origin).any():
            raise ValueError('History must stop at the forecast origin and use the evaluated series.')
        if not h.date.eq(date_base+pd.to_timedelta(h.day-1,unit='D')).all():
            raise ValueError('Historical dates disagree with M5 day indices.')
        if not np.isfinite(h.sales.to_numpy(float)).all() or h.sales.lt(0).any():
            raise ValueError('Historical sales must be finite and nonnegative.')
        for optional in ['validation_predictions','validation_fold_metrics','validation_metrics','inventory_comparison']:
            filename = optional + '.csv'
            if filename in z.namelist():
                if filename not in checksums:
                    raise ValueError(f'Missing checksum for {filename}.')
                result[optional] = pd.read_csv(io.BytesIO(z.read(filename)), float_precision='round_trip')
        return result
