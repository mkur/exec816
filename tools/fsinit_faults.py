"""Small FSINIT acquisition selectors, sharing one image across requested faults."""
from pathlib import Path
import shutil
from library_paths import library_file, read_source
from native_program import ROOT, build, require, sha256, verify_machine
from test_sio_device import PIN
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data

# These acquisitions occur once per mount, so also fail after a live sibling.
PER_MOUNT = {'mount', 'parser-volume', 'backend-volume', 'sdfs-volume',
             'block-volume', 'mount-port', 'owner', 'device-open', 'metadata-read'}


def instrument(out, names, failures):
    modules = {}
    for site, name in enumerate(names, 1):
        if name == 'metadata-read':
            module, old = 'blockwire', '  error=INT(CARD(state))'
            new = old + f'\n  IF error=0 AND FSINITPROBE.Fail({site})<>0 THEN\n' \
                '    request.io_Error=4\n    request.io_Actual=0\n    error=4\n  FI'
        else:
            module, old, failure, _ = failures[name]
            new = f'IF FSINITPROBE.Fail({site})<>0 THEN\n    {failure}\n  ELSE\n    {old}\n  FI'
        text = modules.get(module, read_source(library_file(module+'.act')))
        require(text.count(old) == 1, 'Stale FSINIT fault hook: '+name)
        modules[module] = text.replace(old, new)
    hashes = {}
    for module, text in modules.items():
        text = text.replace('\nUSE ', '\nUSE FSINITPROBE\nUSE ', 1)
        path = out/(module+'.act')
        path.write_text(text)
        hashes[path.name] = sha256(path)
    return hashes


def run(t, out, mode, names, filesystem, failures):
    require(bool(names) and len(names) == len(set(names)), 'Empty/repeated FSINIT fault')
    require(all(n in failures or n == 'metadata-read' for n in names), 'Unknown acquisition fault')
    require(filesystem == 'sdfs' or 'sdfs-volume' not in names, 'SDFS volume fault on MyDOS')
    require(filesystem == 'mydos' or 'backend-volume' not in names, 'MyDOS volume fault on SDFS')
    out.mkdir(parents=True, exist_ok=True)
    overrides = instrument(out, names, failures)
    mounts = [dict(alias='D'+str(i+1), unit=49+i, profile=1, sector_bytes=128,
                   sectors=2000 if filesystem == 'sdfs' else 720,
                   format=2 if filesystem == 'sdfs' else 1) for i in range(2)]
    if 'mutation' in names:
        for mount in mounts:
            mount.update(access='readwrite', profile=4)
    p = build(t, ROOT/'tests/programs/fsinit_failures.act', out, optimize=mode == 'opt',
              tasks=True, task_capacity=8, dos_mounts=mounts, console_deferred=True)
    source = ROOT/'tests/fixtures'/('sdfs/sdfs-21-128.atr' if filesystem == 'sdfs' else 'mydos/mydos450-128.atr')
    media = out/'volume.atr'
    shutil.copyfile(source, media)
    digest = sha256(media)
    cases = []
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        b.config('diskemu', 'generic56k' if 'mutation' in names else 'fastest')
        for unit in range(2):
            b.mount(unit, str(media))
        for site, name in enumerate(names, 1):
            for skip in ((0, 1) if name in PER_MOUNT else (0,)):
                label = name+('-second' if skip else '-first')
                print('FSINIT fault', mode, filesystem, label, flush=True)
                case_out = out/label
                case_out.mkdir(exist_ok=True)
                if cases:
                    b.state_load(slot='loaded')
                def before(b):
                    if not cases:
                        b.state_save(slot='loaded')
                    values = dict(fault=(site, 1), skipCount=(skip, 1),
                                  dynamic=(int(name in PER_MOUNT), 1),
                                  expected=(4 if name == 'metadata-read' else failures[name][3], 4))
                    for variable, (value, size) in values.items():
                        address = next(d['address'] for d in p['image']['data']
                                       if d['name'].startswith('M_FSINITFAILURES_'+variable.upper()+'_'))
                        b.memload(address, (value & ((1 << (8*size))-1)).to_bytes(size, 'little'))
                try:
                    runtime, _ = execute(b, {**p, 'output':case_out}, before_run=before,
                                         preloaded=bool(cases), timeout=240, frame_limit=12000)
                except Exception:
                    print('FSINIT checks', data(b, p['image'], 'checks', True), flush=True)
                    raise
                ownership(b, p, out)
                cases.append(dict(name=label, status='pass', runtime=runtime,
                                  checks=data(b, p['image'], 'checks', True)))
        require(sha256(media) == digest, 'Read-only media changed')
    return dict(status='pass', mode=mode, filesystem=filesystem, build=p['build'],
                machine=machine, cases=cases, overrides=overrides, media_sha256=digest,
                inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                        (Path(__file__), ROOT/'tests/programs/fsinitprobe.act',
                         ROOT/'tests/programs/fsinit_failures.act')},
                bank_zero_delta=dict(fixed=0, per_task=0))


