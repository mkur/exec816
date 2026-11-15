# Cursor drawing-change hint consumption

[Presenter audit](mgview-presenter-audit.md) · [History](README.md) ·
[Development measurements](../development/cursor-drawing-hint.json)

The presenter audit found repeated mouse submissions because the AES mouse
path never consumed the screen drawing-change hint. `CONSOLEBITMAP.Mouse`
now clears the old hint before `Run(OP_MOUSE)` and rearms it if that call
fails. A successful presentation leaves a notification from a later draw
untouched. The fallback `Cursor` path follows the same rule instead of
clearing the hint after `Run(OP_POINTER)`.

The boundary is deliberate. Physical rendering can release the scene and
reclaim it through `AESGATE.Resume`, allowing another Task to draw before
return. Clearing the flag afterward would lose that notification. Failure,
including BUSY admission, leaves a hint for the next eligible presentation.
The existing pointer-dirty and cursor-revision protocols remain in force.
No extra signal, Task, shared counter or lock is introduced.

## Focused checks

```sh
python3 tools/test_cursor_hint.py --output build/mgview-mouse-fix/hint
```

This optimized emitted-code probe extracts the actual `Mouse`, `Cursor` and
`Changed` routines unchanged. A deterministic replacement for the physical
`Run` boundary observes the old hint and can publish a new draw or return
failure. Twelve cases pass 48 checks: ordinary success, failed admission,
late drawing during success, failure without an old hint, late drawing during
failure and successful retry, for both cursor paths. Native status, guards
and ownership restoration pass. The probe does not model hardware rendering;
the loaded MGVIEW check supplies that integration.

Only the native MGVIEW fixture was rebuilt for integration. Its cached C
provider, MGVIEW, Counter, disk document and drawing limits are unchanged.
The paired captures use the same pinned ROM/emulator, mouse profile, viewport,
physical down/up key sequence and independent complete-viewport pixel oracle.
The observer now requires the parked pointer to reach `(632,0)` and checks
that its final position agrees before accepting the measurement.

```sh
python3 tools/measure_mgview.py --presenter \
  --cache build/mgview-dev/smoke \
  --output build/mgview-mouse-fix/baseline-scroll
python3 tools/measure_mgview.py --presenter \
  --cache build/mgview-mouse-fix/cache \
  --output build/mgview-mouse-fix/settled-scroll
```

The changed native fixture is built from the cached `launcher.act` with
`native_program.build`, the unchanged `c-image.json`, optimized mode,
eight Tasks, deferred console, the original memory profile and D1 mount.
Retain its recorded `desktop_mouse` and `gem_applications` metadata when
rebuilding only native code. No APP, C-provider, QED, demo or boot-transport
build is needed.

An initial integration capture omitted the cached mouse-profile metadata.
The positioning helper therefore used the older movement scale and queued
motion during the scroll measurement. Its 360/380 ms results are invalid
for stationary-scroll comparison. The metadata was restored without changing
guest bytes, and both baseline and fixed captures were repeated with the
explicit settled-pointer check. The discarded run remains under
`build/mgview-mouse-fix/scroll/`.

## Matched measurements

| Measurement | Down before → after | Up before → after |
| --- | ---: | ---: |
| Input → complete viewport observed, ms | **222.54 → 180.65** | **200.46 → 180.14** |
| Whole-scroll presenter CPU, ms | 74.39 → 54.93 | 82.80 → 40.34 |
| Whole-scroll mouse-operation returns | **10 → 2** | **15 → 1** |
| Already-owned UPDATE presenter CPU, ms | 55.70 → 36.87 | 65.60 → 22.57 |
| Already-owned UPDATE mouse-presentation CPU, ms | 38.99 → 22.47 | 51.19 → 12.21 |

These paired samples show roughly 42/20 ms lower observed complete-viewport
latency, or 19%/10% down/up. Visibility remains sampled at PAL-frame/COP
boundaries: before brackets are 200.58–222.54 and 180.68–200.46 ms; after
brackets are 160.10–180.65 and 159.98–180.14 ms. These are observations for
this fixture, not percentile or hardware guarantees.

Every observed `Changed()` result during the fixed scrolls is zero. Unlike the
baseline's permanently true hint, that permits the cursor-revision check to
run. Inside already-owned UPDATE, that check reports pending work only twice
down and once up; the fixed mouse operations complete successfully. Counts
include only C returns inside the named interval; intersecting native call
counts and clipped CPU are retained separately in the JSON.

Both images pass exact completed viewport hashes before/after/back, Counter
progress, four Process lifetimes, heap checks, intact stack/domain guards and
ownership restoration. Each key still uses one copy, one exposed text-row
draw, zero AES RPC, twelve successful hardware-copy strips and 48 copy fences.
The viewer's whole-scroll CPU stays around 91 ms; the saved time comes from
reduced presenter work and off-viewer time. No speedup is attributed to a new
blitter path or larger drawing unit.

## Memory and validation scope

The two changed native routines add 73 executable bytes in upper RAM.
`Mouse`'s emitted local stack peak grows from 18 to 20 bytes; `Cursor` remains
at 14. They fit the existing reservations. The native fixture's bank-zero
budget and every Task pool are byte-for-byte identical to the baseline.
Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 private idle and
0 per public Task**, including guards, alignment and unused capacity.

This is development validation: one small emitted probe and one two-key
loaded capture per image, with existing cleanup/heap/stack/domain checks.
It is not a latency distribution, physical-hardware qualification or a
release suite. The wider mouse-form, occlusion and fault matrices were not
rerun. No scheduler, display-admission, cursor-revision or strip-limit policy
was changed.
