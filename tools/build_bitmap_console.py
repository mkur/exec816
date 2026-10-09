#!/usr/bin/env python3
"""Link the optional worker-owned bitmap console into an ordinary native program."""
import argparse,json,re
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract,PORT
from generate_console_bitmap import expected_layout,files
from library_paths import read_source
from native_program import ROOT,build,compiler,require,sha256


def drawing(out,optimize,probe=False,fault=False,widgets=False,widget_probe=False,
            client_sources=(),client_entries=(),client_roots=(),client_probes=(),
            client_optimization=None,renderer_source=None):
    for path,content in files().items():require(path.read_text()==content,'Stale console packet: '+str(path))
    extraction=extract(out/'selected');src=out/'selected/src';ad=PORT/'adapter'
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',ROOT/'platform/altirraos/vbxe.c',
             src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',
             ad/'gem-vbxe.c',ROOT/'lib/console/console-bitmap.c',ROOT/'lib/desktop/desktop-frame.c']
    extra_roots=[];extra_includes=[];extra_probes=[]
    if widgets or widget_probe:
        from extract_gem_aes import extract as aes_extract,PORT as aes
        from generate_widgets import expected_layout as aes_layout
        aes_record=aes_extract(out/'aes-selected')
        sources += [aes/'widgets-model.c',aes/'widgets-graf.c',aes/'widgets-render.c',aes/'menu-render.c',
                    *(out/'aes-selected'/n for n in ('aes-objects.c','aes-graf.c','aes-form.c'))]
        extra_includes=[aes,out/'aes-selected']
        extra_probes=[(aes/'widget-layout.c',aes_layout())]
        if widgets:
            sources += [aes/'widgets-state.c',aes/'widgets-input.c',aes/'widgets-entry.c']
            extra_roots=['WidgetEntry']
        if widget_probe:
            sources += [ROOT/'tests/programs/widgets_pixels.c',
                        ROOT/'tests/programs/glyphs_clipped.c']
            extra_roots=['WidgetPixelProbe']
            original=ROOT/'lib/console/console-bitmap.c'
            instrumented=out/'console-widget-probe.c'
            text=original.read_text().replace('struct ConsoleBitmapPacket ConsoleBitmapPacket',
                'extern void WidgetPixelProbe(void);\nstruct ConsoleBitmapPacket ConsoleBitmapPacket')
            text=text.replace('p->status=GemDrawingOpen(workout);',
                'p->status=GemDrawingOpen(workout);\n        if (!p->status) WidgetPixelProbe();')
            instrumented.write_text(text)
            sources[sources.index(original)]=instrumented
            original=ad/'gem-vbxe.c'
            instrumented=out/'gem-vbxe.c'
            text=original.read_text().replace('static void drain(void)',
                'static UWORD BuilderSubmit(const UBYTE *,UWORD);\nstatic void drain(void)')
            needle='if (commandCount && !fault) latch(VbxeOwnerSubmit(&display,commands,commandCount));'
            require(text.count(needle)==1,'Private list publication changed')
            text=text.replace(needle,'if (commandCount && !fault) latch(BuilderSubmit(commands,commandCount));')
            probe_source=ROOT/'tests/programs/vbxe-builder-probe.h'
            text+='\n'+probe_source.read_text()
            instrumented.write_text(text)
            sources[sources.index(original)]=instrumented
    if fault:
        hardware=(ROOT/'platform/altirraos/vbxe.c').read_text()
        hardware=hardware.replace('#define BUSY ', 'extern UBYTE ConsoleFaultBusy(void);\nextern void ConsoleFaultStop(void);\nextern void ConsoleFaultCopy(void);\nextern void ConsoleFaultText(UWORD count,UWORD fillRows);\n#define BUSY ')
        hardware=hardware.replace('REG(BUSY)&3','ConsoleFaultBusy()&3').replace('REG(BUSY)=0;', 'REG(BUSY)=0; ConsoleFaultStop();')
        needle='status=VbxeNotifyArm(d->operationId);'
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
    if client_sources:
        sources.append(ROOT/'c/calypsi/io.c')
        assembly.append(ROOT/'c/calypsi/io.s')
        extra_roots.append('ExecIOEntry')
    sources += list(client_sources)
    if ROOT/'c/calypsi/aes.c' in sources:
        sources.append(ROOT/'c/calypsi/aes-windows.c')
        sources.append(ROOT/'c/calypsi/aes-input.c')
        sources.append(ROOT/'c/calypsi/vdi.c')
        # A second binding of the same extracted donor routines isolates the
        # presenter's scratch from callers that can block acquiring DISPLAY.
        from extract_gem_aes import extract as object_extract, PORT as object_port
        object_extract(out/'app-objects')
        for name in ('aes-objects.c','aes-graf.c','aes-form.c'):
            path=out/'app-objects'/name
            path.write_text(path.read_text().replace('"aes-hosted.h"','"application-hosted.h"'))
            sources.append(path)
        graf=out/'app-objects'/'app-graf.c'
        graf.write_text((object_port/'widgets-graf.c').read_text().replace('"widgets.h"','"application-hosted.h"'))
        sources += [graf,ROOT/'c/calypsi/aes-objects.c',ROOT/'c/calypsi/aes-edit.c',ROOT/'c/calypsi/aes-form.c',ROOT/'c/calypsi/aes-alert.c',ROOT/'c/calypsi/aes-fsel.c',ROOT/'c/calypsi/file-list.c',ROOT/'c/calypsi/aes-resource.c',ROOT/'c/calypsi/aes-menu.c',ROOT/'c/calypsi/dos.c']
        assembly.append(ROOT/'c/calypsi/dos.s')
        extra_includes.append(object_port)
        from generate_vdi_client import expected_layout as vdi_layout, files as vdi_files
        for path,content in vdi_files().items():
            require(path.read_text()==content, "Stale VDI file: "+str(path))
        extra_probes.append((ROOT/'c/calypsi/vdi-layout.c',vdi_layout()))
    if renderer_source is not None:
        sources[sources.index(ad/'gem-vbxe.c')]=renderer_source
    foreign=emit(out/'drawing',sources,assembly,client_entries,
        optimize=optimize,roots=['ConsoleBitmapEntry']+(['ConsoleBridgeProbe'] if probe else [])+extra_roots+list(client_roots),includes=[src,ad]+extra_includes,definitions={
            'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_'],
            'gem-vbxe.c':['-DGEM_DRAWING_ONLY']},
        probes=[(ROOT/'c/calypsi/console-bitmap-layout.c',expected_layout())]+extra_probes+list(client_probes),
        source_optimization=client_optimization)
    for name in ('GemServiceWorker','GemClientInit','GemVbxeBackend'):
        require(name not in foreign['symbols'],'Unexpected GUI policy: '+name)
    foreign['provenance'].update(extraction=extraction,fixture_bridge=probe,fixture_fault=fault,source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [*sources,*assembly,ROOT/'abi/console-bitmap.json',ROOT/'c/include/hardware/console-bitmap.h']})
    if widgets or widget_probe:foreign['provenance']['aes_extraction']=aes_record
    if widget_probe:foreign['provenance']['builder_probe_sha256']=sha256(probe_source)
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    return foreign


