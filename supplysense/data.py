"""Read both the supplied M5 research archive and the Kaggle CSV schema."""
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

META = ['item_id', 'dept_id', 'cat_id', 'store_id', 'state_id']
REQUIRED = ['sales_train_evaluation.csv', 'calendar.csv', 'sell_prices.csv']


def read_inputs(zip_path, per_stratum=3, seed=42):
    """Select via identifiers only; stream sales/prices to bound laptop RAM."""
    with zipfile.ZipFile(zip_path) as z:
        members = {}
        for name in REQUIRED:
            matches = [n for n in z.namelist() if Path(n).name == name]
            if len(matches) != 1:
                raise ValueError(f'Need exactly one {name}; found {len(matches)}')
            members[name] = matches[0]
        with z.open(members[REQUIRED[0]]) as f:
            meta = pd.read_csv(f, usecols=META)
        if meta.isna().any().any() or meta.duplicated(['item_id', 'store_id']).any():
            raise ValueError('Sales metadata has nulls or duplicate item/store keys.')
        meta['id'] = meta.item_id + '_' + meta.store_id
        if not meta.id.is_unique:
            raise ValueError('Constructed series identifiers collide.')
        meta['sample_key'] = meta.id.map(
            lambda x: hashlib.sha256(f'{seed}:{x}'.encode()).hexdigest())
        selected = (meta.sort_values('sample_key').groupby(['store_id', 'cat_id'])
                    .head(per_stratum).sort_values('id').drop(columns='sample_key'))
        chunks = []
        for c in pd.read_csv(z.open(members[REQUIRED[0]]), chunksize=1000):
            keys = c.item_id + '_' + c.store_id
            keep = keys.isin(selected.id)
            part = c.loc[keep].copy()
            part['id'] = keys[keep]
            chunks.append(part)
        sales = pd.concat(chunks, ignore_index=True)
        days = sorted([c for c in sales if c.startswith('d_')], key=lambda c: int(c[2:]))
        if days != [f'd_{i}' for i in range(1, len(days) + 1)]:
            raise ValueError('Sales day columns must be consecutive from d_1.')
        a = sales[days].to_numpy(dtype=float)
        if not np.isfinite(a).all() or (a < 0).any() or (a != np.floor(a)).any():
            raise ValueError('Sales must be nonnegative, nonmissing integer counts.')
        cal = pd.read_csv(z.open(members[REQUIRED[1]]))
        cal['date'] = pd.to_datetime(cal.date)
        cal = cal.sort_values('date').reset_index(drop=True)
        if cal.date.iloc[0] != pd.Timestamp('2011-01-29'):
            raise ValueError('Cannot map d_1: expected calendar start 2011-01-29.')
        if cal.date.duplicated().any() or not cal.date.diff().dropna().eq(pd.Timedelta(days=1)).all():
            raise ValueError('Calendar dates have duplicates or gaps.')
        derived = 'd_' + ((cal.date - pd.Timestamp('2011-01-29')).dt.days + 1).astype(str)
        if 'd' in cal and not cal.d.eq(derived).all():
            raise ValueError('Calendar d labels disagree with dates.')
        cal['d'] = derived
        if not set(days).issubset(set(cal.d)):
            raise ValueError('Calendar does not cover all sales days.')
        pairs = set(zip(selected.item_id, selected.store_id))
        price_chunks = []
        for c in pd.read_csv(z.open(members[REQUIRED[2]]), chunksize=250000):
            price_chunks.append(c[[p in pairs for p in zip(c.item_id, c.store_id)]])
        prices = pd.concat(price_chunks, ignore_index=True)
        keys = ['item_id', 'store_id', 'wm_yr_wk']
        if prices.duplicated(keys).any() or prices.isna().any().any() or prices.sell_price.le(0).any():
            raise ValueError('Selected prices have duplicate keys, missing or nonpositive values.')
        long = sales.melt(id_vars=META + ['id'], value_vars=days, var_name='d', value_name='sales')
        long = long.merge(cal, on='d', validate='many_to_one')
        long = long.merge(prices, on=keys, how='left', validate='many_to_one')
        long['day'] = long.d.str[2:].astype(int)
        long = long.sort_values(['id', 'day']).reset_index(drop=True)
        audit = {
            'series': len(selected), 'daily_rows': len(long), 'last_day': len(days),
            'missing_sales': int(long.sales.isna().sum()),
            'zero_sales_fraction': float(long.sales.eq(0).mean()),
            'missing_price_rows': int(long.sell_price.isna().sum()),
            'missing_price_positive_sales_rows': int((long.sell_price.isna() & long.sales.gt(0)).sum()),
            'calendar_missing_by_column': cal.isna().sum().astype(int).to_dict(),
            'sample_rule': f'SHA256({seed}:item_id_store_id); {per_stratum} per store/category',
            'source_members': {k: {'member': v, 'crc32': z.getinfo(v).CRC,
                                   'bytes': z.getinfo(v).file_size} for k, v in members.items()},
        }
        return long, selected, audit


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str), encoding='utf-8')
