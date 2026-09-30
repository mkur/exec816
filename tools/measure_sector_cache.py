#!/usr/bin/env python3
"""Compare disabled/cold/warm 8 KiB reads on one image and identical SIO media."""
import argparse
import json
from pathlib import Path

from banked_test_memory import read
from dos_concurrent_trace import call_marker
from filesystem_formats import MYDOS, SDFS
from measure_loading_breakdown import packets, partition_packet
from measure_read_8k import BRIDGE, ROM, PIN, CONFIGURATION, PAYLOAD, configure, observe, prepare
from native_program import ROOT, build, compiler, read_build, require, sha256
from os_boundary import emulator
from sio_transaction_trace import BASE_HZ, read_events
from test_cooperative import data
from test_dos_stack import execute, ownership


def run(output, emit=False, filesystem='sdfs', capacities=(0,512)):
    output.mkdir(parents=True, exist_ok=True)
    if filesystem == 'mydos':
        from make_data_disk import make
        from mydos_fixtures import Image
        files = output/'files'
        files.mkdir(exist_ok=True)
        (files/'READ8K.BIN').write_bytes(PAYLOAD)
        media = output/'read8k.atr'
        make(media, files, binary_names={'READ8K.BIN'}, filesystem='mydos')
        disk = Image(media.read_bytes())
        entry = next(e for e in disk.entries() if e['name']=='READ8K.BIN')
        payload, sectors = disk.file(entry)
        require(payload == PAYLOAD, 'Wrong MyDOS benchmark payload')
    else:
        media = prepare(output, background=True)
        sectors = list(range(7,73))
    source = ROOT/'tests/programs/read_8k_cache.act'
    target = output/'exec-build'
    if emit:
        build(compiler(ROOT/'build/actionc'), source, target, tasks=True, task_capacity=8,
              optimize=True, dos_mounts=[dict(alias='D1', unit=49, sectors=720,
                    sector_bytes=128, profile=4, format=MYDOS if filesystem=='mydos' else SDFS)],
              image_data=[(0xd1000,b'D1:READ8K.BIN\0'),(0xd1020,b'\1')])
    p = read_build(target)
    require(p['build']['source_sha256']==sha256(source), 'Stale cache reader')
    p['labels']['dos_read'] = next(r['address'] for r in p['image']['routines']
                                   if r['name'].startswith('M_DOS_READ_'))
    begin = call_marker(p, 'M_READ8K_READONE_', 'dos_read')
    marks = dict(read_begin=begin, read_end=begin+4)
    marks['fetch'] = next(r['address'] for r in p['image']['routines']
                          if r['name'].startswith('M_BLOCKIO_BEGINFETCH_'))
    results = []
    media_hash = sha256(media)
    for blocks in capacities:
        out = output/f'blocks-{blocks}'
        out.mkdir(exist_ok=True)
        observe(marks)
        def before(b):
            boot = p['build']['memory']['boot_config']
            address = boot['address']+boot['abi']['fields']['cache_blocks']
            b.memload(address,blocks.to_bytes(2,'little'))
            b.profile_start()
        print('Reading twice with cache blocks:',blocks,flush=True)
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            machine = configure(b)
            b.mount(0,str(media))
            runtime,_ = execute(b,p,before_run=before,timeout=300,frame_limit=15000)
            b.profile_stop()
            def number(name):
                return int.from_bytes(bytes(data(b,p['image'],name)),'little')
            def pair(name):
                raw = bytes(data(b,p['image'],name))
                return [int.from_bytes(raw[i:i+4],'little') for i in (0,4)]
            observed = {name:number(name) for name in ('received','ioError','verified','cacheBlocks','checks')}
            require(observed['received']==observed['verified']==8192 and observed['ioError']==0
                    and observed['cacheBlocks']==blocks, 'Wrong read result or cache capacity')
            observed.update({name:pair(name) for name in ('progress','hits','misses')})
            ownership(b,p,target)
            hardware = read(b,p['build']['task_storage']['BASE']+0x800,128,out)
            require(hardware[0]==hardware[1]==hardware[45]==0 and
                    hardware[12:15]==hardware[16:19]==bytes(3),'Retained bus ownership')
        events = read_events(out/'emulator.log')
        stamps = [[t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[name]]
                  for name in ('read_begin','read_end')]
        require(all(len(s)==2 for s in stamps),'Expected two completed Read calls')
        wire = packets(events)
        samples = []
        for index,(start,end) in enumerate(zip(*stamps)):
            rows = [partition_packet(packet) for packet in wire if start<=packet['begin']<end]
            require(start<end and (not rows or rows[-1]['end']<=end),'Bad read interval')
            expected = [] if blocks and index else sectors
            require([r['sector'] for r in rows]==expected,
                    'Unexpected cache wire reads: '+str([r['sector'] for r in rows]))
            require(observed['progress'][index]>0,'CPU worker did not progress during Read')
            samples.append(dict(seconds=(end-start)/BASE_HZ,wire_reads=len(rows),
                                sectors=[r['sector'] for r in rows],
                                logical_reads=sum(start<=t<end and e[0]=='cpu'
                                    and int(e[4],16)==marks['fetch'] for t,e in events),
                                background_rounds=observed['progress'][index]))
        require(sha256(media)==media_hash,'Read-only benchmark media changed')
        result = dict(status='pass',blocks=blocks,samples=samples,observed=observed,
                      machine=machine,runtime=runtime,log_sha256=sha256(out/'emulator.log'))
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        results.append(result)
        print(json.dumps(dict(blocks=blocks,samples=samples)),flush=True)
    record = dict(status='pass',filesystem=filesystem,pin=PIN,configuration=CONFIGURATION,build=p['build'],
                  media_sha256=media_hash,verified_bytes_per_read=len(PAYLOAD),cases=results,
                  source_sha256=sha256(source),harness_sha256=sha256(Path(__file__)),
                  boundary='DOS.Read call through return; Open/Close, allocation and byte verification excluded. '
                           'Same image and disk; fresh boot per capacity, Close/Open between reads; one busy CPU Task.',
                  bank_zero_delta=dict(fixed=0,per_task=0))
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sector-cache/read-8k')
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--format',choices=('mydos','sdfs'),default='sdfs')
    parser.add_argument('--cache-blocks',type=int,choices=(0,512),help='Run only this capacity')
    args = parser.parse_args()
    run(args.output.resolve(),args.prepare,args.format,
        (args.cache_blocks,) if args.cache_blocks is not None else (0,512))
