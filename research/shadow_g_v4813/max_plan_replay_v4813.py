"""Conservative, OHLC-only retrospective Max Telegram trading-plan audit.

Never connects to broker, Render, Telegram, or MT4. Trade levels from archived
Telegram export; M1 candles are bid-quote approximations from user-exported MT4.

Time mapping is research hypothesis: source message clock + offset hours =
MT4 candle-open clock. All decisions use candles AFTER the message minute.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def load_prices(path):
    df = pd.read_csv(path, header=None, names=['date','clock','open','high','low','close','ticks'],
                     dtype={'date':str,'clock':str}, low_memory=False)
    df['t'] = pd.to_datetime(df['date']+' '+df['clock'],format='%Y.%m.%d %H:%M',errors='coerce')
    for k in ['open','high','low','close']:
        df[k] = pd.to_numeric(df[k],errors='coerce')
    df = df.dropna(subset=['t','open','high','low','close'])
    df = df.sort_values('t',kind='stable').drop_duplicates('t',keep='last').reset_index(drop=True)
    return df


def alignment(signals, candles, offsets=(-2,-1,0,1,2,3)):
    times = candles['t'].to_numpy(dtype='datetime64[m]').astype('int64')
    close = candles['close'].to_numpy(float)
    results=[]
    for h in offsets:
        match=[]
        for r in signals.itertuples(index=False):
            # The latest COMPLETED candle has open time strictly before message minute.
            target = np.datetime64((r.dt+pd.Timedelta(hours=h)).floor('min'),'m').astype('int64')-1
            i = np.searchsorted(times,target,side='right')-1
            if i<0 or target-times[i]>4:continue
            mid=float(close[i]); d=max(float(r.zone_low)-mid,mid-float(r.zone_high),0.0)
            match.append(d)
        a=np.asarray(match)
        results.append({'offset_h':h,'matched':len(a),
                        'within_2pts':round(float(np.mean(a<=2)),4) if len(a) else None,
                        'within_5pts':round(float(np.mean(a<=5)),4) if len(a) else None,
                        'within_10pts':round(float(np.mean(a<=10)),4) if len(a) else None,
                        'median_distance_outside_zone':round(float(np.median(a)),3) if len(a) else None})
    return pd.DataFrame(results)


def replay(signals, candles, offset_h=1, spread=0.6, slippage=0.1,
           entry_minutes=30, hold_minutes=240):
    minutes=candles['t'].to_numpy(dtype='datetime64[m]').astype('int64')
    ops=candles[['open','high','low','close']].to_numpy(float)
    rows=[]
    for r in signals.itertuples(index=False):
        side=1 if r.direction=='BUY' else -1
        signal_t=r.dt+pd.Timedelta(hours=offset_h)
        minute=np.datetime64(signal_t.floor('min'),'m').astype('int64')
        # ALWAYS start with next M1 open: avoid pre-publication price range.
        start=int(np.searchsorted(minutes,minute+1,side='left'))
        base={'source_dt':r.dt,'mt4_dt':signal_t,'direction':r.direction,
              'zone_low':float(r.zone_low),'zone_high':float(r.zone_high),
              'sl':float(r.sl),'tp1':float(r.tp1),'tp_last':float(r.tp_last),
              'msg_id':r.msg_id,'source_file':r.source,
              'time_offset_h':offset_h,'spread':spread,'entry_minutes':entry_minutes,'hold_minutes':hold_minutes}
        entry_index=-1; entry_p=None; entry_mode=''; entry_uncertain=False
        if start>=len(minutes) or minutes[start]-minute>2:
            rows.append({**base,'entry_status':'NO_MARKET_DATA','status_tp1':'N/A','status_runner':'N/A'});continue
        last_min=minute
        saw_gap=False
        for j in range(start,len(minutes)):
            t=minutes[j]
            if t>minute+entry_minutes:break
            if t-last_min>2:
                saw_gap=True;break
            last_min=t
            o,hi,lo,c=ops[j]
            market_o=o+(spread if side==1 else 0)
            market_hi=hi+(spread if side==1 else 0)
            market_lo=lo+(spread if side==1 else 0)
            if r.zone_low<=market_o<=r.zone_high:
                entry_index=j;entry_p=market_o;entry_mode='OPEN_IN_ZONE';break
            if market_hi>=r.zone_low and market_lo<=r.zone_high:
                entry_index=j
                entry_p=float(r.zone_low if market_o<r.zone_low else r.zone_high)
                entry_mode='INTRABAR_ZONE_TOUCH'
                # Entry at an unknown instant inside a bar that also touches SL/TP.
                exit_hi=hi if side==1 else hi+spread
                exit_lo=lo if side==1 else lo+spread
                entry_uncertain=(exit_lo<=r.sl or exit_hi>=r.tp1) if side==1 else (exit_hi>=r.sl or exit_lo<=r.tp1)
                break
        if entry_index<0:
            rows.append({**base,'entry_status':'ENTRY_DATA_GAP' if saw_gap else 'NO_ENTRY',
                         'status_tp1':'N/A','status_runner':'N/A'});continue
        # Apply adverse slippage after proposed entry (not to posted SL/TP levels).
        fill_price=round(float(entry_p)+side*slippage,5)
        e_time=minutes[entry_index]
        risk=side*(fill_price-float(r.sl))
        if risk<=0:
            rows.append({**base,'entry_status':'INVALID_RISK','status_tp1':'N/A','status_runner':'N/A'});continue
        res={**base,'entry_status':'FILLED_ESTIMATED','entry_mode':entry_mode,
             'entry_mt4':str(pd.Timestamp(e_time,unit='m')),
             'entry_price':fill_price,'risk_pts':round(risk,4),
             'status_tp1':'OPEN','status_runner':'OPEN',
             'tp1_pnl':None,'half_ladder_pnl':None,
             'tp1_hit_time':None,'runner_pnl':None}
        if entry_uncertain:
            res.update(status_tp1='ENTRY_BAR_AMBIGUOUS',status_runner='ENTRY_BAR_AMBIGUOUS')
            rows.append(res);continue
        tp1_hit=False;last_t=e_time
        first_leg_pnl=None;runner_pnl=None
        runner_level=None
        for j in range(entry_index,len(minutes)):
            t=minutes[j]
            if t>e_time+hold_minutes:break
            if j!=entry_index and t-last_t>2:
                res.update(status_tp1='DATA_GAP' if first_leg_pnl is None else res['status_tp1'],
                           status_runner='DATA_GAP')
                break
            last_t=t
            o,hi,lo,c=ops[j]
            # OHLC stored bid; exits SELL at ask (bid + assumed spread).
            exit_hi=hi+(spread if side==-1 else 0)
            exit_lo=lo+(spread if side==-1 else 0)
            tp1_hit_now=(exit_hi>=r.tp1) if side==1 else (exit_lo<=r.tp1)
            sl_hit_now=(exit_lo<=r.sl) if side==1 else (exit_hi>=r.sl)
            just_hit_tp1=False
            if first_leg_pnl is None:
                if tp1_hit_now and sl_hit_now:
                    res.update(status_tp1='AMBIGUOUS',status_runner='AMBIGUOUS');break
                if sl_hit_now:
                    first_leg_pnl=side*(float(r.sl)-fill_price)
                    runner_pnl=first_leg_pnl
                    res.update(status_tp1='SL',status_runner='SL');break
                if tp1_hit_now:
                    first_leg_pnl=side*(float(r.tp1)-fill_price)
                    res.update(status_tp1='TP1',tp1_hit_time=str(pd.Timestamp(t,unit='m')))
                    tp1_hit=True
                    just_hit_tp1=True
                    runner_level=fill_price # move runner stop to estimated break-even after TP1
            if tp1_hit and runner_pnl is None:
                far_hit=(exit_hi>=r.tp_last) if side==1 else (exit_lo<=r.tp_last)
                be_hit=(exit_lo<=runner_level) if side==1 else (exit_hi>=runner_level)
                # BE/TP_LAST in same bar cannot be sequenced from OHLC.
                # On the TP1 bar, BE may have occurred before TP1.
                if be_hit and (far_hit or just_hit_tp1):
                    # OHLC cannot establish whether BE occurred before or after TP1.
                    res['status_runner']='AMBIGUOUS';break
                if t==minutes[entry_index] and entry_mode=='INTRABAR_ZONE_TOUCH' and (be_hit or far_hit):
                    res['status_runner']='AMBIGUOUS';break
                if far_hit:
                    runner_pnl=side*(float(r.tp_last)-fill_price)
                    res['status_runner']='TP_LAST';break
                if be_hit:
                    runner_pnl=0.0
                    res['status_runner']='BE';break
        if res['status_tp1']=='OPEN' and res['status_runner']=='OPEN':
            res.update(status_tp1='TIMEOUT_MARK',status_runner='TIMEOUT_MARK')
        elif res['status_tp1']=='TP1' and res['status_runner']=='OPEN':
            res['status_runner']='TIMEOUT_MARK'
        # For timeout, mark from last available full M1 close before deadline.
        # In all cases, a timeout is a hypothetical forced close at 4h, not a Max fill.
        if res['status_runner']=='TIMEOUT_MARK' or res['status_tp1']=='TIMEOUT_MARK':
            k=int(np.searchsorted(minutes, min(e_time+hold_minutes,minutes[-1]),side='right')-1)
            if k<entry_index or minutes[k]-last_t>2 or minutes[k]<e_time+hold_minutes-2:
                if res['status_tp1']=='TIMEOUT_MARK':res['status_tp1']='DATA_GAP'
                if res['status_runner']=='TIMEOUT_MARK':res['status_runner']='DATA_GAP'
            else:
                close_exit=ops[k,3]+(spread if side==-1 else 0)
                mark=side*(close_exit-fill_price)
                if res['status_tp1']=='TIMEOUT_MARK':first_leg_pnl=mark
                if res['status_runner']=='TIMEOUT_MARK':runner_pnl=mark
        if res['status_tp1'] in ('SL','TP1','TIMEOUT_MARK'):
            res['tp1_pnl']=round(float(first_leg_pnl),4)
        if res['status_runner'] in ('SL','TP_LAST','BE','TIMEOUT_MARK'):
            res['runner_pnl']=round(float(runner_pnl),4)
        if res.get('tp1_pnl') is not None and res.get('runner_pnl') is not None:
            res['half_ladder_pnl']=round((res['tp1_pnl']+res['runner_pnl'])/2,4)
        rows.append(res)
    return pd.DataFrame(rows)


def summary(df):
    groups=[]
    for (scenario,period),g in df.groupby(['spread','period'],dropna=False):
        fill=g[g.entry_status=='FILLED_ESTIMATED']
        known=fill[fill.tp1_pnl.notna()]
        ladder=fill[fill.half_ladder_pnl.notna()]
        groups.append({'spread':scenario,'period':period,'signals':len(g),
                       'entered_estimated':len(fill),'no_entry':int((g.entry_status=='NO_ENTRY').sum()),
                       'entry_gap_or_no_data':int(g.entry_status.isin(['ENTRY_DATA_GAP','NO_MARKET_DATA']).sum()),
                       'entry_ambiguous':int((fill.status_tp1=='ENTRY_BAR_AMBIGUOUS').sum()),
                       'tp1_hits':int((fill.status_tp1=='TP1').sum()),
                       'sl_before_tp1':int((fill.status_tp1=='SL').sum()),
                       'tp1_ambiguous':int((fill.status_tp1=='AMBIGUOUS').sum()),
                       'tp1_data_gap':int((fill.status_tp1=='DATA_GAP').sum()),
                       'tp1_timeout':int((fill.status_tp1=='TIMEOUT_MARK').sum()),
                       'tp1_known_count':len(known),
                       'tp1_known_sum':round(float(known.tp1_pnl.sum()),2),
                       'tp1_known_mean':round(float(known.tp1_pnl.mean()),3) if len(known) else None,
                       'ladder_known_count':len(ladder),
                       'ladder_known_sum':round(float(ladder.half_ladder_pnl.sum()),2),
                       'ladder_known_mean':round(float(ladder.half_ladder_pnl.mean()),3) if len(ladder) else None,
                       'tp_last_reached':int((fill.status_runner=='TP_LAST').sum())})
    return pd.DataFrame(groups)


def main():
    a=argparse.ArgumentParser();a.add_argument('--prices',required=True);a.add_argument('--signals',required=True)
    a.add_argument('--output',required=True);a.add_argument('--spreads',default='0.30,0.60');
    args=a.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    candles=load_prices(args.prices)
    signals=pd.read_csv(args.signals,parse_dates=['dt'])
    align=alignment(signals,candles)
    align.to_csv(out/'clock_alignment.csv',index=False)
    reports=[]
    for spread in map(float,args.spreads.split(',')):
        res=replay(signals,candles,offset_h=1,spread=spread)
        res['period']=res.source_dt.dt.to_period('M').astype(str)
        reports.append(res)
    trades=pd.concat(reports,ignore_index=True)
    trades.to_csv(out/'max_plans_trades.csv',index=False)
    by_month=summary(trades)
    by_month.to_csv(out/'max_plans_by_month.csv',index=False)
    trades['period']='ALL'
    total=summary(trades)
    total.to_csv(out/'max_plans_total.csv',index=False)
    print('ALIGNMENT:\n',align.to_string(index=False))
    print('TOTAL:\n',total.to_string(index=False))
    print('BY MONTH:\n',by_month.to_string(index=False))

if __name__=='__main__':main()