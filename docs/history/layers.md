# Layers implementation record

[History](README.md) · [Current contracts](../reference/layers.md) ·
[Implementation plan](../plans/layers-implementation-plan.md)

L1–L4 completed on 2026-10-04. The new ordinary-call Action! library supplies
bounded rectangle regions, four opaque layers plus background, cached visibility,
damage and paint/copy transactions. It has no mutable globals, kernel service or
Task of its own. The existing console and exclusive GEM workload are unchanged;
desktop presentation will consume the library in a later milestone.

## Development execution

The final [L4 evidence](../development/layers-l4.json) records identical source
inputs in raw and optimized builds, pinned actionc
`f1ff4ce0d16b4705e66d69aad00ca4a7be3e1d08`, no compiler override, the actual
mouse-capable Altirra bridge hash, ROM hash and verified machine configuration.
The configuration is PAL, 65C816 ×8, 4 MiB CPU RAM and the pinned VBXE profile.
No physical graphics operation is submitted by these fixtures.

Each final build passed 53,207 fixture assertions, together with independent
host oracles covering:

- 128 rectangle subtraction/clipping cases, including empty/touching geometry,
  signed extremes, exact coverage, overlap rejection and atomic overflow.
- 32 scene transitions with stacking, hide/show, movement, deletion, slot reuse,
  stale IDs, failed operations and cache stability.
- 33 incremental paint transactions whose pixels match complete retained-scene
  recomposition, plus one fully visible copy and one covered-scroll fallback.
- Paint/copy BUSY gates, failed drawing, stale completions, hidden damage,
  empty operations, identity/token exhaustion and descriptor reuse. Copy
  preparation snapshots both rectangles before replacing either saved descriptor,
  including when the caller swaps the preceding copy's source and target.
- A 4,782-byte scene beginning at `$11FFF0`, crossing a CPU bank, with a complete
  640×240 visibility oracle. Four separated foreground layers leave fourteen
  background rectangles; all 153,600 pixels have exactly the expected owner.
- Object/output guards, kernel/Task stack guards, ownership restoration and
  normal OS return while VBI is active. These are ordinary native calls, with
  no new IRQ entry or drawing driver path.

The working-tree host suite reported 335 tests, with four expected historical
source-audit skips. Generated definitions and documentation links were checked.
The host count includes pre-existing cartridge tests outside the Layers commits.
Earlier snapshots preserve [L1](../development/layers-l1.json),
[L2](../development/layers-l2.json) and [L3](../development/layers-l3.json).

To reproduce the final emitted checks:

```sh
python3 tools/generate_layers.py --check
python3 tools/test_layers.py --mode raw --output build/layers/raw
python3 tools/test_layers.py --mode opt --output build/layers/opt
python3 -m unittest discover -s tests -p 'test_*.py'
```

The runner uses the existing pinned compiler, ROM and mouse-capable bridge in
`build/`; it verifies their identities before execution. Result JSON, captured
regions and software raster snapshots stay in the selected development directory.

## Memory and work bounds

The scene reserves 4,782 caller-owned upper-RAM bytes, including five 792-byte
layer records, one scratch region and all alignment/unused capacity. A region
reserves 770 bytes for up to 96 rectangles. Four occluders introduce at most nine
coordinate intervals per axis, bounding the subdivision at 81 cells. Generic
region subtraction reports overflow before touching its destination.

Fixed, root/kernel, per-public-Task and idle bank-zero reservation deltas are
all **zero bytes**, including guards, alignment and unused pool capacity. The
eight-Task map still reserves 56,128 bank-zero bytes including OS storage, with
9,408 bytes free after startup. The runner's generated budget matches the L1
baseline. No VRAM reservation, signal or runtime Task is added.

| Final emitted library measurement | Raw | Optimized |
| --- | ---: | ---: |
| Layers and Regions routine bytes | 18,505 | 17,831 |
| Maximum reported local routine stack peak | 58 | 58 |
| Fixture root stack touched-byte watermark | 282 | 296 |
| Root bytes untouched above interrupt reserve | 998 | 984 |
| Kernel stack touched-byte watermark | 266 | 260 |

Code counts exclude shared runtime memory primitives. Local frame reports and
sampled touched-byte watermarks are not complete bounds for the later console/C
presenter call chain. No reserved stack or interrupt headroom was exceeded in
these executions.

The scene corpus uses at most five cached visibility rectangles and four dirty
paint rectangles per update; the separate 640×240 case reaches fourteen cached
background rectangles. Queries and content invalidations leave the rebuild
counter unchanged. These are bounded-work observations, not desktop latency or
blitter performance measurements.

## Remaining integration

Window registration, retained-console presentation, clipped glyph rendering,
pointer/caret/outline coordination and actual VBXE submission remain in the
desktop milestone. The drawing caller must keep a Layers token active until DMA
completion or proven quiescence. There is no backing bitmap, resize policy,
window manager or C binding in this library milestone.

This is development-tier evidence. It does not qualify hardware, physical SIO
coexistence, pointer latency, window movement, final scanout or a desktop demo.
