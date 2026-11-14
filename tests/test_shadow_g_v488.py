import unittest
from datetime import datetime, timezone
from pathlib import Path
from sys import path
from unittest.mock import patch

path.insert(0, str(Path(__file__).resolve().parents[1]))
from shadow_g_v488 import ShadowG, Candidate, aggregate, candidates, normalize_bar

BASE = int(datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc).timestamp())


def bar(minute, *, open=3900.0, high=3900.5, low=3899.5, close=3900.0, spread=0.3):
    return {'end_ts': BASE+60*minute, 'open': open, 'high': high, 'low': low,
            'close': close, 'complete': True, 'spread_points': spread}


def seed_engine():
    engine = ShadowG()
    for minute in range(1, 200):
        engine.push(bar(minute))
    return engine


def inject_buy(engine):
    with patch('shadow_g_v488.candidates', return_value=[Candidate('G1_FAILURE_SHIFT', 'BUY', 3894.0, 3898.0, 'synthetic breakout')]):
        cand = engine.push(bar(200))
    assert cand is not None, engine.diagnostics
    return cand


class ShadowGUnitTests(unittest.TestCase):
    def test_requires_confirmed_complete_m1(self):
        for v in (False, None):
            with self.assertRaises(ValueError):
                normalize_bar({**bar(1), 'complete': v})

    def test_rejects_duplicate_or_out_of_order(self):
        e = ShadowG()
        e.push(bar(1))
        with self.assertRaisesRegex(ValueError, 'out-of-order'):
            e.push(bar(1))

    def test_grouping_only_complete_bars(self):
        rows = [normalize_bar(bar(i)) for i in range(1, 6)]
        self.assertEqual(len(aggregate(rows, 5)), 1)
        self.assertEqual(len(aggregate(rows[:-1], 5)), 0)
        self.assertEqual(len(aggregate(rows[1:], 5)), 0)
        self.assertEqual(aggregate(rows, 5)[0]['close'], 3900)

    def test_causal_pending_next_m1_open_fill(self):
        e = seed_engine()
        cand = inject_buy(e)
        self.assertEqual(cand['state'], 'PENDING')
        self.assertIsNone(cand['entry'])
        self.assertEqual(cand['decision_ts'], BASE + 200*60)
        e.push(bar(201))
        self.assertEqual(cand['state'], 'OPEN')
        self.assertAlmostEqual(cand['entry'], 3900.25)
        self.assertEqual(cand['fill_ts'], BASE+201*60)
        e.push(bar(202, high=3904, low=3899.8, close=3903.7))
        self.assertEqual(cand['tracks']['TP3']['status'], 'TP')
        self.assertEqual(cand['tracks']['TP6']['status'], 'OPEN')
        self.assertEqual(e.report()['scenarios']['TP3']['sum_nominal_points_ex_commission'], 3)

    def test_first_candle_both_sl_and_tp_is_ambiguous(self):
        e = seed_engine()
        cand = inject_buy(e)
        e.push(bar(201, high=3911, low=3893, close=3900))
        self.assertEqual(cand['tracks']['TP3']['status'], 'AMBIGUOUS')
        self.assertIsNone(cand['tracks']['TP3']['points'])
        self.assertEqual(e.report()['scenarios']['TP3']['ambiguous_not_counted'], 1)

    def test_break_even_only_after_tp2(self):
        e = seed_engine()
        cand = inject_buy(e)
        e.push(bar(201))
        e.push(bar(202, open=3901.2, high=3907.2, low=3901.0, close=3906))
        self.assertTrue(cand['tracks']['TP9']['be'])
        self.assertEqual(cand['tracks']['TP6']['status'], 'TP')
        e.push(bar(203, open=3906, high=3906.2, low=3899.8, close=3900))
        self.assertEqual(cand['tracks']['TP9']['status'], 'BE')
        self.assertEqual(cand['tracks']['TP9']['points'], 0.0)

    def test_gap_does_not_credit_future_profit(self):
        e = seed_engine()
        cand = inject_buy(e)
        e.push(bar(201))
        e.push(bar(204, high=3940, low=3899.5, close=3939))
        self.assertEqual(cand['state'], 'DATA_GAP')
        self.assertEqual(cand['tracks']['TP3']['status'], 'DATA_GAP')
        self.assertEqual(e.report()['scenarios']['TP3']['resolved_unambiguous'], 0)

    def test_spike_guard_is_strictly_from_prior_and_current_bars(self):
        e = seed_engine()
        rows = list(e.bars)
        self.assertFalse(e._spike())
        e.push(bar(200, high=3909, low=3899.5, close=3900))
        self.assertTrue(e._spike())

    def test_g1_sweep_requires_microshift(self):
        m15 = [dict(end_ts=BASE+(i+1)*900,open=99,high=101,low=95,close=98) for i in range(12)]
        m15.append(dict(end_ts=BASE+13*900,open=99,high=103,low=96,close=99))
        m5 = [dict(end_ts=BASE+(i+1)*300,open=99,high=101,low=98,close=99) for i in range(11)]
        m5.append(dict(end_ts=m15[-1]['end_ts']+300,open=99,high=100,low=97.4,close=97.5))
        found = candidates(m5,m15)
        self.assertTrue(any(c.mode=='G1_FAILURE_SHIFT' and c.side=='SELL' for c in found))
        m5[-1]['close']=99
        self.assertFalse(any(c.mode=='G1_FAILURE_SHIFT' for c in candidates(m5,m15)))

    def test_g2_bos_then_later_retest(self):
        m15 = [dict(end_ts=BASE+(i+1)*900,open=99,high=101,low=95,close=98) for i in range(11)]
        m15.append(dict(end_ts=BASE+12*900,open=100,high=104,low=99,close=103))
        m15.append(dict(end_ts=BASE+13*900,open=102,high=104,low=100,close=102))
        m5 = [dict(end_ts=BASE+(i+1)*300,open=100,high=104,low=99.5,close=101) for i in range(11)]
        m5.append(dict(end_ts=m15[-1]['end_ts']+300,open=101,high=102.7,low=101.5,close=102.5))
        found=candidates(m5,m15)
        self.assertTrue(any(c.mode=='G2_BOS_RETEST' and c.side=='BUY' for c in found))

    def test_g3_continuation_after_consolidation(self):
        m15 = [dict(end_ts=BASE+(i+1)*900,open=100,high=104,low=96,close=100) for i in range(10)]
        m15.extend([
            dict(end_ts=BASE+11*900,open=100,high=105,low=97,close=102),
            dict(end_ts=BASE+12*900,open=102,high=107,low=100,close=104),
            dict(end_ts=BASE+13*900,open=104,high=109,low=102,close=106),
        ])
        m5 = [dict(end_ts=BASE+(i+1)*300,open=104,high=105,low=103.5,close=104) for i in range(11)]
        m5.append(dict(end_ts=m15[-1]['end_ts']+300,open=104.5,high=106,low=104,close=105.5))
        self.assertTrue(any(c.mode=='G3_CONTINUATION' and c.side=='BUY' for c in candidates(m5,m15)))

    def test_scheduled_candle_at_weekend_no_signal(self):
        e = ShadowG()
        weekend = int(datetime(2026,11,14,10,0,tzinfo=timezone.utc).timestamp())
        with patch('shadow_g_v488.candidates', return_value=[Candidate('G3_CONTINUATION','BUY',3895,3898,'test')]):
            for t in range(1,240):
                e.push({'end_ts':weekend+60*t,'open':3900,'high':3900.1,'low':3899.9,'close':3900,'spread_points':.3,'complete':True})
        self.assertEqual(e.report()['signal_count'], 0)

if __name__ == '__main__':
    unittest.main()

