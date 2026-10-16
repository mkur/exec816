# Damage retirement

[Implementation plan](../plans/gem4xe/damage-retirement-plan.md) ·
[Starting measurements](warm-menu-input.md) ·
[Measurements](../development/damage-retirement.json) ·
[Layers contract](../reference/layers.md#saved-scene-rectangles)

## DR1 First-overlap scratch construction

`SubtractDamage` now returns without rebuilding a list when the completion
rectangle is empty or disjoint from all its entries. Signed half-open edge
comparisons treat touching edges as disjoint. At the first overlap it copies
the unchanged prefix once, then uses the existing splitting and publication
path. Results larger than eight rectangles still leave the original record
untouched. The single-rectangle containment shortcut remains.

This shared change covers saved-background restoration, saved-popup replacement
and external `Painted` completion. There is no new caller check, state, allocation
or ABI. Visibility rebuilding, cache policy, dirty summaries and transaction
ownership are unchanged; manager-damage retirement does not acknowledge an
application's pending repaint.

Development checks pass: six focused host checks and the optimized Layers
fixture, with **8,919 emitted checks**, 128 geometry cases and 40 scene cases.
Twenty-four new completion cases check empty/disjoint/touching rectangles,
first overlap at each position, preserved prefixes/suffixes, exactly eight
pieces, overflow, signed coordinates and overlapping damage. The host oracle
checks the remaining pixel union independently. Saved CLEAN/DIRTY replacement
and dismissal preserve unrelated manager damage and external pending paint,
release the token/pin and retain one rebuild per replacement. Existing stale,
failure, bank-crossing, ownership and guard coverage remains in the fixture.
Normal return and zero live Tasks pass. No raw or qualification matrix ran.

Artifacts are `build/damage-retirement/dr1-layers` and adjacent host/fixture
logs. Emitted-code inspection is retained as
`build/damage-retirement/dr1-subtract.asm`: the disjoint scan returns before
workspace stores, `PaintPiece` or copy-back, and rectangle indexing uses shifts.
The containment shortcut still calls `REGIONS.Contains` for a one-entry list.

The helper grows **1,254 → 1,755 bytes** (+501). Its fixed frame, spill allocation
and local stack peak remain **26 / 16 / 42 bytes**; these are local figures, not
whole-call-chain bounds. No mutable globals are added. Reserved bank-zero delta
is **0 fixed, 0 per public Task, 0 idle bytes**, including guards, alignment and
unused capacity. Scene, DP, stack, VRAM and upper-memory reservations are unchanged.

## DR2 Matched production measurements

The clean `cbc0a16b` package uses the same compiler revision/executable,
emulator, ROM bytes and PAL/65816x8/VBXE/63-bank configuration as WI2's clean
`426f3f8a` package. The passive observer and all 36 actions are unchanged.
Only ROM-path-derived firmware identifiers differ in the machine settings.
All cache-transfer counters match; no timed action repaints Files or performs
disk I/O.

The representative complete keyboard switch now spends about **2.6 ms less
CPU** in the saved-popup scene commit:

| CPU in `complete/keyboard/0` | WI2 | DR2 |
| --- | ---: | ---: |
| `FinishSavedReplace`, inclusive | 16.472 ms | 13.835 ms |
| Nested `Rebuild` | 11.309 ms | 11.350 ms |
| Commit excluding `Rebuild` | 5.163 ms | 2.485 ms |

The exclusive residual includes lookup, geometry publication and cleanup as
well as damage subtraction; it is not an isolated helper measurement. The
other two complete keyboard samples agree: inclusive commit CPU is
13.823/13.836 ms. Rebuild remains near 11.3 ms and accounts for most of the
remaining commit cost.

Three-sample keyboard medians, measured to complete popup **and** heading pixels:

| Measure | WI2 | DR2 |
| --- | ---: | ---: |
| Presenter CPU through complete feedback | 60.274 ms | 57.614 ms |
| Presenter CPU through title retirement | 53.089 ms | 50.439 ms |
| Elapsed time to title retirement | 71.431 ms | 69.970 ms |
| First matching complete frame | 100.288 ms | 100.288 ms |

This saves about **4.4% of complete-switch CPU**, but all three complete pixel
observations remain in the same roughly **80–100 ms** last-nonmatch/first-match
bracket. Post-title CPU stays near 7.2 ms. There is no demonstrated complete
frame improvement and three samples do not establish p95.

Pointer scene commits also get cheaper. CPU from the actual heading crossing
to complete feedback changes **73.779 → 71.082**, **80.741 → 79.305** and
**72.235 → 70.453 ms**. Complete feedback from the stimulus stays near 140 ms.
The first two crossing-to-feedback brackets are effectively unchanged; in
the third pair the pointer crosses about 10.7 ms earlier, widening that
response interval despite lower CPU. Individual crossings and frame brackets
are retained in the measurements; do not infer a universal pointer latency gain.

Historical cropped controls retain their sampled endpoints: cached opening
120 ms, highlight 60 ms, switch/dismiss 100 ms; native opening 120 ms,
highlight/next-row 80 ms and dismissal 100 ms. Application dismissal CPU falls
58.607 → 56.461 ms; native dismissal falls 59.376 → 57.358 ms. Opening and
native highlight/next-row CPU stay close to WI2. The three uncached keyboard
heading controls measure 140/181/201 → 140/160/201 ms. These are different
headings, not repetitions of one operation; their cropped endpoints can also
exclude cache maintenance that runs later. They provide no evidence of an
intersecting-path regression, but the middle observation is not a general
20 ms cold-menu claim.

## Checks, resources and package

The production capture passes complete pixel checks, Counter progress during
30 application and 30 native highlights, normal EXIT, zero-live-Task cleanup
and intact guards. OF816 autoboot remains **249 PAL frames**; all **22 archive
checksums** verify. Together with DR1's focused fixture, these are development
checks. No raw, broad AES/filesystem or release/hardware qualification matrix ran.

Production Action code grows **1,095,517 → 1,096,018 bytes** (+501); native data
stays 13,544 bytes. C text/data/BSS stay **222,330 / 20,773 / 23 bytes**. The
memory reservation manifest is byte-for-byte identical. Reserved bank-zero delta
is **0 fixed, 0 per public Task, 0 idle bytes**, including guards, alignment and
unused capacity; no other reservation grows.

Observed presenter stack use is **838 → 836 of 2,560 bytes**, leaving 1,468
above the floor. Kernel use is 295 → 287 of 1,536; idle is 129 → 141 of 512.
These are workload observations, not whole-program bounds or reservation changes.

Artifacts:

- `build/damage-retirement/demo/exec816-demo.zip`
- `build/damage-retirement/demo/launch-altirra.command`
- `build/damage-retirement/menus` (passive development capture)

The ZIP includes OF816 boot, matching disks, pinned ROM, guide, notices and
checksums. Intermediates and measurements remain outside it. SHA-256:
`ade55940e2468bd000ece5a22266f2b23deac34f47ad1827f708c305ff6d33d3`.

Launch from the repository:

```sh
./build/damage-retirement/demo/launch-altirra.command
```
