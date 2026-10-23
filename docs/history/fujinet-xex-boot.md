# FujiNet split XEX boot

[History](README.md) · [Guide](../guides/fujinet-split-boot.md) ·
[Boot contract](../reference/boot-loading.md)

The reported setup had a D1 XEX from the one-disk build beside the earlier D2
system and D8 work disks. That XEX defaulted to a writable 8,192-sector SYS on
D1. It did not match the separate read-only 2,880-sector system image. The
saved active emulator profile also selected built-in XL firmware (ID 3), while
the supported pin selects the dedicated external 65816 ROM. Neither observation
identifies the cause of the original generic `Exec816 load failed` message:
that message did not expose the loader's rejection status.

The split builder now accepts `--system-drive 2`, builds the configured D2 mount
and matching boot default together, and packages a D1-XEX/D2-SYS/D8-WORK guide.
It retains the current Task/driver/filesystem implementation. Existing standard
D1 and bootable-ATR defaults stay distinct. This delivery uses the graphical
FastBasic profile, with its persistent interpreter and existing commands.

Loader errors now print the hexadecimal status and current MEMLO/MEMTOP.
Admission still requires the existing memory bounds and exact manifest.
The [machine-readable evidence](../development/fujinet-xex-boot.json) records
the actual build, source, ROM/emulator, firmware and artifact hashes.

## Development execution

An initial independent probe reconstructed FujiNet's PicoBoot virtual disk and
reached the first INITAD and OF816. A real FujiNet-PC probe then streamed the
complete existing XEX into native memory. These separate early-loader and
transport faults from native volume mounting; they are not an explanation of
the user's earlier unnumbered failure.

The matching split package was extracted and cold-booted through real
FujiNet-PC's PicoBoot/XEX media handler. The native mount table contains D2,
RAM and WORK on D8. Physical desktop/shell input loads HELLO and FastBasic,
saves BASIC source and text to D8, runs the saved source and saves desktop
preferences. The system ATR and boot XEX stay byte-exact. Normal final EXIT
checks native guards, context and settled ownership.

The persisted work disk is then rebooted through the actual CONFIG client:
the test starts with CONFIG enabled, waits for the drive-slot menu and presses
the physical OPTION console switch. CONFIG's control requests, mounted XEX
reads, native D2 reads and native D8 reads/writes go through the real firmware.
The reboot loads saved desktop preferences, runs the saved BASIC source,
reads the saved text and exits normally. The test compares all expanded native
initialized and zero-fill bytes before entry and preserves firmware vectors,
IOCBs and OF816 guards through the handoff.

Three small emitted rejection cases force excessive MEMLO, inadequate MEMTOP
and a changed manifest. They check the status, rendered hexadecimal bounds,
unchanged firmware bounds and stopped loading. The full host suite contains
561 passing tests, including a non-D1 packaged-guide regression. No compiler
ABI changed: routine native builds are optimized; the diagnostic is assembly.

## Resource accounting and limits

The loader adds 96 used code/text bytes inside its existing 4,608-byte arena.
Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 for each of the
twelve public Tasks, and 0 idle bytes**, including guards, alignment and unused
capacity. Loading and native runtime reservation unions remain unchanged.
PicoBoot and its sector buffer use the existing low OS/binary-loader range.
No additional resident Task or ROM-SIO fallback enters native Exec.

The functional relay handles single-density CONFIG media, double-density XEX
and split ATRs, actual control replies and writes, and the target's observed
serial bit period. CONFIG's optional initial STATUS-poll delay is disabled in
the isolated test config. Host waits pause emulation; this is firmware/media
integration evidence, not physical UART timing or hardware qualification.

The current matching files were copied to the user's FujiNet SD directory.
The existing work disk was byte-identical to the package's baseline and was
left in place. No running user process, firmware config or emulator settings
were changed. Original generic failures outside the tested pin still need the
new diagnostic rather than an inferred cause.

Repeat the checks with:

```sh
python3 tools/test_xex_loader_errors.py --output build/fujinet-errors
python3 tools/test_fujinet_xex.py --bundle build/fujinet-split/demo \
  --output build/fujinet-split/cold --fujinet-pc /path/to/fujinet
python3 tools/test_fujinet_xex.py --bundle build/fujinet-split/demo \
  --output build/fujinet-split/cold --fujinet-pc /path/to/fujinet --restore --menu
```

Run those boot commands sequentially: the second deliberately retains the
modified WORK disk. Development results and corresponding-source rebuilds stay
outside the user boot ZIP.

## Follow-up: low MEMTOP during CONFIG reboot

The later screenshot identifies `$01 MEMLO=$0700 MEMTOP=$9C1F`, a bounds
rejection before OF816. A focused development probe reproduced those exact
values with the pinned 65816 ROM and real FujiNet-PC CONFIG: releasing OPTION
quickly allows the ROM to map BASIC during CONFIG's own restart. This occurs
even with Altirra's BASIC setting disabled: the initial CONFIG boot had
RAMTOP/RAMSIZ `$C0`, BASICF `$02` and PORTB `$FF`, but the XEX's first INIT
received `$A0`, `$00` and `$FD`, respectively, and MEMTOP `$9C1F`.

Holding OPTION through the first XEX INIT retained RAMTOP/RAMSIZ `$C0`,
BASICF `$02`, PORTB `$FF` and MEMTOP `$BC1F`. Loader setup succeeded and
OF816 reached its autoboot countdown with intact guards. These focused
results are in `build/fujinet-memtop/`; they cover the boot admission and
OF816 handoff, rather than repeating the earlier native desktop walkthrough.
The CONFIG boot driver now releases OPTION at the first INIT breakpoint
instead of after a fixed host delay. The user guide recommends holding it
until OF816 appears.

No platform code or memory admission rule changed. Reserved bank-zero deltas
are **0 fixed, 0 root, 0 kernel, 0 per public Task and 0 idle bytes**, including
guards, alignment and unused capacity. The earlier machine-readable record
retains its original evidence; it predates this diagnostic screenshot.
