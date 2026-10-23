"""Measure and reuse the live desktop's lazy Counter-launch resources."""
import json
import struct
from pathlib import Path

from colour_desktop_model import FIELDS as DESKTOP
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import symbols
from generate_aes_server import ABI, expected_layout, layout
from native_program import ROOT, require, sha256
from prime_observer import process_record
from qed_coexist_observe import heap_checkpoint


def allocated(before, after):
    pieces = []
    for start, size in before['extents']:
        spans = [(start, start+size)]
        for free, count in after['extents']:
            spans = [part for lo, hi in spans for part in
                     [(lo, min(hi, free)), (max(lo, free+count), hi)] if part[0] < part[1]]
        pieces.extend(spans)
    return pieces


def warm(s):
    provider = json.loads((s.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
    fields = {n: o for n, _, o in json.loads((ROOT/'abi/process.json').read_text())['record']}
    owner_offset = layout()['Request']['fields']['owner']
    directory = s.p['output']/'bitmap-console'
    desktop_id = s.number(provider['GEMDesktopChildren'], 4)
    desk = symbols(s.b, s.p, directory, 'desktop', desktop_id)['GEMDesk']
    desktop_task = process_record(s.far, s.p, desktop_id)+fields['task']

    def contexts():
        return [s.number(provider['contexts']+4*i, 4) for i in range(ABI['constants']['CONTEXTS'])]

    def at(name):
        return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])

    def move(x, y):
        current = [s.number(at(n)) for n in ('cursorX', 'cursorY')]
        target = schedule(s.b, s.p, current, (x, y)); s.saved['pointer'] = target
        s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' % (at('cursorX'), target[0], at('cursorY'), target[1]))

    def click(x, y):
        move(x, y); s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(15)
        s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(50)

    def heap():
        return heap_checkpoint(s.rendezvous, s.far, s.p['build']['memory'])

    s.saved.setdefault('desktop_menu', {})
    menus = Menus(s, click, move); ledger = s.ledger(); cold = heap(); checkpoints = []
    for _ in range(2):
        menus.select('SYS:'); click(296, 8); click(304, 72)
        child = desk+DESKTOP['children']
        s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)' % (child, child+2))
        identity = s.number(child, 4)
        counter = symbols(s.b, s.p, directory, 'counter', identity)['GEMCounter']
        s.rendezvous('dw($%x)=1' % (counter+12)); s.frames(50)
        task = process_record(s.far, s.p, identity)+fields['task']
        context = next(c for c in contexts() if c and s.number(c+owner_offset, 3) == task)
        wf = layout()['WindowView']['fields']; views = dict(expected_layout())['C context views']
        view = next(s.number(context+views+4*i, 4) for i in range(ABI['constants']['WINDOWS'])
                    if s.number(context+views+4*i, 4) and
                    s.number(s.number(context+views+4*i, 4)+wf['shown']))
        left, top, _, _ = struct.unpack('<4h', s.far(view+wf['bounds'], 8))
        click(left+6, top+5)
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)' % (child, child+2))
        require(s.ledger() == ledger, 'Counter warm-up retained Process ownership')
        checkpoints.append(heap())
    require(checkpoints[0] == checkpoints[1], 'Repeated Counter launch accumulated memory')
    spans = allocated(cold, checkpoints[0])
    (s.p['output']/'desktop-warmup.json').write_text(json.dumps(dict(status='checking-owners',
        cold_heap=cold, warm_heaps=checkpoints, spans=spans), indent=2)+'\n')
    require(sum(hi-lo for lo, hi in spans) == 368, 'Unexpected desktop first-use backing')

    # Identify the retained roots without guessing a C field offset. The native
    # port/request layouts come from the ABI; their pointers must occur in the
    # live desktop C context. DOS's native side entry owns its path scratch.
    context = next(c for c in contexts() if c and s.number(c+owner_offset, 3) == desktop_task)
    raw = s.far(context, dict(expected_layout())['C context size'])
    port_abi = json.loads((ROOT/'abi/ports.json').read_text())['records']
    port_task = next(o for n, _, o in port_abi['MsgPort']['fields'] if n == 'mp_SigTask')
    reply = next(o for n, _, o in port_abi['Message']['fields'] if n == 'mn_ReplyPort')
    timer_size = json.loads((ROOT/'abi/timer-device.json').read_text())['records']['TimerClockRequest']['size']
    addresses = [at for lo, hi in spans for at in range((lo+7)&~7, hi, 8)]
    ports = [at for at in addresses if struct.pack('<I', at) in raw and
             s.number(at+port_task, 3) == desktop_task]
    require(len(ports) == 1, 'Retained timer port is not owned by the desktop')
    requests = [at for at in addresses if at != ports[0] and struct.pack('<I', at) in raw and
                s.number(at+reply, 3) == ports[0]]
    require(len(requests) == 2, 'Desktop does not retain its two timer requests')
    paths = [lo+i for lo, hi in spans
             for i in [s.far(lo, hi-lo).find(b'D1:C/COUNTER.APP\0')] if i >= 0]
    require(len(paths) == 1, 'Missing desktop command-path scratch')
    dos = s.p['build']['memory']['dos_storage']['BASE']
    client = next(s.number(dos+16*i, 3) for i in range(8) if s.number(dos+16*i+3, 3) == desktop_task)
    require(paths[0].to_bytes(3, 'little') in s.far(client, 106), 'Path scratch has no live desktop DOS owner')
    require(256+((port_abi['MsgPort']['size']+7)&~7)+2*((timer_size+7)&~7) == 368,
            'Changed lazy resource sizes')
    report = dict(status='pass', cold_heap=cold, warm_heaps=checkpoints, iterations=2,
        retained_upper_bytes=368, accumulating_bytes=0, desktop_task=desktop_task,
        desktop_context=context, dos_client=client, path_scratch=paths[0], path_bytes=256,
        timer_port=ports[0], timer_requests=requests, timer_backing_bytes=112,
        observer=dict(path=str(Path(__file__).relative_to(ROOT)), sha256=sha256(Path(__file__))))
    (s.p['output']/'desktop-warmup.json').write_text(json.dumps(report, indent=2)+'\n')
    return report
