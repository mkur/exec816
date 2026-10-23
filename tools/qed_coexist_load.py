"""Ordinary Counter and foreground shell checksum loads for production QED."""
import json
import struct

from console_model import read_cells
from colour_desktop_model import FIELDS as DESKTOP
from gem_applications import symbols
from generate_aes_server import ABI, layout, expected_layout
from native_program import require
from program_image_layout import FIELDS as IMAGE
from qed_coexist_observe import heap_checkpoint


def cksum(data):
    """Independent bitwise POSIX checksum, including the encoded file length."""
    crc = 0
    length = len(data)
    suffix = bytearray()
    while length:
        suffix.append(length & 255); length >>= 8
    for value in data+suffix:
        crc ^= value << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04c11db7 if crc & 0x80000000 else 0)) & 0xffffffff
    return crc ^ 0xffffffff


class Loads:
    def __init__(self, session, menus, click, editor, cohort, payload, report):
        self.s, self.menus, self.click, self.e = session, menus, click, editor
        self.cohort, self.payload, self.report = cohort, payload, report
        self.state = dict(cohort=cohort, samples=[])
        report['load'] = self.state

    def live(self):
        return self.s.number(self.s.p['build']['task_storage']['LIVE'], 1)

    def focus(self, title):
        target = next(w['id'] for w in self.menus.windows() if title in w['title'])
        for _ in range(8):
            if self.menus.focus() == target:
                self.e.frames(10)
                return
            self.e.key('TAB', ctrl=True, settle=25)
        raise RuntimeError('Desktop keyboard cycle did not reach '+title)

    def start(self):
        s, e = self.s, self.e
        if self.cohort == 'peer':
            directory = s.p['output']/'bitmap-console'
            shared = e.provider
            self.desk = symbols(s.b, s.p, directory, 'desktop', s.number(shared['GEMDesktopChildren'], 4))['GEMDesk']
            self.menus.select('SYS:')
            self.click(296, 8); self.click(304, 28+4*11)
            at = self.desk+DESKTOP['children']
            s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)' % (at, at+2))
            identity = s.number(at, 4)
            self.counter = symbols(s.b, s.p, directory, 'counter', identity)['GEMCounter']
            s.rendezvous('dw($%x)=1' % (self.counter+12))
            require(self.live() == 8, 'Peer cohort did not fill eight public Tasks')
            self.state['identity'] = identity
            self.focus('Shell'); before = s.ledger()
            initial_heap = heap_checkpoint(s.rendezvous, s.far, s.p['build']['memory'])
            previous = s.begin('HELLO'); s.ready(previous); s.result(103)
            require(s.ledger() == before, 'Rejected ninth Task retained ownership')
            final_heap = heap_checkpoint(s.rendezvous, s.far, s.p['build']['memory'])
            self.state['admission_heap'] = dict(before=initial_heap, after=final_heap)
            (s.p['output']/'coexist-admission.json').write_text(json.dumps(self.state['admission_heap'], indent=2)+'\n')
            require(initial_heap == final_heap, 'Rejected ninth Task retained heap backing')
            self.state['ninth_task_rejected'] = True
            self.focus('SESSION.TXT'); e.move(630, 20)
        elif self.cohort == 'checksum':
            self.menus.select('Shell')
            self.previous = s.begin('CKSUM WORK:LOAD.BIN')
            s.rendezvous('db($%x)=8' % s.p['build']['task_storage']['LIVE'])
            s.frames(30)
            fields = e.fields; storage = s.p['build']['memory']['process_storage']
            candidates = []
            for i in range(1, 8):
                row = storage['BASE']+128*i
                image = s.number(row+fields['image'], 3)
                if s.number(row+fields['state'], 1) == 2 and image and s.number(image+IMAGE['kind'], 1) == 0:
                    candidates.append((row, image))
            require(len(candidates) == 1, 'No unique foreground native checksum Process')
            self.row, image = candidates[0]
            profile = json.loads((s.p['output']/'CKSUM.profile.json').read_text())
            crc = next(v for v in profile['objects'] if v['kind'] == 0 and '_CKSUM_CRC_' in v['name'])
            require(crc['location']['section'] == 'Bss' and crc['size'] == 4, 'Changed checksum observer layout')
            self.crc = s.number(image+IMAGE['bss'], 3)+crc['location']['offset']
            registry = s.p['build']['memory']['dos_storage']['SHARED']
            service = s.number(registry+68, 3); self.cache = s.number(service, 3)+30
            self.state['initial_cache_misses'] = s.number(self.cache+20)
            self.state['initial_crc'] = s.number(self.crc)
            self.menus.select('SESSION.TXT'); e.move(630, 20)
            self.sample('input-start')

    def sample(self, name):
        if self.cohort == 'baseline':
            return
        if self.cohort == 'peer':
            value = self.s.number(self.counter+14, 4)
        else:
            require(self.s.number(self.row+self.e.fields['state'], 1) == 2,
                    'Checksum finished before the concurrent input checkpoint: '+name)
            value = self.s.number(self.crc)
        self.state['samples'].append(dict(name=name, value=value, live_tasks=self.live()))
        require(self.live() == 8, 'Concurrent Task count changed at '+name)

    def held_form(self):
        if self.cohort == 'baseline':
            self.e.frames(100); return
        self.sample('form-start'); self.e.frames(100); self.sample('form-end')
        a, b = self.state['samples'][-2:]
        require(a['value'] != b['value'], 'Concurrent client made no progress during Find')
        self.state['form_progress'] = True

    def expose(self, lines):
        if self.cohort != 'peer':
            return
        e = self.e
        self.lines = list(lines)
        self.focus('Counter'); e.frames(50)
        # Locate the peer's published view instead of borrowing mutable work[] scratch.
        wf = layout()['WindowView']['fields']; offset = dict(expected_layout())['C context views']
        # Other windows can be behind QED; only Counter's front view covers it.
        from prime_observer import process_record
        row = process_record(self.s.far, self.s.p, self.state['identity'])
        task = row+e.fields['task']
        c = next(c for c in e.contexts() if c and e.get(c+e.owner_offset, 3) == task)
        view = next(e.get(c+offset+4*i, 4) for i in range(ABI['constants']['WINDOWS'])
                    if e.get(c+offset+4*i, 4) and e.get(e.get(c+offset+4*i, 4)+wf['shown']))
        e.covered = [struct.unpack('<4h', e.b.memdump(view+wf['bounds'], 8))]
        self.peer_bounds = e.covered[0]
        e.selection('peer-covered', lines, None, 14, 32)
        self.counter_pixels(e.covered[0])
        before = self.s.number(self.counter+14, 4); e.frames(100)
        require(self.s.number(self.counter+14, 4) > before, 'Counter stopped while exposed')
        self.focus('SESSION.TXT'); e.covered = []; e.move(630, 20)
        e.selection('peer-exposed', lines, None, 14, 32)
        self.state['cover_expose'] = True

    def counter_pixels(self, bounds):
        from gem_desktop_oracle import paint
        from gem_render_oracle import Raster, DESKTOP_PALETTE, PENS
        e = self.e; left, top, _, _ = bounds
        rgb = bytes((v & 254)+(v >> 7) for v in DESKTOP_PALETTE)
        colors = {pen: rgb[i*3:i*3+3][::-1] for i, pen in enumerate(PENS)}
        target = e.p['output'].parent/'counter-visible.bgra'
        for _ in range(80):
            raster = Raster(e.font)
            paint(e.b, {'GEMCounter': self.counter}, raster, b'Counter', bounds)
            frame = e.b.rawscreen(str(target)); raw = target.read_bytes()
            if all(raw[y*frame.stride+64+x*4:y*frame.stride+67+x*4] == colors[raster.pixels[y*640+x]]
                   for y in range(top+19, top+27) for x in range(left+16, left+120)):
                self.state['counter_label_pixels'] = 104*8
                return
            e.frames(1)
        raise RuntimeError('Counter did not display its independently rendered count')

    def finish(self):
        s = self.s
        if self.cohort == 'peer':
            e = self.e
            e.key('H'); modified = [b'h'+self.lines[0], *self.lines[1:]]
            self.focus('Shell')
            previous = s.begin('ALIAS STOPQED "BREAK '+str(e.owner['identity'])+'"')
            s.ready(previous); s.result()
            previous = s.begin('EXECUTE WORK:STOP.CMD')
            require(not e.form(), 'Stop script reached BREAK before focus could return')
            self.focus('SESSION.TXT'); e.form_open(); s.ready(previous); s.result()
            self.sample('stop-form-start'); e.frames(100); self.sample('stop-form-end')
            require(self.state['samples'][-1]['value'] > self.state['samples'][-2]['value'],
                    'Counter stopped during the QED Stop decision')
            e.alert(3); e.command_idle(); e.selection('peer-stop-cancel', modified, None, 1, 0)
            e.choose('SESSION.TXT', 'WORK'); e.form_open(); e.alert(2)
            e.loaded('peer-after-stop', self.lines, path=b'WORK:SESSION.TXT')
            self.state['cooperative_stop_cancel'] = True
            self.focus('Shell')
            previous = s.begin('UNALIAS STOPQED'); s.ready(previous); s.result()
            self.focus('Counter')
            self.click(self.peer_bounds[0]+6, self.peer_bounds[1]+5)
            at = self.desk+DESKTOP['children']
            s.rendezvous('(dw($%x)=0)&(dw($%x)=0)' % (at, at+2))
            self.state['collected'] = True
        elif self.cohort == 'checksum':
            self.state['completion_progress'] = []
            for index in range(120):
                if s.number(self.row+self.e.fields['state'], 1) != 2:
                    break
                before = (s.number(self.crc, 4), s.number(self.cache+20, 4))
                s.frames(500)
                if s.number(self.row+self.e.fields['state'], 1) != 2:
                    break
                after = (s.number(self.crc, 4), s.number(self.cache+20, 4))
                self.state['completion_progress'].append(dict(frames=(index+1)*500,
                    crc=after[0], cache_misses=after[1]))
                require(before != after, 'Checksum made no progress in 500 frames')
            else:
                raise RuntimeError('Checksum exceeded its 60000-frame aggregate bound')
            self.menus.select('Shell')
            s.ready(self.previous); s.result()
            expected = ('%d %d' % (cksum(self.payload), len(self.payload))).encode()
            require(expected in read_cells(s.far, s.saved['top']),
                    'Native checksum output differs from independent POSIX checksum')
            self.state['checksum'] = expected.decode()
            self.state['final_cache_misses'] = s.number(self.cache+20)
            require(self.state['final_cache_misses'] > self.state['initial_cache_misses'],
                    'Checksum did not exercise physical disk reads')
            values = [v['value'] for v in self.state['samples']]
            require(len(set(values)) > 1, 'Checksum computation did not advance during QED input')
            self.state['collected'] = True
