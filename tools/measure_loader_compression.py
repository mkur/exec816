#!/usr/bin/env python3
"""Measure actual decoder callbacks and verify complete OF816-loaded images."""
import argparse
import copy
import json
import os
from pathlib import Path

from banked_image import extents
from native_program import ROOT, read_build, require, sha256
from os_boundary import emulator, run_to
from sio_transaction_trace import BASE_HZ
from test_of816 import boot_environment, check_loading_paused, check_boot_guards
from test_of816_loading import snapshot_image


def timings(path, labels, multiplier):
    begin = labels['lz4_decode_begin']
    end = labels['lz4_decode_end']
    first = labels['loader_payload_begin']
    last = labels['loader_return']
    pending = None
    elapsed = 0
    calls = 0
    first_tick = last_tick = None
    previous = None
    wraps = 0
    for line in path.read_text().splitlines():
        if '[SIOPOC] cpu ' not in line:
            continue
        row = line.split('[SIOPOC] ',1)[1].split()
        require(int(row[3]) == multiplier and row[12] == '1', 'Decoder CPU mode/clock changed')
        base = int(row[1])
        if previous is not None and previous-base > 0x80000000:
            wraps += 0x100000000
        previous = base
        tick = wraps + base + int(row[2])/multiplier
        pc = int(row[4],16)
        if pc == first and first_tick is None:
            first_tick = tick
        if pc == last and first_tick is not None:
            last_tick = tick
        if pc == begin:
            require(pending is None, 'Nested decompression callback')
            pending = tick
        elif pc == end:
            require(pending is not None and tick >= pending, 'Unbalanced decompression callback')
            elapsed += tick-pending
            pending = None
            calls += 1
    require(pending is None and calls and first_tick is not None and last_tick is not None,
            'Missing decoder observations')
    return dict(decoder_calls=calls, decoder_ms=elapsed/BASE_HZ*1000,
                native_loading_phase_ms=(last_tick-first_tick)/BASE_HZ*1000,
                scope='Summed lz4_decode call elapsed time including OS interrupts and bus stalls; excludes record admission, progress output and XEX transport.')


def run(bundle, output, multiplier, verify=True):
    output.mkdir(parents=True,exist_ok=True)
    program=read_build(bundle)
    boot=json.loads((bundle/'of816/of816.json').read_text())
    require(sha256(bundle/'of816/Exec-of816.xex')==boot['xex_sha256'],'Changed OF816 XEX')
    pin,binary,rom=boot_environment(boot)
    pin=copy.deepcopy(pin)
    pin['machine']['clock_multiplier']=multiplier
    names=('lz4_decode_begin','lz4_decode_end','loader_payload_begin','loader_return')
    labels=program['labels']
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE')
    old={key:os.environ.get(key) for key in keys}
    os.environ['EXEC816_LATENCY_TRACE']='1'
    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{labels[name]:x}' for name in names)
    os.environ.pop('EXEC816_MASK_TRACE',None)
    report=dict(status='running',tier='development',clock_multiplier=multiplier,
        nominal_cpu_hz=BASE_HZ*multiplier,rom_sha256=sha256(rom),emulator_sha256=sha256(binary/'AltirraBridgeServer'),
        machine=pin['machine'], image_sha256=program['build']['image_sha256'],
        xex_sha256=boot['xex_sha256'], xex_bytes=(bundle/'of816/Exec-of816.xex').stat().st_size,
        loader_sha256=sha256(bundle/'loader.bin'), compression=program['build']['boot_compression'])
    try:
        with emulator(binary,rom,output,pin=pin) as b:
            for key,value in boot.get('media',{}).get('configuration',{}).items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            b.profile_start()
            b.boot(str(bundle/'of816/Exec-of816.xex'))
            b.bp_set(boot['labels']['of_start'])
            run_to(b,boot['labels']['of_start'],3000,90)
            check_loading_paused(b,boot,program)
            b.bp_clear_all(); b.bp_set(boot['labels']['of_handoff'])
            run_to(b,boot['labels']['of_handoff'],1000,30)
            check_boot_guards(b,boot['layout'])
            b.bp_clear_all(); b.bp_set(labels['loader_start'])
            run_to(b,labels['loader_start'],6000,120)
            require(b.peek(labels['loader_error'])==b'\0' and b.peek(labels['lz4_active'])==b'\0',
                    'Decoder failed or still active at handoff')
            require(b.peek16(program['build']['memory']['constants']['NEXT'])==
                    len(extents(program['image'],program['build']['memory'])),
                    'Incomplete native image')
            b.profile_stop()
            # Snapshot only after timing has finished; its NMI-masked diagnostic
            # copies are not part of decoder execution or interrupt evidence.
            report['verification']=snapshot_image(b,program,output) if verify else dict(scope='No repeated snapshot')
        report['timing']=timings(output/'emulator.log',labels,multiplier)
        payload=report['compression']['compressed_output_bytes']
        report['timing']['payload_kib_per_second']=payload/1024/(report['timing']['decoder_ms']/1000)
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        for key,value in old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{bundle.name} {multiplier}x: decoder {report["timing"]["decoder_ms"]:.1f} ms, '
          f'{report["timing"]["payload_kib_per_second"]:.1f} KiB/s',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--multiplier',type=int,choices=(1,8),nargs='+',default=[8,1])
    args=parser.parse_args()
    for index,multiplier in enumerate(args.multiplier):
        run(args.bundle.resolve(),args.output.resolve()/f'{multiplier}x',multiplier,verify=index==0)
