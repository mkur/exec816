#!/usr/bin/env python3
"""Local rejection, native link modes, canonical empties and directory growth."""
import argparse
import json
import time
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute
from test_heap_api import clean_ownership
from test_cooperative import data
from test_filesystem_write import reuse
from generate_dos_mounts import encode
from filesystem_audit import Audit, word
from mydos_fixtures import Image
from make_shell_disk import make as make_mydos
import sdfs_reference

CASES = {'normal': 1, 'readonly': 2, 'protected': 3, 'full': 4,
         'incomplete': 5, 'corrupt': 6, 'sparse': 7, 'legacy-empty': 8,
         'tenbit-full': 9, 'full-directory': 4, 'fragmented': 10,
         'partial-group': 11}


def limited(filesystem, size, folder):
    """Consistent media with fewer free payloads than a full extension group."""
    tree=folder/'limited-source';tree.mkdir(exist_ok=True)
    (tree/'KEEP.BIN').write_bytes(bytes(range(256)))
    (tree/'CREATE.BIN').write_bytes(b'')
    payload=size-3 if filesystem=='mydos' else size
    wanted=3
    for sectors in range(680,720):
        for part in range(15):
            count=min(50,max(0,sectors-part*50))
            (tree/f'FILL{part}.BIN').write_bytes(bytes([0x59])*(count*payload))
        path=folder/'initial.atr'
        try:
            if filesystem=='mydos':
                make_mydos(path,tree,binary_names={p.name for p in tree.iterdir()},sector_bytes=size)
            else:
                sdfs_reference.make(path,tree,720,size)
        except (ValueError,StopIteration):
            continue
        image=Image(path.read_bytes())
        header=image.sector(360 if filesystem=='mydos' else 1)
        if word(header,3 if filesystem=='mydos' else 13)==wanted:
            audit=Audit(image.data);getattr(audit,filesystem)()
            return image
    raise ValueError('Could not produce a consistent nearly-full image')


