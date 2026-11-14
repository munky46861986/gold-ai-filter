"""Offline-only Max plan management audit. No broker, webhook, orders, network.

Compares legacy TP1, next-bar breakeven at favorable +2/+3 points,
next-bar breakeven at +0.5R, and hard entry cancel after 5m.
No parameter optimization is performed; fixed hypotheses are compared.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

STATUSES_KNOWN={'TP1','SL','BE','TIMEOUT_MARK'}

def load_m1(path: str):
    from sys import path as sys_path
    # v48.13 source is re-used exclusively for loading bid-M1 data.
    from max_plan_replay_v4813 import load_prices
    df=load_prices(path)
    return df, df.t.to_numpy(dtype='datetime64[m]').astype('int64'), df[['open','high','low','close']].to_numpy(float)


def simulate_one(r, times, ops, be_mode='NONE', max_hold=240):
    side = 1 if r.direction=='BUY' else -1
    start_t=np.datetime64(r.entry_mt4, 'm').astype('int64')
    j=int(np.searchsorted(times,start_t))
    if j>=len(times) or times[j]!=start_t:
        return ('DATA_GAP',float('nan'),float('nan'),None)
    fill=float(r.entry_price)
    risk=float(r.risk_pts)
    tp=float(r.tp1)
    sl=float(r.sl)
    spread=float(r.spread)
    if be_mode=='NONE': threshold=None
    elif be_mode=='BE_PLUS2':threshold=2.0
    elif be_mode=='BE_PLUS3':threshold=3.0
    elif be_mode=='BE_HALF_R':threshold=0.5*risk
    else:raise ValueError(be_mode)
    be_live=False
    last_t=start_t
    # baseline: TP/SL on the first bar, then gap handling.
    for k in range(j,len(times)):
        t=times[k]
        if t>start_t+max_hold:break
        if k>j and t-last_t>2:
            return ('DATA_GAP',float('nan'),float('nan'),None)
        last_t=t
        o,hi,lo,c=ops[k]
        xhi=hi+(spread if side==-1 else 0.0)
        xlo=lo+(spread if side==-1 else 0.0)
        stop=fill if be_live else sl
        stop_hit=xlo<=stop if side==1 else xhi>=stop
        tp_hit=xhi>=tp if side==1 else xlo<=tp
        if stop_hit and tp_hit:
            return ('AMBIGUOUS',float('nan'),float('nan'),None)
        if stop_hit:
            return ('BE' if be_live else 'SL',0.0 if be_live else round(side*(sl-fill),4),
                    round((t-start_t)),int(t))
        if tp_hit:
            return ('TP1',round(side*(tp-fill),4),round((t-start_t)),int(t))
        if (threshold is not None) and not be_live:
            favorable=side*(xhi-fill) if side==1 else side*(xlo-fill)
            if favorable>=threshold:
                # This bar may have crossed entry before favorable threshold.
                # Only activate BE *starting with the next complete bar*.
                be_live=True
    deadline=start_t+max_hold
    k=int(np.searchsorted(times,deadline,side='right')-1)
    if k<j or times[k]<deadline-2 or times[k]-last_t>2:
        return ('DATA_GAP',float('nan'),float('nan'),None)
    exit_quote=ops[k,3]+(spread if side==-1 else 0.0)
    return ('TIMEOUT_MARK',round(side*(exit_quote-fill),4),max_hold,deadline)


def run(prices, trades_file, output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    df,times,ops=load_m1(prices)
    trades=pd.read_csv(trades_file)
    trades=trades[(trades.entry_status=='FILLED_ESTIMATED') & (trades.status_tp1!='ENTRY_BAR_AMBIGUOUS')].copy()
    # original 2026 plans are not independent OOS because their outcomes were already studied.
    trades['source_dt']=pd.to_datetime(trades.source_dt)
    trades['period']=np.where(trades.source_dt<pd.Timestamp('2026-08-01'),'JAN_JUL','SEP_NOV')
    trades['entry_dt']=pd.to_datetime(trades.entry_mt4)
    trades['entry_delay_min']=(trades.entry_dt - pd.to_datetime(trades.mt4_dt)).dt.total_seconds()/60
    # Published plan RR: available before placement, rather than actual fill-dependent RR.
    rr=(trades.tp1-trades.zone_high)/(trades.zone_high-trades.sl)
    rr_sell=(trades.zone_low-trades.tp1)/(trades.sl-trades.zone_low)
    trades['posted_rr']=np.where(trades.direction=='BUY',rr,rr_sell)
    policies=['NONE','BE_PLUS2','BE_PLUS3','BE_HALF_R']
    rows=[]
    for r in trades.itertuples(index=False):
        for pol in policies:
            st,pnl,exit_min,exit_t=simulate_one(r,times,ops,be_mode=pol)
            rows.append({'msg_id':r.msg_id,'source_file':r.source_file,'source_dt':str(r.source_dt),
                         'spread':r.spread,'period':r.period,'direction':r.direction,
                         'entry_mode':r.entry_mode,'entry_delay_min':r.entry_delay_min,
                         'posted_rr':round(float(r.posted_rr),4),
                         'risk_pts':r.risk_pts,'policy':pol,'status':st,'points':pnl,
                         'exit_minutes':exit_min,'exit_time_minute':exit_t,
                         'baseline_status':r.status_tp1,'baseline_pnl':r.tp1_pnl})
    results=pd.DataFrame(rows)
    # Original baseline validation. Discrepancies are an audit blocker.
    b=results[results.policy=='NONE'].copy()
    compare=b[b.baseline_status.isin(['TP1','SL','TIMEOUT_MARK'])]
    same=((compare.status==compare.baseline_status) &
          ((compare.points-compare.baseline_pnl).abs()<0.0002))
    mismatches=compare.loc[~same]
    if len(mismatches):
        mismatches.to_csv(out/'baseline_mismatches.csv',index=False)
        raise AssertionError('Baseline != v48.13 for %s/%s rows; check first %s' % (len(mismatches),len(compare),mismatches[['source_dt','status','baseline_status','points','baseline_pnl']].head().to_string(index=False)))
    def summarise(df, label_cols):
        rows=[]
        for key,g in df.groupby(label_cols,sort=True,dropna=False):
            if not isinstance(key,tuple):key=(key,)
            known=g[g.status.isin(STATUSES_KNOWN)]
            risk_amb=g.loc[g.status=='AMBIGUOUS','risk_pts'].sum()
            risk_gap=g.loc[g.status=='DATA_GAP','risk_pts'].sum()
            d=dict(zip(label_cols,key));d.update(
                signals=len(g), tp1=int((g.status=='TP1').sum()),sl=int((g.status=='SL').sum()),
                be=int((g.status=='BE').sum()), ambiguous=int((g.status=='AMBIGUOUS').sum()),
                data_gap=int((g.status=='DATA_GAP').sum()),timeouts=int((g.status=='TIMEOUT_MARK').sum()),
                known_count=len(known),sum_points=round(known.points.sum(),3),
                average_known_points=round(float(known.points.mean()),4) if len(known) else float('nan'),
                stress_amb_as_sl=round(known.points.sum()-risk_amb,3),
                stress_amb_and_gap_as_sl=round(known.points.sum()-risk_amb-risk_gap,3))
            rows.append(d)
        return pd.DataFrame(rows)
    results.to_csv(out/'all_policy_trade_results.csv',index=False)
    summary=summarise(results,['spread','period','policy']);summary.to_csv(out/'policy_summary_by_period.csv',index=False)
    totals=summarise(results,['spread','policy']);totals.to_csv(out/'policy_summary_total.csv',index=False)
    # Evaluate entry cancellation policy on EXACT same trade-level baseline outcomes.
    base=results[results.policy=='NONE'].copy()
    base['admitted_5min']=base.entry_delay_min<=5
    base['admitted_rr050']=base.posted_rr>=0.5
    base['admitted_rr075']=base.posted_rr>=0.75
    entry_rows=[]
    for mode,col in [('ALL',''),('CANCEL_AFTER_5MIN','admitted_5min'),
                     ('PUBLISHED_RR_GE_050','admitted_rr050'),('PUBLISHED_RR_GE_075','admitted_rr075')]:
        selected=base if not col else base[base[col]]
        k=summarise(selected,['spread','period'])
        k['entry_rule']=mode
        entry_rows.append(k)
    entry=pd.concat(entry_rows,ignore_index=True)
    entry.to_csv(out/'entry_filter_comparison.csv',index=False)
    validation=pd.DataFrame([{'price_rows':len(df),'candidate_baseline':len(b),
       'legacy_comparable_count':len(compare),'legacy_mismatch_count':len(mismatches),
       'note':'All entry and exit policy decisions respect candle closure; no live execution.'}])
    validation.to_csv(out/'validation.csv',index=False)
    print('VALIDATION\n',validation.to_string(index=False))
    print('TOTAL\n',totals.to_string(index=False))
    print('ENTRY\n',entry.to_string(index=False))
    return totals,entry,summary

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--prices',required=True);a.add_argument('--trades',required=True);a.add_argument('--output',required=True)
    x=a.parse_args();run(x.prices,x.trades,x.output)