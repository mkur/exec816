# IDE Plus development setup

[Guide index](README.md) · [Device contract](../reference/ideplus-device.md)

This optional profile adds IDE: alongside the ordinary SIO SYS:/WORK: and RAM:.
The initial target is IDE Plus 2.0 revision E, PBI ID 0, one ATA master using
512-byte sectors and LBA28. Use the [pinned platform](../reference/platform.md)
and 4 MiB linear RAM. Physical Antonia/IDE Plus hardware remains unqualified.

## Build and attach

From the repository root:

```sh
python3 tools/build_demo.py --output build/development/ideplus-demo \
  --text-shell-only --ideplus --release-compiler
```

This uses the pinned compiler, includes OF816 and keeps its five-second autoboot.
`exec816-demo.zip` contains boot files, matching system/work disks, the pinned
AltirraOS816 ROM, short guide, licences and checksums. The builder stops before
packaging if the compressed boot image exceeds cartridge capacity.

For local use, run the generated `launch-altirra.command` beside the ZIP.
It copies your saved AltirraSDL configuration and attaches the correct media
automatically; see the [local launcher instructions](demo.md#install-and-boot).
The script and private settings stay outside the release package.

The separate `ideplus/` directory contains `ideplus.img`, its checksummed fixture
record and `mounts.json`. The disposable raw disk wraps the matching system disk
as APT unit 2 using independently formatted 512-byte SDFS sectors. The
SIO system/work disks retain their floppy geometry. Changing an old partition
flag does not convert its filesystem; keep old writable images separately.
IDE: is read-only both in the APT flags and the Exec mount policy. It is not a
boot drive. These development files and IDE firmware stay outside the boot ZIP.

In Altirra, add IDE Plus 2.0, select revision E and PBI ID 0, disable SDX and
attach `ideplus.img` as its master raw hard disk. Attach `system.atr` to D1 and
`work.atr` to D8. Boot `of816/Exec-of816.xex`, or make matching carts with
`tools/build_cartridge.py`. The IDE profile requires this attachment: initial
configured mounts are admitted together, so an absent IDE unit fails startup.
Ordinary demo builds without `--ideplus` keep their existing SIO defaults.

Try:

```text
DEVICES
MOUNT
DIR IDE:
CAT IDE:STORY.TXT
IDE:C/HELLO
COPY IDE:LONG.TXT WORK:FROMIDE.TXT
```

## Firmware fixture

Development checks pin BIOS 2.1 rev E and the exact emulator/device/ROM inputs in
[altirra-ideplus.json](../../toolchain/altirra-ideplus.json). Download the
[vendor BIOS archive](https://drac030.krap.pl/ideplus-bios-20251231.arc), extract
BIOS21.COM, then recreate the emulator ROM without flashing a physical board:

```sh
python3 tools/prepare_ideplus_firmware.py /path/to/BIOS21.COM \
  --output build/firmware/ideplus-bios-2.1.rom
```

The converter checks both source and output hashes. The driver uses native ATA,
not a BIOS entry point. No firmware modification or OS SIO replacement is needed.

## Writable media

Use a separate disposable APT disk and change both its partition flags and the
configured mount to permit writes. A source mount selects, for example:

```json
{
  "alias": "IDE",
  "device": "ideplus.device",
  "unit": 2,
  "profile": 0,
  "sectors": 1440,
  "sector_bytes": 512,
  "format": 2,
  "access": "readwrite"
}
```

Geometry must match exactly. IDE requires format 2 (SDFS 2.1), uniform
512-byte sectors and profile 0; MyDOS on IDE is unsupported. Units
1–15 follow APT mapping slots directly. Raw unit 0 is unsupported for filesystem
mounts. SYS may select a fixed IDE mount; SIO drive overrides do not apply.
Writable admission also requires the board
protection switch to allow it and IDENTIFY to report a supported durability
policy. Successful writes preserve neighbours and complete ATA status checks
and any required cache flush before replying, without automatic readback.
Cache-free media has emulator coverage; successful FLUSH on cached
physical devices still needs hardware evidence.

A timeout or uncertain accepted write leaves IDE offline until cold reset.
Closing/reopening or remounting cannot reset it. SIO and RAM remain independent.
There is no automatic retry, software reset, hot-removal handling or partition
editor. See the device contract for cancellation, ownership and further limits.

## IDE-only SYS and WORK demo

Build the separate standard-console profile with:

```sh
python3 tools/build_demo.py --ide-only --text-shell-only --release-compiler \
  --output build/development/ide-only/demo
```

`--ide-only` excludes Exec's SIO driver and cannot be combined with `--ideplus`.
Select `--text-shell-only` for the standard console or `--bitmap-shell-only`
for the 80 by 30 VBXE console. Both IDE-only variants include the raw disk,
OF816 XEX and old/new Atarimax cartridge images. The VBXE variant requires a
full FX core with private 512 KiB VRAM, as described in the
[bitmap setup guide](../bitmap-shell-distribution.txt). Both ZIPs also include
the pinned OS ROM, guide, notices and checksums.
Attach the raw image as a writable ATA master; leave every floppy slot empty.
SYSTEM/SYS is protected APT unit 1; WORK is writable unit 2. Each has 1,440
512-byte logical sectors. Copy the image before writes. SYS contains the exact
external executable as EXEC816.XEX, C commands and S startup scripts.

OF816 retains its five-second autoboot. SYSTEM-DRIVE@ is zero and overrides are
rejected; cache and verbosity settings still work. DEVICES omits sio.device.
The [development record](../history/ide-only-demo.md) distinguishes cartridge
and actual firmware-loader coverage; neither establishes physical qualification.
Native 512-byte APT partitions are visible to the pinned BIOS loader. The
[512-byte development record](../history/ide-512-sector-refactor.md) records
actual executable-load/handoff coverage separately from directory visibility.
The pinned BIOS 2.1 menu loader can launch SYS:EXEC816.XEX: hold START during
reset, select **B**, boot drive **1**, Return, then **L**. Select EXEC816.XEX
with the Atari cursor keys and press Return. Release Return promptly so its
repeat does not cancel OF816's five-second countdown. The real menu route,
OF816 INITAD pause/resume and IDE-only shell have development emulator coverage.
Automatic power-on disk boot remains outside this profile.

Focused development checks (not release qualification):

```sh
python3 tools/test_ide_only_demo.py --full
python3 tools/test_ide_only_demo.py --copy-break
python3 tools/test_ide_only_demo.py --variant old
python3 tools/test_ide_only_failure.py
python3 tools/test_ide_only_firmware.py
python3 tools/test_ide_mixed_demo.py --bundle build/development/ideplus-demo \
  --output build/development/ideplus-demo-smoke
```

The firmware runner uses the real BIOS menu rather than a direct XEX hook.
The failure runner rebuilds its own optimized fixture; `--reuse` selects its existing matching build.
