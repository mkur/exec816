"""Native diagnostic text, real ATA mount failures and causal IoErr preservation."""
import argparse
import json
from pathlib import Path

from generate_memory import PROFILE
from native_program import ROOT, build, compiler, execute, read_build, require, sha256
from generate_dos_mounts import encode
from ideplus_media import filesystem_fixture, sdfs_image
from filesystem_audit import Audit
from test_ideplus import ide_emulator
from test_cooperative import data
from test_heap_api import clean_ownership


def run(out, reuse=False, boot_order=False):
    out.mkdir(parents=True, exist_ok=True)
    atr = sdfs_image(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr', out/'stage.atr')
    mounts = [dict(alias='IDE', device='ideplus.device', unit=2, profile=0,
                   format=2, sectors=Audit(atr).image.count, sector_bytes=512),
              dict(alias='RAM', format=3)]
    source = ROOT/'examples/shell/shell-session.inc'
    text = source.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE SHELLDIAGPROBE\n', 1)
    for path in (ROOT/'examples/shell').glob('*.inc'):
        text = text.replace('"'+path.name+'"', '"'+str(path)+'"')
    hook = '  LET written=DOS.Write(handle,bytes,count)'
    require(text.count(hook) == 1, 'Stale diagnostic output observation hook')
    text = text.replace(hook, '  SHELLDIAGPROBE.Capture(bytes,count)\n'+hook, 1)
    (out/'shell-observed.inc').write_text(text)
    (out/'shelldiagprobe.act').write_text('''MODULE SHELLDIAGPROBE
USE HEAPCORE
USE DOSCORE
PUBLIC BYTE ARRAY writes(8192)
PUBLIC CARD used
PUBLIC BYTE watchBoot,seenIde,seenMount
PUBLIC PROC Capture(BYTE POINTER bytes CARD count)
  CARD index

  LET registry=DOSCORE.GetRegistry()
  IF watchBoot<>0 AND count>=8 THEN
    IF bytes(0)=73 AND bytes(1)=68 AND bytes(2)=69 AND bytes(4)=67 THEN
      IF registry.state<>0 THEN
        HEAPCORE.Abort($ff02)
      FI

      seenIde=1
    ELSEIF count>=12 AND bytes(0)=70 AND bytes(1)=105 AND bytes(2)=108
        AND bytes(10)=115 AND bytes(11)=58 THEN
      IF seenIde=0 OR registry.state<>0 THEN
        HEAPCORE.Abort($ff03)
      FI

      seenMount=1
    FI
  FI

  IF count>8192-used THEN
    HEAPCORE.Abort($ff01)
  FI

  IF count<>0 THEN
    FOR index=0 TO count-1 DO
      writes(used+index)=bytes(index)
    OD
  FI

  used==+count

RETURN
ENDMODULE
''')
    original = ROOT/'tests/programs/ide_diagnostics_shell.act'
    test_source = out/original.name
    test_source.write_text(original.read_text()
        .replace('../../examples/shell/shell-session.inc', 'shell-observed.inc')
        .replace('../../examples/shell/shell-boot.inc', str(ROOT/'examples/shell/shell-boot.inc')))
    profile = out/'profile.json'
    memory = json.loads(PROFILE.read_text()); memory['image_data_bytes'] = 16384
    profile.write_text(json.dumps(memory))
    p = read_build(out) if reuse else build(compiler(ROOT/'build/actionc', release=True),
        test_source, out, optimize=True, tasks=True, task_capacity=8,
        console=True, memory_profile=profile, dos_mounts=mounts,
        system_mount='IDE' if boot_order else None)
    cases = [('valid', 0, []), ('no-controller', -1, ['controller absent', 'IDE CTRL      =NOT DETECTED'])] if boot_order else [
            ('count', -4, ['sector count mismatch', 'expected 1999 x 512B', 'actual   2000 x 512B']),
            ('protected', 4, ['partition/board protected']),
            ('empty-slot', -1, ['empty APT slot']),
            ('bad-apt', -1, ['unsupported APT revision', 'IDE FAULT LBA =0', 'APT STATUS    =FAILED']),
            ('no-controller', -1, ['controller absent', 'IDE CTRL      =NOT DETECTED'])]
    for name, error, expected in cases:
        dest = out/name; dest.mkdir(exist_ok=True)
        raw, _ = filesystem_fixture(atr)
        configured = [dict(m) for m in mounts]
        if name == 'count': configured[0]['sectors'] -= 1
        if name == 'protected': configured[0]['access'] = 'readwrite'
        if name == 'empty-slot': configured[0]['unit'] = 1
        if name == 'bad-apt': raw[0] = 0x20
        disk = dest/'ide.img'; disk.write_bytes(raw)
        with ide_emulator(dest, disk, absent=name == 'no-controller') as b:
            def before(b):
                b.memload(p['build']['task_storage']['BASE']+0x900, encode(configured))
                address = next(d['address'] for d in p['image']['data']
                               if '_IDEDIAGNOSTICSSHELL_EXPECTEDERROR_' in d['name'])
                b.memload(address, error.to_bytes(4, 'little', signed=error < 0))
                address = next(d['address'] for d in p['image']['data']
                               if '_IDEDIAGNOSTICSSHELL_BOOTMODE_' in d['name'])
                b.memload(address, bytes([boot_order]))
            runtime, _ = execute(b, p, before_run=before, timeout=90, frame_limit=4500,
                                 boot_verbose=boot_order)
            clean_ownership(b, p, out)
            used_address = next(d['address'] for d in p['image']['data'] if '_SHELLDIAGPROBE_USED_' in d['name'])
            count = int.from_bytes(b.memdump(used_address, 2), 'little')
            address = next(d['address'] for d in p['image']['data'] if '_SHELLDIAGPROBE_WRITES_' in d['name'])
            transcript = b.memdump(address, count).decode('ascii')
            checks = data(b, p['image'], 'checks', True)
        if boot_order:
            require(transcript.index('IDE CTRL      =') < transcript.index('Filesystems: mounting...'),
                    'Hardware diagnostics followed the mount announcement')
            terminal = 'SYS: -> IDE Plus unit 2: ready' if name == 'valid' else 'MOUNT FAILED  =IDE:'
            require(transcript.index('Filesystems: mounting...') < transcript.index(terminal),
                    'Filesystem outcome preceded the mount announcement')
        for line in ([] if error == 0 else ['MOUNT FAILED  =IDE:']) + expected:
            require(line in transcript, f'{name}: missing {line!r}: {transcript}')
        diagnostic = (transcript[transcript.index('IDE CTRL      ='):transcript.index('Filesystems: mounting...')]
                      if boot_order else transcript)
        require(all(len(line) <= 40 for line in diagnostic.splitlines()), 'Diagnostic line exceeds 40 columns')
        require(disk.read_bytes() == raw, 'Reporting changed disk')
        (dest/'transcript.txt').write_text(transcript)
        (dest/'results.json').write_text(json.dumps(dict(status='pass', tier='development',
            build=p['build'], runtime=runtime, checks=checks, observation_sha256=sha256(out/'shell-observed.inc')),
            indent=2)+'\n')
        print('Native IDE diagnostic report passed', name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/ide-diagnostics/shell')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--boot-order', action='store_true', help='Check actual boot ordering before filesystem startup')
    args = parser.parse_args()
    run(args.output, args.reuse, args.boot_order)
