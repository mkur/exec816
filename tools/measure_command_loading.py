#!/usr/bin/env python3
"""Bounded phase measurements on a demo with a small loader observer.

Small target counters record VBI ticks at loader boundaries and count actual
BLOCKWIRE transfers. The observer never waits, allocates or yields. Build it
once; replay its identical instructions with explicit mount/table overrides.
Host pauses are outside the measured command.
"""
import adapter_state as adapter
import argparse
import hashlib
import json
from pathlib import Path
from generate_console import constants as console_constants
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from library_paths import read_source
import shutil
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_shell_core import KEYS


def sector_classes(path, filesystem):
    """Diagnostic labels only; independent producer read-back remains the oracle."""
    from mydos_fixtures import Image
    disk=Image(path.read_bytes());classes=bytearray(disk.count+1)
    if filesystem=='mydos':
        def directory(start):
            for sector in range(start,start+8):classes[sector]=1
            for entry in disk.entries(start):
                if entry['flags']&16:directory(entry['start'])
                else:
                    for sector in disk.file(entry)[1]:classes[sector]=3
        directory(361)
    else:
        from make_sdfs_fixtures import Media
        media=Media(path.read_bytes());seen=set()
        def directory(start):
            require(start not in seen,'Cyclic diagnostic directory');seen.add(start)
            pages,sectors=media.chain(start)
            for sector in pages:classes[sector]=2
            for sector in sectors:
                if sector:classes[sector]=1
            contents=b''.join(media.raw[media.at(n):media.at(n)+media.size] for n in sectors if n)
            length=int.from_bytes(contents[3:6],'little')
            for pos in range(23,length,23):
                entry=contents[pos:pos+23]
                if not entry[0]:break
                if entry[0]&16 or not entry[0]&8:continue
                first=int.from_bytes(entry[1:3],'little')
                if entry[0]&32:directory(first)
                else:
                    maps,data=media.chain(first)
                    for sector in maps:classes[sector]=2
                    for sector in data:
                        if sector:classes[sector]=3
        directory(media.word(25))
    return classes


