"""SHADOW G v48.18: OFFLINE, append-only decision recorder; no network, broker or MT4 imports.

Receives immutable, already computed decision snapshots through JSONL. It does not
produce signals, change trading configuration, send orders, or replay historical prices.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from collections import Counter

VERSION = '48.18'
DIRECTIONS = {'BUY', 'SELL', 'RANGE', 'WAIT', 'UNKNOWN'}
STATUSES = {'VALID', 'WEAKENING', 'INVALIDATED', 'REASSESSING', 'ARCHIVED', 'UNKNOWN'}
EVENT_KINDS = {'DECISION', 'BROKER_EVENT'}
BROKER_STATES = {'OPENED', 'CLOSED', 'REJECTED', 'NONE', 'UNKNOWN'}
ALLOWED_KEYS = {
    'event_id', 'timestamp', 'event_kind', 'source', 'symbol', 'session', 'candidate_direction',
    'price', 'forecast_initial', 'forecast_live', 'forecast_status', 'thesis_stable',
    'thesis_confirm_count', 'm1_direction', 'm1_score', 'm1_confirmed',
    'campaign_triggered', 'campaign_reason', 'director_action',
    'risk_blocked', 'entry_quality_blocked', 'ghost_prevented',
    'entry', 'sl', 'tp1', 'tp2', 'trade_ref', 'broker_state', 'broker_pnl_eur',
}
FORBIDDEN_FIELD_PATTERN = re.compile(r'(token|passw|secret|api.?key|auth|cookie|credential)',re.I)


def utc_timestamp(v):
    if not isinstance(v, str):
        raise ValueError('timestamp must be an ISO8601 string with timezone')
    try:
        d = datetime.fromisoformat(v.replace('Z', '+00:00'))
    except ValueError as e:
        raise ValueError('invalid timestamp') from e
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError('timestamp must include timezone')
    return d.astimezone(timezone.utc).isoformat(timespec='seconds')


def _enum(value, allowed, field):
    v = str(value if value is not None else 'UNKNOWN').strip().upper()
    if v not in allowed:
        raise ValueError(f'{field}: invalid value {v}')
    return v


def _num(value, field, *, required=False, minimum=None):
    if value is None or value == '':
        if required:
            raise ValueError(f'{field}: missing number')
        return None
    if isinstance(value, bool):
        raise ValueError(f'{field}: boolean is not a number')
    try:
        v = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f'{field}: invalid number') from e
    if not math.isfinite(v) or (minimum is not None and v < minimum):
        raise ValueError(f'{field}: nonfinite or below minimum')
    return v


def _bool(value, field):
    if not isinstance(value, bool):
        raise ValueError(f'{field}: must be boolean')
    return value


def _safe_id(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:@/-]{1,140}', value):
        raise ValueError(f'{field}: empty or unsafe identifier')
    return value


def normalize(raw):
    """Whitelist keys, no secrets, no inferred prices, no later data used."""
    if not isinstance(raw, dict):
        raise ValueError('JSON line must be an object')
    for key in raw:
        if FORBIDDEN_FIELD_PATTERN.search(str(key)):
            raise ValueError('credential-like field refused (including unknown fields)')
    e = {key:raw[key] for key in ALLOWED_KEYS if key in raw}
    e['event_id'] = _safe_id(e.get('event_id'), 'event_id')
    e['timestamp'] = utc_timestamp(e.get('timestamp'))
    e['event_kind'] = _enum(e.get('event_kind','DECISION'), EVENT_KINDS, 'event_kind')
    e['source'] = _safe_id(e.get('source','EXTERNAL_JSONL'), 'source')
    e['symbol'] = _safe_id(e.get('symbol','XAUUSD'), 'symbol').upper()
    e['session'] = _safe_id(e.get('session','UNKNOWN'), 'session').upper()
    e['trade_ref'] = _safe_id(e['trade_ref'],'trade_ref') if e.get('trade_ref') else None
    e['broker_state'] = _enum(e.get('broker_state','UNKNOWN'), BROKER_STATES, 'broker_state')
    e['broker_pnl_eur'] = _num(e.get('broker_pnl_eur'),'broker_pnl_eur')
    if e['event_kind']=='BROKER_EVENT':
        if not e['trade_ref']:
            raise ValueError('BROKER_EVENT requires trade_ref')
        if e['broker_state'] not in {'OPENED','CLOSED','REJECTED'}:
            raise ValueError('BROKER_EVENT requires verified broker_state')
        if e['broker_state']=='CLOSED' and e['broker_pnl_eur'] is None:
            raise ValueError('CLOSED requires actual broker pnl')
        # No hypothetical decision on broker events.
        return {k:e[k] for k in sorted(e)}

    for fld in ('candidate_direction','forecast_initial','forecast_live','thesis_stable','m1_direction'):
        e[fld] = _enum(e.get(fld,'UNKNOWN'), DIRECTIONS, fld)
    e['forecast_status'] = _enum(e.get('forecast_status','UNKNOWN'), STATUSES, 'forecast_status')
    for fld in ('price','entry','sl','tp1','tp2'):
        e[fld]=_num(e.get(fld), fld, minimum=0)
    e['thesis_confirm_count']=_num(e.get('thesis_confirm_count'), 'thesis_confirm_count', minimum=0)
    e['m1_score']=_num(e.get('m1_score'), 'm1_score', minimum=0)
    for fld in ('m1_confirmed','campaign_triggered','risk_blocked','entry_quality_blocked','ghost_prevented'):
        e[fld]=_bool(e.get(fld,False),fld)
    for fld in ('campaign_reason','director_action'):
        value=e.get(fld)
        e[fld]=str(value)[:500] if value is not None else ''
    if e['campaign_triggered'] and e['candidate_direction'] not in ('BUY','SELL'):
        raise ValueError('triggered campaign needs candidate BUY/SELL')
    return {k:e[k] for k in sorted(e)}


def counterfactual(e):
    """A is the *observed* campaign result, never a guessed trade/fill.

    B/C can only veto an A-created campaign; never turn A-rejected trades into fills.
    """
    if e['event_kind'] != 'DECISION':
        return {'A':'NOT_APPLICABLE','B':'NOT_APPLICABLE','C':'NOT_APPLICABLE','reason':'BROKER_EVENT'}
    reason=e.get('campaign_reason') or 'NO_REASON_CAPTURED'
    if not e['campaign_triggered']:
        return {'A':'NOT_CREATED','B':'NOT_CREATED','C':'NOT_CREATED','reason':reason}
    d=e['candidate_direction']
    a='CAMPAIGN_CREATED'  # NOT broker order / fill
    b='BLOCKED_WEAKENING' if e['forecast_status']=='WEAKENING' and e['forecast_initial']==d else a
    c='BLOCKED_OPPOSITE_THESIS' if (e['thesis_confirm_count'] is not None and e['thesis_confirm_count']>=2 and
                                    e['thesis_stable'] in ('BUY','SELL') and e['thesis_stable'] != d) else a
    if e['forecast_status']=='UNKNOWN' or e['forecast_initial']=='UNKNOWN':
        b='UNKNOWN_GATE'  # missing state cannot be silently treated as PASS
    if e['thesis_stable']=='UNKNOWN' or e['thesis_confirm_count'] is None:
        c='UNKNOWN_GATE'
    return {'A':a,'B':b,'C':c,'reason':reason}


def init_db(path):
    db = Path(path); db.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(db), timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('''CREATE TABLE IF NOT EXISTS events (
       event_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, event_kind TEXT NOT NULL,
       payload TEXT NOT NULL, inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn


def append_event(conn, raw):
    e=normalize(raw)
    payload=json.dumps(e,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    with conn:
        try:
            conn.execute('INSERT INTO events (event_id,timestamp,event_kind,payload) VALUES (?,?,?,?)',
                         (e['event_id'],e['timestamp'],e['event_kind'],payload))
            return 'INSERTED'
        except sqlite3.IntegrityError:
            old=conn.execute('SELECT payload FROM events WHERE event_id=?',(e['event_id'],)).fetchone()
            if old and old[0] == payload:
                return 'DUPLICATE'
            raise ValueError('EVENT_ID_CONFLICT: same ID with different content')


def ingest_jsonl(conn,file):
    counts=Counter()
    with open(file,encoding='utf-8-sig') as f:
        for no,line in enumerate(f,1):
            if not line.strip():continue
            try:
                counts[append_event(conn,json.loads(line))]+=1
            except Exception as ex:
                raise ValueError(f'{file}:{no}: {ex}') from ex
    return counts


def rows(conn):
    return [json.loads(x[0]) for x in conn.execute('SELECT payload FROM events ORDER BY timestamp,event_id')]


def report(conn,outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    events=rows(conn)
    decisions=[x for x in events if x['event_kind']=='DECISION']
    broker=[x for x in events if x['event_kind']=='BROKER_EVENT']
    rec=[]
    for e in decisions:
        policies=counterfactual(e)
        rec.append({
            'event_id':e['event_id'],'utc_time':e['timestamp'],'session':e['session'],
            'price':e['price'],'candidate_direction':e['candidate_direction'],
            'forecast_initial':e['forecast_initial'],'forecast_live':e['forecast_live'],
            'forecast_status':e['forecast_status'],'thesis_stable':e['thesis_stable'],
            'thesis_confirm_count':e['thesis_confirm_count'],
            'm1_direction':e['m1_direction'],'m1_score':e['m1_score'],
            'm1_confirmed':e['m1_confirmed'], 'risk_blocked':e['risk_blocked'],
            'entry_quality_blocked':e['entry_quality_blocked'],
            'ghost_prevented':e['ghost_prevented'],
            'has_complete_plan':all(e[k] is not None for k in ('entry','sl','tp1')),
            'campaign_reason':e['campaign_reason'],'director_action':e['director_action'],
            'entry':e['entry'],'sl':e['sl'],'tp1':e['tp1'],'tp2':e['tp2'],
            'A':policies['A'],'B':policies['B'],'C':policies['C'],
            'trade_ref':e['trade_ref'] or '',
        })
    cols=['event_id','utc_time','session','price','candidate_direction','forecast_initial',
          'forecast_live','forecast_status','thesis_stable','thesis_confirm_count',
          'm1_direction','m1_score','m1_confirmed','risk_blocked','entry_quality_blocked','ghost_prevented',
          'has_complete_plan','campaign_reason','director_action','entry','sl','tp1','tp2','A','B','C','trade_ref']
    with (outdir/'decision_audit.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(rec)
    actual=Counter(r['A'] for r in rec)
    abc= {p:Counter(r[p] for r in rec if r['A']=='CAMPAIGN_CREATED') for p in 'ABC'}
    reasons=Counter(e['campaign_reason'] or 'NO_REASON_CAPTURED' for e in decisions if not e['campaign_triggered'])
    summary={
       'version':VERSION,'source':'USER_SUPPLIED_INPUT_EVENTS_UNVERIFIED','total_events':len(events),
       'decision_events':len(decisions),'broker_events':len(broker),
       'campaigns_created_not_broker_fills':actual['CAMPAIGN_CREATED'],
       'not_created':actual['NOT_CREATED'],
       'non_created_with_complete_entry_sl_tp':sum(r['A']=='NOT_CREATED' and r['has_complete_plan'] for r in rec),
       'policy_among_created':{p:dict(abc[p]) for p in 'ABC'},
       'rejection_reasons':dict(reasons),
       'reported_broker_open_events_unverified':sum(e['broker_state']=='OPENED' for e in broker),
       'reported_broker_close_events_unverified':sum(e['broker_state']=='CLOSED' for e in broker),
       'broker_reported_closed_eur_unverified':round(sum(e.get('broker_pnl_eur') or 0 for e in broker if e['broker_state']=='CLOSED'),2),
       'pnl_of_theoretical_rejections':None,'entry_outcomes_verified':False,
       'note':'Broker events are user-supplied claims unless independently matched to MT4 history. No counterfactual PnL, no automatic ingestion from live Render, no broker execution.'
    }
    (outdir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description='SHADOW v48.18 OFFLINE decision log, never trades')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('ingest');a.add_argument('--db',required=True);a.add_argument('--jsonl',required=True)
    b=sub.add_parser('report');b.add_argument('--db',required=True);b.add_argument('--out',required=True)
    args=p.parse_args(argv)
    con=init_db(args.db)
    try:
        if args.command=='ingest':result=dict(ingest_jsonl(con,args.jsonl))
        else:result=report(con,args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:con.close()

if __name__=='__main__': main()
