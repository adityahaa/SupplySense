"""Colab experiment stages; final test labels are scored only after choices freeze."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.metadata
import shutil
import subprocess
import sys
import time
import numpy as np
import pandas as pd
from .data import read_inputs, write_json
from .forecast import (FEATURES, CATEGORICAL, CANDIDATES, make_features, block,
                       predict_block, attach_actuals, point_metrics, training_scales,
                       calibrate, add_intervals, interval_metrics)


def prepare(zip_path, output_root='runs'):
    data, subset, audit = read_inputs(zip_path)
    if audit['last_day'] != 1941 or len(subset) != 90:
        raise ValueError('This protocol expects d_1..d_1941 and 90 selected series.')
    features, mappings = make_features(data)
    run = Path(output_root) / datetime.now(timezone.utc).strftime('m5_%Y%m%dT%H%M%S_%fZ')
    run.mkdir(parents=True, exist_ok=False)
    subset.to_csv(run / 'subset_manifest.csv', index=False)
    write_json(run / 'data_audit.json', audit)
    # Hash the original archive without loading it all into memory.
    digest = hashlib.sha256()
    with open(zip_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    settings = {
        'schema_version': 1, 'run_id': run.name, 'status': 'prepared', 'seed': 42,
        'horizon': 28, 'train_end': 1829, 'validation_origin': 1829,
        'calibration_origins': [1857, 1885], 'test_origin': 1913, 'test_end': 1941,
        'train_start_day': 57, 'selection_metric': 'validation MAE across 90 series x 28 days',
        'alpha': .10, 'candidates': CANDIDATES, 'source_zip_sha256': digest.hexdigest(),
        'versions': {p: importlib.metadata.version(p) for p in
                     ['numpy', 'pandas', 'lightgbm', 'scikit-learn']},
        'python_version': sys.version, 'test_evaluated': False,
        'refit_policy': 'Frozen at d_1829; no refit after calibration.',
        'scope': 'Historical M5 subset experiment; not current demand or official WRMSSE.',
    }
    write_json(run / 'experiment.json', settings)
    write_json(run / 'preprocessing.json', {
        'features': FEATURES, 'categorical_features': CATEGORICAL, 'mappings': mappings,
        'sales_lags': [28, 35, 56], 'rolling_shift': 28,
        'price_handling': 'Per-series forward fill then shift 28; remaining missing preserved.',
        'event_nulls': 'No named event; converted to event-presence indicator.',
        'calendar_assumption': 'Holiday and SNAP calendar known at the forecast origin.',
        'id': 'item_id + underscore + store_id', 'calendar_day_1': '2011-01-29',
        'training_rows': 'd_57..d_1829; all sampled series, including leading zeros',
    })
    return {'data': data, 'features': features, 'run': run, 'settings': settings}


def fit_and_select(state):
    if state['settings']['status'] != 'prepared':
        raise ValueError('Model selection is already frozen for this run. Preserve the existing results.')
    from lightgbm import LGBMRegressor
    f, settings, run = state['features'], state['settings'], state['run']
    training = f[f.day.between(57, settings['train_end'])]
    models = {'seasonal_naive': None}
    predictions, rows = [], []
    for name in ['seasonal_naive', *CANDIDATES]:
        started = time.perf_counter()
        if name != 'seasonal_naive':
            model = LGBMRegressor(objective='regression_l1', learning_rate=.05,
                random_state=42, n_jobs=2, verbosity=-1, deterministic=True,
                force_col_wise=True, **CANDIDATES[name])
            model.fit(training[FEATURES], training.sales, categorical_feature=CATEGORICAL)
            models[name] = model
        p = attach_actuals(predict_block(models[name], f, 1829), state['data'])
        p['model'] = name; p['split'] = 'validation'
        predictions.append(p)
        rows.append({'model': name, 'split': 'validation', **point_metrics(p),
                     'fit_predict_seconds': time.perf_counter() - started})
        print(name, rows[-1])
    table = pd.DataFrame(rows)
    chosen = table[table.model.ne('seasonal_naive')].sort_values(['MAE', 'model']).iloc[0].model
    champion = table.sort_values(['MAE', 'model']).iloc[0].model
    models[chosen].booster_.save_model(str(run / 'lightgbm_model.txt'))
    settings.update({'selected_booster': chosen, 'validation_champion': champion,
                     'selected_model_parameters': models[chosen].get_params(),
                     'baseline': 'Repeat the last seven observed days across the 28-day horizon',
                     'status': 'model_selection_frozen'})
    write_json(run / 'experiment.json', settings)
    table.to_csv(run / 'validation_metrics.csv', index=False)
    pd.concat(predictions).to_csv(run / 'validation_predictions.csv', index=False)
    state.update({'models': {'seasonal_naive': None, chosen: models[chosen]},
                  'validation_metrics': table})
    return table


def calibrate_models(state):
    if state['settings']['status'] != 'model_selection_frozen':
        raise ValueError('Calibration requires freshly frozen model selection and runs once per run.')
    scales = training_scales(state['features'], 1829)
    calibration, frames = {}, []
    for name, model in state['models'].items():
        p = pd.concat([attach_actuals(predict_block(model, state['features'], origin), state['data'])
                       for origin in [1857, 1885]], ignore_index=True)
        calibration[name] = calibrate(p, scales)
        p = add_intervals(p, calibration[name]); p['model'] = name; p['split'] = 'calibration'
        frames.append(p)
    state['calibration'] = calibration
    write_json(state['run'] / 'calibration.json', calibration)
    pd.concat(frames).to_csv(state['run'] / 'calibration_predictions.csv', index=False)
    state['settings']['status'] = 'calibration_frozen'
    write_json(state['run'] / 'experiment.json', state['settings'])
    return pd.DataFrame([{'model': name, 'calibration_blocks': 2,
                          'scores_per_horizon': 180, 'nominal_coverage': .90}
                         for name in calibration])


def evaluate_final_test(state):
    if state['settings']['status'] != 'calibration_frozen':
        raise ValueError('Select models and freeze calibration before testing. Test stage runs once per run.')
    frames, rows, detailed = [], [], []
    for name, model in state['models'].items():
        # Predictions are made and frozen before this function joins final test labels.
        p = add_intervals(predict_block(model, state['features'], 1913), state['calibration'][name])
        p = attach_actuals(p, state['data'])
        p['model'] = name; p['split'] = 'test'; frames.append(p)
        rows.append({'model': name, 'split': 'test', **point_metrics(p), **interval_metrics(p)})
        for series, g in p.groupby('id'):
            detailed.append({'id': series, 'model': name, **point_metrics(g), **interval_metrics(g)})
    final = pd.concat(frames, ignore_index=True)
    final.to_csv(state['run'] / 'test_predictions.csv', index=False)
    pd.DataFrame(detailed).to_csv(state['run'] / 'per_series_metrics.csv', index=False)
    metrics = pd.concat([state['validation_metrics'], pd.DataFrame(rows)], ignore_index=True)
    metrics.to_csv(state['run'] / 'metrics.csv', index=False)
    # The dashboard receives only recent history available at the test origin.
    state['data'][state['data'].day.between(1746, 1913)][
        ['id', 'item_id', 'store_id', 'cat_id', 'date', 'day', 'sales']
    ].to_csv(state['run'] / 'history.csv', index=False)
    state['settings'].update({'test_evaluated': True, 'status': 'complete',
        'completed_utc': datetime.now(timezone.utc).isoformat()})
    write_json(state['run'] / 'experiment.json', state['settings'])
    state['test_predictions'] = final
    return metrics


def export_bundle(state):
    if not state['settings']['test_evaluated']:
        raise ValueError('Run final evaluation before exporting a dashboard bundle.')
    run = state['run']
    # Include exact source alongside package versions for a reproducible handoff.
    source = run / 'source'
    source.mkdir(exist_ok=True)
    for p in Path(__file__).parent.glob('*.py'):
        shutil.copy2(p, source / p.name)
    (run / 'environment.txt').write_text(subprocess.check_output(
        [sys.executable, '-m', 'pip', 'freeze'], text=True), encoding='utf-8')
    write_json(run / 'checksums.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in run.iterdir() if p.is_file() and p.name != 'checksums.json'})
    return Path(shutil.make_archive(str(run), 'zip', root_dir=run))
