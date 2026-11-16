"""Portable synthetic unit tests; optional archival tests when user file supplied.
Run: MAX_GOLD_NOV16_SOURCE=/path/to/input.txt python -m unittest discover -s .
"""
import os
import unittest
from pathlib import Path
from nov16_audit import messages, plans, dynamic_sessions

SOURCE=Path(os.environ.get('MAX_GOLD_NOV16_SOURCE','/mnt/data/Testo incollato(20261116-163851).txt'))

class SyntheticTests(unittest.TestCase):
    def test_sell_conservative_entry_uses_lower_edge(self):
        sample='''Max Gold Operativo, [16 Nov 2026 alle 09:00]
SELL su GOLD (XAUUSD)
💰 Entry: 100-102
🛑 Stop: 110
✅ TP 1 — 96
✅ TP 2 — 93
✅ TP 3 — 90
'''
        result=plans(sample)[0]
        self.assertEqual(result['risk_points'],10)
        self.assertEqual(result['rr_tp1'],.4)
        self.assertEqual(result['rr_tp2'],.7)
    def test_buy_conservative_entry_uses_upper_edge(self):
        sample='''Max Gold Operativo, [16 Nov 2026 alle 09:00]
BUY su GOLD (XAUUSD)
💰 Entry: 100-102
🛑 Stop: 90
✅ TP 1 — 106
✅ TP 2 — 109
✅ TP 3 — 112
'''
        result=plans(sample)[0]
        self.assertEqual(result['risk_points'],12)
        self.assertEqual(result['rr_tp1'],.3333)
    def test_wrong_stop_side_rejected(self):
        sample='''Max Gold Operativo, [16 Nov 2026 alle 09:00]
SELL GOLD
💰 Entry: 100-102
🛑 Stop: 90
✅ TP 1 — 96
✅ TP 2 — 93
✅ TP 3 — 91
'''
        with self.assertRaises(ValueError):plans(sample)
    def test_no_messages(self):
        self.assertEqual(plans('other text'),[])

@unittest.skipUnless(SOURCE.exists(), 'Historical user-owned source file not included in repo')
class ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=SOURCE.read_text(encoding='utf-8')
        cls.plans=plans(cls.text)
        cls.sessions=dynamic_sessions(cls.text)
    def test_plan_count(self):self.assertEqual(len(self.plans),6)
    def test_tp1_filter_all_rejected(self):self.assertEqual(sum(x['v4815_rr_tp1_qualified'] for x in self.plans),0)
    def test_tp2_filter_three(self):self.assertEqual(sum(x['rr_tp2']>=.5 for x in self.plans),3)
    def test_tp3_six(self):self.assertEqual(sum(x['rr_tp3']>=.5 for x in self.plans),6)
    def test_mix_three(self):self.assertEqual(sum(x['rr_half_tp1_half_tp3']>=.5 for x in self.plans),3)
    def test_forecast_wrong_two(self):self.assertEqual(sum(x['initial_review']=='ERRATO' for x in self.sessions),2)
    def test_warning_lead_times(self):self.assertEqual(sorted(x['minutes_warning_to_revision'] for x in self.sessions),[138,142])
    def test_first_europe_warning_thesis_same_side(self):
        eu=next(x for x in self.sessions if x['session']=='EUROPE')
        self.assertEqual(eu['warning_thesis_side'],'SELL')
        self.assertAlmostEqual(eu['distance_warning_to_invalidation_pts'],8.242,places=3)
    def test_ny_warning_thesis_counter_side(self):
        ny=next(x for x in self.sessions if x['session']=='NEWYORK')
        self.assertEqual(ny['warning_thesis_side'],'SELL')
        self.assertEqual(ny['initial_bias'],'BUY')
        self.assertAlmostEqual(ny['distance_warning_to_invalidation_pts'],8.026,places=3)
    def test_never_use_success_annotations_as_fills(self):
        self.assertTrue(all('NOT_FILLED' in p['note'] for p in self.plans))
    def test_message_count_nonzero(self):self.assertGreater(len(list(messages(self.text))),25)
if __name__=='__main__':unittest.main()
