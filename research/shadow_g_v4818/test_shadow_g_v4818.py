import json
from pathlib import Path
import tempfile
import unittest
from shadow_g_v4818_recorder import append_event, counterfactual, ingest_jsonl, init_db, normalize, report
from decision_adapter_v4818 import from_director_context

BASE = {
 'event_id':'e1','timestamp':'2026-11-16T14:41:00+01:00','source':'TEST_FIXTURE',
 'symbol':'XAUUSD','session':'NEWYORK','candidate_direction':'BUY','price':3866.52,
 'forecast_initial':'BUY','forecast_live':'BUY','forecast_status':'WEAKENING',
 'thesis_stable':'BUY','thesis_confirm_count':2,
 'm1_direction':'BUY','m1_score':7,'m1_confirmed':True,
 'campaign_triggered':True,'campaign_reason':'Forecast+Thesis+M1',
 'entry':3866.52,'sl':3859.0,'tp1':3870.0,'tp2':3875.0,
 'trade_ref':'example_1'
}

class TestRecorder(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory();self.db=init_db(Path(self.dir.name)/'events.sqlite')
    def tearDown(self):self.db.close();self.dir.cleanup()
    def test_basic(self):
        self.assertEqual(append_event(self.db,BASE),'INSERTED')
        self.assertEqual(append_event(self.db,BASE),'DUPLICATE')
    def test_conflict(self):
        append_event(self.db,BASE)
        with self.assertRaisesRegex(ValueError,'CONFLICT'):
            append_event(self.db,{**BASE,'price':3870})
    def test_unknown_fields_are_dropped(self):
        ev=normalize({**BASE,'arbitrary':'not saved'})
        self.assertNotIn('arbitrary',ev)
    def test_secret_field_refused(self):
        with self.assertRaisesRegex(ValueError,'credential'):
            normalize({**BASE,'BridgeToken':'dontstore'})
    def test_requires_timezone(self):
        with self.assertRaises(ValueError): normalize({**BASE,'timestamp':'2026-11-16T14:41:00'})
    def test_nonfinite_price(self):
        with self.assertRaises(ValueError):normalize({**BASE,'price':float('nan')})
    def test_invalid_trigger_direction(self):
        with self.assertRaises(ValueError):normalize({**BASE,'candidate_direction':'WAIT'})
    def test_b_weakening_veto(self):
        d=counterfactual(normalize(BASE));self.assertEqual(d['A'],'CAMPAIGN_CREATED')
        self.assertEqual(d['B'],'BLOCKED_WEAKENING')
        self.assertEqual(d['C'],'CAMPAIGN_CREATED')
    def test_c_opposite_thesis_veto(self):
        d=counterfactual(normalize({**BASE,'thesis_stable':'SELL'}))
        self.assertEqual(d['C'],'BLOCKED_OPPOSITE_THESIS')
    def test_both_can_only_veto_existing_campaign(self):
        d=counterfactual(normalize({**BASE,'campaign_triggered':False,'campaign_reason':'rischio bloccato'}))
        self.assertEqual((d['A'],d['B'],d['C']),('NOT_CREATED',)*3)
    def test_missing_gate_state_mark_unknown(self):
        d=counterfactual(normalize({**BASE,'forecast_status':'UNKNOWN','thesis_stable':'UNKNOWN'}))
        self.assertEqual((d['B'],d['C']),('UNKNOWN_GATE','UNKNOWN_GATE'))
    def test_no_invented_entry_from_adapter(self):
        item=from_director_context(event_id='x2',timestamp=BASE['timestamp'],symbol='XAUUSD',
          session='EUROPE',price=3880,forecast={'bias':'SELL','live_status':'WEAKENING'},
          campaign_result={'reason':'attendo retest','triggered':False})
        e=normalize(item)
        self.assertIsNone(e['entry']);self.assertEqual(e['campaign_reason'],'attendo retest')
    def test_broker_event_requires_proof(self):
        ev={'event_id':'broker1','timestamp':BASE['timestamp'],'event_kind':'BROKER_EVENT','trade_ref':'x2',
            'broker_state':'CLOSED','broker_pnl_eur':12.0}
        self.assertEqual(append_event(self.db,ev),'INSERTED')
        with self.assertRaises(ValueError):append_event(self.db,{**ev,'event_id':'broker2','broker_pnl_eur':None})
    def test_ingest_and_report(self):
        p=Path(self.dir.name)/'events.jsonl'
        p.write_text('\n'.join([json.dumps(BASE),json.dumps({**BASE,'event_id':'e2','campaign_triggered':False,'campaign_reason':'BROKER_DAY_HISTORY_UNVERIFIED'})]),encoding='utf-8')
        self.assertEqual(ingest_jsonl(self.db,p)['INSERTED'],2)
        out=report(self.db,Path(self.dir.name)/'out')
        self.assertEqual(out['decision_events'],2)
        self.assertEqual(out['campaigns_created_not_broker_fills'],1)
        self.assertEqual(out['reported_broker_open_events_unverified'],0)
        self.assertIsNone(out['pnl_of_theoretical_rejections'])
        self.assertTrue((Path(self.dir.name)/'out/decision_audit.csv').exists())
    def test_session_thesis_not_confused_with_fast_stable(self):
        item=from_director_context(event_id='e3',timestamp=BASE['timestamp'],symbol='XAUUSD',
          session='NEWYORK',price=3870,forecast={'bias':'BUY','live_status':'WEAKENING'},
          fast_thesis={},m1={'direction':'BUY','score':7},campaign_result={'triggered':False})
        e=normalize(item)
        self.assertEqual(e['thesis_stable'],'UNKNOWN')
        self.assertIsNone(e['thesis_confirm_count'])
    def test_fast_thesis_from_fast_state(self):
        item=from_director_context(event_id='e4',timestamp=BASE['timestamp'],symbol='XAUUSD',
          session='NEWYORK',price=3870,fast_thesis={'stable_preferred':'SELL','candidate_count':2},
          forecast={'bias':'BUY','live_status':'WEAKENING'},campaign_result={'triggered':False})
        e=normalize(item)
        self.assertEqual(e['thesis_stable'],'SELL')
        self.assertEqual(e['thesis_confirm_count'],2)
    def test_no_live_execution_imports(self):
        src=Path(__file__).with_name('shadow_g_v4818_recorder.py').read_text()
        for bad in ('MetaTrader5','OrderSend','requests.post','send_telegram','mt4_bridge_queue_trade'):
            self.assertNotIn(bad,src)

if __name__=='__main__':unittest.main()
