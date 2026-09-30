"""Retain the continuous-sector deadline for B5's independent full-file reader."""
from sio_adapter_trace import transmit_bursts
from sio_transaction_trace import read_events, BASE_HZ
from sio_concurrent_trace import LIMITS
from mydos_fixtures import Image
from os_boundary import require


def continuous_gaps(sectors, starts, posts, chain):
    require(len(sectors) == len(starts) == len(posts), 'Incomplete sector timeline')
    matches = [i for i in range(len(sectors)-len(chain)+1)
               if sectors[i:i+len(chain)] == chain]
    require(len(matches) == 1 and len(chain) > 1, 'Missing/ambiguous complete file chain')
    at = matches[0]
    gaps = [(starts[i+1]-posts[i])/BASE_HZ*1e6 for i in range(at,at+len(chain)-1)]
    require(all(0 <= gap <= LIMITS['next_start_max_us'] for gap in gaps),
            'Continuous peer Read exceeded its existing next-sector deadline')
    return gaps


def analyze(trace, marks, media, size):
    disk = Image(media.read_bytes())
    name = 'LARGE.BIN' if size == 256 else 'TOOLS/SUB/DATA.BIN'
    entry = next(e for e in disk.walk() if e['path'] == name)
    payload, chain = disk.file(entry)
    expected = 70003 if size == 256 else 777
    require(len(payload) == expected, 'Wrong peer file length')
    events = read_events(trace)
    times = lambda name: [t for t,e in events if e[0] == 'cpu' and int(e[4],16) == marks[name]]
    starts, posts, stop = times('sio_start'), times('signal_post'), times('sio_shutdown')[0]
    active = [(t,e) for t,e in events if starts[0] <= t <= stop]
    bursts = transmit_bursts(active, require)
    frames = [[int(e[2]) for _,e in ready] for ready, writes, end in bursts]
    require(all(len(f) == 5 and f[:2] == [49,82] for f in frames), 'Unexpected peer command')
    gaps = continuous_gaps([f[2]+(f[3]<<8) for f in frames], starts, posts, chain)
    return dict(file=name,bytes=expected,sectors=len(chain),gaps=len(gaps),
                max_us=max(gaps),limit_us=LIMITS['next_start_max_us'],
                scope='Consecutive sectors of the independently extracted complete file chain within one peer DOS.Read.')