def prepare(source,out,foreign,desktop=False,aes=False,mouse_profile=None):
    if desktop:
        from generate_mouse_acceleration import configuration
        (out/'deskmouseconfig.act').write_text(configuration(mouse_profile))
    text=read_source(source);sy=foreign['symbols']
    require(len(re.findall(r'(?m)^PROC Main\(\)',text))==1,'Expected one ordinary Main entry')
    text=text.replace('PROC Main()','PROC BitmapApplication(BYTE unused)')
    uses=''.join('USE '+name+'\n' for name in ('EXEC','CONSOLEDRIVER','CONSOLEBITMAP','DISPLAY','DISPLAYBOOT','DISPLAYADAPTER','BLITTER','BLITTERADAPTER','HEAPCORE') if not re.search(r'(?mi)^USE '+name+r'\s*$',text))
    text=re.sub(r'(?m)^(MODULE \w+\n)',lambda m:m[1]+uses,text,count=1)
    binding=f'CONST C_EXECDISPLAYENTRIES=${sy["ExecDisplayEntries"]:x}\n'
    binding+=read_source(ROOT/'c/calypsi/display-bridge.inc')
    if 'ExecIOEntry' in sy:
        binding+=f'CONST C_EXECIOENTRY=${sy["ExecIOEntry"]:x}\n'
        binding+=read_source(ROOT/'c/calypsi/io-bridge.inc')
    if 'ExecDosEntries' in sy:
        text=text.replace('USE EXEC\n','USE EXEC\nUSE DOS\nUSE PROGRAMFILE\nUSE PROGRAM\nUSE PROCESS\n',1)
        binding+=f'CONST C_EXECDOSENTRIES=${sy["ExecDosEntries"]:x}\n'
        binding+=read_source(ROOT/'c/calypsi/dos-bridge.inc')
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
    if 'ExecDosEntries' in sy:
        binding=binding.replace('  BindDisplay()', '  BindDos(0)\n  BindDisplay()', 1)
    if 'ExecIOEntry' in sy:
        binding=binding.replace('  BindDisplay()', '  BindIO()\n  BindDisplay()', 1)
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
        text=text.replace('USE EXEC\n','USE EXEC\nUSE DESKBOOT\nUSE DESKWIDGETS\n',1)
        binding=binding.replace('  BindDisplay()', '  BindDisplay()\n  IF DESKWIDGETS.Bind($%x,$%x)=0 THEN\n    HEAPCORE.Abort($fab1)\n  FI' % (sy['WidgetEntry'],sy['WidgetPacket']))
        binding=binding.replace('  IF CONSOLEDRIVER.Start()=0 THEN', '  IF DESKBOOT.Enable()=0 THEN\n    HEAPCORE.Abort($fae6)\n  FI\n\n  IF CONSOLEDRIVER.Start()=0 THEN')
        binding=binding.replace('  IF CONSOLEDRIVER.Start()=0 THEN\n    HEAPCORE.Abort($f731)', '  IF CONSOLEDRIVER.Start()=0 THEN\n    DESKBOOT.Disable()\n    HEAPCORE.Abort($f731)')
        binding=binding.replace('  BitmapApplication(0)', '  IF DESKBOOT.Attach()=0 THEN\n    IF CONSOLEDRIVER.Stop()=0 THEN\n      HEAPCORE.Abort($f732)\n    FI\n\n    DESKBOOT.Disable()\n    HEAPCORE.Abort($fae7)\n  FI\n\n  BitmapApplication(0)\n  IF DESKBOOT.StopAdmission()=0 THEN\n    HEAPCORE.Abort($faea)\n  FI\n\n  DESKBOOT.Detach()')
        binding=binding.removesuffix('RETURN\n')+'  DESKBOOT.Disable()\n\nRETURN\n'
    if aes:
        require(desktop, 'AES requires the existing desktop presenter')
        text=text.replace('USE EXEC\n', 'USE EXEC\nUSE AESBOOT\n', 1)
        # Optional AES failure leaves the native desktop usable. Applications
        # test the retained endpoint after the presenter's readiness reply.
        binding=binding.replace('  IF CONSOLEDRIVER.Start()=0 THEN',
            '  BEGIN\n    LET enabled=AESBOOT.Enable()\n  END\n\n  IF CONSOLEDRIVER.Start()=0 THEN',1)
        binding=binding.replace('    DESKBOOT.Disable()', '    AESBOOT.Disable()\n    DESKBOOT.Disable()')
        binding=binding.replace('  IF DESKBOOT.StopAdmission()=0 THEN',
            '  BEGIN\n    LET stopped=AESBOOT.StopAdmission()\n  END\n\n  IF DESKBOOT.StopAdmission()=0 THEN')
        binding=binding.replace('  DESKBOOT.Disable()\n\nRETURN',
            '  AESBOOT.Disable()\n  DESKBOOT.Disable()\n\nRETURN')
    if foreign['provenance'].get('disk_component'):
        # DOS mounts lazily through native code; no C or console call may precede
        # this gate. Ordinary root retirement shuts down native workers on error.
        text=text.replace('USE EXEC\n','USE EXEC\nUSE GEMCOMPONENT\n',1)
        binding=binding.replace('PROC Main()\n','PROC Main()\n\n  IF GEMCOMPONENT.Load()=0 THEN\n    HEAPCORE.Abort($fc90)\n  FI\n',1)
    text=text.replace('ENDMODULE',binding+'\nENDMODULE')
    path=out/'launcher.act';path.write_text(text);return path


