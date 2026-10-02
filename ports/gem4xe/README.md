# Hosted GEM4XE port

[Implementation plan](../../docs/plans/gem4xe/minimal-vdi-implementation-plan.md) · [Current hosting contract](../../docs/reference/gem-vdi.md)

G0 provides read-only VBXE detection. G1 extracts and links the selected GEM C
subset, then exercises its entry points through a recording device on an ordinary
Exec Task. [G2](service/README.md) implements the private message service with a
fixture backend. [G3](../../platform/altirraos/vbxe.md) implements shared display
ownership and a bounded VBXE adapter with a hardware test pattern.
[G4](adapter/README.md) connects accepted requests to the selected renderer and
checks real pixels, attributes, font expansion and failure recovery.

[inputs.json](inputs.json) pins GEM4XE 0.9.4, the Exec baseline, compiler/runtime
hashes and selected source roles. [selection.json](selection.json) selects exact
lines from those immutable inputs; the [hosted patch](patches/0001-hosted-storage-and-subset.patch)
adapts storage, dispatch and initialization. Fetch missing inputs and verify all
hashes with:

```sh
python3 tools/gem_vdi_inputs.py --fetch
```

Existing but changed inputs fail verification rather than being overwritten.
The selected notices include COPYING, COPYING.LIB, font provenance and the
upstream licence note; preserve these with imported source and distributions.
Exec's MIT interface grant does not relicense donor code.

Using the pinned local compiler, firmware and `build/shell-paced-bridge`, run:

```sh
python3 tools/test_gem_vdi.py --mode raw
python3 tools/test_gem_vdi.py --mode opt
```

Each build runs with FX 1.26, without VBXE and with unsupported FX 1.24.
The target reads identity bytes, sleeps across VBI and exits through the hosted
restoration path. Tests check detection status, all existing stack/domain guards,
OS display state and the unmapped aperture sentinel. They do not enable graphics.
Results and source/build records stay under `build/gem-vdi/g0-{raw,opt}/`.

Run the selected C subset in raw Action! NIR/Calypsi `-O0` and optimized NIR/`-O2`:

```sh
python3 tools/test_gem_vdi.py --slice g1 --mode raw
python3 tools/test_gem_vdi.py --slice g1 --mode opt
```

[build_gem_vdi.py](../../tools/build_gem_vdi.py) reproduces selected source,
applies the ordered patch series without fuzz, generates validation from the operation manifest,
checks target-emitted C layouts and packages the linked image through the existing
Exec builder. Generated source, notices, maps, provenance and test results stay
under `build/gem-vdi/g1-{raw,opt}/`. Repeated extraction has identical content
hashes. No legacy startup, keyboard initialization, printer, CIO font loader or
virtual-workstation dispatcher is linked. No omitted service has a success stub.

The private [adapter](hosted/hosted-dispatch.inc) accepts only the frozen operation
subset. Its caller owns the bound device and parameter storage; it is not a public
message interface. A successful call submits callbacks, not a hardware fence.
The fixture checks open/close, attributes, clipping, reversed rectangles, lines,
one built-in glyph, upper-bank font access and rejection without mutation. It
observes VBI in selected GEM C and the computing peer, checks results, all existing
guards and cleanup, and measures stack high-water marks. These are entry/layout
checks, not the G4 pixel corpus or a worst-case C stack bound.

In the G1 probe, the VBXE device table and its dependency closure are linked for
sizing but never bound or executed. G4 excludes the donor low-level hardware
implementation, substitutes the bounded adapter and fixes wide-coordinate
arithmetic through separate reproducible patches. The recording callbacks validate actual GEM
calls without changing the hardware. The test verifies inactive MEMAC/blitter/IRQ,
OS presentation and the unmapped aperture sentinel after execution.

