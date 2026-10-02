"""Independent timer-latch accounting from POKEY writes and emitted entries."""
from os_boundary import require
from sio_transaction_trace import read_events


def accounting(path, labels):
    pending = None
    acknowledged = None
    consumed = set()
    physical = logical = alarms = samples = 0
    dispatch = None
    for cycle, event in read_events(path):
        if event[0] == 'timer' and int(event[2]) == 0:
            physical += 1
            pending = physical
        elif event[0] == 'register' and int(event[2]) == 14 and int(event[3]) & 1 == 0:
            if pending is not None:
                acknowledged = pending
                pending = None
        elif event[0] == 'cpu':
            pc = int(event[4], 16)
            if pc == labels['timer_tick']:
                require(acknowledged is not None and acknowledged not in consumed,
                        'Timer dispatch without a new acknowledged physical edge')
                consumed.add(acknowledged)
                logical += 1
                dispatch = set()
            elif pc in (labels['sio_alarm'], labels['timer_sample']):
                require(dispatch is not None and pc not in dispatch,
                        'Duplicate backend service in one timer dispatch')
                dispatch.add(pc)
                alarms += pc == labels['sio_alarm']
                samples += pc == labels['timer_sample']
    require(logical > 0 and samples > 0, 'No shared timer dispatch observed')
    return dict(physical_edges=physical, logical_dispatches=logical,
                alarm_services=alarms, pointer_samples=samples,
                duplicate_dispatches=0, duplicate_backend_services=0)
