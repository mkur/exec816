# AES UPDATE snapshot reuse

[Design](../plans/gem4xe/update-snapshot-reuse-design.md) ·
[Implementation plan](../plans/gem4xe/update-snapshot-reuse-plan.md) ·
[AES contract](../reference/aes.md) · [Layers contract](../reference/layers.md) ·
[Matched evidence](../development/update-snapshot-us3.json) ·
[History](README.md)

## Implementation and freshness

`AESWINDOWSTATE.Publish` reuses bounds, work geometry and clipped visibility
when the scene layout epoch and the window's source bounds, frame kind and
iconified mode match. The existing view holds the geometry; eight private
aligned bytes per AES window hold the tags. Creation, deletion and service
binding invalidate the tags.

Layers v14 appends `Scene.layoutEpoch`. Reconstruction advances it before
doing work, so failure also retires the previous geometry. On exhaustion it
becomes zero and permanently disables reuse for that scene lifetime. A new
unpublished scene lifetime and fresh service binding establish new validity.
The successful-rebuild statistic retains its existing wrapping behavior.
Hidden bounds changes need no scene rebuild and are caught by the source-bound
comparison. Desktop v17 incorporates the larger Scene record.

Every publication still refreshes paint epoch, pixel readiness, shown state
and iterator revision. BEGIN still touches content, invalidates cache state
and resets the journals; END still consumes them synchronously and publishes
completion. Hidden model changes remain conservative. Completing the current
work area can leave older repaint obligations outside it pending. Local/RPC
policy, nesting, scoped updates, display borrowing and public AES layouts
retain their behavior.

## Executed slices

The [US0 record](../development/update-snapshot-us0.json) profiles the exact
frozen `ac33f02b` guest image: eleven frame digests and all original timing
groups match. A fragmented Counter tick costs 39.306 ms caller CPU, including
5.204 ms publishing snapshots and 1.924 ms clipping visibility. Those helper
costs overlap other inclusive measurements.

The [US1 record](../development/update-snapshot-us1.json) establishes behavior
before production changes. The [US2 record](../development/update-snapshot-us2.json)
records the implementation checks:

- 137 normal native assertions and 22 independent visible-set observations,
  matching geometry, paint readiness, epochs and iterator revisions.
- 174 assertions with a test-only failed-subtraction injection, recovery,
  exhaustion, service rebinding and scene recreation. Two publications at an
  exhausted epoch make eight clipping calls for four owned views.
- Real cache, lock and physical window fixtures pass 224, 181 and 285 C
  assertions respectively, plus four native assertions each. These retain
  exact pixels/geometry, local/RPC combinations, scheduled peers, nesting,
  scoped updates, FIRST/NEXT invalidation, iconification and retirement.
- The optimized Layers fixture passes 8,924 checks; the small desktop/Scene
  layout probe passes 126 checks in each raw and optimized mode.
- Host checks pass 665 tests with four historical-source skips. Guards,
  ownership and heap restoration pass in the selected emitted fixtures.

All captures and development attempts remain under `build/update-snapshot-reuse/`.
The original object-traversal and MagiC baseline records remain intact.

## Controlled metadata cost

The direct native workload measures actual BEGIN/publication/END work without
renderer or admission costs. Each case retains eight calls after two warmups.
The changed-layout case mutates geometry outside the measured call and then
requires fresh publication. Equal window counts separate layout changes from
the cost of additional owned views.

| Case | Before caller CPU median | After caller CPU median | Change |
| --- | ---: | ---: | ---: |
| One owned window, fixed layout | 3.081 ms | 2.724 ms | -11.6% |
| Four owned windows, fixed layout | 11.487 ms | 10.050 ms | -12.5% |
| Four windows, fixed fragmented visibility | 12.397 ms | 10.044 ms | -19.0% |
| Four windows, changing fragmented visibility | 12.404 ms | 12.724 ms | +2.6% |

Fixed-layout clipping calls fall from one/four to zero. Changed layouts still
make four calls. The 10% controlled target passes; the changed-layout overhead
is within the planned 5% investigation threshold.

## Matched application workload

US3 reuses the frozen final guest image for the final capture. The Counter and
all guest workload source remain unchanged. C image segments and zero-fill
records are byte-for-byte identical to the baseline. Compiler/runtime, ROM,
emulator, machine settings and complete bank-zero reservation maps match.

