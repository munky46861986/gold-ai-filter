"""Offline causal feature audit for v48.9 G1 retest. No broker or live code.

Input trades are frozen historical G1_SEQ_RETEST proposals from v48.9.
All new features are computed from M1 candles *strictly before the entry time*.
The MT4 clock and bid assumption remain uncertain; see report.
"""
import argparse
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd

SOURCE_NAMING = ('g1_seq_retest_trades.csv', 'holdout_2018_2021/g1_seq_retest_trades.csv')


def load_trades(zip_path):
    with ZipFile(zip_path) as z:
        sources = [pd.read_csv(z.open(n), float_precision='round_trip') for n in SOURCE_NAMING]
    out = pd.concat(sources, ignore_index=True)
    if out.duplicated(['decision', 'side', 'spread']).any():
        raise ValueError('Duplicated decision/side/spread')
    return out.sort_values(['decision','side','spread']).reset_index(drop=True)


def merged_windows(trades, pre_min=370):
    starts=[]
    keys=trades[['decision','sweep_end']].drop_duplicates()
    for d, s in keys.itertuples(index=False):
        start=datetime.fromisoformat(s)-timedelta(minutes=pre_min)
        end=datetime.fromisoformat(d)  # strictly exclude entry candle
        starts.append((start, end))
    intervals=[]
    for a,b in sorted(starts):
        if intervals and a<=intervals[-1][1]+timedelta(minutes=1):
            intervals[-1]=(intervals[-1][0],max(b,intervals[-1][1]))
        else:
            intervals.append((a,b))
    return [(a.strftime('%Y.%m.%d %H:%M'),b.strftime('%Y.%m.%d %H:%M')) for a,b in intervals]


def load_selected_bars(source_zip, intervals):
    """Only read M1 within ex-ante feature windows; single streaming pass."""
    starts=[a for a,_ in intervals]
    candles={}
    found=0
    with ZipFile(source_zip) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1: raise ValueError('expected one CSV')
        with z.open(names[0]) as src:
            for raw in src:
                # sort-preserving MT4 format: YYYY.MM.DD,HH:MM
                key=raw[:10].decode('ascii','ignore')+' '+raw[11:16].decode('ascii','ignore')
                j=bisect_left(starts,key)
                # previous interval may include the current key
                i=j-1 if j else 0
                if not (starts[i]<=key<=intervals[i][1]):
                    if j>=len(intervals) or not (starts[j]<=key<=intervals[j][1]):
                        continue
                parts=raw.decode('utf-8-sig').strip().split(',')
                if len(parts)<6: continue
                vals=tuple(float(k) for k in parts[2:6])
                if key in candles:raise ValueError('duplicate OHLC '+key)
                candles[key]=vals;found+=1
    return candles


def key_at(dt):return dt.strftime('%Y.%m.%d %H:%M')


def candle_bucket(bars, end, duration):
    """Return exact full closed OHLC of [end-duration,end); None for missing bars."""
    rows=[]
    for n in range(duration,0,-1):
        v=bars.get(key_at(end-timedelta(minutes=n)))
        if v is None:return None
        rows.append(v)
    return (rows[0][0],max(r[1] for r in rows),min(r[2] for r in rows),rows[-1][3])


def causal_features(event, bars):
    """Never uses timestamps >= decision, i.e., the entry candle is unavailable."""
    decision=datetime.fromisoformat(event['decision'])
    sweep_end=datetime.fromisoformat(event['sweep_end'])
    prev=[]
    for k in range(15,0,-1):
        row=candle_bucket(bars,sweep_end-timedelta(minutes=k*15),15)
        if row is None:return None
        prev.append(row)
    sweep=candle_bucket(bars,sweep_end,15)
    retest=candle_bucket(bars,decision,5)
    if sweep is None or retest is None or sweep_end>=decision: return None
    old=prev[-8:]
    side=event['side'];level=max(x[1] for x in old) if side=='SELL' else min(x[2] for x in old)
    sweep_depth=(sweep[1]-level) if side=='SELL' else (level-sweep[2])
    reclaim=(level-sweep[3]) if side=='SELL' else (sweep[3]-level)
    # 14 completed M15 ATR, using previous candle close (all prior to sweep).
    trs=[]
    for i in range(1,len(prev)):
        o,h,l,c=prev[i];pclose=prev[i-1][3]
        trs.append(max(h-l,abs(h-pclose),abs(l-pclose)))
    atr=sum(trs)/len(trs) if trs else np.nan
    o,h,l,c=retest
    rang=max(h-l,1e-9)
    wick=(h-max(o,c))/rang if side=='SELL' else (min(o,c)-l)/rang
    micro=float(event['micro_level'])
    close_beyond=(micro-c) if side=='SELL' else (c-micro)
    penetr=(h-micro) if side=='SELL' else (micro-l)
    return {'atr15_prev':atr,'sweep_depth':sweep_depth,'sweep_depth_atr':sweep_depth/atr if atr>0 else np.nan,
            'reclaim_atr':reclaim/atr if atr>0 else np.nan,
            'retest_wick_fraction':wick,'retest_close_beyond':close_beyond,
            'retest_close_fraction':close_beyond/rang,'retest_penetration':penetr,
            'retest_range':rang,'retest_rejection_fraction':(close_beyond+max(0,penetr))/rang,
            'sweep_end':event['sweep_end'],'decision':event['decision'],
            'side':side}


