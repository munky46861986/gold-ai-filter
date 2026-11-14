"""Read Max Telegram HTML source and audit multiple target tiers, read-only."""
import argparse, json, re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from max_plan_replay_v4813 import load_prices,replay,summary
TP_RE=re.compile(r'(?i)\bTP\s*(?:[1-9]\s*(?:[:—-]|\s)\s*)?(\d{4,5}(?:[.,]\d+)?)')


def extract_ladder(signals, html_folder):
    mapping={}
    for fn in signals['source'].unique():
        soup=BeautifulSoup((Path(html_folder)/fn).read_text(encoding='utf-8'),'html.parser')
        for el in soup.select('div.message[id]'):
            child=el.select_one('div.text')
            if child is None: continue
            targets=[float(y.replace(',','.')) for y in TP_RE.findall(child.get_text(' ',strip=True))]
            mapping[(fn,el['id'])]=targets
    records=[]
    for r in signals.itertuples(index=False):
        raw=mapping.get((r.source,r.msg_id),[])
        clean=[float(r.tp1)]
        discarded=[]
        last_valid = (r.tp_last>=r.tp1) if r.direction=='BUY' else (r.tp_last<=r.tp1)
        for v in raw:
            # If the published last target points in the WRONG direction, it
            # must NEVER be used as a winning far target. The earlier levels
            # may still be audited if monotonically favorable and plausible.
            correct_side=(v>=r.tp1-.0001) if r.direction=='BUY' else (v<=r.tp1+.0001)
            in_last=(v<=r.tp_last+.0001) if r.direction=='BUY' else (v>=r.tp_last-.0001)
            plausible=(abs(v-r.tp1)<=100.0)
            valid=correct_side and plausible and (in_last if last_valid else True)
            if valid and v not in clean:clean.append(v)
            elif not valid:discarded.append(v)
        clean=sorted(clean,reverse=r.direction=='SELL')
        if last_valid and float(r.tp_last) not in clean:clean.append(float(r.tp_last))
        records.append({'source_dt':r.dt,'source_file':r.source,'msg_id':r.msg_id,'direction':r.direction,
                        'tp1':float(r.tp1),'tp2':clean[1] if len(clean)>1 else float('nan'),
                        'tp3':clean[2] if len(clean)>2 else float('nan'),
                        'tp_last':float(r.tp_last),'valid_tp_last':bool(last_valid),'level_count':len(clean),
                        'raw_level_count':len(raw),'raw_invalid_values':json.dumps(discarded),
                        'levels':json.dumps(clean)})
    return pd.DataFrame(records)


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    sig=pd.read_csv(args.signals,parse_dates=['dt'])
    levels=extract_ladder(sig,args.html)
    levels.to_csv(out/'max_levels_verified.csv',index=False)
    candles=load_prices(args.prices)
    rows=[]
    for spread in [0.3,0.6]:
        for tier in ['tp2','tp3','tp_last']:
            plans=sig.copy()
            keep=levels[tier].notna()
            if tier=='tp_last':keep=keep & levels['valid_tp_last']
            plans=plans.loc[keep].copy()
            plans['tp_last']=levels.loc[keep,tier]
            d=replay(plans,candles,spread=spread)
            d['exit_tier']=tier
            d['period']='ALL'
            res=summary(d)
            res['exit_tier']=tier
            res['plans_with_usable_tier']=len(plans)
            # Compare two-leg PnL to TP1-only on precisely the same resolved rows.
            both=d.loc[d.half_ladder_pnl.notna()]
            res['paired_tp1_sum']=round(float(both.tp1_pnl.sum()),2)
            res['paired_ladder_increment']=round(float(both.half_ladder_pnl.sum()-both.tp1_pnl.sum()),2)
            res['runner_ambiguous']=int((d.status_runner=='AMBIGUOUS').sum())
            res['runner_be']=int((d.status_runner=='BE').sum())
            res['runner_sl']=int((d.status_runner=='SL').sum())
            res['runner_timeouts']=int((d.status_runner=='TIMEOUT_MARK').sum())
            rows.append(res)
    report=pd.concat(rows,ignore_index=True)
    report.to_csv(out/'ladder_target_comparison.csv',index=False)
    print(report[['spread','exit_tier','entered_estimated','tp1_hits','sl_before_tp1',
                  'ladder_known_count','ladder_known_sum','ladder_known_mean',
                  'tp_last_reached','runner_ambiguous']].to_string(index=False))
    print('Plans with invalid raw numeric TP:', int((levels.raw_invalid_values!='[]').sum()))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--prices',required=True);a.add_argument('--signals',required=True)
    a.add_argument('--output',required=True);a.add_argument('--html',required=True)
    run(a.parse_args())