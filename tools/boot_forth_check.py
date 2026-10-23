"""Exercise a real ROM SIO call from a temporary Forth CODE-word fixture."""
import json
import subprocess
from native_program import ROOT,require,sha256
from test_of816 import enter_forth,press,screen_text
from test_bootable_atr import wait_at


def exercise(b,monitor,program,output):
    labels=monitor['labels'];output.mkdir(parents=True,exist_ok=True)
    cancel=enter_forth(b,labels)
    def line(text):
        for c in text+'\n':press(b,labels,c)
        return screen_text(b.memdump(b.peek16(88),960))
    source=ROOT/'probes/boot-sio/forth-status.s'
    stage=program['build']['memory']['constants']['STAGE'];buffer=stage+256
    (output/'probe.cfg').write_text(f'MEMORY {{ RAM: start=${stage:x},size=$100,file=%O; }}\nSEGMENTS {{ CODE: load=RAM,type=ro; }}\n')
    subprocess.run(['ca65','-D',f'OF_OS_STACK={labels["of_os_stack"]}','-D',f'TEST_BUFFER={buffer}',
                    '-o',str(output/'probe.o'),str(source)],check=True)
    subprocess.run(['ld65','-C',str(output/'probe.cfg'),'-o',str(output/'probe.bin'),str(output/'probe.o')],check=True)
    raw=(output/'probe.bin').read_bytes();require(len(raw)<256,'Oversized Forth SIO probe')
    # Bank-zero test stimulus only. STAGE is idle during OF816, and the next
    # native record replaces it after this CODE word has retired. No debugger
    # far-write trampoline or production monitor modification is involved.
    b.memload(stage,raw)
    line('hex code sio-check '+' '.join(f'{v:x} c,' for v in bytes([0x22,stage&255,stage>>8,0]))+' c;')
    require(b.memdump(stage,len(raw))==raw,'Forth compile changed STAGE probe')
    for c in 'sio-check':press(b,labels,c)
    press(b,labels,'\n',stage)
    (output/'entry.json').write_text(json.dumps(dict(regs=b.regs()),indent=2)+'\n')
    wait_at(b,labels['of_wait_key'],(),30)
    require(b.peek(0x303)==b'\1' and b.peek(buffer)[0]&0x20,'Forth ROM STATUS failed')
    text=line('decimal 6 7 * .')
    require('42 ' in text,'Forth context lost after ROM disk operation')
    line('128 CACHE-BLOCKS! 0 BOOT-VERBOSE!')
    before=int.from_bytes(b.memdump(0x12,3),'big');b.bp_clear_all();b.frame(100);b.pause()
    ticks=(int.from_bytes(b.memdump(0x12,3),'big')-before)&0xffffff
    require(99<=ticks<=101,'ROM VBI stopped during interactive pause')
    settings=b.memdump(monitor['boot_config']['address'],8)
    for c in 'EXEC816':press(b,labels,c)
    press(b,labels,'\n',labels['of_handoff'])
    return dict(cancel=cancel,rom_status=1,arithmetic=42,pause_frames=100,pause_vbi_ticks=ticks,
                source_sha256=sha256(source),fixture_sha256=sha256(output/'probe.bin'),
                fixture_scope='Test-only CODE word calls an emitted bank-zero STAGE probe; production monitor unchanged'),settings
