# Hosted GEM4XE port

[Implementation plan](../../docs/plans/gem4xe/minimal-vdi-implementation-plan.md) · [G0 contracts](../../docs/plans/gem4xe/hosting-contracts.md)

G0 provides read-only VBXE detection. G1 extracts and links the selected GEM C
subset, then exercises its entry points through a recording device on an ordinary
Exec Task. The message service and display lease remain pending.

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
applies the patch without fuzz, generates validation from the operation manifest,
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

The VBXE device table and its dependency closure are linked for sizing but never
bound or executed. In particular, the imported backend's busy waits, mapping,
shutdown and extreme-coordinate arithmetic are **not ready for hosted drawing**.
G3 must implement display ownership, bounded internal waits/fences and recovery;
G4 must establish pixel correctness. The recording callbacks validate actual GEM
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
for the later SDFS workload; G0/G1 do not mount a disk or claim concurrent I/O.
Existing default platform checks continue to require add-ons off.
