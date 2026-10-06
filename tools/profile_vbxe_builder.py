#!/usr/bin/env python3
"""Run the original panel protocol with passive builder and presenter markers."""
import argparse
import json
from pathlib import Path
import test_widget_panel as panel
from bitmap_console_performance import native_markers
from console_turn_profile import flat_markers
from dos_concurrent_trace import call_marker
from vbxe_builder_csites import csites,workpoints


def run(program,out,idle_only=False):
    original=panel.observers
    def observers(p,breakdown=False):
        spans,marks,definition=original(p,breakdown)
        names='''CONSOLEDRIVER_COLLECT CONSOLEDRIVER_READQUANTUM CONSOLEDRIVER_WRITEQUANTUM CONSOLEDRIVER_ARRIVAL CONSOLECORE_FEED CONSOLECORE_EDITQUANTUM CONSOLEDISPLAY_PRESENT CONSOLEDISPLAY_CELLS CONSOLEDISPLAY_REMOVECURSOR CONSOLEDISPLAY_CURSOR CONSOLEDISPLAY_ADVANCE CONSOLEDISPLAY_PRESENTBATCH CONSOLEDISPLAY_FLUSHBATCH CONSOLEDISPLAY_POLL CONSOLEBITMAP_CLIPPEDTEXT CONSOLEBITMAP_DESKTOPDRAW CONSOLEBITMAP_RUN CONSOLEBITMAP_TEXT CONSOLEBITMAP_TEXTCARET CONSOLEBITMAP_FILL CONSOLEBITMAP_RAWFILL CONSOLEBITMAP_SCROLL CONSOLEBITMAP_CURSOR DESKHOST_CONTROLS DESKHOST_AFTERPAINT DESKHOST_EVENTS DESKHOST_CACHE DESKPAINT_PAINTSTRIP DESKINPUT_SERVICE DESKINPUT_ADVANCE DESKINPUT_PRESENT DESKCACHE_PUMP DESKMOVE_PUMP AESCORE_DISPATCH'''.split()
        extra=native_markers(p,[(n,n.lower()) for n in names])
        extra.update(csites(p,json.loads((p['output'].parent/'c-image.json').read_text())))
        definition['spans'].update(extra);spans.update(extra)
        definition['points'].update(workpoints(p,json.loads((p['output'].parent/'c-image.json').read_text())))
        mapped={**p,'labels':{**p['labels'],'collect':extra['consoledriver_collect']['entry']}}
        definition['points']['worker_turn']=call_marker(mapped,'M_CONSOLEDRIVER_WORKER_','collect')
        marks.update(flat_markers(definition))
        out.mkdir(parents=True,exist_ok=True)
        (out/'presenter-definition.json').write_text(json.dumps(definition,indent=2)+'\n')
        return spans,marks,definition
    panel.observers=observers
    try:
        panel.run(out.resolve(),program.resolve(),count=10,feedback=True,
                  breakdown=True,idle_only=idle_only)
    finally:
        panel.observers=original


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('program',type=Path)
    a.add_argument('output',type=Path)
    a.add_argument('--idle-only',action='store_true')
    args=a.parse_args();run(args.program,args.output,args.idle_only)
