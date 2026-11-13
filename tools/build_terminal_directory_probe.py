#!/usr/bin/env python3
"""Real shell publishers with two timer-free directory observers and UPDATE."""
import argparse
from pathlib import Path
from unittest.mock import patch
from native_program import ROOT
from library_paths import read_source
import build_gem_desktop as desktop


def build(out,probe_only=False):
    out.mkdir(parents=True,exist_ok=True)
    observers=out/'observers.inc'
    source=out/'root.act'
    control=out/'controller.inc'
    control.write_text(read_source(ROOT/'examples/shell/shell-controller.inc').replace(
        '  ShellControllerQuiesce()\n\nRETURN(controllerStatus)',
        '  directoryStopping=1\n  ShellControllerQuiesce()\n  DirectoryFinish()\n\nRETURN(controllerStatus)',1))
    text=read_source(ROOT/'examples/gem-desktop.act',includes={'shell-controller.inc':control})
    text=text.replace('USE DESKBOOT','USE DESKBOOT\nUSE AESSTATE\nUSE CONSOLEVIEW\nUSE CONSOLEVIEWTYPES AS VIEW',1)
    text=text.replace('LONGINT exitStatus',f'INCLUDE "{observers}"\n\nLONGINT exitStatus')
    text=text.replace('  IF ShellControllerStart(0)<>0 THEN','  DirectoryStart()\n  IF ShellControllerStart(0)<>0 THEN',1)
    text=text.replace('    exitStatus=ShellControllerRun()','    DirectoryPublishers()\n    exitStatus=ShellControllerRun()',1)
    if probe_only:text=text.replace('    DirectoryPublishers()','    DirectoryPublishers()\n    ShellControllerCloseAll()',1)
    source.write_text(text)
    original=desktop.drawing
    def drawing(*args,**kwargs):
        kwargs['client_sources']=[*kwargs['client_sources'],ROOT/'tests/programs/directory_update.c']
        kwargs['client_roots']=[*kwargs['client_roots'],'DirectoryUpdate']
        foreign=original(*args,**kwargs)
        observers.write_text((ROOT/'tests/programs/directory_observers.inc').read_text().replace(
            '$DIRECTORYUPDATE',f"${foreign['symbols']['DirectoryUpdate']:x}"))
        return foreign
    with patch.object(desktop,'drawing',drawing):
        return desktop.build_desktop(out,source=source,task_capacity=12,release_compiler=True,stack_checks=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--probe-only',action='store_true')
    args=a.parse_args();build(args.output.resolve(),args.probe_only)
