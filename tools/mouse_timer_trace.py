"""Independent timer-latch accounting from POKEY writes and emitted entries."""
from os_boundary import require
from sio_transaction_trace import read_events, stats, BASE_HZ
from statistics import median


def cadence(events, labels):
    """Separate physical periods from capture cadence, including rate changes.

    The AUDF write does not reset the running counter. Omit the first edge-to-
    edge interval of each segment from steady-period statistics; retain all
    sample gaps in the caller's end-to-end envelope check.
    """
    segments = []
    current = None
    for cycle, event in events:
        if event[0] == 'register' and int(event[2]) == 0:
            divisor = int(event[3])
            if current is not None:
                current['end'] = cycle
            current = dict(start=cycle, end=cycle, divisor=divisor, edges=[], samples=[])
            segments.append(current)
        elif current is not None:
            current['end'] = cycle
            if event[0] == 'timer' and int(event[2]) == 0:
                current['edges'].append(cycle)
            elif event[0] == 'cpu' and int(event[4], 16) == labels['timer_sample']:
                current['samples'].append(cycle)
    modes = {}
    for divisor in (15, 7):
        selected = [s for s in segments if s['divisor'] == divisor]
        periods = [b-a for s in selected for a, b in zip(s['edges'][1:], s['edges'][2:])]
        gaps = [b-a for s in selected for a, b in zip(s['samples'], s['samples'][1:])]
        modes[str(divisor)] = dict(intervals=len(selected),
            configured_ms=sum(s['end']-s['start'] for s in selected)/BASE_HZ*1000,
            physical_edges=sum(len(s['edges']) for s in selected),
            pointer_samples=sum(len(s['samples']) for s in selected),
            physical_period=stats(periods), sample_period=stats(gaps),
            median_sample_period_cycles=median(gaps) if gaps else None,
            median_physical_period_cycles=median(periods) if periods else None)
    return dict(au_df1=modes,
        transitions=[dict(begin=s['start'], end=s['end'], divisor=s['divisor'],
                          physical_edges=len(s['edges']), pointer_samples=len(s['samples']))
                     for s in segments if s['divisor'] in (7, 15)])


def require_normal_cadence(observation, fine=False):
    """Reject an 8 kHz interrupt stream with merely decimated captures."""
    modes = observation['cadence']['au_df1']
    require(modes['15']['physical_edges'] > 100 and
            modes['15']['median_physical_period_cycles'] == 448,
            'Normal timer did not physically run at about 4 kHz')
    if fine:
        require(modes['7']['physical_edges'] > 10 and
                modes['7']['median_physical_period_cycles'] == 224,
                'Fine SIO timer did not run at about 8 kHz')
        if modes['7']['sample_period']['count'] >= 10:
            require(350 < modes['7']['median_sample_period_cycles'] < 550,
                    'Fine SIO interrupts did not preserve about 4 kHz capture')


def accounting(path, labels, events=None):
    pending = None
    acknowledged = None
    consumed = set()
    physical = logical = alarms = samples = 0
    dispatch = None
    events = read_events(path) if events is None else events
    for cycle, event in events:
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
                duplicate_dispatches=0, duplicate_backend_services=0,
                cadence=cadence(events, labels))