def config(t, out, mode):
    """Corrupt loaded descriptors, preserving one unmodified production image."""
    from banked_test_memory import write
    out.mkdir(parents=True, exist_ok=True)
    mounts = [dict(alias='D'+str(i+1), unit=49+i, profile=1, sector_bytes=128,
                   sectors=720) for i in range(2)]
    p = build(t, ROOT/'tests/programs/fsinit_config.act', out, optimize=mode == 'opt',
              tasks=True, task_capacity=8, dos_mounts=mounts, system_mount='D2')
    word = lambda n: n.to_bytes(2, 'little')
    # Descriptor offsets are the packaged ABI, not compiler-private record offsets.
    variants = [('valid', 0, 2, [], False), ('count-zero', 218, 0, [], False),
                ('count-nine', 218, 9, [], False), ('selected-outside-count', 218, 1, [], False),
                ('empty-alias', 206, 2, [(0, bytes(32))], False),
                ('reserved-alias', 206, 2, [(0, b'SYS'+bytes(29))], False),
                ('unterminated-alias', 206, 2, [(0, b'A'*32)], False),
                ('illegal-alias', 206, 2, [(0, b'A!'+bytes(30))], False),
                ('system-unit', 115, 2, [(46+32, word(51))], False),
                ('system-alias', 115, 2, [(46, b'D3'+bytes(30))], False),
                ('unknown-format', 225, 2, [(43, b'\xff')], False),
                ('invalid-unit', 115, 2, [(32, word(48))], False),
                ('invalid-profile', 115, 2, [(34, word(3))], False),
                ('zero-sectors', 115, 2, [(36, bytes(4))], False),
                ('invalid-sector-size', 115, 2, [(40, word(512))], False),
                ('invalid-boot', 115, 2, [(42, b'\0')], False),
                ('duplicate-unit', 202, 2, [(32, word(50))], False),
                ('duplicate-alias', 202, 2, [(0, b'd2'+bytes(30))], False),
                ('generation', 103, 2, [], True)]
    media = ROOT/'tests/fixtures/mydos/mydos450-128.atr'
    digest = sha256(media)
    cases = []
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        b.config('diskemu', 'fastest')
        for unit in range(2):
            b.mount(unit, str(media))
        for name, error, count, patches, exhausted in variants:
            print('FSINIT config', mode, name, flush=True)
            case_out = out/name
            case_out.mkdir(exist_ok=True)
            if cases:
                b.state_load(slot='loaded')
            def before(b):
                if not cases:
                    b.state_save(slot='loaded')
                config_at = p['build']['task_storage']['BASE']+0x900
                for offset, raw in patches:
                    write(b, config_at+offset, raw, out)
                for variable, value, size in [('expected', error, 4), ('count', count, 1), ('exhausted', int(exhausted), 1)]:
                    address = next(d['address'] for d in p['image']['data']
                                   if d['name'].startswith('M_FSINITCONFIG_'+variable.upper()+'_'))
                    b.memload(address, value.to_bytes(size, 'little'))
            try:
                runtime, _ = execute(b, {**p, 'output':case_out}, before_run=before,
                                     preloaded=bool(cases), timeout=240, frame_limit=12000)
            except Exception:
                print('Config checks', data(b, p['image'], 'checks', True), flush=True)
                raise
            ownership(b, p, out)
            cases.append(dict(name=name, status='pass', expected_error=error, runtime=runtime,
                              checks=data(b, p['image'], 'checks', True)))
        require(sha256(media) == digest, 'Read-only media changed')
    return dict(status='pass', mode=mode, build=p['build'], machine=machine, cases=cases,
                media_sha256=digest, inputs={str(Path(__file__).relative_to(ROOT)):sha256(Path(__file__))},
                bank_zero_delta=dict(fixed=0, per_task=0))
