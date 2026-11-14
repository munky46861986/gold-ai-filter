import unittest
from types import SimpleNamespace
import numpy as np
from max_management_v4814 import simulate_one


def plan(**kw):
    x=dict(entry_mt4='2026-01-01 09:00:00',direction='BUY',entry_price=100.0,
           tp1=103.0,sl=95.0,risk_pts=5.0,spread=0.6)
    x.update(kw)
    return SimpleNamespace(**x)

def data(*bars):
    t=np.arange(len(bars),dtype='int64')+np.datetime64('2026-01-01T09:00','m').astype('int64')
    return t,np.array(bars,dtype=float)

class TestMaxManagement(unittest.TestCase):
    def test_baseline_tp(self):
        t,x=data((100,101,99.5,100),(100,103.5,99.8,103))
        self.assertEqual(simulate_one(plan(),t,x,'NONE')[0:2],('TP1',3.0))
    def test_baseline_sl(self):
        t,x=data((100,100.4,94.8,95))
        self.assertEqual(simulate_one(plan(),t,x,'NONE')[0:2],('SL',-5.0))
    def test_be_activates_only_on_next_candle(self):
        t,x=data((100,102.2,99,101),(101,101.3,99.8,100))
        self.assertEqual(simulate_one(plan(),t,x,'BE_PLUS2')[0:2],('BE',0.0))
    def test_be_does_not_lookback_within_trigger_bar(self):
        t,x=data((100,102.2,99.8,101),(101,103.2,100.4,102.9))
        self.assertEqual(simulate_one(plan(),t,x,'BE_PLUS2')[0:2],('TP1',3.0))
    def test_sl_be_trigger_same_bar_sl_wins(self):
        t,x=data((100,102.2,94.8,95))
        self.assertEqual(simulate_one(plan(),t,x,'BE_PLUS2')[0:2],('SL',-5.0))
    def test_be_tp_same_candle_ambiguous(self):
        t,x=data((100,102.2,99.2,101),(101,103.5,99.6,102))
        self.assertEqual(simulate_one(plan(),t,x,'BE_PLUS2')[0],'AMBIGUOUS')
    def test_sell_spread_on_exit(self):
        t,x=data((100,101.6,96.2,97.2),(97.2,98,95.2,95.5))
        # SELL exit ask = bid + 0.6. On first bar low ask=96.8, no TP;
        # on second bar low ask=95.8 <= 96.0, so TP occurs then.
        r=plan(direction='SELL',tp1=96.0,sl=105.0,risk_pts=5.0)
        st,pts,minutes,_=simulate_one(r,t,x,'NONE')
        self.assertEqual((st,pts,minutes),('TP1',4.0,1))
    def test_missing_market(self):
        t,x=data((100,101,99,100))
        self.assertEqual(simulate_one(plan(entry_mt4='2026-01-01 08:59'),t,x,'NONE')[0],'DATA_GAP')
    def test_gap_prevents_outcome(self):
        t,x=data((100,101,99,100),(100,101,99,100))
        t[1]+=3
        self.assertEqual(simulate_one(plan(),t,x,'NONE')[0],'DATA_GAP')
    def test_both_tp_and_sl_same_bar_ambiguous(self):
        t,x=data((100,103.2,94.8,100))
        self.assertEqual(simulate_one(plan(),t,x,'NONE')[0],'AMBIGUOUS')
    def test_half_r_threshold(self):
        t,x=data((100,102.6,99.9,101),(101,102,99.7,100))
        self.assertEqual(simulate_one(plan(),t,x,'BE_HALF_R')[0],'BE')

if __name__=='__main__':unittest.main()