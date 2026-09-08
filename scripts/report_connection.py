#!/usr/bin/env python3
"""Join backend monotonic durations with BlueZ/QML observer timestamps."""
import argparse
import json
from summarize_connection import completed_runs


def load(path):
    with open(path) as stream:
        return [json.loads(line) for line in stream if line.strip()]


def report(backend, observer):
    previous = {}
    for run in completed_runs(backend):
        start, end = run[0], run[-1]
        pid = start['pid']
        product = next(r['product_id'] for r in run if r['phase'] == 'profile_resolved')
        hosts = [r for r in backend if r['pid'] == pid and r['phase'] in ('process_start', 'host_start')]
        host = hosts[0]
        signals = [r for r in observer if r['phase'] == 'bluez_connected_signal'
                   and host['unix_ns'] < r['unix_ns'] <= end['unix_ns']]
        prior = previous.get(pid)
        signal = signals[-1] if signals else None
        if signal and (prior is None or signal['unix_ns'] > prior[1]):
            scenario = 'arrival' if prior is None else ('reconnect' if prior[0] == product else 'switch')
            origin = signal['unix_ns']
        else:
            scenario = 'cold_service'
            origin = host['unix_ns']
        ui = next((r for r in observer if r['phase'] == 'ui_usable'
                   and r.get('product_id') == product
                   and end['unix_ns'] / 1e6 - 1 <= r['observed_unix_ms'] < end['unix_ns'] / 1e6 + 3000), None)
        spans = []
        pending = {}
        for row in run:
            phase = row['phase']
            if phase.endswith('.begin'):
                pending[(phase[:-6], row.get('command'))] = row
            elif phase.endswith('.end') or phase.endswith('.failed'):
                suffix = '.end' if phase.endswith('.end') else '.failed'
                key = (phase[:-len(suffix)], row.get('command'))
                begin = pending.pop(key, None)
                if begin:
                    spans.append({'phase': key[0], 'command': key[1],
                                  'failed': suffix == '.failed',
                                  'ms': round((row['monotonic_ns'] - begin['monotonic_ns']) / 1e6, 3)})
        yield {'pid': pid, 'product_id': product, 'scenario': scenario,
               'origin_unix_ns': origin, 'controller_unix_ns': start['unix_ns'],
               'notice_delay_ms': round((start['unix_ns'] - origin)/1e6, 3),
               'setup_ms': round((end['monotonic_ns']-start['monotonic_ns'])/1e6, 3),
               'to_ui_ms': round(ui['observed_unix_ms'] - origin/1e6, 3) if ui else None,
               'phases': spans}
        previous[pid] = (product, end['unix_ns'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend')
    parser.add_argument('observer')
    args = parser.parse_args()
    print(json.dumps(list(report(load(args.backend), load(args.observer))), indent=2))


if __name__ == '__main__':
    main()
