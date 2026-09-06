import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from test_backend import STATUS_RESULT
from test_bridge import SNAPSHOT
from oneplus_buds.models import ControlResult
from oneplus_buds.timing import AncRequestError

spec = importlib.util.spec_from_file_location(
    'measure_anc', Path(__file__).resolve().parents[1] / 'scripts' / 'measure_anc.py'
)
measure_anc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_anc)


class MeasurementTests(unittest.TestCase):
    def run_measurement(self, controller, product='062014', reuse=False):
        output = io.StringIO()
        with patch.object(measure_anc, 'BudsController', return_value=controller), \
             patch('sys.argv', ['measure_anc.py', '--product', product, '--run'] + (['--reuse-session'] if reuse else [])), \
             contextlib.redirect_stdout(output):
            code = measure_anc.main()
        return code, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_nonstandard_discovery_exception_is_not_exported(self):
        controller = Mock()
        controller.start.side_effect = Exception('sensitive device information')
        code, records = self.run_measurement(controller)
        self.assertEqual(code, 1)
        self.assertNotIn('sensitive', json.dumps(records))
        controller.set_anc.assert_not_called()
        controller.shutdown.assert_called_once()

    def test_wrong_product_never_writes(self):
        controller = Mock()
        controller.start.return_value.status = STATUS_RESULT
        controller.start.return_value.advertised_event_codes = (1, 2)
        code, _ = self.run_measurement(controller, '060C14')
        self.assertEqual(code, 1)
        controller.set_anc.assert_not_called()
        controller.shutdown.assert_called_once()

    def test_failed_write_exports_only_timings_and_stops(self):
        controller = Mock()
        controller.start.return_value.status = STATUS_RESULT
        controller.start.return_value.advertised_event_codes = (1, 2)
        controller.set_anc.side_effect = AncRequestError('sensitive packet', {'backend_total': 1000.0})
        code, records = self.run_measurement(controller)
        self.assertEqual(code, 1)
        self.assertEqual(records[1]['timings_ms'], {'backend_total': 1000.0})
        self.assertNotIn('sensitive', json.dumps(records))
        controller.set_anc.assert_called_once_with('off')
        controller.shutdown.assert_called_once()

    def test_late_monitoring_loss_cannot_report_completed_run(self):
        controller = Mock()
        controller.start.return_value = SNAPSHOT
        controller.snapshot.return_value = SNAPSHOT
        controller.set_anc.return_value = ControlResult('test', '062014', 'off', None, 0, True)
        sleeps = []
        def listening_pause(_seconds):
            sleeps.append(True)
            if len(sleeps) == 8:
                controller._session = object()
        with patch.object(measure_anc.time, 'sleep', side_effect=listening_pause):
            code, records = self.run_measurement(controller, reuse=True)
        self.assertEqual(code, 1)
        self.assertEqual(records[-1]['phase'], 'final_monitoring_check')
        self.assertFalse(any(record.get('completed') for record in records))
        controller.shutdown.assert_called_once()
