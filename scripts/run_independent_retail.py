"""Execute the frozen UCI replication once; never overwrite an existing checkpoint."""
from pathlib import Path
import argparse, hashlib, io, json, sys, zipfile
from datetime import datetime, timezone
from itertools import product
from dataclasses import replace
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from supplysense.forecast import point_metrics, interval_metrics
from supplysense.inventory import Assumptions, simulate
from supplysense.research import compare_models

def digest(b): return hashlib.sha256(b).hexdigest()
def write_json(path,obj): path.write_text(json.dumps(obj,indent=2,default=str,allow_nan=False),encoding='utf-8')

def features(y,origin,dates):
    """origin is the count of observed days; features cannot see y[:, origin:]."""
    h=np.arange(1,29)
    n=len(y)
    history=y[:,:origin]
    summary=np.column_stack([history[:,-1],history[:,-7],history[:,-28],
        history[:,-7:].mean(1),history[:,-28:].mean(1),history[:,-56:].mean(1),
        (history[:,-28:]==0).mean(1)])
    return pd.DataFrame(np.column_stack([np.repeat(np.arange(n),28),np.tile(h,n),
        np.tile(dates[origin:origin+28].dayofweek,n),np.repeat(summary,28,axis=0)]),
        columns=['series','horizon','weekday','last','lag7','lag28','mean7','mean28','mean56','zero28'])