def feature_rules(df):
    """Predeclared illustrative filters, NOT optimized for profit."""
    dep=df['sweep_depth_atr'];wick=df['retest_wick_fraction'];rc=df['reclaim_atr'];close=df['retest_close_fraction']
    return {
        'BASE':pd.Series(True,index=df.index),
        'F1_MODERATE_SWEEP':(dep>=0.15)&(dep<=0.75),
        'F2_REJECTION':(wick>=0.30)&(close>=0.15),
        'F3_BOTH':(dep>=0.15)&(dep<=0.75)&(wick>=0.30)&(close>=0.15),
        'F4_RECLAIM':(rc>=0.20)&(dep<=0.75)
    }


def summarize(df):
    all_rows=[]
    masks=feature_rules(df)
    for rule, mask in masks.items():
        for (spread, year), frame in df.groupby(['spread','year']):
            v=frame[mask.loc[frame.index]]
            done=v[v.status.isin(['TP','SL'])]
            unknown=v[v.status.isin(['DATA_GAP','AMBIGUOUS'])]
            val=float(done.points.sum())
            all_rows.append({'rule':rule,'spread':spread,'year':year,'trades':len(v),
                 'tp':int((v.status=='TP').sum()),'sl':int((v.status=='SL').sum()),
                 'ambiguous':int((v.status=='AMBIGUOUS').sum()),
                 'data_gap':int((v.status=='DATA_GAP').sum()),
                 'resolved':len(done),'nominal_known':round(val,3),
                 'stress_ambiguous_as_sl':round(val-float(v.loc[v.status=='AMBIGUOUS','risk_points'].sum()),3),
                 'stress_unresolved_as_sl':round(val-float(unknown.risk_points.sum()),3)})
    return pd.DataFrame(all_rows)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--trades-zip',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--additional-trades',type=Path,default=None,help='Extra frozen backtest CSV for earlier years')
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    trades=load_trades(args.trades_zip)
    if args.additional_trades:
        extra=pd.read_csv(args.additional_trades,float_precision='round_trip')
        trades=pd.concat([trades,extra],ignore_index=True)
        if trades.duplicated(['decision','side','spread']).any(): raise ValueError('duplicate combined trades')
    print('loaded trades',len(trades),flush=True)
    intervals=merged_windows(trades)
    print('merged windows',len(intervals),flush=True)
    bars=load_selected_bars(args.archive,intervals)
    print('selected M1',len(bars),flush=True)
    distinct=trades.drop_duplicates(['decision','side'])
    features=[]
    for _,v in distinct.iterrows():
        new=causal_features(v,bars)
        if new is not None:features.append(new)
    features=pd.DataFrame(features)
    print('features computed',len(features),'/',len(distinct),flush=True)
    enriched=trades.merge(features,on=['decision','side','sweep_end'],how='left',validate='many_to_one')
    enriched['features_available']=enriched.atr15_prev.notna()
    print('missing', (~enriched.features_available).sum(),flush=True)
    enriched.to_csv(args.out/'features_and_trades.csv',index=False)
    results=summarize(enriched)
    results.to_csv(args.out/'yearly_results.csv',index=False)
    totals=results.groupby(['rule','spread'],as_index=False)[['trades','tp','sl','ambiguous','data_gap','resolved','nominal_known','stress_ambiguous_as_sl','stress_unresolved_as_sl']].sum()
    totals.to_csv(args.out/'totals.csv',index=False)
    print(totals.to_string(index=False),flush=True)
    print(results[results.spread==.6].to_string(index=False),flush=True)

if __name__=='__main__':main()