def build_bitmap(source,out,optimize=True,probe=False,fault=False,program_output=None,compiler_dir=None,desktop=False,aes=False,
                 client_sources=(),client_entries=(),client_roots=(),client_probes=(),mouse_profile=None,**kwargs):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if aes:
        from generate_aes_server import files as aes_files
        for path,content in aes_files().items():
            require(path.read_text()==content,'Stale AES protocol: '+str(path))
    if desktop and 'memory_profile' not in kwargs:
        from generate_memory import PROFILE
        profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
        memory=out/'fixture-memory.json'
        memory.write_text(json.dumps(profile,indent=2)+'\n')
        kwargs['memory_profile']=memory
    foreign=drawing(out,optimize,probe,fault,widgets=desktop,
        client_sources=client_sources,client_entries=client_entries,
        client_roots=client_roots,client_probes=client_probes)
    launcher=prepare(Path(source),out,foreign,desktop,aes,mouse_profile)
    program=build(compiler(compiler_dir or ROOT/'build/actionc'),launcher,program_output or out/'program',optimize=optimize,tasks=True,
                 task_capacity=8,console=False,console_deferred=True,foreign_image=foreign,**kwargs)
    if desktop:
        from generate_mouse_acceleration import metadata
        program['build']['desktop_mouse']=metadata(mouse_profile)
        (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--raw',action='store_true');a=p.parse_args()
    build_bitmap(a.source,a.output,not a.raw)
