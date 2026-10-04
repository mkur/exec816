#!/usr/bin/env python3
"""Link the optional worker-owned bitmap console into an ordinary native program."""
import argparse,json,re
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract,PORT
from generate_console_bitmap import expected_layout,files
from library_paths import read_source
from native_program import ROOT,build,compiler,require,sha256


def drawing(out,optimize,probe=False,fault=False,widgets=False,widget_probe=False):
    for path,content in files().items():require(path.read_text()==content,'Stale console packet: '+str(path))
    extraction=extract(out/'selected');src=out/'selected/src';ad=PORT/'adapter'
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',ROOT/'platform/altirraos/vbxe.c',
             src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',
             ad/'gem-vbxe.c',ROOT/'lib/console/console-bitmap.c']
    extra_roots=[];extra_includes=[];extra_probes=[]
    if widgets or widget_probe:
        from extract_gem_aes import extract as aes_extract,PORT as aes
        from generate_widgets import expected_layout as aes_layout
        aes_record=aes_extract(out/'aes-selected')
        sources += [aes/'widgets-model.c',aes/'widgets-graf.c',aes/'widgets-render.c',
                    *(out/'aes-selected'/n for n in ('aes-objects.c','aes-graf.c','aes-form.c'))]
        extra_includes=[aes,out/'aes-selected']
        extra_probes=[(aes/'widget-layout.c',aes_layout())]
        if widget_probe:
            sources.append(ROOT/'tests/programs/widgets_pixels.c')
            extra_roots=['WidgetPixelProbe']
            original=ROOT/'lib/console/console-bitmap.c'
            instrumented=out/'console-widget-probe.c'
            text=original.read_text().replace('struct ConsoleBitmapPacket ConsoleBitmapPacket',
                'extern void WidgetPixelProbe(void);\nstruct ConsoleBitmapPacket ConsoleBitmapPacket')
            text=text.replace('p->status=GemDrawingOpen(workout);',
                'p->status=GemDrawingOpen(workout);\n        if (!p->status) WidgetPixelProbe();')
            instrumented.write_text(text)
            sources[sources.index(original)]=instrumented
    if fault:
        hardware=(ROOT/'platform/altirraos/vbxe.c').read_text()
        hardware=hardware.replace('#define BUSY ', 'extern UBYTE ConsoleFaultBusy(void);\nextern void ConsoleFaultStop(void);\nextern void ConsoleFaultCopy(void);\nextern void ConsoleFaultText(UWORD count,UWORD fillRows);\n#define BUSY ')
        hardware=hardware.replace('REG(BUSY)&3','ConsoleFaultBusy()&3').replace('REG(BUSY)=0;', 'REG(BUSY)=0; ConsoleFaultStop();')
        needle='status=VbxeNotifyArm(d->scrollId);'
        require(hardware.count(needle)==1,'Scroll launch boundary changed')
        hardware=hardware.replace(needle,needle+' ConsoleFaultCopy();')
        needle='start(d);\n        status=VbxeOwnerFence(d);'
        require(hardware.count(needle)==1,'Text launch boundary changed')
        hardware=hardware.replace(needle,'start(d); ConsoleFaultText(n,upload.fillRows);\n        status=VbxeOwnerFence(d);')
        target=out/'vbxe-fault.c';target.write_text(hardware)
        sources[sources.index(ROOT/'platform/altirraos/vbxe.c')]=target
        sources.append(ROOT/'tests/programs/console_bitmap_fault.c')
    if probe:sources.append(ROOT/'tests/programs/console_bridge.c')
    assembly=[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s']
    if probe:assembly.append(ROOT/'tests/programs/console_bridge.s')
    foreign=emit(out/'drawing',sources,assembly,[],
        optimize=optimize,roots=['ConsoleBitmapEntry']+(['ConsoleBridgeProbe'] if probe else [])+extra_roots,includes=[src,ad]+extra_includes,definitions={
            'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_'],
            'gem-vbxe.c':['-DGEM_DRAWING_ONLY']},
        probes=[(ROOT/'c/calypsi/console-bitmap-layout.c',expected_layout())]+extra_probes)
    for name in ('GemServiceWorker','GemClientInit','GemVbxeBackend'):
        require(name not in foreign['symbols'],'Unexpected GUI policy: '+name)
    foreign['provenance'].update(extraction=extraction,fixture_bridge=probe,fixture_fault=fault,source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [*sources,*assembly,ROOT/'abi/console-bitmap.json',ROOT/'c/include/hardware/console-bitmap.h']})
    if widgets or widget_probe:foreign['provenance']['aes_extraction']=aes_record
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    return foreign


