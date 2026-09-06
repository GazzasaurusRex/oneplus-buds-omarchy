#!/usr/bin/env python3
"""Explicit hardware test; run from checkout with PYTHONPATH=src."""
import argparse
import json
import time
from threading import Event, Thread

from oneplus_buds.service import BudsServiceRunner

from oneplus_buds.controller import BudsController
from oneplus_buds.timing import AncRequestError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product', required=True, choices=('060C14', '062014'))
    parser.add_argument('--run', action='store_true', help='Authorize two Off → Transparency → On → Off cycles; ends Off')
    parser.add_argument('--reuse-session', action='store_true', help='Test persistent-session control')
    parser.add_argument('--service', action='store_true', help='Run concurrent service polling during measurements')
    parser.add_argument('--pause', type=float, default=0, help='Listening interval between requests (not counted in request timing)')
    args = parser.parse_args()
    if not args.run:
        parser.error('--run is required: this test changes ANC and ends Off')
    controller = BudsController(reuse_session=args.reuse_session)
    cancelled = Event()
    worker = None
    service_failures = []
    service_states = []
    phase = 'startup'
    try:
        snapshot = controller.start()
        if snapshot.status.product_id != args.product:
            raise RuntimeError('wrong reference model connected')
        initial_session = controller._session
        initial_codes = snapshot.advertised_event_codes
        if args.service:
            def run_service():
                try:
                    BudsServiceRunner(controller, on_state=lambda state: service_states.append(state.connection)).run(cancelled)
                except Exception as error:
                    service_failures.append(type(error).__name__)
            worker = Thread(target=run_service)
            worker.start()
        print(json.dumps({'reuse_session': args.reuse_session, 'service_polling': args.service,
                          'advertised_event_codes': list(initial_codes), 'product_id': args.product, 'firmware': snapshot.status.firmware_version,
                          'initial_anc': snapshot.status.anc}), flush=True)
        for cycle in range(1, 3):
            for mode in ('off', 'transparency', 'on', 'off'):
                phase = 'control'
                try:
                    result = controller.set_anc(mode)
                except AncRequestError as error:
                    print(json.dumps({'cycle': cycle, 'requested': mode, 'ok': False,
                                      'timings_ms': error.timings_ms}), flush=True)
                    raise
                monitoring = controller.snapshot()
                same_session = controller._session is initial_session
                print(json.dumps({'cycle': cycle, 'requested': mode, 'ok': True,
                                  'same_session': same_session,
                                  'notification_event_codes': list(monitoring.notification_event_codes),
                                  'observed': result.anc, 'level': result.anc_level,
                                  'set_status': result.set_status, 'verified': result.verified,
                                  'verification_queries': result.verification_queries,
                                  'timings_ms': result.timings_ms}), flush=True)
                phase = 'monitoring_check'
                if args.reuse_session and (not same_session or not monitoring.session_connected
                                           or monitoring.advertised_event_codes != initial_codes
                                           or service_failures):
                    raise RuntimeError('monitoring did not survive control request')
                if not args.service:
                    controller.poll(0.5)
                time.sleep(max(0, args.pause))
        phase = 'final_monitoring_check'
        final = controller.snapshot()
        if args.reuse_session and (controller._session is not initial_session
                                   or not final.session_connected or service_failures):
            raise RuntimeError('monitoring failed after final request')
        print(json.dumps({'completed': True, 'final_anc': final.status.anc,
                          'session_retained': controller._session is initial_session,
                          'service_errors': service_failures}), flush=True)
    except Exception as error:
        # Includes D-Bus exceptions, which are not OSError/RuntimeError.
        # Error strings can contain addresses/raw responses: never export them.
        print(json.dumps({'stopped': True, 'phase': phase, 'error_type': type(error).__name__,
                          'service_errors': service_failures, 'service_states': service_states,
                          'reason': 'test failed; final ANC state may differ'}), flush=True)
        return 1
    finally:
        cancelled.set()
        if worker is not None:
            worker.join()
        controller.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
