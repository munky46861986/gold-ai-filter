import tempfile
import unittest
from pathlib import Path
from prospective_rr_register import evaluate_plan, register, run


def plan(**overrides):
    d = dict(source='max', message_id='abc001', published_at='2026-11-16T08:00:00+01:00',
             captured_at='2026-11-16T08:01:00+01:00', direction='BUY',
             zone_low='100', zone_high='101', sl='95', tp1='104')
    d.update(overrides)
    return d

class RegisterTests(unittest.TestCase):
    def test_buy_half_r(self):
        x=evaluate_plan(plan())
        self.assertEqual(x['status'],'RR_QUALIFIED_SHADOW')
        self.assertEqual(x['rr'],'0.500000')
    def test_sell_half_r(self):
        x=evaluate_plan(plan(direction='SELL',zone_low='100',zone_high='101',sl='106',tp1='97'))
        self.assertEqual(x['status'],'RR_QUALIFIED_SHADOW')
        self.assertEqual(x['rr'],'0.500000')
    def test_below_threshold(self):
        self.assertEqual(evaluate_plan(plan(tp1='103'))['status'],'RR_REJECTED')
    def test_wrong_direction_geometry(self):
        self.assertEqual(evaluate_plan(plan(sl='102'))['reason'],'INVALID_LEVEL_ORDER_OR_DIRECTION')
    def test_late_copy_not_prospective(self):
        self.assertEqual(evaluate_plan(plan(captured_at='2026-11-16T08:10:00+01:00'))['reason'],'LATE_CAPTURE_UNVERIFIED_OUTCOME')
    def test_timezone_mandatory(self):
        self.assertEqual(evaluate_plan(plan(published_at='2026-11-16T08:00:00'))['reason'],'TIMEZONE_REQUIRED_OR_INVALID_TIME')
    def test_prior_to_freeze_invalid(self):
        self.assertEqual(evaluate_plan(plan(published_at='2026-11-14T08:00:00+01:00'))['reason'],'NOT_PROSPECTIVE_AFTER_FREEZE')
    def test_duplicate_never_overwrite(self):
        first, second=register([plan(),plan(tp1='999')])
        self.assertEqual(first['status'],'RR_QUALIFIED_SHADOW')
        self.assertEqual(second['status'],'DUPLICATE')
    def test_missing_data_flagged(self):
        self.assertEqual(evaluate_plan(plan(tp1=''))['reason'],'MISSING_REQUIRED_FIELD')
    def test_non_finite_values_rejected(self):
        self.assertEqual(evaluate_plan(plan(tp1='nan'))['reason'],'INVALID_PRICE_OR_ZONE')
    def test_real_timezone_offsets(self):
        self.assertEqual(evaluate_plan(plan(captured_at='2026-11-16T07:01:00Z'))['status'],'RR_QUALIFIED_SHADOW')
    def test_reject_capture_before_post(self):
        self.assertEqual(evaluate_plan(plan(captured_at='2026-11-16T07:00:00+01:00'))['reason'],'CAPTURE_BEFORE_PUBLICATION')

if __name__=='__main__':
    unittest.main()
