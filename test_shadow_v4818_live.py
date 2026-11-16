import unittest
from unittest.mock import patch
import json
from pathlib import Path
from shadow_g_v4818_live import ShadowV4818Live, DDL, INSERT


class V4818LiveTest(unittest.TestCase):
    def setUp(self):
        self.x=ShadowV4818Live(enabled=True,dsn='not-a-real-dsn')
        self.events=[]
        def fake_push(payload):
            from research.shadow_g_v4818.shadow_g_v4818_recorder import normalize
            self.events.append(normalize(payload))
            return True
        self.x.push=fake_push
        self.base={
            'symbol':'XAUUSD','session':'NEWYORK','price':3890,
            'forecast':{'bias':'BUY','initial_bias':'BUY','live_bias':'BUY','live_status':'WEAKENING'},
            'fast_thesis':{'stable_preferred':'SELL','candidate_count':2,'stable_session':'NEWYORK'},
            'm1':{'confirmed':True,'direction':'BUY','score':7},
            'campaign_result':{'triggered':False,'reason':'blocked risk'},
            'director_result':{'action':'WAIT_ENTRY'},
        }
    def test_disabled_no_events(self):
        x=ShadowV4818Live(enabled=False,dsn='some-dsn')
        self.assertFalse(x.capture_director(**self.base))
        self.assertEqual(x.status()['enabled'],False)
    def test_no_db_logs_temporarily_without_credentials(self):
        x=ShadowV4818Live(enabled=True,dsn='')
        from unittest.mock import patch
        with patch('builtins.print') as mocked:
            self.assertTrue(x.capture_director(**self.base))
        raw=mocked.call_args.args[0]
        self.assertTrue(raw.startswith('SHADOW_V4818_RECORD '))
        self.assertNotIn('token',raw.lower())
        self.assertEqual(x.status()['database_configured'],False)
        self.assertEqual(x.status()['metrics_since_process_start']['logged'],1)
    def test_capture_nontrigger_and_causal_gate(self):
        self.assertTrue(self.x.capture_director(**self.base))
        e=self.events[0]
        self.assertEqual(e['campaign_reason'],'blocked risk')
        self.assertEqual(e['thesis_stable'],'SELL')
        self.assertFalse(e['campaign_triggered'])
        from research.shadow_g_v4818.shadow_g_v4818_recorder import counterfactual
        self.assertEqual(counterfactual(e)['A'],'NOT_CREATED')
    def test_triggered_with_plan(self):
        x=dict(self.base,campaign_result={'triggered':True,'reason':'Forecast+Thesis+M1'},
               trade={'id':'tid3','direction':'BUY','entry':3890,'sl':3881,'tp1':3893,'tp2':3896})
        self.assertTrue(self.x.capture_director(**x))
        e=self.events[0]
        from research.shadow_g_v4818.shadow_g_v4818_recorder import counterfactual
        self.assertEqual(counterfactual(e)['A'],'CAMPAIGN_CREATED')
        self.assertEqual(counterfactual(e)['B'],'BLOCKED_WEAKENING')
        self.assertEqual(counterfactual(e)['C'],'BLOCKED_OPPOSITE_THESIS')
        self.assertEqual(e['entry'],3890)
    def test_mismatched_thesis_session_is_unknown(self):
        x=dict(self.base,fast_thesis={'stable_preferred':'SELL','candidate_count':20,'stable_session':'EUROPE'})
        self.x.capture_director(**x)
        self.assertEqual(self.events[0]['thesis_stable'],'UNKNOWN')
        self.assertIsNone(self.events[0]['thesis_confirm_count'])
    def test_no_signal_no_trace(self):
        x=dict(self.base,m1={'confirmed':False,'direction':'UNKNOWN','score':0},
               forecast={'live_status':'VALID'},campaign_result={'triggered':False})
        self.assertFalse(self.x.capture_director(**x))
    def test_deduplicate_in_one_minute(self):
        self.assertTrue(self.x.capture_director(**self.base))
        self.assertFalse(self.x.capture_director(**self.base))
        self.assertEqual(len(self.events),1)
    def test_triggered_not_dedup(self):
        x=dict(self.base,campaign_result={'triggered':True},trade={'direction':'BUY','entry':3890,'sl':3881,'tp1':3893})
        self.assertTrue(self.x.capture_director(**x))
        self.assertTrue(self.x.capture_director(**x))
        self.assertEqual(len(self.events),2)
    def test_secret_cannot_be_saved(self):
        x=ShadowV4818Live(enabled=True,dsn='x')
        with patch.object(x,'_start'):
            self.assertFalse(x.push({'event_id':'foo','token':'secret'}))
        self.assertEqual(x._queue.qsize(),0)
    def test_broker_record(self):
        self.assertTrue(self.x.capture_broker_event({'event':'CLOSED','trade_id':'fx-1','pnl':8.2,'account':'PRIVATE'}))
        self.assertEqual(self.events[0]['broker_pnl_eur'],8.2)
        self.assertNotIn('account',self.events[0])
    def test_broker_error_not_assumed_rejected(self):
        self.assertFalse(self.x.capture_broker_event({'event':'ERROR','trade_id':'a'}))
    def test_no_pnl_from_decision(self):
        self.x.capture_director(**self.base)
        self.assertIsNone(self.events[0].get('broker_pnl_eur'))
    def test_sql_idempotent(self):
        self.assertIn('ON CONFLICT (event_id) DO NOTHING',INSERT)
        self.assertIn('event_ts TIMESTAMPTZ',DDL)

if __name__=='__main__':unittest.main()