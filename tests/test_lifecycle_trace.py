import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from oneplus_buds.lifecycle_trace import mark, span


class TraceTests(unittest.TestCase):
    def test_opt_in_trace_has_correlatable_timestamps_and_failure_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'
            with patch.dict(os.environ, {'ONEPLUS_BUDS_LIFECYCLE_TRACE': str(path)}):
                with span('query', command=262):
                    pass
                with self.assertRaises(RuntimeError):
                    with span('authentication'):
                        raise RuntimeError('sensitive error is never logged')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r['phase'] for r in rows],
                             ['query.begin', 'query.end', 'authentication.begin', 'authentication.failed'])
            self.assertEqual(sorted(r['monotonic_ns'] for r in rows),
                             [r['monotonic_ns'] for r in rows])
            self.assertTrue(all(r['unix_ns'] > 0 for r in rows))
            self.assertNotIn('sensitive', path.read_text())

    def test_unwritable_trace_does_not_break_connections(self):
        with patch.dict(os.environ, {'ONEPLUS_BUDS_LIFECYCLE_TRACE': '/nonexistent/trace.jsonl'}):
            mark('test')

class ReportTests(unittest.TestCase):
    def test_incomplete_start_is_not_reported_as_success(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('summary', Path(__file__).resolve().parents[1] / 'scripts/summarize_connection.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = [{'pid': 1, 'phase': 'controller_start'},
                {'pid': 2, 'phase': 'controller_start'},
                {'pid': 2, 'phase': 'controller_usable'}]
        self.assertEqual(list(module.completed_runs(rows)), [rows[1:]])
