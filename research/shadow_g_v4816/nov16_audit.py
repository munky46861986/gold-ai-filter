"""SHADOW G v48.16 - offline audit of user-provided Nov 16 Max/GOLD MASTER chat.
Never calls any network, broker, or MT4. Does not calculate hypothetical fill or PnL.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path

H = re.compile(r'(?m)^(Max Gold Operativo|GOLD MASTER), \[([0-9]{1,2} Nov 2026) alle ([0-9]{2}:[0-9]{2})\]\s*')
LEVEL = re.compile(r'(?im)^\s*✅\s*TP\s*(\d+)\s*[—–-]\s*([0-9]+(?:\.[0-9]+)?|OPEN)\s*$')
ZONE = re.compile(r'(?im)^\s*💰\s*Entry:\s*([0-9]+(?:\.[0-9]+)?)\s*[-–—]\s*([0-9]+(?:\.[0-9]+)?)')
STOP = re.compile(r'(?im)^\s*🛑\s*Stop:\s*([0-9]+(?:\.[0-9]+)?)')

def messages(source: str):
    match = list(H.finditer(source))
    for i, m in enumerate(match):
        body = source[m.end(): match[i+1].start() if i+1<len(match) else len(source)].strip()
        yield {
            'speaker':m.group(1),
            'timestamp':dt.datetime.strptime(f'{m.group(2)} {m.group(3)}','%d %b %Y %H:%M'),
            'body':body,
        }

def plans(source: str):
    rows=[]
    for m in messages(source):
        if m['speaker']!='Max Gold Operativo': continue
        body=m['body']
        entry=ZONE.search(body);sl=STOP.search(body)
        if not entry or not sl: continue
        direction=re.search(r'(?i)(?:\bBUY\b|\bSELL\b)',body.splitlines()[0])
        if not direction: raise ValueError(f"No direction at {m['timestamp']}")
        direction=direction.group().upper()
        lo,hi=sorted([float(entry.group(1)),float(entry.group(2))])
        stop=float(sl.group(1))
        tps={int(n):float(v) for n,v in LEVEL.findall(body) if v.upper()!='OPEN'}
        if not {1,2,3}.issubset(tps): raise ValueError(f"No targets at {m['timestamp']}")
        e=hi if direction=='BUY' else lo
        risk=(e-stop) if direction=='BUY' else (stop-e)
        if risk<=0:raise ValueError('wrong stop side')
        reward=lambda target:(target-e) if direction=='BUY' else (e-target)
        rw=[reward(tps[i]) for i in (1,2,3)]
        if any(x<=0 for x in rw):raise ValueError('wrong target side')
        first_50=next((i for i in sorted(tps) if reward(tps[i])/risk>=.5),None)
        rows.append({
            'published_at':m['timestamp'].strftime('%Y-%m-%d %H:%M'),
            'direction':direction,'zone_low':lo,'zone_high':hi,'sl':stop,
            'tp1':tps[1],'tp2':tps[2],'tp3':tps[3],
            'conservative_entry':e,'risk_points':round(risk,4),
            'rr_tp1':round(rw[0]/risk,4),'rr_tp2':round(rw[1]/risk,4),
            'rr_tp3':round(rw[2]/risk,4),
            'rr_half_tp1_half_tp3':round((rw[0]+rw[2])/(2*risk),4),
            'first_tp_with_rr_ge_050':first_50,
            'v4815_rr_tp1_qualified':rw[0]/risk >= 0.5,
            'note':'RETROSPECTIVE_CHAT_AUDIT_NOT_PROSPECTIVE_NOT_FILLED',
        })
    return rows

def dynamic_sessions(source: str):
    events={}
    for m in messages(source):
        if m['speaker']!='GOLD MASTER':continue
        b=m['body'];t=m['timestamp']
        if 'MORNING EUROPE FORECAST' in b:
            events.setdefault('EUROPE',{})['initial_at']=t
            events['EUROPE']['initial_bias']='SELL'
            events['EUROPE']['invalidation']=float(re.search(r'Invalidazione SELL:\s*sopra\s*([0-9.]+)',b).group(1))
            events['EUROPE']['initial_price']=float(re.search(r'Prezzo al forecast:\s*([0-9.]+)',b).group(1))
        elif 'NEW YORK SESSION FORECAST' in b:
            events.setdefault('NEWYORK',{})['initial_at']=t
            events['NEWYORK']['initial_bias']='BUY'
            events['NEWYORK']['invalidation']=float(re.search(r'Invalidazione BUY operativa:\s*sotto\s*([0-9.]+)',b).group(1))
            events['NEWYORK']['initial_price']=float(re.search(r'Prezzo al forecast:\s*([0-9.]+)',b).group(1))
        elif 'FORECAST LIVE — SCENARIO IN INDEBOLIMENTO' in b:
            session=re.search(r'XAUUSD\s*\|\s*(EUROPE|NEWYORK)',b).group(1)
            e=events.setdefault(session,{})
            e['warning_at']=t;e['warning_price']=float(re.search(r'Prezzo:\s*([0-9.]+)',b).group(1))
            match=re.search(r'Session Thesis:\s*([A-Z_]+)\s*->\s*(BUY|SELL)',b)
            e['warning_thesis_status']=match.group(1);e['warning_thesis_side']=match.group(2)
        elif 'FORECAST REVISION #1' in b:
            session='EUROPE' if 'EUROPE FORECAST REVISION' in b else 'NEWYORK'
            e=events.setdefault(session,{})
            e['revision_at']=t;e['revision_price']=float(re.search(r'Prezzo revisione:\s*([0-9.]+)',b).group(1))
            e['revision_side']=re.search(r'Active play:\s*(BUY|SELL)_',b).group(1)
        elif 'FORECAST REVIEW — ERRATO' in b:
            session='NEWYORK' if 'NEW YORK FORECAST REVIEW' in b else 'EUROPE'
            e=events.setdefault(session,{})
            e['review_at']=t
            e['real_open']=float(re.search(r'Open:\s*([0-9.]+)',b).group(1))
            e['real_high']=float(re.search(r'High:\s*([0-9.]+)',b).group(1))
            e['real_low']=float(re.search(r'Low:\s*([0-9.]+)',b).group(1))
            e['real_close']=float(re.search(r'Close:\s*([0-9.]+)',b).group(1))
            e['initial_review']='ERRATO'
    rows=[]
    for session,e in sorted(events.items()):
        dist=abs(e['warning_price']-e['invalidation'])
        rows.append({
            'session':session, 'initial_time':e['initial_at'].strftime('%H:%M'),
            'initial_bias':e['initial_bias'], 'initial_price':e['initial_price'],
            'warning_time':e['warning_at'].strftime('%H:%M'),
            'warning_price':e['warning_price'],'warning_thesis_status':e['warning_thesis_status'],
            'warning_thesis_side':e['warning_thesis_side'],
            'invalidation':e['invalidation'], 'distance_warning_to_invalidation_pts':round(dist,3),
            'revision_time':e['revision_at'].strftime('%H:%M'),
            'revision_price':e['revision_price'],'revision_bias':e['revision_side'],
            'minutes_warning_to_revision':int((e['revision_at']-e['warning_at']).total_seconds()/60),
            'initial_review':e['initial_review'],
            'session_open':e['real_open'],'session_high':e['real_high'],
            'session_low':e['real_low'],'session_close':e['real_close'],
            'note':'EXACT_FIRST_CROSS_TIME_UNKNOWN_NO_BROKER_FILL',
        })
    return rows

def run(inp:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    txt=inp.read_text(encoding='utf-8')
    p=plans(txt);ss=dynamic_sessions(txt)
    for file,rows in [('max_plans_nov16.csv',p),('forecast_events_nov16.csv',ss)]:
        if not rows:raise ValueError('missing '+file)
        with (output/file).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'signal_count':len(p),'rr_tp1_qualified':sum(x['v4815_rr_tp1_qualified'] for x in p),
            'rr_tp2_qualified':sum(x['rr_tp2']>=.5 for x in p),
            'rr_tp3_qualified':sum(x['rr_tp3']>=.5 for x in p),
            'half_tp1_half_tp3_qualified':sum(x['rr_half_tp1_half_tp3']>=.5 for x in p),
            'warnings':len(ss),'initial_forecasts_wrong':sum(x['initial_review']=='ERRATO' for x in ss),
            'warning_to_revision_minutes':[x['minutes_warning_to_revision'] for x in ss],
            'scope':'nov16 archival event audit; no independent fills; no trading'}
    (output/'audit_summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--input',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    x=a.parse_args();print(json.dumps(run(x.input,x.output),indent=2))