def entry(image, filesystem, name):
    if filesystem == 'mydos':
        row = next(e for e in image.entries() if e['name'] == name)
        at = image.offset(361 + row['ordinal']//8) + (row['ordinal'] % 8)*16
        return list(range(at, at+16)), row['start'], row['ordinal']
    page = word(image.sector(1), 9)
    sectors = []
    while page:
        block = image.sector(page)
        sectors.extend(word(block, i) for i in range(4, image.size, 2))
        page = word(block, 0)
    length = int.from_bytes(image.sector(sectors[0])[3:6], 'little')
    for offset in range(23, length, 23):
        addresses = [image.offset(sectors[pos//image.size]) + pos % image.size
                     for pos in range(offset, offset+23)]
        row = bytes(image.data[i] for i in addresses)
        stored = row[6:14].decode().rstrip() + ('.' + row[14:17].decode().rstrip() if row[14:17] != b'   ' else '')
        if stored == name:
            return addresses, word(row, 1), offset//23-1
    raise ValueError('Missing entry ' + name)


def bitmap(image, filesystem, sector):
    if filesystem == 'mydos':
        logical = 10 + sector//8
        return image.offset(360-logical//image.size) + logical % image.size
    return image.offset(word(image.sector(1), 16) + (sector//8)//image.size) + (sector//8) % image.size


def prepare(filesystem, size, name):
    if name == 'full-directory':
        require(filesystem == 'mydos', 'Fixed directory case needs MyDOS')
        image=Image((ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr').read_bytes())
        require(len(list(image.entries()))==64, 'Expected a full native directory')
        return image
    image = Image((ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr').read_bytes())
    row, first, ordinal = entry(image, filesystem, 'EMPTY' if name == 'legacy-empty' else 'CREATE.BIN')
    header = image.offset(360 if filesystem == 'mydos' else 1)
    free_at = header + (3 if filesystem == 'mydos' else 13)
    if name == 'fragmented':
        require(filesystem == 'mydos', 'Contiguous directory case needs MyDOS')
        chain=[s for s in range(8,image.count+1,8)
               if image.data[bitmap(image,filesystem,s)] & (0x80 >> (s & 7))]
        for i,sector in enumerate(chain):
            image.data[bitmap(image,filesystem,sector)] &= ~(0x80 >> (sector & 7))
            payload=bytearray(size)
            next_sector=chain[i+1] if i+1<len(chain) else 0
            payload[-3:]=bytes((next_sector>>8,next_sector&255,size-3))
            image.data[image.offset(sector):image.offset(sector)+size]=payload
        row=bytearray(16)
        row[0]=0x46
        row[1:3]=len(chain).to_bytes(2,'little')
        row[3:5]=chain[0].to_bytes(2,'little')
        row[5:]=b'FILLER     '
        image.data[image.offset(361)+112:image.offset(361)+128]=row
        image.data[free_at:free_at+2]=(word(image.data,free_at)-len(chain)).to_bytes(2,'little')
        Audit(image.data).mydos()
    elif name == 'protected':
        image.data[row[0]] |= 0x20 if filesystem == 'mydos' else 1
    elif name == 'full':
        image.data[free_at:free_at+2] = b'\0\0'
    elif name == 'incomplete':
        image.data[row[0]] |= 1 if filesystem == 'mydos' else 0x80
    elif name == 'corrupt':
        if filesystem == 'mydos':
            at = image.offset(first)+size-3
            image.data[at:at+2] = bytes(((ordinal << 2) | (first >> 8), first & 255))
        else:
            image.data[image.offset(first)+2:image.offset(first)+4] = b'\1\0'
    elif name == 'sparse':
        require(filesystem == 'sdfs', 'Sparse case needs SDFS')
        image.data[image.offset(first)+4:image.offset(first)+6] = b'\0\0'
    elif name == 'legacy-empty':
        require(first != 0, 'Producer empty already has zero start')
        at = bitmap(image, filesystem, first)
        image.data[at] |= 0x80 >> (first & 7)
        free = word(image.data, free_at)
        image.data[free_at:free_at+2] = (free+1).to_bytes(2, 'little')
        for index in ((1, 2, 3, 4) if filesystem == 'mydos' else (1, 2)):
            image.data[row[index]] = 0
    elif name == 'tenbit-full':
        require(filesystem == 'mydos' and size == 256, 'Ten-bit exhaustion needs large MyDOS')
        data, chain = image.file(next(e for e in image.entries() if e['name'] == 'CREATE.BIN'))
        image.data[row[0]] &= ~4
        for sector in chain:
            at = image.offset(sector)+size-3
            image.data[at] = (image.data[at] & 3) | (ordinal << 2)
        removed = 0
        for sector in range(4, 1024):
            at = bitmap(image, filesystem, sector)
            mask = 0x80 >> (sector & 7)
            removed += bool(image.data[at] & mask)
            image.data[at] &= ~mask
        image.data[free_at:free_at+2] = (word(image.data, free_at)-removed).to_bytes(2, 'little')
    return image


def run(output, mode, filesystem, size, names, from_build):
    baseline = Audit((ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr').read_bytes())
    getattr(baseline, filesystem)()
    mounts = [dict(alias='D1', unit=49, sectors=baseline.image.count, sector_bytes=size,
                   format=1 if filesystem == 'mydos' else 2, access='readwrite')]
    program = reuse(from_build) if from_build else build(compiler(ROOT/'build/actionc'),
                ROOT/'tests/programs/filesystem_write_edges.act', output, optimize=mode == 'opt',
                tasks=True, console_deferred=True, dos_mounts=mounts, system_mount='D1')
    require(program['build']['optimize'] == (mode == 'opt'), 'Changed emission mode')
    cases = []
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        configuration = {**PIN['configuration'], 'diskemu': 'fastest', 'accuratedisk': False}
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        for index, name in enumerate(names):
            print('Write edge', name, flush=True)
            case_out = output/name
            case_out.mkdir(exist_ok=True)
            media = case_out/'volume.atr'
            initial = limited(filesystem,size,case_out) if name=='partial-group' else prepare(filesystem, size, name)
            media.write_bytes(initial.data)
            mounts[0]['sectors']=initial.count
            mounts[0]['access'] = 'readonly' if name == 'readonly' else 'readwrite'
            if index:
                bridge.state_load(slot='loaded')

            def before(bridge):
                if not index:
                    bridge.state_save(slot='loaded')
                bridge.mount(0, str(media))
                bridge.memload(program['build']['task_storage']['BASE'] + 0x900, encode(mounts))
                address = next(d['address'] for d in program['image']['data'] if '_FSWRITEEDGES_SCENARIO_' in d['name'])
                bridge.memload(address, CASES[name].to_bytes(2, 'little'))

            try:
                runtime, _ = execute(bridge, {**program, 'output': case_out}, before_run=before,
                                     timeout=900, frame_limit=60000, preloaded=bool(index))
            except Exception:
                inspection = {**program['image'], 'data': [d for d in program['image']['data'] if '_FSWRITEEDGES_' in d['name']]}
                print({key: data(bridge, inspection, key, True) for key in ('checks', 'scenario', 'phase', 'result', 'error')}, flush=True)
                raise
            clean_ownership(bridge, program, program['output'])
            time.sleep(3)
            bridge.regs()
            bridge._cmd_ok('EJECT drive=0')
            report = None
            if name not in ('normal', 'legacy-empty', 'tenbit-full', 'partial-group'):
                require(media.read_bytes() == initial.data, 'Rejected operation changed media')
            elif name == 'tenbit-full':
                after = Image(media.read_bytes())
                row, _, _ = entry(after, filesystem, 'CREATE.BIN')
                require(after.data[row[0]] == 0x42, 'Changed ten-bit link mode')
                file = next(e for e in after.entries() if e['name'] == 'CREATE.BIN')
                content, _ = after.file(file)
                require(content == baseline.files['CREATE.BIN'] + bytes(i ^ 0xc3 for i in range(206)), 'Wrong exhausted prefix')
                for sector in range(1024, after.count+1):
                    at = bitmap(after, filesystem, sector)
                    require(after.data[at] == initial.data[at], 'Ten-bit writer allocated a high sector')
            else:
                audit = Audit(media.read_bytes())
                report = getattr(audit, filesystem)()
                if name=='partial-group':
                    initial_audit=Audit(initial.data);getattr(initial_audit,filesystem)()
                    expected=dict(initial_audit.files)
                    length=(size-3)*3 if filesystem=='mydos' else size*3
                    expected['CREATE.BIN']=bytes((i&255)^0xc3 for i in range(length))
                else:
                    expected = dict(baseline.files)
                if name == 'normal':
                    payload = bytearray(expected['CREATE.BIN'])
                    payload[124:128] = bytes(i ^ 0xc3 for i in range(4))
                    payload.extend(i ^ 0xc3 for i in range(4))
                    expected['CREATE.BIN'] = bytes(payload)
                require(audit.files == expected, 'Persisted edge contents changed')
            cases.append(dict(status='pass', name=name, runtime=runtime, audit=report,
                              media_sha256=sha256(media)))
            (output/'progress.json').write_text(json.dumps(cases, indent=2) + '\n')
    return dict(status='pass', build=program['build'], cases=cases, machine=machine,
                configuration=configuration, bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), required=True)
    parser.add_argument('--size', type=int, choices=(128, 256), default=128)
    parser.add_argument('--suite', default='normal,readonly,protected,full,incomplete,corrupt,legacy-empty')
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(output, args.case, args.filesystem, args.size, args.suite.split(','),
                     args.from_build.resolve() if args.from_build else None)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Write edges passed', args.case, args.filesystem)
