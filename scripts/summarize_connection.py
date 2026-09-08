#!/usr/bin/env python3
"""Print completed controller-start phases from lifecycle JSONL traces."""
import argparse
import json


def completed_runs(records):
    active = {}
    for row in records:
        pid = row['pid']
        if row['phase'] == 'controller_start':
            active[pid] = []
        if pid not in active:
            continue
        active[pid].append(row)
        if row['phase'] == 'controller_usable':
            yield active.pop(pid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace')
    args = parser.parse_args()
    with open(args.trace) as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    for run in completed_runs(rows):
        origin = run[0]['monotonic_ns']
        print('RUN', run[0]['pid'], 'unix_ns', run[0]['unix_ns'])
        for row in run:
            print(f"{(row['monotonic_ns']-origin)/1e6:9.1f} ms", row['phase'],
                  row.get('command', row.get('product_id', '')))


if __name__ == '__main__':
    main()