def sba(y,alpha=.1):
    out=[]
    for row in y:
        nz=np.flatnonzero(row>0)
        if not len(nz): out.append(0.);continue
        z=float(row[nz[0]]); interval=float(nz[0]+1); last=nz[0]
        for i in nz[1:]:
            z=alpha*row[i]+(1-alpha)*z
            interval=alpha*(i-last)+(1-alpha)*interval;last=i
        out.append((1-alpha/2)*z/interval)
    return np.asarray(out)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True);args=parser.parse_args()
    out=ROOT/'results/independent';out.mkdir(exist_ok=False)
    protocol_bytes=(ROOT/'docs/INDEPENDENT_PROTOCOL.json').read_bytes();protocol=json.loads(protocol_bytes)
    write_json(out/'freeze.json',{'started_utc':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':digest(protocol_bytes),'script_sha256':digest(Path(__file__).read_bytes()),
        'source_sha256':digest(args.data.read_bytes()),'original_data_path_published':False})
    with zipfile.ZipFile(args.data) as z:
        name=next(n for n in z.namelist() if n.endswith('.xlsx'))
        raw=pd.read_excel(io.BytesIO(z.read(name)),usecols=['InvoiceNo','StockCode','Quantity','InvoiceDate','UnitPrice','Country'])
    raw_count=len(raw);dupes=int(raw.duplicated().sum());raw=raw.drop_duplicates()
    keep=(raw.Country.eq('United Kingdom') & raw.Quantity.gt(0) & raw.UnitPrice.gt(0)
          & ~raw.InvoiceNo.astype(str).str.upper().str.startswith('C')
          & raw.StockCode.astype(str).str.fullmatch(r'\d{5}[A-Za-z]*'))
    raw=raw[keep].copy();raw['date']=pd.to_datetime(raw.InvoiceDate).dt.normalize()
    raw['id']=raw.StockCode.astype(str)
    cutoff=pd.Timestamp(protocol['selection_end']);dates=pd.date_range(protocol['day_one'],'2011-12-08')
    hist=raw[raw.date.le(cutoff)].groupby(['id','date']).Quantity.sum()
    candidates=hist.reset_index().groupby('id').agg(nonzero=('date','nunique'),first=('date','min'))
    candidates=candidates[(candidates.nonzero>=10)&(candidates['first']<=dates[59])]
    ids=sorted(candidates.index,key=lambda s:digest(('42:'+s).encode()))[:90]
    assert len(ids)==90
    table=raw[raw.id.isin(ids)].groupby(['id','date']).Quantity.sum().unstack(fill_value=0).reindex(index=ids,columns=dates,fill_value=0)
    y=table.to_numpy(float);end=int((cutoff-dates[0]).days+1)
    positive=(y[:,:end]>0).sum(1);adi=end/positive
    groups=np.where(adi>1.32,'Intermittent','Frequent')
    manifest=pd.DataFrame({'id':ids,'store_id':'UK_online','cat_id':groups,'ADI':adi,
        'CV_squared':[float(np.var(r[r>0])/np.mean(r[r>0])**2) for r in y[:,:end]],
        'training_mean':y[:,:end].mean(1)})
    manifest.to_csv(out/'subset_manifest.csv',index=False)
    budget_reference=float(y[:,:end].mean(1).sum()*28*2)
    write_json(out/'data_audit.json',{'raw_rows':raw_count,'duplicates_removed_used_columns':dupes,
        'retained_transaction_rows':len(raw),'eligible_products':len(candidates),'selected_products':90,
        'selection_end':str(cutoff.date()),'training_zero_fraction':float((y[:,:end]==0).mean()),
        'group_counts':manifest.cat_id.value_counts().to_dict(),'budget_reference_CU':budget_reference,
        'source':protocol['dataset'],'customer_fields_read':False,'zero_assumption':'No recorded positive sale = zero proxy; availability unknown'})
    train_origins=range(56,end-27)
    X=pd.concat([features(y,o,dates) for o in train_origins],ignore_index=True)
    target=np.concatenate([y[:,o:o+28].reshape(-1) for o in train_origins])
    model=LGBMRegressor(objective='poisson',n_estimators=120,num_leaves=15,learning_rate=.05,
        min_child_samples=30,random_state=42,n_jobs=2,verbosity=-1,deterministic=True,force_col_wise=True)
    model.fit(X,target);model.booster_.save_model(str(out/'lightgbm_direct_model.txt'))
    frames=[]
    for split in ['validation','calibration','test']:
        for stamp in protocol[split+'_origins']:
            o=int((pd.Timestamp(stamp)-dates[0]).days+1)
            predictions={'seasonal_naive':np.tile(y[:,o-7:o],(1,4)),
                'mean_28':np.repeat(y[:,o-28:o].mean(1)[:,None],28,axis=1),
                'croston_sba':np.repeat(sba(y[:,:o])[:,None],28,axis=1),
                'lightgbm_direct':model.predict(features(y,o,dates)).reshape(90,28)}
            for name,pred in predictions.items():
                frames.append(pd.DataFrame({'id':np.repeat(ids,28),'store_id':'UK_online','cat_id':np.repeat(groups,28),
                    'date':np.tile(dates[o:o+28],90),'day':np.tile(np.arange(o+1,o+29),90),'origin':o,
                    'horizon':np.tile(np.arange(1,29),90),'model':name,'prediction':pred.reshape(-1),
                    'sales':y[:,o:o+28].reshape(-1),'split':split}))
    p=pd.concat(frames,ignore_index=True)
    # Selection uses validation only; calibration never changes weights or champion.
    scores=pd.DataFrame([{'model':m,**point_metrics(g)} for m,g in p[p.split.eq('validation')].groupby('model')])
    champion=scores.sort_values(['MAE','model']).iloc[0].model
    write_json(out/'selection.json',{'champion':champion,'selected_using':'validation MAE only','model_refit':False})
    cal=p[p.split.eq('calibration')].copy();cal['abs_error']=abs(cal.sales-cal.prediction)
    radii=cal.groupby(['model','id']).abs_error.apply(lambda a:float(np.sort(a)[min(len(a),int(np.ceil((len(a)+1)*.9)))-1]))
    p=p.join(radii.rename('radius'),on=['model','id']);p['lower']=(p.prediction-p.radius).clip(lower=0);p['upper']=p.prediction+p.radius
    p.to_csv(out/'all_predictions.csv',index=False)
    metrics=pd.DataFrame([{'split':split,'model':m,**point_metrics(g),**interval_metrics(g)} for (split,m),g in p.groupby(['split','model'])])
    metrics.to_csv(out/'metrics.csv',index=False)
    per_origin=pd.DataFrame([{'origin':o,'model':m,**point_metrics(g),**interval_metrics(g)} for (o,m),g in p[p.split.eq('test')].groupby(['origin','model'])])
    per_origin.to_csv(out/'test_origin_metrics.csv',index=False)
    test=p[p.split.eq('test')];sim_rows=[];group_rows=[]
    for o,g in test.groupby('origin'):
        for ratio,lead,short in product([.5,1,2],[1,3,7],[1,5,10]):
            a=Assumptions(budget=budget_reference*ratio,lead_days=lead,shortage_penalty=short)
            scenario=f'b{ratio}_l{lead}_s{short}'
            result=compare_models(g,a,scenario_id=scenario,family='independent')
            result['origin']=o;result['budget_ratio']=ratio;sim_rows.append(result)
            for m,mg in g.groupby('model'):
                trace,_=simulate(mg,a)
                trace=trace.merge(manifest[['id','cat_id']],on='id',validate='many_to_one')
                for cat,t in trace.groupby('cat_id'):
                    demand=float(t.demand.sum());lost=float(t.lost_units.sum())
                    group_rows.append({'origin':o,'scenario_id':scenario,'model':m,'group':cat,'budget_ratio':ratio,
                        'lead_days':lead,'shortage_penalty':short,'MAE':point_metrics(mg[mg.cat_id.eq(cat)])['MAE'],
                        'simulated_total_cost':float(t[['procurement_spend','order_fees','holding_cost','shortage_cost']].sum().sum()),
                        'fill_rate':1-lost/demand if demand else None,'lost_units':lost,
                        'note':'Group outcome within full shared-budget simulation; not a separate budget'})
    simulations=pd.concat(sim_rows,ignore_index=True);simulations.to_csv(out/'sensitivity_results.csv',index=False)
    pd.DataFrame(group_rows).to_csv(out/'intermittency_results.csv',index=False)
    # Paired product clusters preserve the complete two-origin path for each product.
    loss=test.assign(error=abs(test.sales-test.prediction)).groupby(['id','model']).error.mean().unstack()
    rng=np.random.default_rng(42);draw=rng.integers(0,len(loss),(2000,len(loss)));ci=[]
    for m in loss:
        diff=(loss[m]-loss.seasonal_naive).to_numpy();rep=diff[draw].mean(1)
        ci.append({'model':m,'MAE_difference_vs_seasonal':float(diff.mean()),'conditional_95_low':float(np.quantile(rep,.025)),
                   'conditional_95_high':float(np.quantile(rep,.975)),'clusters':len(loss),'replicates':2000})
    pd.DataFrame(ci).to_csv(out/'mae_cluster_intervals.csv',index=False)
    last=int(test.origin.max());latest=test[test.origin.eq(last)].drop(columns=['split','radius'])
    history=pd.DataFrame({'id':np.repeat(ids,84),'day':np.tile(np.arange(last-83,last+1),90),
        'date':np.tile(dates[last-84:last],90),'sales':y[:,last-84:last].reshape(-1)})
    settings={'schema_version':3,'dataset':'UCI Online Retail','date_base':protocol['day_one'],'evaluation_series':90,
        'run_id':protocol['protocol_id'],'status':'complete','test_evaluated':True,'test_origin':last,'horizon':28,
        'validation_champion':champion,'models':protocol['models'],'source_license':'CC BY 4.0',
        'source_citation':protocol['dataset'],'protocol_sha256':digest(protocol_bytes),'interval_alpha':.1,
        'scope':'Public dashboard shows last origin; independent report includes both test origins; inspected after execution.'}
    members={'experiment.json':json.dumps(settings).encode(),'test_predictions.csv':latest.to_csv(index=False).encode(),
        'history.csv':history.to_csv(index=False).encode(),'metrics.csv':metrics.to_csv(index=False).encode(),
        'subset_manifest.csv':manifest.to_csv(index=False).encode(),'data_audit.json':(out/'data_audit.json').read_bytes(),
        'validation_predictions.csv':p[p.split.eq('validation')].drop(columns=['lower','upper','radius','split']).to_csv(index=False).encode()}
    members['checksums.json']=json.dumps({k:digest(v) for k,v in members.items()}).encode()
    with zipfile.ZipFile(ROOT/'results/public_results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for k,v in members.items(): z.writestr(k,v)
    assert len(simulations)==216
    write_json(out/'execution.json',{'completed_utc':datetime.now(timezone.utc).isoformat(),'simulations':len(simulations),
        'test_origins':2,'test_observations_per_model':5040,'champion':champion,'training_rows':len(X),
        'protocol_sha256':digest(protocol_bytes),'claims':'Independent dataset replication; now inspected; no significance or novelty claim'})
    write_json(out/'checksums.json',{f.name:digest(f.read_bytes()) for f in out.iterdir() if f.is_file()})
    print(metrics[metrics.split.eq('test')].to_string(index=False))
    print('Independent evaluation complete. Original M5 artifacts untouched.')

if __name__=='__main__': main()
