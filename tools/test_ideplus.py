"""Focused emitted IDE Plus checks with a disposable media/profile fixture."""
import argparse,json,sys
from contextlib import contextmanager
from pathlib import Path
import os_boundary
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256,read_build
from test_cooperative import data
from test_heap_api import clean_ownership
PIN=json.loads((ROOT/'toolchain/altirra-ideplus.json').read_text())

@contextmanager
def ide_emulator(output,media,absent=False,writable=False,history=False):
    firmware=ROOT/'build/firmware/ideplus-bios-2.1.rom'
    require(firmware.exists(),'Place the pinned BIOS ROM at '+str(firmware))
    require(sha256(firmware)==PIN['ideplus']['firmware_sha256'],'Unpinned IDE firmware')
    require(sha256(ROOT/'build/mouse-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned IDE emulator')
    original=os_boundary.settings
    run_pin={**PIN,'devices':[] if absent else PIN['devices']}
    def settings(rom,pin):
        value=14695981039346656037
        for char in str(firmware).lower(): value=((value^ord(char))*1099511628211)&((1<<64)-1)
        value|=1<<63
        devices=[] if absent else [dict(tag='kmkjzide2',params=dict(revision='e',enablesdx=False,id=0),buses={'0':dict(children=[dict(tag='hdrawimage',params=dict(path=str(media),write_enabled=writable,solid_state=True))])})]
        return original(rom,pin)+'\n[User\\AltirraSDL\\Profiles\\00000000]\n"Devices" = '+json.dumps(json.dumps(devices))+'\n\"CPU: History enabled\" = '+str(int(history))+'\n'+rf'''
[User\AltirraSDL\Firmware\Available\{value:016X}]
"Name" = "IDE Plus pinned BIOS 2.1"
"Path" = "{firmware}"
"Type" = "kmkjzide2"
"Flags" = 0
[User\AltirraSDL\Firmware\Default]
"kmkjzide2" = "{firmware}"
'''
    os_boundary.settings=settings
    # The pinned SDK package is shared; the emulator binary is separately pinned.
    sys.path.insert(0,str(ROOT/'build/altirra-sio-multi/sdk/python'))
    try:
        with os_boundary.emulator(ROOT/'build/mouse-bridge',ROOT/'build/firmware/altirraos-816.rom',output,run_pin) as bridge:
            for k,v in PIN['configuration'].items(): bridge.config(k,str(v).lower() if isinstance(v,bool) else v)
            yield bridge
    finally: os_boundary.settings=original


def run(output,reuse=False,absent=False):
    output.mkdir(parents=True,exist_ok=True)
    p=read_build(output) if reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ideplus_raw.act',output,optimize=True,tasks=True,task_capacity=8,image_data=[(0x2dfff0,bytes([0xa5])*512)])
    disk=output/'ide.img';media=bytearray(8192*512)
    for sector,seed in [(7,0xa7),(8191,0x6c)]: media[sector*512:(sector+1)*512]=bytes((i&255)^seed for i in range(512))
    disk.write_bytes(media)
    with ide_emulator(output,disk,absent=absent) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',{**PIN,'devices':[] if absent else PIN['devices']})
        selection=[]
        def before(b):
            selection.append(b.peek(0x247))
            b.memload(next(d['address'] for d in p['image']['data'] if '_EXPECTEDFAILURE_' in d['name']),bytes([absent]))
        try: runtime,_=execute(b,p,before_run=before,timeout=60,frame_limit=3000)
        except Exception:
            print('checks',data(b,p['image'],'checks',True),'regs',b.regs(),flush=True)
            print('IDE metadata',b.memdump(p['build']['memory']['ideplus_storage']['BASE'],96).hex(),flush=True)
            print('CONTROL',b.memdump(p['build']['memory']['ideplus_storage']['BASE']+640,48).hex(),flush=True)
            print('DEVICE',b.device_get('kmkjzide2'),flush=True)
            b.poke(0xd1ff,1);print('BOARD',b.memdump(0xd110,16).hex(),b.peek(0xd1fa),flush=True);b.poke(0xd1ff,0)
            raise
        clean_ownership(b,p,output)
        checks=data(b,p['image'],'checks',True);progress=data(b,p['image'],'progress',True)
        require(b.peek(0x247)==selection[0],f'PBI selection shadow not restored: {selection[0].hex()} -> {b.peek(0x247).hex()}')
    require(disk.read_bytes()==media,'Read-only driver modified media')
    result=dict(status='pass',tier='development',build=p['build'],runtime=runtime,machine=machine,checks=checks,progress=progress,absent=absent)
    (output/('absent-results.json' if absent else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('IDE Plus raw read/absence passed',flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=ROOT/'build/development/ideplus-ip1/raw');a.add_argument('--reuse',action='store_true');a.add_argument('--absent',action='store_true');v=a.parse_args();run(v.output,v.reuse,v.absent)
