# Layers visibility rebuild improvement

[Plan](../plans/gem4xe/layers-rebuild-plan.md) ·
[Measurements](../development/layers-rebuild.json) ·
[Layers contract](../reference/layers.md) ·
[PT4 baseline](popup-transition.md)

## LR1 Rebuild order and skipped work

Each layer now subtracts nearer occluders before farther ones, skips rectangles
disjoint from its bounds, and stops once no visible pixels remain. This avoids
fragmenting a fully covered lower layer before discovering its covering window.
The visible set, damage obligations, scene transaction and rebuild counter
semantics are unchanged. Rectangle partition/order may differ, as permitted by
the visibility contract. No new cache, state or public operation is introduced.

Development checks pass: 491 host tests (four historical skips) and 8,796
optimized emitted Layers checks. The existing 128 geometry cases, 40 scene
snapshots, software paint/copy fallback, saved replacement, external damage,
bank-crossing and guard/OS-return checks pass. Four new snapshots compare all
768 pixels independently for covered layers, edge-touching neighbours,
crossing overlays and exposure after hiding/moving/reordering the cover.

Artifacts: `build/layers-rebuild/lr1-layers`. No raw or qualification matrix
was run; no ABI layout or language-bridge behavior changed.

Rebuild native code grows **1,576 → 1,778 bytes** (+202); its local stack peak
falls **36 → 34 bytes**. Layers/Regions code grows 38,646 → 38,848 bytes, with
the same 56-byte maximum local stack peak and no mutable globals. Scene size
remains 9,186 bytes. Reserved bank-zero delta is **0 fixed, 0 per public Task,
0 idle bytes**, including guards, alignment and unused capacity. DP, stack,
VRAM and upper-memory reservations are unchanged.

## LR2 Matched menu measurements

The clean `62b4202` demo is compared with the preserved clean PT4 `95fee02`
package and its original 18-action capture. Compiler pin/binary, emulator,
ROM, PAL/65816x8/VBXE/63-bank settings and accurate generic-56K disk configuration
match. The same passive observer and input sequence are used, without target
instrumentation or a compiler override.

The representative warm switch uses **10 subtraction calls instead of 15**,
and 20 rectangle intersections instead of 50 within Rebuild. Subtraction CPU
falls 12.794 → 5.639 ms. Rebuild CPU falls **18.612 → 10.998 ms** (41%), within
final replacement-commit CPU **23.247 → 15.595 ms**. These nested costs overlap.
There is still one rebuild and two cached whole-image copies. All 18 transfer
counter records match PT4; Files paints and timed serial events remain zero.

Medians in milliseconds, three samples per action family:

| Action | Elapsed PT4 → LR2 | Presenter CPU PT4 → LR2 |
| --- | ---: | ---: |
| Warm open | 140.454 → 140.454 | 97.942 → 90.402 |
| Highlight | 60.374 → 60.122 | 25.564 → 25.569 |
| Warm File → View | 120.245 → 120.498 | 78.920 → 71.334 |
| Dismiss | 120.497 → 120.497 | 73.054 → 71.423 |
| Keyboard headings | 240.490 → 240.490 | 191.926 → 190.666 |
| Physical pointer headings | 280.656 → 280.908 | 158.898 → 145.339 |

The record contains minimum/median/maximum for every cohort. Warm-switch
presenter CPU drops 9.6%, with new samples 71.334 / 71.334 / 71.369 ms.
Its elapsed samples are 120.245 / 120.498 / 120.498 ms: the CPU saving does
not cross a sampled PAL-frame boundary. This is a CPU reduction, not evidence
of a perceptible menu-latency improvement. The representative final scene
commit finishes at 55.999 ms instead of 63.559 ms; title painting finishes at
75.969 ms instead of 83.502 ms. The menu-title path itself is unchanged.

The three-heading sequence still exceeds the two popup cache slots. In its
middle sample the rebuild is 7.6 ms cheaper, but CPU charged up to the same
pixel endpoint falls only 1.3 ms: the last title-paint call moves from
239.933–249.733 ms to 230.725–240.448 ms, so substantially more of that existing
work now falls inside the 240.49 ms measurement window. There is no extra paint
call across the complete captured action. Physical pointer timing includes
travel and motion handling, not just the time after crossing a heading.

## Packaged validation and resources

The exact ZIP passes the menu capture, five-second OF816 autoboot (249 PAL
frames), stack/domain guards, normal OS return and zero-live-Task cleanup.
Observed presenter peak is 828 of 2,560 bytes, leaving 1,476 above its floor;
kernel peak is 297 of 1,536 bytes and idle peak 59 of 512. These observations
are not whole-program stack bounds.

Native code totals **1,095,128 → 1,095,330 bytes** (+202); native data remains
13,544 bytes. The entire memory reservation manifest is identical to PT4.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. Scene, DP, stack, VRAM and
upper-memory reservations remain unchanged. LR2 adds no target state.

Artifacts:

- `build/layers-rebuild/demo/exec816-demo.zip`
- `build/layers-rebuild/demo/launch-altirra.command`
- `build/layers-rebuild/menus` (development trace outside the ZIP)

All 22 ZIP checksums verify. OF816 wraps the matching native payload and system
disk; the pinned ROM, notices and user guide are present, with no manifests,
trace logs or build intermediates in the archive. SHA-256:
`0513975c569b10a0783f5fb0429d9057e03178ff82d0d9534abd65ee4191e3a0`.

Validation is development tier. No release/hardware qualification or p95 claim
is made from three samples. Pixel timing includes scanout and once-per-PAL-frame
sampling; copy timing includes software and interrupt latency, not pure DMA.