| Workload | Before caller CPU median | After caller CPU median | Change |
| --- | ---: | ---: | ---: |
| Fragmented Counter tick | 39.306 ms | 36.686 ms | -6.7% |
| Full fragmented Counter redraw | 96.668 ms | 93.921 ms | -2.8% |
| Uncovered Counter redraw | 40.971 ms | 40.716 ms | -0.6% |
| Move and redraw | 49.052 ms | 49.355 ms | +0.6% |

Tick elapsed median falls from 50.782 to 47.494 ms. Its BEGIN median falls
from 9.590 to 6.938 ms, with zero UPDATE RPCs in both cohorts; END remains
about 11.3 ms. Clipping calls fall from four to zero while paint-readiness
checks remain. The 5% total caller CPU target passes. Object-only caller CPU
changes by less than 0.3%; the immediate timer changes by -0.1%. Display
admission, release, borrow and submission counts match outside the exposure
control.

All eleven full-frame digests match. The run retains 67 measured operations
after the same warmups and passes 505 fixture assertions, normal retirement,
heap/ownership and guard
checks. Inclusive helper costs overlap; these samples do not establish tail
latency or loaded-application/input-to-scanout performance.

The first US3 capture stopped at the observer's minimum-two-redraw guard.
A diagnostic replay showed one legal bounding redraw `[72,43,352,48]` in
later exposure bursts, covering all three closed windows. All eleven frames
still matched. The [diagnostic record](../development/update-snapshot-us3-diagnostic.json)
preserves that attempt and the unprofiled replay. The observer now checks
bounded geometry and complete exposure coverage; focused host tests reject
missing, duplicate and unexpectedly broad damage. Every recorded baseline
exposure also passes the new oracle. The guest and GUI coalescing policy are
unchanged, and the original observer remains archived.
The two fewer delivered redraws account for six fewer loop assertions than
the 511-assertion baseline.

Later repair area grows from 5,376 to 16,896 pixels per burst while delivered
messages fall from two to one, reducing the number of UPDATE scopes. Exposure
caller CPU and elapsed medians therefore have different repair/admission
work; their reductions are not counted as direct snapshot savings. The
independent geometry/pixel checks continue to enforce correct repair.

The old 349-file build manifest omits native GUI modules. The final source
audit supplements it with 863 production files recovered from baseline Git
commit `ac33f02b` and frozen current inputs. Exactly eight native/layout files
differ. Observer inputs and their validation correction are recorded
separately rather than treating the old manifest as a complete source closure.

The final host suite passes **668 tests, with four historical-source skips**.
The additional raw/optimized ABI probe checks the layout epoch's exact offset
and passes 127 checks per mode. Full release qualification was not run.

| Commit | Slice |
| --- | --- |
| `df256ce3` | Implementation plan |
| `96752e04` | US0 profiling and mechanism selection |
| `51ce0675` | US1 behavior before replacement |
| `7dbf8184` | US2 bounded geometry reuse |
| `ec5bec79` | US3 exposure-oracle correction and ABI offset check |

The final US3 evidence commit completes the development gate.

## Memory and emitted code

Scene storage grows by four upper-RAM bytes, from 9,186 to 9,190. The embedded
desktop Service grows by the same four bytes. Private AES Window records grow
eight aligned bytes each, adding 48 bytes to the six-window service table.
No second region array or hot-path allocation is introduced. Native callers
must rebuild for the Layers/Desktop record versions; the AES view/wire and
C import ABI are unchanged.

The measured Publish body shrinks from 2,271 to 2,226 bytes. Its fixed frame
grows from 36 to 40 bytes and compiler-reported local stack peak from 50 to 54;
these are not complete Task call-chain bounds. The controlled root stack
watermark grows from 283 to 287 bytes within its existing 1,536-byte reservation.
Full native executable segments grow by 323 bytes; C executable/initialized
segments and zero-fill records are unchanged. The matched run touches 740 root
stack bytes, leaving 540 above the protected floor. These observed watermarks
depend on execution and interrupt phase.

Reserved bank-zero growth is **0 fixed/root/kernel bytes, 0 per public Task
and 0 idle bytes**, including guards, alignment and unused capacity. Complete
budget, Task-pool, runtime and phase-reservation maps match the before builds.
These are development checks; full hosted/hardware qualification and demo
delivery remain separate.
