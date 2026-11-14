"""GOLD MASTER: isolated G1 sequential confirmation research. No broker, no network, no live orders.

MT4 M1 CSV ZIP: DATE,HH:MM,open,high,low,close,volume (M1 opening timestamps).
Assumptions: naive broker time approximates Europe/Rome, BID OHLC, constant spread,
slippage; 5/15 minute aggregation strictly uses complete contiguous closed M1 bars.
This is a PREDECLARED alternative to G1 and NOT a validated profitable system.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd

MODES = ('G1_SEQ_CONFIRM',)
TARGET = 6.0
SLIPPAGE = 0.10

def load_m1(zip_path, years=('2022','2023','2024','2025','2026')):
    rows=[]
    with ZipFile(zip_path) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1: raise ValueError('ZIP must contain exactly one CSV')
        with z.open(names[0]) as f:
            allowed={y.encode() for y in years}
            for raw in f:
                if raw[:4] not in allowed: continue
                dt,clock,o,h,l,c,vol=raw.decode('utf-8-sig').strip().split(',')
                rows.append((dt+' '+clock,float(o),float(h),float(l),float(c)))
    m1=pd.DataFrame(rows,columns=['ts','open','high','low','close'])
    m1['ts']=pd.to_datetime(m1.ts,format='%Y.%m.%d %H:%M')
    if m1.ts.duplicated().any() or not m1.ts.is_monotonic_increasing:
        raise ValueError('duplicated or unordered broker clock timestamps')
    return m1

def timeframe(m1,minutes):
    raw=m1.copy()
    raw['bucket']=raw['ts'].dt.floor(f'{minutes}min')
    grouped=raw.groupby('bucket',sort=True).agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),count=('ts','size'),first=('ts','first'),last=('ts','last'))
    full=(grouped['count'].eq(minutes) & grouped['first'].eq(grouped.index) & grouped['last'].eq(grouped.index+pd.Timedelta(minutes=minutes-1)))
    out=grouped.loc[full,['open','high','low','close']].copy()
    out.index.name='start'
    out['end']=out.index+pd.Timedelta(minutes=minutes)
    return out

def sweeping_m15(m15):
    old_hi=m15.high.shift(1).rolling(8,min_periods=8).max()
    old_lo=m15.low.shift(1).rolling(8,min_periods=8).min()
    continuous=(m15.index.to_series()-m15.index.to_series().shift(8)).eq(pd.Timedelta(minutes=120))
    sell=continuous & (m15.high>=old_hi+0.5) & (m15.close<=old_hi-0.25)
    buy=continuous & (m15.low<=old_lo-0.5) & (m15.close>=old_lo+0.25)
    out=[]
    for side,mask,level in [('SELL',sell,old_hi),('BUY',buy,old_lo)]:
        for t in m15.index[mask.fillna(False)]:
            bar=m15.loc[t]
            out.append({'side':side,'sweep_end':t+pd.Timedelta(minutes=15), 'sweep_high':float(bar.high),
                        'sweep_low':float(bar.low),'sweep_level':float(level.loc[t])})
    return sorted(out,key=lambda d:d['sweep_end'])

def confirm_events(m1,m15,m5):
    # Four prior, *closed* M5 candles. All must be consecutive.
    p_low=m5.low.shift(1).rolling(4,min_periods=4).min()
    p_high=m5.high.shift(1).rolling(4,min_periods=4).max()
    contig=(m5.index.to_series()-m5.index.to_series().shift(4)).eq(pd.Timedelta(minutes=20))
    m5lookup={ts:i for i,ts in enumerate(m5['end'])}
    p_l=p_low.to_numpy();p_h=p_high.to_numpy();ok=contig.to_numpy()
    open5=m5.open.to_numpy();close5=m5.close.to_numpy();high5=m5.high.to_numpy();low5=m5.low.to_numpy()
    proposals=[]
    for e in sweeping_m15(m15):
        for step in (5,10,15):
            end=e['sweep_end']+pd.Timedelta(minutes=step)
            j=m5lookup.get(end)
            if j is None or not ok[j]:continue
            range5=max(high5[j]-low5[j],0.001)
            body=abs(close5[j]-open5[j])/range5
            if body < .45:continue  # fixed ex ante; no fit against outcomes
            sell=(e['side']=='SELL' and close5[j]<open5[j] and close5[j]<p_l[j]-0.15)
            buy=(e['side']=='BUY' and close5[j]>open5[j] and close5[j]>p_h[j]+0.15)
            if not (sell or buy):continue
            proposals.append({**e,'decision':end,'entry_ref':float(close5[j]),'body_ratio':float(body),
                              'stop_bid':e['sweep_high']+.75 if sell else e['sweep_low']-.75,
                              'lag_minutes':step,'micro_level':float(p_l[j] if sell else p_h[j])})
            break # earliest post-sweep confirmed shift only
    return sorted(proposals,key=lambda e:e['decision'])

def retest_events(m5, events):
    """After confirmed microshift, require a later M5 to retest/reject the broken level.

    Deliberately fixed rules and strictly later closes; exploratory second hypothesis.
    """
    lookup={end:i for i,end in enumerate(m5['end'])}
    o=m5.open.to_numpy();h=m5.high.to_numpy();l=m5.low.to_numpy();c=m5.close.to_numpy()
    out=[]
    for e in events:
        level=e['micro_level']
        for step in (5,10,15):
            t=e['decision']+pd.Timedelta(minutes=step)
            j=lookup.get(t)
            if j is None:break  # cannot jump an absent M5 bar
            rng=max(h[j]-l[j],.001)
            if abs(c[j]-o[j])/rng < .35:continue
            if e['side']=='SELL':
                valid=(h[j]>=level-.40 and h[j]<=level+1.50
                       and c[j] < level-.15 and c[j]<o[j])
            else:
                valid=(l[j]<=level+.40 and l[j]>=level-1.50
                       and c[j] > level+.15 and c[j]>o[j])
            if valid:
                out.append({**e,'decision':t,'entry_ref':float(c[j]),
                            'retest_minutes':step,'retest_level':level})
                break
    return sorted(out,key=lambda d:d['decision'])


def run(m1, events, spread):
    # Raw MT4 OHLC treated as BID. Offer: bid + spread. Slippage adverse at entry.
    ts=m1.ts.to_numpy(dtype='datetime64[ns]')
    opens=m1.open.to_numpy();hi=m1.high.to_numpy();lo=m1.low.to_numpy();close=m1.close.to_numpy()
    gaps=np.r_[True,(np.diff(ts).astype('timedelta64[m]').astype('int64')!=1)]
    starts=np.flatnonzero(gaps)
    stops=np.r_[starts[1:],len(ts)]
    segment=np.cumsum(gaps)-1
    by_ts={pd.Timestamp(v):i for i,v in enumerate(ts)}
    out=[];last_by_side={};count_per_day=Counter()
    for e in events:
        when=e['decision'];side=e['side'];day=when.strftime('%Y-%m-%d')
        if when.weekday()>=5 or not (8<=when.hour<18): continue
        if count_per_day[day]>=20:continue
        if side in last_by_side and (when-last_by_side[side]).total_seconds()<1800:continue
        idx=by_ts.get(when)
        if idx is None or idx==0 or gaps[idx]:continue # entry next M1 open, contiguous only
        # Ex ante 12 M1 bars preceding decision, all complete, guard spikes.
        if idx<12 or (ts[idx-1]-ts[idx-12])!=np.timedelta64(11,'m'):continue
        if (hi[idx-12:idx]-lo[idx-12:idx]).max()>=8. or np.abs(np.diff(close[idx-12:idx])).max()>=6.:continue
        direction=1 if side=='BUY' else -1
        entry=opens[idx]+(spread+SLIPPAGE if direction==1 else -SLIPPAGE)
        if abs(entry-e['entry_ref'])>2.0:continue
        # stop adjusted for mid on source bar, as v48.8 mid-based engine
        stop=e['stop_bid']+spread/2
        risk=(entry-stop)*direction
        if risk<2. or risk>15.:continue
        count_per_day[day]+=1;last_by_side[side]=when
        end=stops[segment[idx]]
        # On each bar, two-sided touch is ambiguous; no knowledge about first tick.
        sl_hit=(entry-lo[idx:end])>=risk if direction==1 else (hi[idx:end]+spread-entry)>=risk
        tp_hit=(hi[idx:end]-entry)>=TARGET if direction==1 else (entry-lo[idx:end]-spread)>=TARGET
        touched=np.flatnonzero(sl_hit|tp_hit)
        if len(touched):
            first=touched[0]
            status=('AMBIGUOUS' if sl_hit[first] and tp_hit[first] else 'SL' if sl_hit[first] else 'TP')
            points=(-risk if status=='SL' else TARGET if status=='TP' else np.nan)
        else:
            status='DATA_GAP';points=np.nan
        out.append({'decision':when.isoformat(),'year':when.year,'side':side,'status':status,'points':points,
                    'risk_points':risk,'entry':entry,'stop':stop,'spread':spread,
                    'lag_minutes':e['lag_minutes'],'body_ratio':e['body_ratio'],
                    'sweep_end':e['sweep_end'].isoformat(),
                    'micro_level':e['micro_level']})
    return pd.DataFrame(out)

def summary(df):
    if df.empty:return pd.DataFrame()
    rows=[]
    for (spread,year),v in df.groupby(['spread','year']):
        done=v[v.status.isin(['TP','SL'])]
        ambiguous=v[v.status=='AMBIGUOUS']
        rows.append({'spread':spread,'year':year,'proposals':len(v),'tp':sum(v.status=='TP'),
                     'sl':sum(v.status=='SL'),'ambiguous':len(ambiguous),
                     'data_gap':sum(v.status=='DATA_GAP'),
                     'nominal_ex_ambiguous':round(float(done.points.sum()),2),
                     'stress_ambiguous_as_sl':round(float(done.points.sum()-ambiguous.risk_points.sum()),2)})
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--years',nargs='+',default=['2022','2023','2024','2025','2026'])
    opts=ap.parse_args();opts.out.mkdir(parents=True,exist_ok=True)
    m1=load_m1(opts.zip,years=opts.years)
    print('m1:',len(m1),'from',m1.ts.min(),'to',m1.ts.max(),flush=True)
    m5=timeframe(m1,5);m15=timeframe(m1,15)
    print('m5:',len(m5),'m15:',len(m15),flush=True)
    events=confirm_events(m1,m15,m5)
    print('sweep events with sequential confirmation:',len(events),flush=True)
    for label,ev in [('seq',events),('seq_retest',retest_events(m5,events))]:
        outputs=[]
        for sp in (.30,.60):
            df=run(m1,ev,sp);outputs.append(df)
            print(label,'spread',sp,'accepted',len(df),flush=True)
        combined=pd.concat(outputs,ignore_index=True)
        res=summary(combined)
        combined.to_csv(opts.out/f'g1_{label}_trades.csv',index=False)
        res.to_csv(opts.out/f'g1_{label}_summary.csv',index=False)
        print(label,'\n',res.to_string(index=False),flush=True)


if __name__=='__main__':main()

