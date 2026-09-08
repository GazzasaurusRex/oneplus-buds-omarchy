"""Opt-in local lifecycle timestamps; never include addresses or protocol payloads."""
from contextlib import contextmanager
import json
import os
from threading import Lock
from time import monotonic_ns, time_ns

_lock = Lock()


def mark(phase: str, **fields: str | int | bool) -> None:
    path = os.environ.get('ONEPLUS_BUDS_LIFECYCLE_TRACE')
    if not path:
        return
    record = dict(phase=phase, monotonic_ns=monotonic_ns(), unix_ns=time_ns(),
                  pid=os.getpid(), **fields)
    try:
        with _lock, open(path, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, sort_keys=True) + '\n')
    except OSError:
        # Diagnostics must never change connection success/failure policy.
        pass


@contextmanager
def span(phase: str, **fields: str | int | bool):
    mark(phase + '.begin', **fields)
    try:
        yield
    except BaseException:
        mark(phase + '.failed', **fields)
        raise
    else:
        mark(phase + '.end', **fields)
