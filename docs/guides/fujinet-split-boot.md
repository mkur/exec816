# Split-disk XEX boot through FujiNet

[Guides](README.md) · [OF816](boot-monitor.md) ·
[Development record](../history/fujinet-xex-boot.md)

Build the FastBasic desktop with SYS on D2:

```sh
python3 tools/build_demo.py --basic-workbench --system-drive 2 \
  --release-compiler --output build/fujinet-split/demo
```

Extract the matching `exec816-demo.zip`. Select its `altirraos-816.rom` explicitly
in Altirra's firmware settings. Standard AltirraOS XL and the dedicated 65816
ROM are separate firmware selections. Keep BASIC disabled, no cartridge,
65C816 at multiplier 8 with shadow ROMs, 64K base RAM and 63 linear high banks.
Graphical builds require VBXE and an ST mouse. See the
[platform contract](../reference/platform.md).

Use these FujiNet slots before selecting OPTION → Boot:

| Drive | File | Access |
| --- | --- | --- |
| D1 | `Exec-of816.xex` | Read-only |
| D2 | `system.atr` | Read-only |
| D8 | `work.atr` | Writable |

Hold OPTION until the XEX starts loading; releasing it when OF816 appears is
safe. CONFIG restarts the ROM itself, so a quick press can let the ROM enable
BASIC again even when Altirra's Internal BASIC setting was disabled. Keep that
setting disabled too, but do not rely on it for CONFIG's reboot.

The five-second OF816 countdown enters Exec with SYS on D2 automatically.
WORK: remains the separate D8 volume. No Forth drive override is needed in this
build. To use Forth first, interrupt the countdown and enter `EXEC816` later.
The local `launch-altirra.command` launches the XEX directly in the emulator;
the FujiNet path uses its drive-slot menu instead.

Boot loading uses `--boot-sio auto` by default: the small prefix loads at
standard speed and the remaining OF816/kernel stream uses nominal 57,600 baud
when FujiNet reports HSIO index 8. Set FujiNet's HSIO index to 8; native disk
access retains that profile. Interactive Forth gets standard-speed ROM I/O.
The reader checks the source and renegotiates when `EXEC816` returns.

For a standard-speed boot comparison or recovery image:

```sh
python3 tools/build_demo.py --output build/fujinet-split/demo \
  --refresh-boot-sio --boot-sio standard
```

Use `--boot-sio auto` to restore fast boot. This refresh preserves the frozen
canonical OF816/native image and regenerates the prefix and package. Standard
boot still establishes 57,600 baud for native storage. A boot reader error
requires reset: `$8A` timeout, `$8F` checksum, `$C8` BREAK, `$CB` failed speed
recovery, `$CC` incompatible native speed, `$CD` source changed after Forth.
The early prefix reports `$C9` for memory bounds (including BASIC enabled during
CONFIG reboot) and `$CA` for inconsistent prefix metadata. Repeat `$C9` with
OPTION held; replace the matching boot/system files for `$CA`.
See the [boot contract](../reference/boot-loading.md#boot-only-sio-reader) for
supported transport and recovery behaviour.

Keep the XEX and system disk from one package together. After replacing files
on FujiNet's SD directory, remount D1/D2 so firmware reopens them. Preserve the
user's writable work disk across system updates; its saved source and desktop
preferences belong to the user. Cold reset can return to FujiNet's configuration
menu when CONFIG boot is enabled; use OPTION → Boot there.

An XEX from the combined `exec816.atr` profile expects its writable system disk
on D1. Use the [one-disk guide](bootable-system-atr.md) for that profile. The
split build deliberately leaves FujiNet's virtual XEX disk outside Exec mounts.

Loader failures now include a hexadecimal status and current MEMLO/MEMTOP:

```text
Exec816 load failed $01 MEMLO=$0A01 MEMTOP=$BC1F
```

The line can wrap on the ROM display. `$01` means host memory bounds, `$02`
manifest mismatch, `$03` malformed staged data and `$04` incomplete loading.
These failures occur before native filesystem mounting; changing SYS selection
cannot repair a failed XEX transfer. The bounds checks remain enforced.

For `$01 MEMLO=$0700 MEMTOP=$9C1F`, repeat OPTION boot while holding OPTION
through the start of loading. This exact failure was reproduced with BASIC
mapped during CONFIG's reboot. Exec needs MEMTOP at least `$BC00`; with BASIC
disabled the tested ROM reports `$BC1F`. The lower display allocation overlaps
Exec's bank-zero Task layout, so raising MEMTOP by hand is unsafe.

The [development record](../history/fujinet-xex-boot.md) distinguishes real
FujiNet-PC/PicoBoot and CONFIG-menu tests from physical serial qualification.

Current fast-boot measurements and test scope are in the
[boot-only SIO record](../history/boot-only-fast-sio.md).
