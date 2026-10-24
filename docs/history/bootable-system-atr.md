# Bootable system ATR implementation record

[History](README.md) · [Plan](../plans/bootable-system-atr-implementation-plan.md) ·
[Boot contract](../reference/boot-loading.md#bootable-system-atr) ·
[User guide](../guides/bootable-system-atr.md)

BA0–BA4 implement one writable D1 SDFS/256 image containing the boot reader,
matching OF816/kernel XEX, system files and WORK directory. WORK: uses the
existing assign facility. This adds no resident Task, kernel operation, native
filesystem variant or firmware-I/O fallback after native handoff.

The [machine-readable development record](../development/bootable-system-atr.json)
freezes source, build, ROM/emulator, firmware binary and delivery hashes.
The native kernel and commands use the pinned optimized compiler without an
override. C applications and the renderer were reused after checking their
input and product hashes. The boot reader is emitted assembly; no compiler ABI
changed and no duplicate raw system matrix was required.

## Memory by phase

All twelve public Tasks retain their existing reservations. Fixed, root,
kernel, each public Task and idle runtime deltas are **zero bytes**, including
guards, alignment and unused capacity. Native runtime including OS remains
55,008 bytes in this build.

The loading phase grows from 40,336 to 48,528 union bytes: **8,192 extra live
bytes** at $4000–$5FFF. The arena includes 2,064 used bytes (including its two
16-byte outer guards) and 6,128 unused reserved bytes. It borrows these public
stack ranges before Task initialization:

| Public slot | Borrowed bytes | Runtime reservation delta |
| --- | ---: | ---: |
| 3 | 512 | 0 |
| 4 | 1,344 | 0 |
| 5 | 1,344 | 0 |
| 6 | 2,592 | 0 |
| 7 | 2,400 | 0 |

The first-stage 384-byte claim at $3000–$317F is already within the native
loading kernel-stack reservation, so it adds zero union bytes. Its code and
return targets retire before OF816 borrows that storage. The second stage
retires before native stack initialization. The generated layout check rejects
live overlap with OF816, staging, loader, OS or XEX destinations and retains the
existing firmware MEMLO admission bound.

## Executed development scope

Host checks cover media construction and independent read-back, short-sector
geometry, allocated protected boot files, locator/contiguity, exact large XEX
bytes, phase accounting and rejection of overlap/truncated input. The full host
suite contains 560 passing tests.

The emitted reader fixture streams a fragmented file beyond 64 KiB, with map
transitions, sector-crossing headers, repeated XEX markers and 300 INITAD
callbacks. Nine focused failures cover invalid header, missing file,
truncation, invalid sector, cyclic maps, live-reader overwrite, first-stage
guard, BREAK and transport failure. Each failure stops before native entry and
reaches the visible ROM error/park path.

Direct ROM cold boot passed the five-second OF816 countdown and native
shell/desktop save walkthrough, with no direct-XEX loading hook. The final
FujiNet-PC delivery checks cold-boot the extracted ATR through real firmware
media operations and native SIO, save source/files/preferences, and reboot the
modified disk through interactive OF816. The walkthrough exercises the WORK
assign, one physical D1 mount, HELLO and FastBasic loading, copy/CMP,
mkdir/rename/delete, boot-file protection and normal final EXIT. Native entry
compares all 1,745,390 initialized/zero-fill bytes against the emitted image;
guards and firmware context are checked across callbacks and at shutdown.

Full-disk and read-only checks replay verified pre-native snapshots with the
same kernel. They are focused native storage-failure tests, not additional
cold-boot claims. Disk-full returns 221; a real read-only FujiNet attachment
returns device error 3. The console remains usable, rejected data is absent,
read-only bytes are unchanged and final EXIT preserves guards/context.

The direct walkthrough predates the final compact error-display and on-disk
README changes. Its native XEX is identical; the final FujiNet package tests
and focused emitted reader cases cover the changed disk/reader bytes. These
are development checks, not a full hosted-system qualification matrix.

To repeat the core boot and persistence checks after building this profile:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_disk_boot_reader.py --bundle build/demo-basic-disk \
  --output build/disk-reader-check
python3 tools/test_bootable_atr.py --bundle build/demo-basic-disk \
  --fujinet-pc /path/to/fujinet
python3 tools/test_bootable_atr.py --bundle build/demo-basic-disk \
  --fujinet-pc /path/to/fujinet --restore --manual
```

Run the save and restore commands sequentially: restore deliberately reuses the
modified test ATR. `tools/test_boot_atr_storage_errors.py` selects `full` or
`readonly` with `--case`, a separate `--output` and the boot check's
`--snapshot .../before-native.altstate2`. Read-only uses `--fujinet-pc` too.
Build/test intermediates remain outside the distributed ZIP.

## Transport and delivery limits

The FujiNet-PC binary reports v1.6-808feb26f, built 24 August 2026. Its hash is
recorded separately from any local source checkout. The test starts its own
isolated config, mount and NetSIO peer; it does not alter the user's running
FujiNet instance. The raw-SIO relay observes standard-rate boot and native
profile-4 traffic and forwards actual firmware ACK/COMPLETE/data/checksums.
It pauses emulation while waiting for host responses. This proves firmware and
media integration; it does not qualify physical UART timing or real hardware.

The user ZIP contains one ATR, matching recovery XEX, pinned AltirraOS ROM,
short guide, notices and checksums. It excludes split system/work disks,
CAR/BIN images, manifests and test output. The launcher maintains a persistent
writable copy. The separate corresponding-source ZIP includes the boot sources
and has its own checksum and clean offline FastBasic/workbench rebuild result;
it is excluded from the record's self-hash chain.

Supported boot media is the packaged SDFS 2.1/256 root-file layout. Arbitrary
DOS environments, IDE power-on boot, cartridge launching, boot acceleration
and physical-hardware qualification remain outside this delivery.


## Combined distribution, BASIC preparation and cartridge return

The 2026-10-23 distribution uses one writable `exec816.atr` by default for
standalone SIO builds. ATR, external XEX and Atarimax boot share SYS and its
WORK directory. QED stays on a separate optional `qed.atr` in D2. MD5, ARC,
EDX, manuals and ARC overlays are in SYS:C; workspace fixtures are in WORK.
Explicit split disks remain a development selection.

Boot preparation turns internal BASIC off. For the pinned ROM's BASIC/cart
mode-0 allocation (`RAMTOP=$A0`, `MEMTOP=$9C1F`), it reopens E: through CIO with
RAMTOP restored to $C0. The ROM derives MEMTOP=$BC1F and screen $BC40; the
routine preserves IOCB0 and caller flags, and leaves unrelated low bounds for
normal admission to reject. An unknown mapped cartridge is not disabled.
Atarimax switches its mapper off around callbacks; its initial and subsequent
mapped reads mask IRQ/NMI, and its RAM reader retires at RUNAD.

Development checks passed: 643 host tests; emitted ROM screen/IOCB/bound probes;
cold ATR boot with BASIC initially enabled, a 250-frame OF816 countdown and
1,747,969 initialized/zero-fill native bytes verified; XEX and both Atarimax
routes with the same system image, MD5, argument-free ARC help, ARC listing,
EDX, workspace writes, guards and EXIT. The final initial cartridge masking
change also passed a focused 40-callback, bank-crossing check on both mappers.
System file operations, protected boot files and FastBasic source execution
passed from the verified native-entry snapshot. Production QED passed two
normal launches, three saves, backup rotation, reopen and ownership cleanup
from a separate disk using the same verified native-entry replay. Its observer
now searches the build's actual Task capacity, including the twelfth slot.

This is development evidence, not full release or physical timing qualification.
See the [machine-readable record](../development/combined-distribution.json).

Reserved bank-zero growth over the existing SDX-enabled profile is zero fixed,
root/kernel, per public Task and idle bytes, including guards, alignment and
unused capacity. Selecting SDX by default adds its existing 544 fixed bytes to
a previously SDX-disabled distribution, with zero per-Task/root/kernel/idle
change. The cartridge borrows 1,024 additional bytes only while loading, before
those high-RAM Task pools become live. The shared boot reader keeps its existing
8,192-byte reservation.
