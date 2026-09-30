"""Qualify heap registration, rollback and terminal cleanup in native Tasks."""
import json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,platform_files,require,sha256,verify_machine
from test_banked import PIN
from test_cooperative import data
from banked_test_memory import read as far_read
from os_boundary import emulator


def case(bridge,toolchain,output,optimize,capacity,kernel,kind):
    output.mkdir(parents=True,exist_ok=True)
    profile=json.loads((ROOT/'platform/altirraos/memory-1m.json').read_text())
    if kind=='empty': profile['usable_banks']=[kernel,kernel+1,kernel+2,15]
    if kind=='holes': profile['usable_banks']=[b for b in profile['usable_banks'] if b not in (6,10)]
    (output/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    source=output/'heap_registration.act'
    source.write_text((ROOT/'tests/programs/heap_registration.act').read_text())
    program=build(toolchain,source,output,optimize=optimize,
                  tasks=True,task_capacity=capacity,kernel_bank=kernel,memory_profile=output/'profile.json',
                  image_data=[(0x80000,b'IMAGE')] if kind=='holes' else [(((kernel+3)<<16)-1,b'X')] if kind=='empty' else [])
    result,_=execute(bridge,program,frame_limit=2400,timeout=180,load_timeout=180)
    memory=program['build']['memory'];c=memory['constants']
    seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    available=[i for i in range(c['MAX_BANKS']) if seed[i*4]==1]
    active=bytearray(seed)
    for bank in available: active[bank*4:bank*4+4]=bytes([3,0,5,0])
    regions=[]
    for bank in available:
        if regions and regions[-1][1]==bank<<16: regions[-1][1]=(bank+1)<<16
        else: regions.append([bank<<16,(bank+1)<<16])
    checks=data(bridge,program['image'],'checks',True)
    require(checks==[len(regions),1,0xff62 if available else 0,0xff62 if available else 0,
                     0,0xff62,len(regions),1,1,0,0,0],f'Registration checks: {checks}')
    snapshots=bytes(data(bridge,program['image'],'snapshots'))
    expected=[active,seed,seed,seed,active,active]
    require(snapshots==b''.join(expected),'Ownership differed during rollback/restart')
    raw=bytes(data(bridge,program['image'],'regions'))
    observed=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(regions)*8,4)]
    require(observed==[x for pair in regions for x in pair],'Published regions differ from bank map')
    final=far_read(bridge,c['TABLE'],c['TABLE_BYTES'],output) if c['TABLE']>=65536 else bridge.memdump(c['TABLE'],c['TABLE_BYTES'])
    require(final==seed,'Terminal shutdown leaked or released another owner')
    registry=memory['ports_storage']
    require(far_read(bridge,registry['BASE'],3,output)==b'\xff'*3,'Cleanup traversed/rewrote corrupt registry')
    storage=memory['heap_storage'];meta=far_read(bridge,storage['BASE'],storage['BYTES'],output)
    require(meta[11:14]==bytes(3) and meta[16:16+c['MAX_BANKS']]==bytes(c['MAX_BANKS']), 'Shutdown left published state/claims')
    return dict(build=program['build'],runtime=result,checks=checks,regions=regions,
                initial_bank_table=list(seed),active_bank_table=list(active),final_bank_table=list(final),
                reservation_delta=dict(bank_zero_fixed=0,bank_zero_per_task=0,loading=0,runtime=0,
                                       upper_metadata_bytes=storage['BYTES']))


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    cases=[(f'{kind}-{capacity}-k{kernel}-{mode}',mode=='opt',capacity,kernel,kind)
           for mode in ('raw','opt') for capacity,kernel,kind in
           [(4,1,'single'),(4,3,'holes'),(8,1,'holes'),(8,3,'single'),(4,1,'empty')]]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown registration case')
    report=dict(schema_version=1,status='running',platform=PIN,cases=[],inputs={p:sha256(ROOT/p) for p in
        ('abi/memory-v1.json','lib/exec/execmemory.act','lib/exec/heappolicy.act','lib/exec/taskpolicy.act',
         'tools/generate_heap.py','tools/generate_memory.py','tools/native_program.py',
         'platform/altirraos/hosted.s','tests/programs/heap_registration.act','tools/test_heap_registration.py')})
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config']=verify_machine(bridge,args.rom,PIN)
            for name,optimize,capacity,kernel,kind in cases:
                print('Running '+name+'...',flush=True)
                observed=case(bridge,toolchain,output/name,optimize,capacity,kernel,kind)
                report['cases'].append(dict(name=name,status='pass',**observed))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally: (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} registration cases',flush=True)