def prepare(source,out,foreign,desktop=False):
    text=read_source(source);sy=foreign['symbols']
    require(len(re.findall(r'(?m)^PROC Main\(\)',text))==1,'Expected one ordinary Main entry')
    text=text.replace('PROC Main()','PROC BitmapApplication(BYTE unused)')
    uses=''.join('USE '+name+'\n' for name in ('EXEC','CONSOLEDRIVER','CONSOLEBITMAP','DISPLAY','DISPLAYBOOT','DISPLAYADAPTER','BLITTER','BLITTERADAPTER','HEAPCORE') if not re.search(r'(?mi)^USE '+name+r'\s*$',text))
    text=re.sub(r'(?m)^(MODULE \w+\n)',lambda m:m[1]+uses,text,count=1)
    binding=f'CONST C_EXECDISPLAYENTRIES=${sy["ExecDisplayEntries"]:x}\n'
    binding+=read_source(ROOT/'c/calypsi/display-bridge.inc')
    binding+=f'''
PROC Main()

  BindDisplay()
  DISPLAYBOOT.Authorize()
  IF CONSOLEBITMAP.Bind(${sy['ConsoleBitmapEntry']:x},${sy['ConsoleBitmapPacket']:x})=0 THEN
    HEAPCORE.Abort($f730)
  FI

  IF CONSOLEDRIVER.Start()=0 THEN
    HEAPCORE.Abort($f731)
  FI

  BitmapApplication(0)
  IF CONSOLEDRIVER.Stop()=0 THEN
    HEAPCORE.Abort($f732)
  FI

RETURN
'''
    if 'ConsoleBridgeProbe' in sy:
        binding=binding.replace('  BindDisplay()',f'  LET probe=LONGCARD POINTER(${sy["ConsoleProbeNative"]:x})\n  probe^=LONGCARD(ADDRESS(@CONSOLEBITMAP.Call))\n  CONSOLEBITMAP.Call(${sy["ConsoleBridgeProbe"]:x})\n  BindDisplay()',1)
    if 'ConsoleBridgeProbe' in sy:
        checks=''
        for entry,packet in [(0xbffff,sy['ConsoleBitmapPacket']),(0xd0000,sy['ConsoleBitmapPacket']),
                             (sy['ConsoleBitmapEntry'],0xcfffe),(sy['ConsoleBitmapEntry'],0xdffce),
                             (sy['ConsoleBitmapEntry'],sy['ConsoleBitmapPacket']+1),(sy['ConsoleBitmapEntry'],0xdffc8),
                             (0x1000000,sy['ConsoleBitmapPacket'])]:
            checks+=f'  IF CONSOLEBITMAP.Bind(${entry:x},${packet:x})<>0 THEN\n    HEAPCORE.Abort($f733)\n  FI\n\n'
        binding=binding.replace('  BindDisplay()',checks+'  BindDisplay()',1)
    if desktop:
        text=text.replace('USE EXEC\n','USE EXEC\nUSE DESKBOOT\n',1)
        binding=binding.replace('  IF CONSOLEDRIVER.Start()=0 THEN', '  IF DESKBOOT.Enable()=0 THEN\n    HEAPCORE.Abort($fae6)\n  FI\n\n  IF CONSOLEDRIVER.Start()=0 THEN')
        binding=binding.replace('  IF CONSOLEDRIVER.Start()=0 THEN\n    HEAPCORE.Abort($f731)', '  IF CONSOLEDRIVER.Start()=0 THEN\n    DESKBOOT.Disable()\n    HEAPCORE.Abort($f731)')
        binding=binding.replace('  BitmapApplication(0)', '  IF DESKBOOT.Attach()=0 THEN\n    IF CONSOLEDRIVER.Stop()=0 THEN\n      HEAPCORE.Abort($f732)\n    FI\n\n    DESKBOOT.Disable()\n    HEAPCORE.Abort($fae7)\n  FI\n\n  BitmapApplication(0)\n  IF DESKBOOT.StopAdmission()=0 THEN\n    HEAPCORE.Abort($faea)\n  FI\n\n  DESKBOOT.Detach()')
        binding=binding.removesuffix('RETURN\n')+'  DESKBOOT.Disable()\n\nRETURN\n'
    text=text.replace('ENDMODULE',binding+'\nENDMODULE')
    path=out/'launcher.act';path.write_text(text);return path


def build_bitmap(source,out,optimize=True,probe=False,fault=False,program_output=None,compiler_dir=None,desktop=False,**kwargs):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    foreign=drawing(out,optimize,probe,fault)
    launcher=prepare(Path(source),out,foreign,desktop)
    program=build(compiler(compiler_dir or ROOT/'build/actionc'),launcher,program_output or out/'program',optimize=optimize,tasks=True,
                 task_capacity=8,console=False,console_deferred=True,foreign_image=foreign,**kwargs)
    if desktop:
        from generate_desktop import ABI
        program['build']['desktop_pointer_pixels_per_step']=ABI['constants']['POINTER_PIXELS_PER_STEP']
        (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--raw',action='store_true');a=p.parse_args()
    build_bitmap(a.source,a.output,not a.raw)
