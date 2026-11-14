"""Descriptive pre-entry RR fragility tests, based only on archival Max plans.
The thresholds are EXPLORATORY; no OOS performance may be claimed.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd


def make_report(plan_file, trade_file, policy_file, out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    signals=pd.read_csv(plan_file)
    base=pd.read_csv(trade_file)
    base=base[base.spread==0.6].copy()
    rr=(signals.tp1-signals.zone_high)/(signals.zone_high-signals.sl)
    rr_sell=(signals.zone_low-signals.tp1)/(signals.sl-signals.zone_low)
    signals['posted_rr']=np.where(signals.direction=='BUY',rr,rr_sell)
    # source_file rather than source; unique joining on Telegram message origin
    sig=signals[['source','msg_id','posted_rr']].rename(columns={'source':'source_file'})
    base=base.merge(sig,on=['source_file','msg_id'],how='left',validate='one_to_one')
    assert base.posted_rr.notna().all()
    base['source_dt']=pd.to_datetime(base.source_dt)
    base['day']=base.source_dt.dt.date
    base['period']=np.where(base.source_dt<pd.Timestamp('2026-08-01'),'JAN_JUL','SEP_NOV')
    eligible=base[base.posted_rr>=.5].copy()
    est=eligible[(eligible.entry_status=='FILLED_ESTIMATED')&(eligible.status_tp1!='ENTRY_BAR_AMBIGUOUS')]
    known=est[est.status_tp1.isin(['TP1','SL','TIMEOUT_MARK'])]
    assert len(known)==55 and abs(known.tp1_pnl.sum()-113.82)<0.01
    # Causal one-per-day selection: FIRST PUBLISHED eligible plan, not first winning plan.
    first_plan=eligible.sort_values(['day','source_dt','msg_id']).groupby('day',as_index=False).head(1)
    first_est=first_plan[(first_plan.entry_status=='FILLED_ESTIMATED') & (first_plan.status_tp1!='ENTRY_BAR_AMBIGUOUS')]
    first_known=first_est[first_est.status_tp1.isin(['TP1','SL','TIMEOUT_MARK'])]
    # Exclude theoretical mark-to-close PnL as robustness, rather than claim target hit.
    no_timeout=known[known.status_tp1!='TIMEOUT_MARK']
    no_apr30=known[known.day.astype(str)!='2026-04-30']
    top3=known.nlargest(3,'tp1_pnl')
    # A daily-block bootstrap; does not address backtest overfit or missing data.
    daily=known.groupby('day',as_index=False).tp1_pnl.sum()
    vals=daily.tp1_pnl.to_numpy(float)
    rng=np.random.default_rng(4814)
    samples=rng.choice(vals,size=(6000,len(vals)),replace=True).sum(axis=1)
    ci=np.quantile(samples,[.025,.975])
    # Comparative BE_plus2: compare exact same underlying trade, count ambiguous as initial SL.
    pol=pd.read_csv(policy_file)
    pol=pol[pol.spread==0.6]
    none=pol[pol.policy=='NONE'].set_index(['source_file','msg_id'])
    be2=pol[pol.policy=='BE_PLUS2'].set_index(['source_file','msg_id'])
    both=none[['period','source_dt','points','risk_pts','status']].join(
        be2[['points','risk_pts','status']],rsuffix='_be',validate='one_to_one')
    both['effective_none']=np.where(both.status=='DATA_GAP',-both.risk_pts,both.points)
    both['effective_be']=np.where(both.status_be.isin(['DATA_GAP','AMBIGUOUS']),-both.risk_pts_be,both.points_be)
    both['diff']=both.effective_be-both.effective_none
    both['day']=pd.to_datetime(both.source_dt).dt.date
    delta=both.groupby('day')['diff'].sum()
    dd=delta.to_numpy(float)
    boot=rng.choice(dd,size=(6000,len(dd)),replace=True).sum(axis=1)
    delta_ci=np.quantile(boot,[.025,.975])
    # Per-month breakdown and representative extraction facts.
    monthly=known.assign(month=known.source_dt.dt.strftime('%Y-%m')).groupby('month',as_index=False).agg(
       n=('tp1_pnl','size'),points=('tp1_pnl','sum'),tp1=('status_tp1',lambda x:int((x=='TP1').sum())),
       sl=('status_tp1',lambda x:int((x=='SL').sum())),timeout=('status_tp1',lambda x:int((x=='TIMEOUT_MARK').sum())))
    monthly.to_csv(out/'rr_050_monthly.csv',index=False)
    first_plan.to_csv(out/'rr_050_first_published_per_day.csv',index=False)
    both.reset_index().to_csv(out/'be_plus2_paired_comparison.csv',index=False)
    entries=[
      ('RR >=0.50, known filled',len(known),known.tp1_pnl.sum()),
      ('RR >=0.50 excluding theoretical 4h closes',len(no_timeout),no_timeout.tp1_pnl.sum()),
      ('RR >=0.50 excluding all 30-Apr plans',len(no_apr30),no_apr30.tp1_pnl.sum()),
      ('RR >=0.50 less 3 largest wins',len(known)-3,known.tp1_pnl.sum()-top3.tp1_pnl.sum()),
      ('RR >=0.50 first published eligible plan/day: resolved fills',len(first_known),first_known.tp1_pnl.sum()),
    ]
    stress=pd.DataFrame(entries,columns=['scenario','resolved_n','nominal_points'])
    stress['nominal_points']=stress.nominal_points.round(3)
    stress.to_csv(out/'rr_050_sensitivity.csv',index=False)
    print('RR FRAGILITY\n',stress.to_string(index=False))
    print('DAILY BLOCK BOOTSTRAP RR>=0.5 n_days',len(vals),'95% CI sum',ci)
    print('PAIRED BE2 minus BASE (gap/amb as SL): sum',both['diff'].sum(),'days',len(delta),'bootstrap 95%',delta_ci)
    print('1-per-day possible plans',len(first_plan),'first planned fills',len(first_est),'first known',len(first_known))
    print('MONTH\n',monthly.to_string(index=False))
    metrics={
       'rr_eligible_published':int(len(eligible)),
       'rr_resolved_fills':int(len(known)),
       'rr_resolved_days':int(len(vals)),
       'rr_nominal':round(float(known.tp1_pnl.sum()),3),
       'rr_bootstrap_sum_p025':round(float(ci[0]),3),
       'rr_bootstrap_sum_p975':round(float(ci[1]),3),
       'apr30_sum':round(float(known.loc[known.day.astype(str)=='2026-04-30','tp1_pnl'].sum()),3),
       'three_largest_sum':round(float(top3.tp1_pnl.sum()),3),
       'be2_paired_conservative_sum_difference':round(float(both['diff'].sum()),3),
       'be2_bootstrap_delta_p025':round(float(delta_ci[0]),3),
       'be2_bootstrap_delta_p975':round(float(delta_ci[1]),3),
    }
    pd.DataFrame([metrics]).to_csv(out/'robustness_metrics.csv',index=False)
    return metrics

if __name__=='__main__':
  a=argparse.ArgumentParser()
  a.add_argument('--plans',required=True);a.add_argument('--trades',required=True)
  a.add_argument('--policies',required=True);a.add_argument('--output',required=True)
  x=a.parse_args();make_report(x.plans,x.trades,x.policies,x.output)