The [G1 development record](../../docs/development/gem-vdi-g1.json) contains the
combined map, raw/optimized results and C control regressions. Both modes fit the
existing code bank `$0C` and data/BSS bank `$0D`; both complete banks remain reserved
(131,072 bytes, including unused capacity). `FAR`, `TINY` and `ZWIN` use ordinary
huge data, and all renderer globals/font/tables are in upper RAM. Calypsi retains
its existing 20-byte lower-DP workspace. Fixed and per-Task bank-zero increments
are **zero**, including guards, alignment and unused pool capacity. The two workers
use the existing 2,560-byte stacks. G1 reserves no VRAM; the pinned 512 KiB is
inactive. The standard OF816 demo is unchanged; this fixture is not a demo bundle.

The [separate platform pin](../../toolchain/altirra-gem-vdi.json) enables only
VBXE with private 512 KiB VRAM at `$D600`. It also selects physical SIO settings
for the later SDFS workload; G0–G2 do not mount a disk or claim concurrent I/O.
Existing default platform checks continue to require add-ons off.

## G3 display adapter

```sh
python3 tools/test_gem_display.py --mode raw --output build/gem-vdi/g3-raw
python3 tools/test_gem_display.py --mode opt --output build/gem-vdi/g3-opt
```

The [G3 record](../../docs/development/gem-vdi-g3.json) covers the pinned hardware
adapter, full-pattern mapped readback, CPU/VRAM separation, physical SIO, console
restoration and reset-required recovery. The [display contract](../../docs/reference/display.md)
and [VRAM map](../../platform/altirraos/vbxe-vram.json) define the current boundary.
These are development checks; no full hosted-system qualification is claimed.

## G4 rendering

The [renderer backend](adapter/README.md) documents integration and the raw/optimized
pixel corpus. Its [development record](../../docs/development/gem-vdi-g4.json)
keeps exact pixels, scanout, font/palette checks and measured stack use together.
G5 remains the combined drawing, computing-peer and physical SDFS workload.

## G5 concurrent workload

```sh
python3 tools/test_gem_concurrent.py --mode raw --output build/gem-vdi/g5-final-raw
python3 tools/test_gem_concurrent.py --mode opt --output build/gem-vdi/g5-final-opt
```

The [G5 record](../../docs/development/gem-vdi-g5.json) records the fixed drawing,
computing and physical-SDFS workload and 12 lifecycle/failure controls per mode.
The diagnostic start rendezvous borrows `$6000` only in the test environment.
Renderer/peer progress is observed during live physical transactions; a pending
reply alone does not count as overlap. The [optional artifact guide](../../docs/guides/gem-vdi.md) describes the G6
distribution and exact machine configuration.

## Current optional artifact

```sh
python3 tools/build_demo.py --gem-vdi --output build/gem-mouse/m6-demo
python3 tools/test_gem_interactive.py --mode opt --production --replay \
  --case keyboard --case wrong-disk --case no-disk --output build/gem-mouse/m6-demo/gem-vdi
python3 tools/test_gem_mouse.py --mode opt --production --replay \
  --case controls --case close-held --output build/gem-mouse/m6-demo/gem-vdi
python3 tools/test_of816.py --output build/gem-mouse/m6-demo/of816
```

The historical [G6 record](../../docs/development/gem-vdi-g6.json) covers raw/optimized
uninstrumented graphics, exact visible pixels/palette, the packaged optimized
image, standard OF816 boot/exit routes and shell/prime controls. The ZIP includes
only boot files, guides, notices and checksums. The standard five-second OF816
shell/prime autoboot remains the default; graphics is selected explicitly.

The current artifact is the [interactive application](interactive/README.md):
a native keyboard and ST mouse scene with root supervising disk I/O and the application owning
the renderer. [I0–I7](../../docs/history/gem-input.md) record reusable input,
cursor/injected gestures, measured concurrency, failures and the refreshed bundle.
[M0–M6](../../docs/history/gem-mouse.md) add ST mouse motion and the left
button on port 1 through INPUT, bounded timing checks and the current bundle.
There is no AES support. The G5 computing-peer regression remains
available through its development runner and retains its historical evidence.
