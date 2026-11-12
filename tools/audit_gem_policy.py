#!/usr/bin/env python3
"""Audit the current GEM source and an emitted provider for retired policy."""
import argparse
import json
import re
from pathlib import Path

from generate_desktop import ABI, layout
from native_program import ROOT, read_build, require, sha256


def audit(directory):
    retired = ('DESKTOP', 'DESKCONSOLE', 'DESKTABS', 'DESKEVENTS',
               'DESKWIDGETS', 'DESKWIDGETINPUT', 'DESKAPP')
    sources = [p for folder in ('lib', 'c', 'examples', 'ports/gem4xe/aes', 'tests/programs')
               for p in (ROOT/folder).rglob('*')
               if p.suffix in ('.act', '.inc', '.c', '.h')]
    forbidden = re.compile(
        r'\b(?:ExecAESConsole|WF_EXEC_CONSOLE|CONTENT_COMMANDS|CONTENT_WIDGETS|'
        r'CONTENT_CONSOLE|FRAME_SHELL_TABS|WidgetContext|WidgetEntry)\b|'
        r'\bDESKTYPES\.(?:Request|Content|Client|ClientRecord)\b')
    for path in sources:
        text = path.read_text()
        require(not forbidden.search(text), 'Retired graphical policy: '+str(path))
        imports = re.findall(r'^USE (\w+)\s*$', text, re.M)
        require(not set(imports).intersection(retired), 'Retired import: '+str(path))
    require(not {'Request', 'Content', 'Client', 'ClientRecord'} & ABI['records'].keys(),
            'Scene ABI still exposes native client packets')
    app = json.loads((ROOT/'abi/c-program.json').read_text())
    require('ExecAESConsole' not in app['imports'], 'Retired APP import')
    aes = json.loads((ROOT/'abi/aes-server.json').read_text())
    require('WF_EXEC_CONSOLE' not in aes['constants'], 'Retired AES field')
    provider = json.loads((directory/'c-image.json').read_text())
    require(not {'WidgetEntry', 'WidgetPacket', 'ExecAESConsole'} & provider['symbols'].keys(),
            'Emitted provider retains native widget/console policy')
    program = read_build(directory/'program')
    for routine in program['image']['routines']:
        require(not any(routine['name'].startswith('M_'+name+'_') for name in retired),
                'Emitted native client/dispatcher: '+routine['name'])
    return dict(status='pass', tier='development', qualification=False,
                source_files=len(sources), app_abi=app['version'],
                scene_layout={k: v['size'] for k, v in layout().items()},
                authoritative_windows=ABI['constants']['WINDOWS'],
                xex_sha256=sha256(program['xex']),
                provider_sha256=sha256(directory/'c-image.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.build.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('GEM policy source/provider audit passed', result['source_files'], 'files')