def prepare(bundle, output, filesystem=None):
    output.mkdir(parents=True, exist_ok=True)
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    filesystem=filesystem or manifest.get('filesystem','mydos')
    disk_name=filesystem+'.atr'
    from make_data_disk import make
    for kind in ('sdfs','mydos'):
        files=make(output/(kind+'.atr'),bundle/'media',binary_names={f'C/{name}' for name in manifest['commands']},
                   filesystem=kind,sector_bytes=manifest['mounts'][0]['sector_bytes'],
                   sectors=manifest['system_sectors'])
        require({name:hashlib.sha256(data).hexdigest() for name,data in files.items()}==
                {name:item['sha256'] for name,item in manifest['files'].items()},'Comparison payloads differ')
    classes=sector_classes(output/disk_name,filesystem)
    table_address=manifest['kernel']['task_storage']['BASE']+0xe000
    require(len(classes)<=0x2000,'Diagnostic table exceeds reserved kernel bank tail')
    (output/'loadprobe.act').write_text(f"""MODULE LOADPROBE
VOLATILE CARD clock=${adapter.VBI_COUNT:04x}
PUBLIC CARD ARRAY ticks(9),reads(9),kinds(4),snapshots(36)
PUBLIC CARD transfers
PUBLIC PROC Mark(BYTE phase)
  BYTE index
  ticks(phase)=clock reads(phase)=transfers
  FOR index=0 TO 3 DO snapshots(CARD(phase)*4+CARD(index))=kinds(index) OD
RETURN
PUBLIC PROC Transfer(CARD sector)
  BYTE kind
  BYTE POINTER table
  table=BYTE POINTER($"""+format(table_address,'x')+""") kind=0
  IF sector<"""+str(len(classes))+""" THEN kind=table(sector) FI
  kinds(kind)==+1 transfers==+1
RETURN
ENDMODULE
""")
    text=read_source(ROOT/'lib/dos/programfile.act').replace('USE EXEC', 'USE EXEC\nUSE LOADPROBE', 1)
    markers=[('  file=DOS.Open', 1), ('  position=DOS.Seek', 2), ('    length=DOS.Seek', 3),
             ('        position=0', 4), ('  closed=DOS.Close', 5)]
    for line, phase in markers:
        require(text.count(line)==1, 'Stale loading observer: '+line)
        indent=line[:len(line)-len(line.lstrip())]
        text=text.replace(line, indent+f'LOADPROBE.Mark({phase})\n'+line, 1)
    text=text.replace('image=PROGRAM.Load(bytes,LONGCARD(length))\n    error=DOS.IoErr()',
                      'LOADPROBE.Mark(6) image=PROGRAM.Load(bytes,LONGCARD(length)) LOADPROBE.Mark(7) error=DOS.IoErr()')
    text=text.replace('  DOSCLIENT.SetError(error)', '  LOADPROBE.Mark(8)\n  DOSCLIENT.SetError(error)')
    (output/'programfile.act').write_text(text)
    text=read_source(ROOT/'lib/io/blockwire.act').replace('USE EXEC', 'USE EXEC\nUSE LOADPROBE', 1)
    marker='  control=0'
    require(text.count(marker)==1, 'Stale sector-transfer observer')
    text=text.replace(marker, '  LOADPROBE.Transfer(CARD(request.sio_Aux1)+(CARD(request.sio_Aux2) LSH 8))\n'+marker)
    (output/'blockwire.act').write_text(text)
    source=output/'demo.act'; source.write_text(read_source(ROOT/'examples/demo.act'))
    manifest['mounts'][0]['format']=2 if filesystem=='sdfs' else 1
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    (output/'memory.json').write_text(json.dumps(profile))
    program=build(compiler(ROOT/'build/actionc'),source,output,memory_profile=output/'memory.json',optimize=True,tasks=True,task_capacity=8,
                  console=True,stack_checks=True,dos_mounts=manifest['mounts'],image_data=[(table_address,bytes(classes))])
    shutil.copyfile(bundle/'README.md',output/'README.md')
    shutil.copyfile(bundle/'PRIMES.profile.json',output/'PRIMES.profile.json')
    manifest['kernel']=program['build'];manifest['filesystem']=filesystem;manifest['media']=disk_name
    artifacts=['program.xex','sdfs.atr','mydos.atr','sdfs.verification.json','README.md']
    manifest['artifacts']={name:sha256(output/name) for name in artifacts}
    manifest['observer_table']=dict(address=table_address,bytes=len(classes),sha256=hashlib.sha256(classes).hexdigest())
    manifest['observer']={name:sha256(output/name) for name in ('loadprobe.act','programfile.act','blockwire.act')}
    (output/'demo-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return output


def run(bundle, output, filesystem=None, prime_worker='active', cpu_trace=False):
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    p = read_build(bundle); pin = manifest['pin']
    console = console_constants()
    filesystem=filesystem or manifest['filesystem']
    media=filesystem+'.atr'
    override=filesystem!=manifest['filesystem']
    require(all(sha256(bundle/name) == value for name, value in manifest['artifacts'].items()), 'Changed bundle')
    def probe(name): return next(d['address'] for d in p['image']['data'] if '_LOADPROBE_'+name.upper()+'_' in d['name'])
    def at(name): return next(d['address'] for d in p['image']['data'] if '_DEMO_'+name.upper()+'_' in d['name'])
    require(prime_worker in ('active', 'stopped'), 'Unknown prime-worker mode')
    samples = []; directory = {}; prime = dict(mode=prime_worker)
    names=('other','directory','map','data')
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', output, pin=pin) as b:
        for key, value in manifest['configuration'].items(): b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.mount(0, str(bundle/media)); machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', pin)
        def far(address, size):
            raw = b''.join((b.eval_expr(f'dw(${address+i:x})')&65535).to_bytes(2, 'little') for i in range(0, size, 2))
            return raw[:size]
        def num(address, size=4):
            return int.from_bytes(far(address,size),'little')
        def counts(address):return {name:num(address+2*i,2) for i,name in enumerate(names)}
        last_prime={}
        def prime_state():
            from prime_observer import state
            identity=num(at('job'))
            if num(at('job')+12,1)!=3:
                last_prime.update(state(far,p,bundle,identity))
            return dict(**last_prime,live_tasks=num(p['build']['task_storage']['LIVE'],1))
        def rendezvous(condition):
            marker = p['labels']['native_nmi']; b.bp_clear_all(); b.bp_set(marker, condition=condition)
            run_to(b, marker, 12000, 240, condition)
        def frames(count=3): rendezvous(f'@frame>={b.eval_expr("@frame")+count}')
        capture = p['build']['memory']['console_storage']['CAPTURE']
        def press(char):
            name, shift = KEYS[char]
            if shift: b._cmd_ok('KEY SHIFT down')
            previous = num(capture+10, 2); b._cmd_ok(f'KEY {name} down')
            rendezvous(f'dw(${capture+10:x})>{previous}')
            b._cmd_ok(f'KEY {name} up')
            if shift: b._cmd_ok('KEY SHIFT up')
            frames()
        def before(_):
            if override:
                from banked_test_memory import write
                write(b,p['build']['task_storage']['BASE']+0x900+43,
                      bytes([2 if filesystem=='sdfs' else 1]),output)
                write(b,manifest['observer_table']['address'],sector_classes(bundle/media,filesystem),output)
            b._cmd_ok('KEY ALL up')
            rendezvous(f'db(${at("started"):x})=1')
            windows = p['build']['memory']['console_storage']['WINDOWS']
            row = windows+console['WINDOWS_ITEMS']+console['WINDOW_SIZE']*0
            top = num(row+console['WINDOW_INSTANCE'], 3)
            dos = p['build']['memory']['dos_storage']['BASE']; scope = num(num(dos, 3)+83, 3)
            ready = f'(db(${top+51:x})=2)&(db(${scope+54:x})=0)'
            rendezvous(ready)
            prime['before'] = prime_state()
            require(prime['before']['live_tasks'] == 5, 'Unexpected initial demo Task count')
            if prime_worker == 'stopped':
                identity=num(at('job'))
                for char in 'BREAK '+str(identity)+'\n':press(char)
                rendezvous(ready+f'&(db(${p["build"]["task_storage"]["LIVE"]:x})=4)')
                prime['stopped'] = prime_state()
                prime['stopped_identity'] = identity
            for char in 'HELLO': press(char)
            previous = num(scope+14)
            start_frame=b.eval_expr('@frame'); start_tick=num(adapter.VBI_COUNT,2)
            if cpu_trace: b.profile_start()
            press('\n')
            rendezvous(ready+f'&(dw(${scope+14:x})>{previous&65535})')
            if cpu_trace: b.profile_stop()
            phases=('unused','open','seek_end','rewind','payload','close','relocate','loaded','returned')
            for index in range(1,9):
                ticks=(num(probe('ticks')+2*index,2)-start_tick)&65535
                samples.append(dict(phase=phases[index],frame=start_frame+ticks,transfers=num(probe('reads')+2*index,2),reads_by_kind=counts(probe('snapshots')+8*index)))
            samples.append(dict(phase='prompt',frame=b.eval_expr('@frame'),transfers=num(probe('transfers'),2),reads_by_kind=counts(probe('kinds'))))
            shell = num(at('shell'), 3)
            require(num(shell+32) == num(shell+36) == 0, 'HELLO failed')
            for char in 'DIR': press(char)
            previous = num(scope+14)
            directory['start_frame'] = b.eval_expr('@frame')
            directory['start_transfers'] = num(probe('transfers'), 2)
            directory['start_reads_by_kind']=counts(probe('kinds'))
            press('\n')
            rendezvous(ready+f'&(dw(${scope+14:x})>{previous&65535})')
            require(num(shell+32) == num(shell+36) == 0, 'DIR failed')
            directory['frames'] = b.eval_expr('@frame')-directory['start_frame']
            directory['transfers'] = num(probe('transfers'), 2)-directory['start_transfers']
            directory['reads_by_kind']={name:value-directory['start_reads_by_kind'][name] for name,value in counts(probe('kinds')).items()}
            if filesystem=='sdfs':
                require(samples[2]['transfers']==samples[1]['transfers'],'SDFS size discovery performed I/O')
                require(samples[3]['reads_by_kind']['data']==samples[0]['reads_by_kind']['data'],'SDFS loading performed a preliminary payload traversal')
                require(directory['reads_by_kind']['data']==0,'SDFS DIR read ordinary-file payload')
            prime['after_commands'] = prime_state()
            if prime_worker == 'stopped':
                require(prime['after_commands'] == prime['stopped'], 'Prime worker progressed after stopping')
            for char in 'EXIT': press(char)
            b._cmd_ok('KEY RETURN down'); b.bp_clear_all()
        runtime, _ = execute(b, p, before_run=before, timeout=240, frame_limit=12000)
        b._cmd_ok('KEY ALL up'); ownership(b, p, bundle)
    result = dict(status='pass', media_sha256=sha256(bundle/media), xex_sha256=sha256(bundle/'program.xex'),
                  filesystem=filesystem,mount_table_override=override,observer=manifest['observer'],observer_table=manifest['observer_table'],runtime_table_sha256=hashlib.sha256(sector_classes(bundle/media,filesystem)).hexdigest(),bundle_manifest_sha256=sha256(bundle/'demo-manifest.json'),
                  payload_sha256=manifest['files']['C/HELLO']['sha256'], compiler=p['build']['revision'],
                  machine=machine, configuration=manifest['configuration'], samples=samples, directory=directory, runtime=runtime,
                  prime_worker=prime,cpu_trace=cpu_trace,harness_sha256=sha256(Path(__file__)),
                  conditions=f'Cold startup; first disk command HELLO; demo prime worker {prime_worker}; guest timing excludes debugger pauses.')
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(samples), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--bundle', type=Path, default=ROOT/'build/demo')
    parser.add_argument('--format',choices=('mydos','sdfs')); parser.add_argument('--output', type=Path, required=True); parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--prime-worker',choices=('active','stopped'),default='active')
    parser.add_argument('--cpu-trace',action='store_true',help='Enable passive CPU markers for HELLO; select PCs with EXEC816_LATENCY_PCS'); args = parser.parse_args()
    bundle=prepare(args.bundle.resolve(),args.output.resolve()/'bundle',args.format) if args.prepare else args.bundle.resolve()
    run(bundle, args.output.resolve(),args.format,args.prime_worker,args.cpu_trace)
