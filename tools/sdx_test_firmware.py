"""Explicit ROM overrides for focused SDX tests; machine/emulator pins stay fixed."""
import copy
from pathlib import Path
from generate_sdx_firmware import ROOT, identify


def select(rom, pin):
    path = Path(rom).resolve() if rom else ROOT/'build/firmware/altirraos-816.rom'
    profile = identify(path.read_bytes())
    actual = copy.deepcopy(pin)
    actual['rom'] = dict(name=profile['name'], bytes=profile['bytes'],
                         sha256=profile['sha256'])
    return path, actual


def configure(bridge, rom):
    if identify(rom.read_bytes())['name'].startswith('xlos-'):
        bridge.config('exeloadmode', 'diskboot')
