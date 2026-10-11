"""Small TEDINFO ABI/access probe and independent object-display pixel checks."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
    from test_desktop_presentation import rectangle
    import adapter_state as adapter
    sy=foreign['symbols'];out=p['output'].parent
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
    font=font_bytes(out/'selected/src/vdi/font8x8.c')
    rgb=bytes((v&254)+(v>>7) for v in PALETTE);hardware=[None]*16
    for pen,hw in enumerate(PENS):hardware[hw]=rgb[pen*3:pen*3+3][::-1]
    report['tedinfo_pixels']=[]
    for phase in range(1,4):
        reach('dw($%x)=%d'%(sy['TEDPhase'],phase))
        reach('@frame>=%d'%(b.eval_expr('@frame')+80))
        model=Raster(font)
        for y in (52,76):
            rectangle(model,(55,y-1,185,y+9),1)
            rectangle(model,(56,y,184,y+8),0)
        text=b'-2147483647' if phase==1 else b'          7'
        for x,y in ((56,52),(96,76),(76,100)):model.apply(8,(x,y+6),text)
        path=out/('tedinfo-%d.bgra'%phase);frame=b.rawscreen(str(path));raw=path.read_bytes()
        for y in range(44,132):
            for x in range(48,208):
                at=y*frame.stride+(x+16)*4
                require(raw[at:at+3]==hardware[model.pixels[y*640+x]],
                        'TEDINFO pixels phase %d at %d,%d'%(phase,x,y))
        report['tedinfo_pixels'].append(dict(phase=phase,pixels=160*88))
        b.poke16(sy['TEDGo'],phase)
    report['edit_pixels']=[]
    for phase in range(1,5):
        reach('dw($%x)=%d'%(sy['EditPhase'],phase))
        reach('@frame>=%d'%(b.eval_expr('@frame')+40))
        model=Raster(font)
        rectangle(model,(55,51,121,69),1)
        rectangle(model,(56,52,120,68),0)
        text={1:b'2B-Cd',2:b'56789ab',3:b'01234567',4:b'01234567'}[phase]
        model.apply(8,(56,62),text)
        if phase in (1,2):rectangle(model,(96 if phase==1 else 112,56,97 if phase==1 else 113,64),1)
        path=out/('edit-%d.bgra'%phase);frame=b.rawscreen(str(path));raw=path.read_bytes()
        for y in range(50,70):
            for x in range(54,122):
                at=y*frame.stride+(x+16)*4
                require(raw[at:at+3]==hardware[model.pixels[y*640+x]],
                        'Editable pixels phase %d at %d,%d'%(phase,x,y))
        report['edit_pixels'].append(dict(phase=phase,pixels=68*20))
        b.poke16(sy['EditGo'],phase)
    b.bp_clear_all()


def layout(out,optimize):
    from calypsi_build import emit
    from native_program import build,compiler,verify_machine
    from os_boundary import emulator
    from test_dos_stack import execute,ownership
    from test_cooperative import data
    from stack_budget import bank_zero_delta
    out.mkdir(parents=True,exist_ok=True)
    from extract_gem_aes import extract,PORT
    extract(out/'selected')
    graf=out/'selected/aes-graf.c'
    graf.write_text(graf.read_text().replace('aes-hosted.h','application-hosted.h'))
    f=emit(out/'c',[ROOT/'c/calypsi/exec.c',ROOT/'tests/programs/tedinfo_layout.c',graf],
           [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),optimize,
           roots=['TedProbe'],includes=[PORT],probes=[(ROOT/'tests/programs/tedinfo_layout.c',[
               ('OBJECT',24),('TEDINFO',28),('ptext',0),('ptmplt',4),('pvalid',8),
               ('font',12),('fontid',14),('just',16),('color',18),('fontsize',20),
               ('thickness',22),('txtlen',24),('tmplen',26)])])
    source=out/'probe.act'
    source.write_text('''MODULE TEDPROBE
USE CALYPSICALL
LONGINT result
PROC Main()

  result=CALYPSICALL.Invoke(ADDRESS($%x),0)

RETURN
ENDMODULE
'''%f['symbols']['TedProbe'])
    p=build(compiler(ROOT/'build/actionc'),source,out/'program',tasks=True,task_capacity=8,
            foreign_image=f,optimize=optimize,console=False)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,p,timeout=120,frame_limit=6000,timer_irq=True)
        observed=data(b,p['image'],'result',True)
        measurement=b.memdump(f['symbols']['TedObserved'],14).hex()
        require(observed==[0,0],'TEDINFO upper-pointer access failed: '+str(observed))
        ownership(b,p,p['output'])
    record=dict(status='pass',tier='development',optimized=optimize,machine=machine,
                runtime=runtime,text_measurement=measurement,layout=f['provenance']['checked_layout'],
                bank_zero_delta=bank_zero_delta(p['build']['memory']))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true')
    args=parser.parse_args();layout(args.output.resolve(),not args.raw)
