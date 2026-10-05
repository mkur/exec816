# Build from source

[Contributor guide](README.md)

Building from source is optional. To run the prebuilt distribution, follow the
[ZIP installation guide](../../README.md#installation).

Run commands from the repository root. The hosted build uses Python 3, Rust/Cargo,
and ca65/ld65 from cc65. It also needs the pinned AltirraSDL bridge and 65816 ROM;
the demo builder verifies their hashes before compiling.

## Pinned inputs

| Input | Source of truth | Default local path |
| --- | --- | --- |
| Action! compiler and native ABI | [actionc.json](../../toolchain/actionc.json) | `build/actionc` |
| Demo emulator and ROM | [altirra-shell-paced.json](../../toolchain/altirra-shell-paced.json) | `build/shell-paced-bridge/AltirraBridgeServer`, `build/firmware/altirraos-816.rom` |
| OF816 | [of816.json](../../toolchain/of816.json) | `build/of816-upstream` |
| Kernel defaults | [kernel.json](../../config/kernel.json) | repository file |
| Default demo mounts | [shell-sdfs.json](../../config/shell-sdfs.json) | repository file |

Prepare the compiler checkout at the recorded revision:

```sh
git clone https://github.com/mkur/actionc.git build/actionc
actionc_revision=$(python3 -c 'import json; print(json.load(open("toolchain/actionc.json"))["revision"])')
git -C build/actionc fetch ../../toolchain/actionc-pointer-arrays.bundle refs/heads/fix/record-pointer-array-elements
git -C build/actionc checkout --detach "$actionc_revision"
```

For an existing checkout, fetch the recorded revision before checking it out.
The small incremental bundle contains the locally pinned pointer-array typing
fix on top of the upstream revision named by `bundle_base` in the pin. It is
included so this build does not depend on an unpublished remote commit.
The builders compile the compiler as needed. Use the exact bridge and ROM from
the platform pin; an arbitrary installed AltirraSDL build does not satisfy that
input check. The emulator is [AltirraSDL](https://github.com/ilmenit/AltirraSDL);
upstream Altirra will not run the current Exec816 build.
See the [platform contract](../reference/platform.md) for the
machine boundary and the pin's provenance for platform inputs.

## Build the demo

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/build_demo.py
```

The build always includes OF816 and produces `build/demo/exec816-demo.zip` with
the boot XEX, system disk and matching ROM. It fetches the pinned OF816 checkout
if absent. Build reports and intermediate files remain outside the ZIP.
See the [demo guide](../guides/demo.md) for machine setup, media alternatives and
the walkthrough, and the [boot monitor guide](../guides/boot-monitor.md) for
repackaging an existing image.

For a full-screen bitmap shell without the prime task, use a fresh output
directory and the shell-only boot selection:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 python3 tools/build_demo.py --bitmap-shell-only --output build/demo-bitmap-shell
```

This keeps OF816's five-second autoboot and packages the matching disk, ROM
and GEM notices. See the [bitmap shell package guide](../bitmap-shell-distribution.txt)
for VBXE configuration and commands. Reserved bank-zero memory is unchanged,
both fixed and per Task; the prime Task is never started.

To add Atarimax 8 Mbit cartridge images to an existing demo, preserving its
exact XEX, disk and firmware, use a separate output directory:

```sh
python3 tools/build_demo.py --cartridge-from path/to/exec816-demo.zip \
  --cartridge-source-sha256 <published-ZIP-SHA256> --output build/cartridge-demo
```

This requires Python and ca65/ld65, without recompiling Exec or OF816. The new
`exec816-demo.zip` adds old/new Atarimax CAR headers over the same 1 MiB ROM,
a raw BIN for programming, the [cartridge guide](../cartridge-distribution.txt)
and updated checksums. The 128 KiB cartridge is unsupported. The RAM loader
temporarily borrows `$9000–$93FF` below the cartridge-era OS screen, with no
additional runtime bank-zero reservation or per-Task cost. It switches the
cartridge off around INITAD callbacks and before entering the unchanged XEX.
CPU, ROM and memory requirements remain those of the input demo; physical
cartridge/accelerator hardware requires separate qualification.

Check an image with the matching development build and Exec source revision
(use a checkout of the release tag for an older published demo):

```sh
python3 tools/test_cartridge.py \
  --cartridge-build build/cartridge-demo/cartridge-build/Exec-of816 \
  --demo-build build/demo --exec-source path/to/matching/exec816 \
  --output build/cartridge-check-new --variant new
```

Repeat with `--variant old --manual` and a different output directory to check
the other power-on bank, final-second countdown cancellation and Forth entry.
The fixture checks the cartridge handoff, documented shell/disk commands and
EXIT, using the source revision's original guard and ownership assertions.
It reads upper RAM through the debugger because cartridge boot places the OS
screen below the scratch area assumed by the older XEX test helper.

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
