import unittest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from zipfile import ZipFile
import pandas as pd
from feature_audit import candle_bucket, causal_features, feature_rules, load_selected_bars, merged_windows, summarize

class TestV4811FeatureAudit(unittest.TestCase):
    def setup_example(self):
        sweep_end = datetime(2026, 3, 2, 10)
        decision = sweep_end + timedelta(minutes=20)
        bars={}
        for i in range(275,0,-1):
            d=decision-timedelta(minutes=i)
            bars[d.strftime('%Y.%m.%d %H:%M')]=(100.,101.,99.,100.)
        for i in range(15,0,-1):
            d=sweep_end-timedelta(minutes=i)
            bars[d.strftime('%Y.%m.%d %H:%M')]=(100.,103.,99.,100.5)
        for i in range(5,0,-1):
            d=decision-timedelta(minutes=i)
            bars[d.strftime('%Y.%m.%d %H:%M')]=(100.,100.4,97.,98.)
        event={'decision':decision.isoformat(),'sweep_end':sweep_end.isoformat(),
               'side':'SELL','micro_level':99.}
        return event,bars

    def test_sweep_depth_is_not_zero_from_including_current_sweep(self):
        ev,bars=self.setup_example()
        f=causal_features(ev,bars)
        self.assertIsNotNone(f)
        self.assertAlmostEqual(f['sweep_depth'],2.0)
        self.assertGreater(f['sweep_depth_atr'],0.0)

    def test_no_future_or_entry_candle_leakage(self):
        ev,bars=self.setup_example()
        expected=causal_features(ev,bars)
        dec=ev['decision'].replace('T',' ')[:16].replace('-','.')
        bars[dec]=(99999,99999,1,1)
        bars[(datetime.fromisoformat(ev['decision'])+timedelta(minutes=1)).strftime('%Y.%m.%d %H:%M')]=(1,1,1,1)
        self.assertEqual(expected,causal_features(ev,bars))

    def test_missing_m1_rejects_feature(self):
        ev,bars=self.setup_example()
        d=datetime.fromisoformat(ev['decision'])-timedelta(minutes=3)
        del bars[d.strftime('%Y.%m.%d %H:%M')]
        self.assertIsNone(causal_features(ev,bars))

    def test_retest_features_only_closed_m5(self):
        ev,bars=self.setup_example()
        self.assertIsNotNone(candle_bucket(bars,datetime.fromisoformat(ev['decision']),5))
        self.assertIsNone(candle_bucket(bars,datetime.fromisoformat(ev['decision'])+timedelta(minutes=6),5))
        f=causal_features(ev,bars)
        self.assertGreater(f['retest_close_beyond'],0)

    def test_bad_or_missing_fields_do_not_filter_in(self):
        rows=pd.DataFrame({'sweep_depth_atr':[.2,None,.95],
                 'retest_wick_fraction':[.35,.4,None],
                 'retest_close_fraction':[.2,.2,None],
                 'reclaim_atr':[.3,.4,.5]})
        x=feature_rules(rows)
        self.assertEqual(x['F3_BOTH'].tolist(),[True,False,False])
        self.assertEqual(x['F1_MODERATE_SWEEP'].tolist(),[True,False,False])

    def test_summarize_does_not_treat_data_gap_as_win(self):
        df=pd.DataFrame({'year':[2026]*3,'spread':[.6]*3,'status':['TP','SL','DATA_GAP'],
            'points':[6.,-8.,float('nan')], 'risk_points':[4.,8.,7.],
            'sweep_depth_atr':[.3]*3,'retest_wick_fraction':[.4]*3,
            'retest_close_fraction':[.2]*3,'reclaim_atr':[.5]*3})
        base=summarize(df).query("rule=='BASE'").iloc[0]
        self.assertEqual(base.trades,3)
        self.assertEqual(base.data_gap,1)
        self.assertEqual(base.resolved,2)
        self.assertAlmostEqual(base.nominal_known,-2.0)
        self.assertAlmostEqual(base.stress_unresolved_as_sl,-9.0)

    def test_merge_windows_converts_dates_to_sortable_keys(self):
        df=pd.DataFrame([{'decision':'2026-03-02T10:20:00','sweep_end':'2026-03-02T10:00:00','side':'BUY'}])
        windows=merged_windows(df)
        self.assertEqual(len(windows),1)
        self.assertEqual(windows[0][1],'2026.03.02 10:20')

if __name__=='__main__':unittest.main()
