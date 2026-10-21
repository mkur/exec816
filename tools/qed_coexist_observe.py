"""Passive production QED and heap observers for the step 6 desktop workload."""
import json
import re
import struct

import adapter_state as adapter
from gem_render_oracle import font_bytes, Raster, DESKTOP_PALETTE, PENS
from generate_aes_server import ABI, layout, expected_layout
from native_program import ROOT, require, sha256
from prime_observer import process_record
from program_image_layout import FIELDS as IMAGE_FIELDS
from qed_form_oracle import paint
from qed_saving_observe import SavingEditor


def heap_snapshot(read, storage):
    """Read a paused checkpoint using the public heap record ABI."""
    records = json.loads((ROOT / 'abi/heap-v1.json').read_text())['records']
    hf = {n: o for n, _, o in records['MemHeader']['fields']}
    cf = {n: o for n, _, o in records['MemChunk']['fields']}
    number = lambda data, at, size: int.from_bytes(data[at:at+size], 'little')
    stride = (storage['BYTES'] - (storage['HEADERS'] - storage['BASE'])) // storage['CAPACITY']
    extents, regions = [], []
    for i in range(storage['CAPACITY']):
        raw = read(storage['HEADERS'] + i*stride, records['MemHeader']['size'])
        high = number(raw, hf['mh_Upper'], 4)
        if not high:
            continue
        low = number(raw, hf['mh_Lower'], 3)
        free = number(raw, hf['mh_Free'], 4)
        at = number(raw, hf['mh_First'], 3)
        require(0 < low < high <= 0x1000000 and (low | high | free) % 8 == 0,
                'Invalid heap region bounds/alignment')
        total, end, seen = 0, low, set()
        while at:
            require(at not in seen and end <= at <= high-8 and at % 8 == 0,
                    'Invalid heap free-list pointer/order')
            seen.add(at)
            chunk = read(at, records['MemChunk']['size'])
            size = number(chunk, cf['mc_Bytes'], 4)
            require(size >= 8 and size % 8 == 0 and at+size <= high,
                    'Invalid heap free extent')
            extents.append([at, size]); total += size; end = at+size
            at = number(chunk, cf['mc_Next'], 3)
            require(len(seen) <= (high-low)//8, 'Unbounded heap free list')
        require(total == free, 'Heap free-byte accounting differs')
        regions.append([low, high, free])
    require(regions, 'No published heap regions')
    return dict(free_bytes=sum(n for _, n in extents),
                largest_bytes=max((n for _, n in extents), default=0),
                free_extents=len(extents), regions=regions, extents=extents)


def heap_checkpoint(reach, read, memory):
    # lib/exec/heap-system.inc requires SWITCHING for every system-list writer.
    # IRQ/NMI never mutate these lists. The paused zero checkpoint is quiescent;
    # caller-side CLEAR touches only the allocated payload, outside free lists.
    reach('db($%x)=0' % adapter.SWITCHING)
    return heap_snapshot(read, memory['heap_storage'])


def emitted_offsets(production, fixture):
    """Borrow only a matching target-emitted constant table, never fixture code."""
    for directory in ('qed/src', 'cflib'):
        a, b = production/'inputs/source'/directory, fixture/'inputs/source'/directory
        for header in a.glob('*.h'):
            require(sha256(header) == sha256(b/header.name), 'Changed QED layout header: '+header.name)
    a = json.loads((production/'inputs/sources.json').read_text())
    b = json.loads((fixture/'inputs/sources.json').read_text())
    require(a['patches'] == b['patches'], 'Changed QED layout patch set')
    app = json.loads((fixture/'app.json').read_text())
    address = app['image']['symbols']['QedEditingLayout']
    for segment in app['image']['segments']:
        index = address-segment['address']
        if 0 <= index <= len(segment['bytes'])-62:
            return struct.unpack('<31H', bytes(segment['bytes'][index:index+62]))
    raise RuntimeError('Missing target-emitted QED layout table')


class ProductionEditor(SavingEditor):
    """Reuse independent ring/form/pixel oracles without interposing production."""
    def __init__(self, session, production, offsets, identity, output, record, cycle):
        self.s, self.b, self.record = session, session.b, record
        self.p = {**session.p, 'output': output/'program'}
        self.app = json.loads((production/'app.json').read_text())
        row = process_record(session.far, session.p, identity)
        fields = {n: o for n, _, o in json.loads((ROOT/'abi/process.json').read_text())['record']}
        image = session.number(row+fields['image'], 3)
        base = session.number(image+IMAGE_FIELDS['text'], 3)
        delta = base-(self.app['abi']['link_bank'] << 16)
        self.sy = {n: at+delta for n, at in self.app['image']['symbols'].items()}
        self.owner = dict(record=row, identity=identity, image_base=base)
        self.task = row+fields['task']; self.fields = fields
        self.offsets, self.extra = offsets[:27], offsets[27:]
        self.provider = json.loads((session.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
        self.font = font_bytes(session.p['output']/'bitmap-console/selected/src/vdi/font8x8.c')
        self.owner_offset = layout()['Request']['fields']['owner']
        self.contexts = lambda: [self.get(self.provider['contexts']+4*i, 4) for i in range(ABI['constants']['CONTEXTS'])]
        self.ids = {n: int(v) for n, v in re.findall(r'^#define\s+(\w+)\s+(\d+)',
            (production/'inputs/source/qed/src/qed.h').read_text(encoding='latin1'), re.M)}
        self.pending_dispatch = self.pending_global = None
        self.expected_range = None
        self.scene = dict(process=identity, image_base=base, cycle=cycle, snapshots=[], keys=[], timings=[])
        record.setdefault('qed_editing', []).append(self.scene)

    def reach(self, condition, timeout=120):
        self.s.rendezvous(condition)

    def frames(self, n=30):
        self.s.frames(n)

    def key(self, name, ctrl=False, shift=False, settle=12, **unused):
        if ctrl: self.b._cmd_ok('KEY CTRL down')
        if shift: self.b._cmd_ok('KEY SHIFT down')
        require(self.b._cmd_ok('KEY '+name+' down')['raw_scan'], 'Unavailable physical key: '+name)
        self.frames(3); self.b._cmd_ok('KEY '+name+' up')
        if shift: self.b._cmd_ok('KEY SHIFT up')
        if ctrl: self.b._cmd_ok('KEY CTRL up')
        if settle: self.frames(settle)

    def form_key(self, name, **options):
        return self.key(name, **options)

    def native(self, name, size=2):
        require(name == 'cycle', 'Production observer requested a fixture variable')
        return self.scene['cycle']

    def menu(self, title, item):
        from qed_editing_observe import Editor
        return Editor.menu(self, title, item)

    def text_pixels(self, name, lines):
        state = self.text()
        require(state['lines'] == lines, 'Pending text model: '+name)
        return self._pixels(name, lines, state)

    def form_pixels_once(self, name):
        require(self.form(), 'Pending native form: '+name)
        raster = Raster(self.font)
        x, y, w, h = paint(self.b, self.context(), raster)
        target = self.p['output'].parent/('form-'+name+'.bgra')
        capture = self.b.rawscreen(str(target)); raw = target.read_bytes()
        rgb = bytes((v & 254)+(v >> 7) for v in DESKTOP_PALETTE)
        colors = {pen: rgb[i*3:i*3+3][::-1] for i, pen in enumerate(PENS)}
        for yy in range(y, y+h):
            for xx in range(x, x+w):
                at = yy*capture.stride+64+xx*4
                require(raw[at:at+3] == colors[raster.pixels[yy*640+xx]], 'Pending form pixels: '+name)
        return dict(pixels=w*h)

    def timed_key(self, name, key, oracle, limit_ms, ctrl=False):
        from sio_transaction_trace import BASE_HZ
        start = self.b.eval_expr('@clk') & 0xffffffff
        self.key(key, ctrl=ctrl, settle=0)
        for attempt in range(100):
            try:
                observed = oracle()
                break
            except RuntimeError:
                if attempt == 99: raise
                self.frames(1)
        elapsed = ((self.b.eval_expr('@clk')-start) & 0xffffffff)/BASE_HZ*1000
        item = dict(name=name, elapsed_ms=elapsed, limit_ms=limit_ms,
                    observations=attempt+1, endpoint='first independently correct completed scanout', observed=observed)
        self.scene['timings'].append(item)
        print('QED coexistence:', name, round(elapsed, 1), 'ms', flush=True)
        require(elapsed <= limit_ms, 'QED response limit exceeded: '+name)
        return item

    def snapshot(self, name):
        heap = heap_checkpoint(self.reach, self.s.far, self.s.p['build']['memory'])
        private = list(struct.unpack('<4I', self.b.memdump(self.sy['totals'], 16)))
        item = dict(name=name, heap=heap, qed_private=private,
                    live_tasks=self.s.number(self.s.p['build']['task_storage']['LIVE'], 1))
        self.scene.setdefault('memory', []).append(item)
        return item
