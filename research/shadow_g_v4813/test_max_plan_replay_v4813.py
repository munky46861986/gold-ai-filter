"""Tests with artificial candles; no claim of market predictive accuracy."""
import unittest
import pandas as pd
from max_plan_replay_v4813 import replay, alignment

DT=pd.Timestamp('2026-03-03 10:00:30')

def plan(direction='BUY',zone=(1000.,1001.),sl=995.,tp1=1003.,tp_last=1010.):
    return pd.DataFrame([{'dt':DT,'direction':direction,'zone_low':zone[0],'zone_high':zone[1],
                          'sl':sl,'tp1':tp1,'tp_last':tp_last,'msg_id':'x','source':'synthetic'}])

def candles(bars):
    return pd.DataFrame([{'t':pd.Timestamp('2026-03-03 11:'+minute),
                          'open':o,'high':h,'low':l,'close':c}
                          for minute,o,h,l,c in bars])

class PlanReplayTests(unittest.TestCase):
    def test_buy_tp1_and_runner_tp_last(self):
        d=candles([('01',1000.,1000.5,999.9,1000.2),('02',1001.2,1004.,1001.1,1003.5),
                   ('03',1008.,1011.,1007.,1010.)]);p=replay(plan(),d,spread=.3).iloc[0]
        self.assertEqual((p.status_tp1,p.status_runner),('TP1','TP_LAST'))
        self.assertAlmostEqual(p.entry_price,1000.4)
        self.assertAlmostEqual(p.tp1_pnl,2.6)
    def test_sell_sl_and_spread(self):
        d=candles([('01',1000.,1002.,999.,1001.),('02',1003.,1008.,1002.,1007.)]);p=replay(plan('SELL',(999,1001),1005,996,990),d,spread=.6).iloc[0]
        self.assertEqual(p.status_tp1,'SL')
        self.assertAlmostEqual(p.entry_price,999.9)
        self.assertAlmostEqual(p.tp1_pnl,-5.1)
    def test_same_bar_sl_tp_is_ambiguous(self):
        d=candles([('01',1000.,1010.,994.,1000.)]);p=replay(plan(),d,spread=.3).iloc[0]
        self.assertEqual(p.status_tp1,'AMBIGUOUS')
        self.assertTrue(pd.isna(p.tp1_pnl))
    def test_no_fill_when_only_prepublication_bar_hits(self):
        d=candles([('00',1000.,1007.,994.,1000.),('01',990.,993.,989.,991.)]);p=replay(plan(),d,spread=.3).iloc[0]
        self.assertEqual(p.entry_status,'NO_ENTRY')
    def test_gap_after_open(self):
        d=candles([('01',1000.,1001.,999.,1000.),('10',1000.,1004.,998.,1003.)]);p=replay(plan(),d,spread=.3).iloc[0]
        self.assertEqual(p.status_tp1,'DATA_GAP')
    def test_intrabar_entry_with_barrier_hit_unknown(self):
        d=candles([('01',1012.,1013.,994.,1000.)]);p=replay(plan(),d,spread=.3).iloc[0]
        self.assertEqual(p.status_tp1,'ENTRY_BAR_AMBIGUOUS')
    def test_runner_be_same_minute_as_tp1_is_ambiguous(self):
        d=candles([('01',1000.,1004.,1000.,1003.)]);p=replay(plan(),d,spread=.3).iloc[0]
        self.assertEqual(p.status_tp1,'TP1')
        self.assertEqual(p.status_runner,'AMBIGUOUS')
    def test_alignment_uses_previous_completed_candle(self):
        d=candles([('59',1000.,1000.,1000.,1000.)]); d.loc[0,'t']=pd.Timestamp('2026-03-03 10:59')
        a=alignment(plan(),d,offsets=(0,1)).set_index('offset_h')
        self.assertEqual(a.loc[0,'matched'],0)
        self.assertEqual(a.loc[1,'matched'],1)
        self.assertEqual(a.loc[1,'within_5pts'],1.)

if __name__=='__main__':unittest.main()