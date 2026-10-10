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

The separate `ideplus/` directory contains `ideplus.img`, its checksummed fixture
record and `mounts.json`. The disposable raw disk wraps the matching system disk
as APT unit 2, packing two 256-byte containers into each physical sector and
preserving boot tails. With 128-byte filesystem sectors, each container uses
every other byte.
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
  "sectors": 2880,
  "sector_bytes": 256,
  "format": 2,
  "access": "readwrite"
}
```

Geometry must match exactly; format 1 is MyDOS and format 2 is SpartaDOS. Units
1–15 follow APT mapping slots directly. Raw unit 0 is unsupported for filesystem
mounts. SYS may select a fixed IDE mount; SIO drive overrides do not apply.
Writable admission also requires the board
protection switch to allow it and IDENTIFY to report a supported durability
policy. Successful writes preserve neighbours and complete verification before
replying. Cache-free media has emulator coverage; successful FLUSH on cached
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
The ZIP includes `ideplus.img`, the external combined OF816/kernel XEX, both
Atarimax cartridge variants, pinned OS ROM, guide, notices and checksums.
Attach the raw image as a writable ATA master; leave every floppy slot empty.
SYSTEM/SYS is protected APT unit 1; WORK is writable unit 2. Each has 2,880
256-byte logical sectors. Copy the image before writes. SYS contains the exact
external executable as EXEC816.XEX, C commands and S startup scripts.

OF816 retains its five-second autoboot. SYSTEM-DRIVE@ is zero and overrides are
rejected; cache and verbosity settings still work. DEVICES omits sio.device.
The [development record](../history/ide-only-demo.md) distinguishes cartridge
and actual firmware-loader coverage; neither establishes physical qualification.
