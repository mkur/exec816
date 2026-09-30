"""Acceptance checks for observed eight-Task shell interruption timelines."""
from math import isclose
from sio_transaction_trace import BASE_HZ
LIMITS = dict(delivery_ms=100, queued_reply_ms=250, prompt_ms=500)


def validate(timing, queued=False):
    required = ('capture', 'durable', 'retained', 'physical', 'usable')
    if any(name not in timing for name in required):
        raise ValueError('Incomplete break timeline')
    if not timing['capture'] <= timing['durable'] <= timing['retained'] <= timing['physical']:
        raise ValueError('Break/prompt ownership timeline is out of order')
    if not timing['usable'] >= timing['retained']:
        raise ValueError('Prompt reported usable before its write was committed')
    measured = dict(delivery_ms=(timing['durable']-timing['capture'])/BASE_HZ*1000,
                    prompt_ms=(max(timing['physical'],timing['usable'])-timing['capture'])/BASE_HZ*1000)
    if queued:
        if not all(name in timing for name in ('queued_publication','queued_reply')):
            raise ValueError('Incomplete queued cancellation timeline')
        if not timing['durable'] <= timing['queued_publication'] <= timing['queued_reply'] <= timing['usable']:
            raise ValueError('Queued cancellation timeline is out of order')
        measured['queued_reply_ms']=(timing['queued_reply']-timing['queued_publication'])/BASE_HZ*1000
    for name, value in measured.items():
        if name not in timing or not isclose(value,timing[name],rel_tol=1e-12,abs_tol=1e-9):
            raise ValueError('Timing does not match observed milestones: '+name)
    for name, limit in LIMITS.items():
        if name == 'queued_reply_ms' and not queued:
            continue
        if name not in timing or not 0 <= timing[name] <= limit:
            raise ValueError(f'{name} exceeds its {limit} ms acceptance bound')
