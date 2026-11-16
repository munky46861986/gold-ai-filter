"""Pure adapter from existing GOLD MASTER Director return objects to OFFLINE snapshots.

This adapter is NOT installed/called by app.py. The caller owns timestamp/event_id.
The actual stable Thesis must come from _thesis_fast_state(), NOT the session
preferred direction (which is not necessarily confirmed 2/2).
Never pass full request/env/account objects, credentials, or broker tokens here.
"""
from __future__ import annotations


def from_director_context(*, event_id, timestamp, symbol, session, price,
                          forecast=None, fast_thesis=None, m1=None, campaign_result=None,
                          director_result=None, candidate_direction=None, trade=None):
    forecast=forecast or {}
    fast_thesis=fast_thesis or {}
    m1=m1 or {}
    campaign_result=campaign_result or {}
    director_result=director_result or {}
    trade=trade or {}
    direction = candidate_direction or (trade.get('direction') if trade else None) or m1.get('direction')
    return {
       'event_id':event_id,'timestamp':timestamp,'event_kind':'DECISION','source':'GOLD_MASTER_DIRECTOR',
       'symbol':symbol,'session':session,'price':price,
       'candidate_direction':direction or 'UNKNOWN',
       'forecast_initial':forecast.get('initial_bias') or forecast.get('bias') or 'UNKNOWN',
       'forecast_live':forecast.get('live_bias') or forecast.get('bias') or 'UNKNOWN',
       'forecast_status':forecast.get('live_status') or 'UNKNOWN',
       'thesis_stable':fast_thesis.get('stable_preferred') or 'UNKNOWN',
       'thesis_confirm_count':fast_thesis.get('candidate_count'),
       'm1_direction':m1.get('direction') or 'UNKNOWN','m1_score':m1.get('score'),
       'm1_confirmed':bool(m1.get('confirmed')),
       'campaign_triggered':bool(campaign_result.get('triggered')),
       'campaign_reason':campaign_result.get('reason') or '',
       'director_action':director_result.get('action') or '',
       'risk_blocked':bool(campaign_result.get('risk_blocked')),
       'entry_quality_blocked':bool(campaign_result.get('entry_quality_blocked')),
       'ghost_prevented':bool(campaign_result.get('ghost_prevented')),
       'entry':trade.get('entry'),'sl':trade.get('sl'),
       'tp1':trade.get('tp1'),'tp2':trade.get('tp2'),
       'trade_ref':str(trade.get('id')) if trade.get('id') else None,
    }
