#!/usr/bin/env python3
"""Link the optional worker-owned bitmap console into an ordinary native program."""
import argparse,json,re
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract,PORT
from generate_console_bitmap import expected_layout,files
from library_paths import read_source
from native_program import ROOT,build,compiler,require,sha256


def drawing(out,optimize,probe=False,fault=False):
    for path,content in files().items():require(path.read_text()==content,'Stale console packet: '+str(path))
    extraction=extract(out/'selected');src=out/'selected/src';ad=PORT/'adapter'
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',ROOT/'platform/altirraos/vbxe.c',
             src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',
             ad/'gem-vbxe.c',ROOT/'lib/console/console-bitmap.c']
    if fault:
        hardware=(ROOT/'platform/altirraos/vbxe.c').read_text()
        hardware=hardware.replace('#define BUSY ', 'extern UBYTE ConsoleFaultBusy(void);\nextern void ConsoleFaultStop(void);\n#define BUSY ')
        hardware=hardware.replace('REG(BUSY)&3','ConsoleFaultBusy()&3').replace('REG(BUSY)=0;', 'REG(BUSY)=0; ConsoleFaultStop();')
        target=out/'vbxe-fault.c';target.write_text(hardware)
        sources[sources.index(ROOT/'platform/altirraos/vbxe.c')]=target
        sources.append(ROOT/'tests/programs/console_bitmap_fault.c')
    if probe:sources.append(ROOT/'tests/programs/console_bridge.c')
    assembly=[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s']
    if probe:assembly.append(ROOT/'tests/programs/console_bridge.s')
    foreign=emit(out/'drawing',sources,assembly,[],
        optimize=optimize,roots=['ConsoleBitmapEntry']+(['ConsoleBridgeProbe'] if probe else []),includes=[src,ad],definitions={
            'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_'],
            'gem-vbxe.c':['-DGEM_DRAWING_ONLY']},
        probes=[(ROOT/'c/calypsi/console-bitmap-layout.c',expected_layout())])
    for name in ('GemServiceWorker','GemClientInit','GemVbxeBackend','cursor_show','cursor_hide'):
        require(name not in foreign['symbols'],'Unexpected GUI policy: '+name)
    foreign['provenance'].update(extraction=extraction,fixture_bridge=probe,fixture_fault=fault,source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [*sources,*assembly,ROOT/'abi/console-bitmap.json',ROOT/'c/include/hardware/console-bitmap.h']})
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    return foreign


def prepare(source,out,foreign):
    text=read_source(source);sy=foreign['symbols']
    require(len(re.findall(r'(?m)^PROC Main\(\)',text))==1,'Expected one ordinary Main entry')
    text=text.replace('PROC Main()','PROC BitmapApplication(BYTE unused)')
    uses=''.join('USE '+name+'\n' for name in ('EXEC','CONSOLEDRIVER','CONSOLEBITMAP','DISPLAY','DISPLAYBOOT','DISPLAYADAPTER','HEAPCORE') if not re.search(r'(?mi)^USE '+name+r'\s*$',text))
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
                             (sy['ConsoleBitmapEntry'],sy['ConsoleBitmapPacket']+1),
                             (0x1000000,sy['ConsoleBitmapPacket'])]:
            checks+=f'  IF CONSOLEBITMAP.Bind(${entry:x},${packet:x})<>0 THEN\n    HEAPCORE.Abort($f733)\n  FI\n\n'
        binding=binding.replace('  BindDisplay()',checks+'  BindDisplay()',1)
    text=text.replace('ENDMODULE',binding+'\nENDMODULE')
    path=out/'launcher.act';path.write_text(text);return path


def build_bitmap(source,out,optimize=True,probe=False,fault=False,**kwargs):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    foreign=drawing(out,optimize,probe,fault)
    launcher=prepare(Path(source),out,foreign)
    return build(compiler(ROOT/'build/actionc'),launcher,out/'program',optimize=optimize,tasks=True,
                 task_capacity=8,console=False,console_deferred=True,foreign_image=foreign,**kwargs)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--raw',action='store_true');a=p.parse_args()
    build_bitmap(a.source,a.output,not a.raw)
