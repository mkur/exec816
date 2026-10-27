# Build from source

[Contributor guide](README.md)

Building from source is optional. To run the prebuilt distribution, follow the
[ZIP installation guide](../../README.md#installation).

Run commands from the repository root. The hosted build uses Python 3, Rust/Cargo,
ca65/ld65 from cc65, and a shared liblz4 library for HC12 boot compression.
The builder discovers liblz4 through the system library search or the installed
`lz4` executable's library directory. Set `EXEC816_LZ4_LIBRARY` to its full path
when automatic discovery is unavailable. Build reports record its version.
The build also needs the pinned AltirraSDL bridge and 65816 ROM;
the demo builder verifies their hashes before compiling.

## Pinned inputs

| Input | Source of truth | Default local path |
| --- | --- | --- |
| Action! compiler and native ABI | [actionc.json](../../toolchain/actionc.json) | `build/actionc` |
| Demo emulator and ROM | [altirra-shell-paced.json](../../toolchain/altirra-shell-paced.json) | `build/shell-paced-bridge/AltirraBridgeServer`, `build/firmware/altirraos-816.rom` |
| SDFS producer | [sdfs_reference.py](../../tools/sdfs_reference.py), [adapter](../../tools/sdfs_reference.cpp) | `build/altirra-irq-fix`, portable `build/latency` libraries |
| OF816 | [of816.json](../../toolchain/of816.json) | `build/of816-upstream` |
| Kernel defaults | [kernel.json](../../config/kernel.json) | repository file |
| Default demo mounts | [shell-sdfs.json](../../config/shell-sdfs.json) | repository file |

Prepare the compiler checkout at the recorded revision:

```sh
git clone https://github.com/mkur/actionc.git build/actionc
actionc_revision=$(python3 -c 'import json; print(json.load(open("toolchain/actionc.json"))["revision"])')
git -C build/actionc fetch origin "$actionc_revision"
git -C build/actionc checkout --detach "$actionc_revision"
```

For an existing checkout, fetch the recorded revision before checking it out.
The current pin is available directly from upstream; no local bundle is needed.
The builders compile the compiler as needed. Use the exact bridge and ROM from
the platform pin; an arbitrary installed AltirraSDL build does not satisfy that
input check. The emulator is [AltirraSDL](https://github.com/ilmenit/AltirraSDL);
upstream Altirra will not run the current Exec816 build.
See the [platform contract](../reference/platform.md) for the
machine boundary and the pin's provenance for platform inputs.

SDFS media creation also needs the pinned AltirraSDL source tree at
`build/altirra-irq-fix`, with its portable latency build prepared. The independent
producer checks the two SDFS source hashes in `tools/sdfs_reference.py` and links
`ATIO`, `ATCore` and `system` archives under `build/latency/src/`. Build those
libraries using the pinned emulator's configuration before making SDFS media.
Prepare the small host producer once before concurrent builds:

```sh
python3 -c 'import sys; sys.path.insert(0,"tools"); import sdfs_reference; print(sdfs_reference.reference())'
```

The media verification report records the producer hash. Clean-checkout QED
reproduction may share these verified tool/source caches; it must not import a
previous QED APP, provider or disk. See the [QED build guide](../guides/qed-exec.md).

The OF816 pin also records `build_timestamp`, the pinned upstream commit's
Unix timestamp. Preparation replaces its informational `.time` literal before
assembly, preserving the upstream checkout. `.VERSION` therefore identifies
that fixed input rather than the host wall clock. Native/media/monitor builds
can be reproduced across different assembly times and checkout paths.

## Build the demo

The 0.2.3 release package contains the GEM desktop, windowed Shell and FastBasic
workbench. QED is supplied separately:

```sh
python3 tools/build_demo.py --basic-workbench --release-compiler --output build/demo
```

The build always includes OF816 and produces `build/demo/exec816-demo.zip` with
the boot XEX, system disk and matching ROM. It fetches the pinned OF816 checkout
if absent. Build reports and intermediate files remain outside the ZIP.
The release version comes from [VERSION](../../VERSION); the Shell banner and
`VER` retain the exact source commit as well. `--release-compiler` selects the
optimized host compiler; target code is optimized in every demo build.
On a clean checkout tagged exactly `v<VERSION>`, the startup banner and `VER`
show that release tag. Other builds show their commit and clean/dirty status;
the full source revision remains in the build record.
See the [GEM desktop guide](../gem-desktop-distribution.txt) for machine setup and
desktop controls, the [console demo guide](../guides/demo.md) for other source-build profiles,
and the [boot monitor guide](../guides/boot-monitor.md) for
repackaging an existing image.

For a single writable disk that boots through ROM sector reads, add
`--bootable-atr`. It retains OF816 and packages SYS and WORK on D1. The
[bootable ATR guide](../guides/bootable-system-atr.md) covers the graphical
FastBasic build, disk-only refresh and persistent launcher copy.

For FujiNet's separate XEX/system/work disks, add `--system-drive 2` instead.
Mount the XEX on D1, the system disk on D2 and writable WORK on D8. See the
[split-disk guide](../guides/fujinet-split-boot.md), including firmware selection
and CONFIG's OPTION → Boot path.

For a full-screen standard text shell without starting the prime task, use:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/build_demo.py --text-shell-only --output build/demo-text-shell
```

This starts the same standalone shell as the bitmap selection, using the
40 by 24 Atari text display. PRIMES remains available as a command; `RUN PRIMES`
opens its lower pane on demand. Fixed and per-Task bank-zero reservations are
unchanged. See the [text shell package guide](../text-shell-distribution.txt).

For a full-screen bitmap shell without the prime task, use a fresh output
directory and the shell-only boot selection:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/build_demo.py --bitmap-shell-only --output build/demo-bitmap-shell
```

This keeps OF816's five-second autoboot and packages the matching disk, ROM
and GEM notices. See the [bitmap shell package guide](../bitmap-shell-distribution.txt)
for VBXE configuration and commands. Reserved bank-zero memory is unchanged,
both fixed and per Task; the prime Task is never started.

Standalone text and bitmap/desktop SIO distributions include MD5, ARC and EDX
by default. Prepare their pinned original binaries first, using a built
`nomarch` extractor:

```sh
python3 tools/prepare_sdx_inputs.py --nomarch /path/to/nomarch
python3 tools/build_demo.py --release-compiler --output build/demo-sdx
```

The system disk contains the COM files, manuals and ARC overlays in SYS:C,
with small checksum/archive/editor fixtures in WORK. No utility disk is needed.
Add `--gem-desktop` for the graphical desktop; both retain OF816's five-second
countdown. Guest A: uses WORK: and CAR: uses SYS:C/ independently of native CD.
Those roots can be changed explicitly with the development `--sdx-drive-a` and
`--sdx-car-root` options. `--no-sdx` omits this personality from a development
build; FastBasic requires it.

The [SDX service contract](../reference/sdx-services.md) lists supported operations.
The profile reserves 12 KiB of upper static storage and the existing 544 fixed
bank-zero bytes, including DP alignment and outer guards; per-Task growth is zero.


To refresh OF816 assembly, boot guides and the ZIP around an existing matching
native build, use:

```sh
python3 tools/build_demo.py --refresh-monitor --output build/demo-bitmap-shell
```

This verifies the existing native artifacts and records their reuse without
recompiling them. The native build must already contain the current loader's
progress callbacks; rebuild it first when the loader or kernel changes. OF816
runs from INITAD before the main payload, then returns to the reader with RTS.
The XEX and cartridge routes retain their guarded final kernel entry.

To rebuild the bootstrap and compression transport around an existing verified
native demo without recompiling the kernel, use:

```sh
python3 tools/build_demo.py --refresh-loader --output build/demo-bitmap-shell
```

This verifies the existing native artifacts and requires an unchanged runtime
memory ABI. It preserves the native image and compiler revision, regenerates
loading definitions, repackages compressed records, then refreshes OF816 and the
distribution ZIP. Rebuild the whole demo for kernel/runtime ABI changes.
See the [boot-loading contract](../reference/boot-loading.md) for encoding,
context and memory limits.

Standalone SIO distributions default to one writable `exec816.atr`, including
OF816, Exec, system applications, MD5/ARC/EDX and WORK. ATR, external XEX and
Atarimax CAR boot share that same disk. QED remains on an optional separate
`qed.atr` outside the demo ZIP; add `--qed` to build that disk locally. For example:

```sh
python3 tools/build_demo.py --basic-workbench --qed --release-compiler \
  --output build/system-distribution
```

Use `launch-altirra.command` for ATR boot, `launch-xex.command` for XEX, or
`launch-cart-new.command` / `launch-cart-old.command` for Atarimax. All retain
one private writable system disk. ATR launch selects read-write disk loading;
XEX launch selects executable loading. The cartridge reader keeps its mapper and
low OS screen through INITAD, then disables it and reopens E: before final
native admission and high-RAM pool initialization. Boot transport
disables BASIC before native admission; arbitrary mapped cartridges remain
unsupported. `--split-disks` selects separate SYS/WORK development media.
Distribute `exec816-demo.zip` with boot media, ROM, guide, notices and checksums.

## Firmware diagnostics

AltirraOS 3.44/65816 remains the bundled platform ROM. The current SDX adapter
also identifies the exact stock **XLOS816F 2.48 and 2.49** images in the
[firmware catalog](../../platform/altirraos/sdx-firmware.json). The
[adapter contract](../reference/sdx-firmware.md) defines identification, original
vector chaining, stack limits and unsupported extensions. Supply your own XLOS
ROM; it is neither embedded nor redistributed. Other images continue as
`XLOS (assumed)` and report their actual CRC/vectors. Firmware and stack
qualification remains specific to the recorded images. The host classifier
uses the same visible ranges as runtime and records the actual full-file SHA-256
separately, including a difference confined to the hidden self-test slot.

Validate a local image and boot the current combined-ATR demo with it:

```sh
python3 tools/generate_sdx_firmware.py --check --rom path/to/XLOS816F.ROM
build/system-distribution/launch-altirra.command --rom path/to/XLOS816F.ROM
```

The launcher selects that ROM in its private settings and reuses the private
writable D1 image. SIO, FP and fast-boot patches are disabled; external XEX
loading with a ROM override uses Disk Boot, so stock XLOS needs no loader hook.
For an automated boot/tool check:

```sh
python3 tools/test_sdx_firmware_demo.py --bundle build/system-distribution \
  --rom path/to/XLOS816F.ROM --output build/xlos-atr --route atr
```

For the early identity/ROM output, mapping/state failure and first-cause cases:

```sh
python3 tools/test_rom_diagnostics.py --output build/rom-diagnostics
python3 tools/test_rom_diagnostics_demo.py --bundle build/system-distribution \
  --rom path/to/XLOS816F.ROM --route atr --output build/rom-diagnostics-atr
```

The second runner verifies extracted ZIP checksums, captured startup screen text,
matching `VER`, MD5, ARC help/listing, writable WORK, guards and EXIT. Select
`--route cart` for the new Atarimax image, or `--route xex` with AltirraOS.
Use `--assume-xlos` to mismatch only the private comparison catalog and exercise
the fallback with the original ROM and unmodified packaged boot files.
All routes use the same writable combined disk on D1 and retain OF816's
five-second countdown. The runner records
the actual ROM hash, tool commands, WORK write/read, guards and native cleanup.
Selected application and resident-stack runners also accept `--rom`; all keep
their pinned emulator/machine settings. See the
[implementation evidence](../history/xlos-sdx-support.md) for executed cases.
Development checks do not qualify physical accelerator/FujiNet hardware or all
XLOS services.

Altirra's default XEX loader fails before Exec's INITAD under XLOS, including
for a minimal executable with no Exec code. Standalone XEX fixtures select
**Computer → Boot → Program load mode: Disk Boot**. That loader borrows D1,
so fixture data disks use another physical unit. Prefer actual ATR or cartridge
boot for the distribution. The older split-D2/D8 experiment and cartridge
interlock diagnosis remain in the [historical boot record](../development/xlos-boot.json);
they do not define the current single-disk layout. Released v0.2.1 still has the
old AltirraOS-only admission described by the [original audit](../history/xlos-sdx-audit.md).

## Build an individual program

For a resident Task example with console support:

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console --task-capacity 8 --source examples/tasks.act --output build/tasks
```

For a disk-loaded command:

```sh
python3 tools/build_command.py examples/commands/hello.act -o build/commands/HELLO
```

The command build produces an o65 file; it does not install it on a disk image.
See [writing commands](../guides/commands.md). The [C guide](../guides/calypsi-c.md)
has the separate Calypsi prerequisites and build command.

## Reading build results

Use each build's `build.json`, `memory.json` and image/compiler reports to inspect
resolved settings, occupied banks and reservations. The [Task-capacity note](../architecture/task-capacity.md)
explains why payload size and reserved bank-zero size are different quantities.
Record local toolchain overrides with results; they do not change the repository
pin or qualify the pinned system. Choose checks using the
[testing policy](testing.md).

## Mouse development observer

The `mouse_input.tooling` section of
[altirra-gem-vdi.json](../../toolchain/altirra-gem-vdi.json) pins a separate
headless bridge for physical ST mouse tests. Apply its additive
[observer patch](../../toolchain/patches/altirra-mouse-observer.patch) after the
existing console, keyboard and frame-pacing patches, build the recorded target,
and copy the binary to `build/mouse-bridge/AltirraBridgeServer`. Put the matching
Python SDK at `build/mouse-bridge/sdk/python`. Keep the earlier baseline binaries
at their recorded paths for historical replay.

`MOUSE ST` enables the built-in `Mouse -> ST Mouse (port 1)` preset and removes
other input maps in the test's temporary profile. `MOUSE AT delay dx dy left`
schedules relative host movement and an optional left-button change on the
base-cycle scheduler; `left` is -1 for unchanged, 0 for released, or 1 for pressed.
The existing controller still schedules its electrical phases in scanline units.
`MOUSE CLEAR` cancels queued host stimuli and releases the left button; disconnect
does the same. Tests do not read or change the user's GUI profile.

Set `EXEC816_MOUSE_TRACE=1` to record host delivery and passive controller output
on the same base-cycle clock. Leave it unset for unobserved replay. This hook
does not replace the ST controller, its mapping, or its phase scheduling.

```sh
python3 tools/test_mouse_observe.py --mode opt --output build/gem-mouse/m0/opt
python3 tools/test_mouse_observe.py --mode opt --replay --output build/gem-mouse/m0/replay
python3 tools/test_mouse_baseline.py --mode opt --case keyboard --output build/gem-mouse/m0/keyboard
```

### Desktop preview

Build the optional framed shell and independent graphical client (no primes):

```sh
python3 tools/build_demo.py --desktop --output build/desktop/preview
python3 tools/test_demo.py --bundle build/desktop/preview --boot-smoke
```

The standard command without `--desktop` retains the five-second OF816 boot
into the shell/prime demo. Both selections include OF816, the matching system
ATR, pinned AltirraOS ROM, notices and checksums. Distribute only the generated
`exec816-demo.zip`; development manifests, images and traces stay outside it.
The [desktop guide](../desktop-distribution.txt) specifies ST mouse/port 1 and
records the outstanding interaction timing limits. This builds a local preview;
it does not publish a GitHub release.

For SIO boot images, `--boot-sio auto` selects the shared boot-only 57,600 baud
reader. `--boot-sio standard` retains standard-speed bulk loading for recovery
and matched measurements; native storage keeps its configured profile. To
change this policy around verified, frozen OF816/native bytes, use:

```sh
python3 tools/build_demo.py --output build/fujinet-split/demo \
  --refresh-boot-sio --boot-sio auto
```

The canonical `of816/Exec-core.xex` remains a development artifact; the split
package contains its wrapped `Exec-of816.xex`, while the combined ATR stores
the canonical stream internally. See the
[boot SIO contract](../reference/boot-loading.md#boot-only-sio-reader).
