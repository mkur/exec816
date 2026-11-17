# One grant for packed-edge screen copies

[GEM plans](../plans/gem4xe/README.md) ·
[Inputs and measurements](../development/gem-copy-grant.json) ·
[Previous mask-height slice](gem-mask-height.md) ·
[Current display contract](../reference/display.md)

Same-parity screen copies now retain one physical display grant through
source-edge capture, the aligned interior, masked restoration and the final
fence. Captured edge columns stay in the existing VRAM scratch. The matched
MGVIEW copy drops from 27–28 to **13–14 ms Task CPU**, with zero CPU edge reads
or writes. Application source, geometry and the public ABI remain unchanged.

## Structure and implementation

The user approved this complete-copy grant on 2026-11-17. MagiC's pinned
`AESOBJ.S:599–613` `vro_cpyfm` binding issues one opaque-raster VDI call and
returns after its trap. GEM4XE's pinned `dev_copy_form` separates packed edge
columns from its byte-aligned interior; the provenance and source paths remain
in the [earlier copy plan](../plans/gem4xe/odd-edge-screen-copy-plan.md).
The Exec adaptation now retains its existing platform resource for that whole
copy instead of introducing an intermediate physical handoff.

`GemDrawingCopyBorrow` acquires once, erases intersecting source/destination
overlays, captures every source edge into `$36000` scratch, fences that capture,
performs the existing typed interior copy and restores destination nibbles from
the saved columns. Capturing both source edges before interior writes preserves
horizontal and diagonal overlap. The caller's descriptor is restored after
the interior call, including failure. The shared borrower retirement path
supplies the final fence and release on success or an operational failure.

Normal Task preemption and IRQ/NMI delivery continue. Competing renderers wait
for physical access and cannot overwrite scratch during the copy. The existing
typed encoder touches screen and command storage, leaving these captured
columns intact. Ownership/fault retention, the 640×240 typed-screen bound,
64-record/8,192-work raw lists and work-derived mask heights are unchanged.
No new platform service or GUI coordination mechanism is introduced.

The unused upper-buffer argument is removed from the internal drawing method
and both production callers. The workstation's existing 642-byte raster buffer
remains available to other modes; its size/layout and the application ABI do
not change. Source-edge CPU transfers and the second admission are removed.
VRAM and all reserved memory capacities stay fixed.

## Focused development validation

The optimized emitted copy/mask probe passes **58 cases**. Its complete-source
pixel oracle checks nibble preservation, one/two edges, zero-interior copies,
full-height/screen boundaries and horizontal/vertical/diagonal overlap. It
checks one admission, descriptor restoration, zero CPU edge transfers and
capture-submission/capture-fence/interior-submission/restoration/final-fence
failures. Modeled scratch is replaced at every release; an intermediate
release would violate the one-grant assertion and invalidate captured edges.
The existing eighteen mask height/work/capacity cases remain covered.

Small raw and optimized C/Action copy-admission probes pass **24 assertions
each**, covering the updated internal call and result/diagnostic publication.
The optimized fixture supplies tripwire bindings for retained lifecycle helpers
and checks they are never called. This repairs a fixture link omission without
changing production lifecycle behavior. The host suite passes **724 tests,
four skipped**. The display-borrow observation hooks also match the new single
admission; no broader display matrix was run.

Only the drawing adapter and its two internal callers were recompiled; the
remaining 54 provider objects were reused with checked source/header/tool inputs.
The provider was relinked and native loader rebuilt. MGVIEW's APP was reused.
No Counter, QED, catalog, demo or release build/check ran. These are development
checks and two-action observations.

## Matched MGVIEW results

The baseline is `build/gem-mask-height/scroll`. APP/document hashes, font, work
`(1,22,616,200)`, frame geometry, parked pointer, pinned ROM and PAL/8× machine
configuration match. Each scroll still copies 616×192 pixels, draws one exposed
text row and paints the selected scrollbar subtree once.

| Per scroll | Down before → after | Up before → after |
| --- | ---: | ---: |
| `vro_cpyfm` Task CPU | 27.045 → **13.701 ms** | 28.083 → **13.228 ms** |
| `vro_cpyfm` elapsed | 34.440 → **17.443 ms** | 35.700 → **16.838 ms** |
| Copy grants | 2 → **1** | 2 → **1** |
| CPU edge reads/writes | 1/1 → **0/0** | 1/1 → **0/0** |
| Copy fence calls | 12 → **8** | 12 → **8** |
| Whole `set_shift` Task CPU | 96.927 → **83.500 ms** | 98.044 → **82.503 ms** |
| Whole `set_shift` elapsed | 134.019 → **116.953 ms** | 135.329 → **113.155 ms** |
| Key offered → complete viewport observed | 140.112 → **120.031 ms** | 140.339 → **140.308 ms** |

Inclusive costs overlap and must not be added. The one typed interior copy and
two mask-list submissions remain; this slice removes CPU transfers and a
handoff rather than combining hardware lists or weakening fences. Scrollbar
paint remains about 14 ms CPU, and exposed-row drawing about 19 ms CPU.

Both viewport pixel hashes match. The final full window, including its frame
and scrollbar, also matches all **140,526 pixels** with the same BGRA hash.
The single copy grant lasts **14.924/14.369 ms elapsed** down/up. During it the
viewer is off-Task for **0.733/0.733 ms**, with native interrupt time separately
recorded. Normal scheduling therefore continues while scratch is retained.

The new completion polling brackets are **104.299–120.031 ms down** and
**122.350–140.308 ms up**. The up action enters `set_shift` 6.447 ms later than
the baseline; its complete-viewport observation remains in the same PAL-frame
bracket despite shorter processing. These two samples establish a copy/CPU
reduction and a lower observed down latency, not an observed up latency gain
or a latency distribution.

Three Process lifetimes complete with heap/ownership restoration and intact
stack/domain guards. MGVIEW touches 1,302 bytes in its existing 2,560-byte pool,
leaving 1,002 above the ordinary floor. Generated bank-zero budget, runtime
reservations and every Task pool exactly match the baseline: **0 added fixed,
root, kernel, idle and per-public-Task reserved bytes**, including guards,
alignment and unused capacity. No buffer, VRAM region, Task, signal or service
is added.
