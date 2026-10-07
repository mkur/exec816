#!/usr/bin/env python3
"""Observe actual resident command output, including TYPE's writes to NIL."""
import argparse,json,shutil,hashlib,struct,time
from pathlib import Path
from native_program import ROOT,compiler,build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read as far_read
from test_shell_core import instrument,draw,collect_capture,diagnostic_text
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
from test_console_display import terminal
from mydos_fixtures import Image
LOADED_SOURCE_SHA256=sha256(Path(__file__))
SCENARIOS=('basic','large','raw-text','fault-read','fault-enumeration')
LIMITS=dict(host_seconds=900,guest_frames=45000)

from generate_console import constants as console_layout
CONSOLE_LAYOUT=console_layout()

def convert(raw):return bytes(10 if x==155 else x if x in (9,10)or 32<=x<=126 else 46 for x in raw if x!=13)

def prepare(size,scenario):
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text());volume=next(v for v in manifest['volumes']if v['sector_bytes']==size)
    original=ROOT/volume['path'];require(sha256(original)==volume['sha256'],'Original media changed')
    disk=Image(original.read_bytes());rows=[dict(e)for e in volume['entries']if e['parent']==361]
    contents={f['path']:bytes((i&255)^f['seed']for i in range(f['bytes']))for f in volume['files']}
    derived={};occupied={360,*range(361,369)}
    for f in volume['files']:occupied.update(f['chain'])
    for e in volume['entries']:
        if e['flags']&16:occupied.update(range(e['start'],e['start']+8))
    def free():return [s for s in range(500,disk.count+1)if s not in occupied]
    def put(row,name,start,count,flags):
        base,_,suffix=name.partition('.');raw=bytes([flags])+struct.pack('<HH',count,start)+base.encode().ljust(8,b' ')+suffix.encode().ljust(3,b' ')
        require(len(raw)==16,'Invalid derived entry')
        at=disk.offset(361+row//8)+16*(row%8);disk.data[at:at+16]=raw
        rows[row]=dict(name=name,path=name,flags=flags,count=count,start=start,parent=361,ordinal=row)
    if scenario in ('basic','raw-text'):
        available=set(free());start=next(s for s in sorted(available)if set(range(s,s+8))<=available)
        for sector in range(start,start+8):
            occupied.add(sector);at=disk.offset(sector);disk.data[at:at+size]=bytes(size)
        put(59,'EDIR',start,8,16)
        for row,count in enumerate((511,512,513,1025),60):
            name='B'+str(count)+'.BIN';payload=bytes(i&255 for i in range(count));chain=free()[:(count+size-4)//(size-3)]
            require(len(chain)*(size-3)>=count,'No space for derived file')
            for index,sector in enumerate(chain):
                occupied.add(sector);chunk=payload[index*(size-3):(index+1)*(size-3)];nxt=chain[index+1]if index+1<len(chain)else 0
                raw=chunk.ljust(size-3,b'\0')+bytes([nxt>>8,nxt&255,len(chunk)]);at=disk.offset(sector);disk.data[at:at+size]=raw
            put(row,name,chain[0],len(chain),0x46);contents[name]=payload
            derived[name]=dict(source_bytes=count,sha256=hashlib.sha256(payload).hexdigest(),chain=chain)
    if scenario=='fault-enumeration':
        row=rows[1];at=disk.offset(361)+16+5;disk.data[at]=33
        derived['fault']=dict(kind='illegal second root name',ordinal=1,byte=33)
    if scenario=='fault-read':
        target=next(f for f in volume['files']if f['path']=='EXT.BIN');first=target['chain'][0];at=disk.offset(first)+size-3
        high=first>>8 if target['flags']&4 else (target['ordinal']<<2)|(first>>8)
        disk.data[at:at+2]=bytes([high,first&255]);derived['fault']=dict(kind='first file sector links to itself',sector=first)
    def listing(entries):return b''.join(e['name'].encode()+(b'/'if e['flags']&16 else b' '+str(len(contents[e['path']])).encode())+b'\n'for e in entries)
    def item(command,output=b'',error=0,kind='run',source=None):return dict(command=command,output=output,status=10 if error else 0,error=error,kind=kind,source=source)
    if scenario=='basic':
        cases=[item('DIR',listing(rows)),item('DIR TOOLS',b'SUB/\n'),item('DIR TOOLS/SUB',b'DATA.BIN 777\n'),item('DIR EDIR'),
               item('DIR TEXT.TXT',diagnostic_text(212,'DIR'),212),item('TYPE MISSING',diagnostic_text(205,'TYPE'),205),item('TYPE',diagnostic_text(212,'TYPE'),212)]
        for name in ('EMPTY','TEXT.TXT','B511.BIN','B512.BIN','B513.BIN','TOOLS/SUB/DATA.BIN'):
            cases.append(item('TYPE '+name,convert(contents[name]),source=contents[name]))
        cases += [item('TYPE',kind='default'),item('MEM',kind='memory'),
                  item('signed-decimal',b'-2147483648 -1 0 2147483647\n',kind='numbers'),
                  item('row-bounds',b'X'*31+b' -2147483648\n'+b'X'*31+b' 2147483647\n'+b'X'*31+b'/\n',kind='rows'),
                  item('DIR TOOLS',b'SUB/\n',kind='pipe')]
    elif scenario=='large':
        require(size==256,'Full TYPE requires 256-byte fixture');payload=contents['LARGE.BIN'];require(len(payload)==70003,'Not the full file')
        cases=[item('TYPE LARGE.BIN',convert(payload),source=payload)]
    elif scenario=='raw-text':cases=[item('TYPE B1025.BIN',convert(contents['B1025.BIN']),kind='raw',source=contents['B1025.BIN'])]
    elif scenario=='fault-read':cases=[item('TYPE EXT.BIN',diagnostic_text(213,'TYPE'),213)]
    else:cases=[item('DIR',b'TOOLS/\n'+diagnostic_text(210,'DIR'),210)]
    return disk,cases,derived,volume['sha256']

def run(t,out,mode,bank=1,size=128,scenario='basic',profile=1):
    out.mkdir(parents=True,exist_ok=True);source=instrument(out,'shell_commands.act')
    observed=out/'shell-observed.inc'
    observed.write_text(observed.read_text().replace('  NativeShellWrite(handle,bytes,count)',
                                                   '  writes==+1\n  NativeShellWrite(handle,bytes,count)'))
    capture_address=None
    command_address=0xf8000
    source.write_text(source.read_text().replace('$e0000','$f8000'))
    disk,cases,derived,original_sha=prepare(size,scenario);media=out/'volume.atr';media.write_bytes(disk.data);digest=sha256(media)
    blob=bytearray();calls=[]
    for case in cases:
        offset=len(blob);blob+=case['command'].encode()+b'\0';kind=case['kind']
        if kind=='run':
            calls.append(f'  Run({offset},{case["status"]},{case["error"]})')
            if case['command'].startswith('DIR') and not case['error']:
                calls.append(f'  Check(writes-rowStart={len(case["output"].splitlines())})')
        else:calls.append(f'  {dict(default="DefaultInput",memory="Memory",raw="RawText",numbers="Numbers",rows="Rows",pipe="PipeOutput")[kind]}({offset})')
    # A straight sequence of tiny dispatch helpers keeps generated fixed frames bounded.
    (out/'shell-command-cases.inc').write_text('PROC Cases()\n'+'\n'.join(calls)+'\nRETURN\n')
    fixture_profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    fixture_profile['image_data_bytes']=4096
    profile_path=out/'fixture-memory.json';profile_path.write_text(json.dumps(fixture_profile)+'\n')
    p=build(t,source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,memory_profile=profile_path,
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=disk.count,sector_bytes=size,profile=profile)],
            image_data=[(command_address,bytes(blob))])
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned shell bridge')
    require(sha256(ROOT/'build/firmware/altirraos-816.rom')==PIN['rom']['sha256'],'Unpinned ROM')
    def at(name):return next(d['address']for d in p['image']['data']if '_SHELLAPP_'+name.upper()+'_'in d['name'])
    observations=[];saved={}
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN)as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','generic56k' if profile==4 else 'fastest');b.mount(0,str(media))
        def before(b):
            nonlocal capture_address
            saved.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['bytes']=b.memdump(saved['screen'],960)
            if scenario!='raw-text':
                capture_address=collect_capture(b,p,out);return
            payload=draw(b'')+cases[0]['output'];cells,screen,cursor=terminal(payload)
            cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE']
            condition=f'(db(${at("stage"):x})=2)&(db(${instance+CONSOLE_LAYOUT["INSTANCE_DIRTYROWS"]:x})=0)&(dw(${cs["PRESENTATION"]+10:x})={cursor})'
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);run_to(b,p['labels']['native_nmi'],LIMITS['guest_frames'],LIMITS['host_seconds'],condition)
            far=lambda addr,n:bytes(b.eval_expr(f'db(${addr+i:x})')for i in range(n))
            pointer=int.from_bytes(far(instance,3),'little');actual_cells=far(pointer,960);actual_screen=b.memdump(saved['screen'],960)
            (out/'cells.bin').write_bytes(actual_cells);(out/'screen-text.bin').write_bytes(actual_screen)
            require(actual_cells==cells and actual_screen==screen,'RAW text/cursor/scrolling differs')
            observations.append(dict(stage='raw-text',cursor=cursor,cells_sha256=sha256(out/'cells.bin'),screen_sha256=sha256(out/'screen-text.bin')))
            b.poke(at('gate'),1);b.bp_clear_all()
            capture_address=collect_capture(b,p,out)
        original_regs=b.regs;last=time.monotonic()
        def regs():
            nonlocal last
            r=original_regs()
            if time.monotonic()-last>30:
                print('Command progress',scenario,'executed',b.peek16(at('executed')),'checks',b.peek16(at('checks')),'writes',b.peek16(at('captureCount')),'frame',b.eval_expr('@frame'),flush=True);last=time.monotonic()
            return r
        b.regs=regs
        try:rt,_=execute(b,p,before_run=before,timeout=LIMITS['host_seconds'],frame_limit=LIMITS['guest_frames'])
        except Exception:
            pointer=int.from_bytes(bytes(data(b,p['image'],'shell')),'little')
            print('Shell command checks/executed',data(b,p['image'],'checks',True),data(b,p['image'],'executed',True),'shell result',[b.eval_expr(f'dw(${pointer+i:x})')for i in (24,28,32,36,54)],flush=True);raise
        finally:b.regs=original_regs
        counts={k:int.from_bytes(bytes(data(b,p['image'],k)),'little')for k in ('captureCount','checks','executed')}
        require(data(b,p['image'],'stage')==[3]and counts['executed']==len(cases)+(2 if scenario=='basic'else 0),'Incomplete commands')
        memory={};expected=bytearray(draw(b''))
        for case in cases:
            if case['kind']=='memory':
                output=bytearray()
                for name in ('memBefore','memDuring','memAfter'):
                    values=struct.unpack('<4I',bytes(data(b,p['image'],name)));memory[name]=values
                    output+=b''.join(label+str(value).encode()+b'\n'for label,value in zip((b'ordinary total ',b'ordinary largest ',b'linear total ',b'linear largest '),values))
                case['output']=bytes(output)
            expected+=case['output']
        require(counts['captureCount']==len(expected),'Wrong command output length')
        actual=(out/'writes.bin').read_bytes();(out/'expected.bin').write_bytes(expected)
        require(actual==expected,'Actual command Write bytes differ');ownership(b,p,out)
        require(b.memdump(saved['screen'],960)==saved['bytes']and b.peek(752)==saved['cursor']and b.peek(16)==saved['mask'],'Console not restored')
        require(sha256(media)==digest,'Read-only fixture changed')
    commands=[]
    for c in cases:
        record={k:v for k,v in c.items()if k not in ('output','source')};record.update(output_bytes=len(c['output']),output_sha256=hashlib.sha256(c['output']).hexdigest())
        if c['source']is not None:record.update(source_bytes=len(c['source']),source_sha256=hashlib.sha256(c['source']).hexdigest())
        commands.append(record)
    return dict(status='pass',mode=mode,kernel_bank=bank,sector_bytes=size,profile=profile,scenario=scenario,build=p['build'],runtime=rt,machine=machine,pin=PIN,limits=LIMITS,counts=counts,commands=commands,memory=memory,observations=observations,derived=derived,
                capture_address=capture_address,command_address=command_address,fixture_sha256=sha256(source),writes_sha256=sha256(out/'writes.bin'),expected_sha256=sha256(out/'expected.bin'),media_sha256=digest,original_media_sha256=original_sha,hook_sha256=sha256(out/'shell-observed.inc'),
                source_inputs={s:LOADED_SOURCE_SHA256 if s=='tools/test_shell_commands.py' else sha256(ROOT/s)for s in ('examples/shell/shell.act','examples/shell/shell-session.inc','examples/shell/shell-commands.inc','tests/programs/shell_commands.act','tools/test_shell_commands.py','tools/test_shell_core.py')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--bank',type=int,default=1);p.add_argument('--sector-size',type=int,default=128);p.add_argument('--profile',type=int,choices=(1,4),default=1);p.add_argument('--scenario',choices=SCENARIOS,default='basic');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case,a.bank,a.sector_size,a.scenario,a.profile);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell commands passed',a.case,a.scenario,a.bank,a.sector_size,flush=True)
