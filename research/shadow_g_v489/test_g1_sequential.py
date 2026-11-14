import unittest
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from g1_sequential_replay import timeframe,sweeping_m15,retest_events,run

class G1SequenceTest(unittest.TestCase):
    def m1(self,n=20):
        ts=pd.date_range('2026-10-05 09:00',periods=n,freq='min')
        return pd.DataFrame({'ts':ts,'open':[100.0]*n,'high':[100.1]*n,
                             'low':[99.9]*n,'close':[100.0]*n})
    def event(self):
        return {'side':'BUY','decision':pd.Timestamp('2026-10-05 09:15'),
                'entry_ref':100.,'stop_bid':96.,'micro_level':99.,
                'sweep_end':pd.Timestamp('2026-10-05 09:00'),
                'body_ratio':.5,'lag_minutes':15}
    def test_only_complete_m15(self):
        self.assertEqual(len(timeframe(self.m1(14),15)),0)
        self.assertEqual(len(timeframe(self.m1(15),15)),1)
        self.assertEqual(len(timeframe(self.m1(15).drop(index=7),15)),0)
    def test_sweep_only_after_eight_contiguous_m15(self):
        ts=pd.date_range('2026-10-05 07:00',periods=9,freq='15min')
        m15=pd.DataFrame({'open':[100]*9,'high':[101]*8+[102],
                         'low':[99]*9,'close':[100]*9}, index=ts)
        events=sweeping_m15(m15)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['side'],'SELL')
        self.assertEqual(events[0]['sweep_end'],pd.Timestamp('2026-10-05 09:15'))
        self.assertEqual(len(sweeping_m15(m15.iloc[:8])),0)
    def test_retest_only_after_confirmation(self):
        # The first M5 bar AFTER confirmation retests and closes above resistance.
        m5=pd.DataFrame({'end':pd.date_range('2026-10-05 09:10',periods=4,freq='5min'),
                         'open':[100,100,99.8,100],
                         'high':[100.3,100.3,100.5,100.3],
                         'low':[99.6,99.6,99.1,99.6],
                         'close':[100.1,100.1,100.4,100.1]})
        e=self.event()
        e['decision']=pd.Timestamp('2026-10-05 09:15')
        e['micro_level']=100.1
        result=retest_events(m5,[e])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['decision'],pd.Timestamp('2026-10-05 09:20'))
        self.assertGreater(result[0]['decision'],e['decision'])
    def test_same_m1_tp_and_stop_is_not_winner(self):
        bars=self.m1()
        bars.loc[15,'high']=107.
        bars.loc[15,'low']=95.
        res=run(bars,[self.event()],.3)
        self.assertEqual(len(res),1)
        self.assertEqual(res.iloc[0].status,'AMBIGUOUS')
        self.assertTrue(pd.isna(res.iloc[0].points))
    def test_future_bars_do_not_change_past_first_touch(self):
        bars=self.m1()
        bars.loc[15,'low']=95.
        first=run(bars,[self.event()],.3)
        self.assertEqual(first.iloc[0].status,'SL')
        extended=pd.concat([bars,pd.DataFrame({'ts':[pd.Timestamp('2026-10-05 09:20')],
               'open':[100],'high':[200],'low':[99.9],'close':[100]})],ignore_index=True)
        after=run(extended,[self.event()],.3)
        self.assertEqual(after.iloc[0].status,'SL')
        self.assertEqual(first.iloc[0].points,after.iloc[0].points)
    def test_gaps_cannot_masquerade_as_profitable_close(self):
        bars=self.m1()
        bars.loc[16:,'ts']+=pd.Timedelta(minutes=10)
        bars.loc[16,'high']=200.
        result=run(bars,[self.event()],.3)
        self.assertEqual(result.iloc[0].status,'DATA_GAP')

if __name__=='__main__':unittest.main()

