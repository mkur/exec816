# END_UPDATE audit

[GEM port](../plans/gem4xe/README.md) ·
[Measurements and frozen inputs](../development/gem-end-update-audit.json) ·
[Previous text slice](gem-text-preparation.md) ·
[MagiC source model](../architecture/magic.md)

Final `wind_update(END_UPDATE)` takes **17.34/17.45 ms elapsed** down/up,
but native UPDATE release costs **0.069 ms Task CPU**. The largest elapsed
interval is **9.06 ms off-Task at Permit after the semaphore is released**.
SCRENMGR runs one wake cycle costing **6.81 ms CPU**, with no interaction,
UPDATE acquisition or VBXE submission. This audit changes observation tools
and documentation only.

## Frozen observation

The cached optimized native/provider/APP from the text-preparation slice run
unchanged. One down key and one up key scroll the same document in the same
616×200 work area. The observer decodes native entries, calls and RTLs and
resolves linked C entries; it adds no guest instructions. The first capture
locates the release interval; a second adds C mouse/display-owner boundaries.
Both reproduce the baseline phase timings and viewport observations exactly.
Subsequent reporting changes use the retained trace without running the guest.

```sh
python3 tools/measure_mgview.py \
  --cache build/gem-text-preparation/viewer \
  --output build/gem-end-update/detail \
  --end-detail --expect-copy-units 1
```

Task CPU is a conservative residency charge, including gateway, scheduler
return work and bus stalls. Native interrupt intervals and other Tasks are
separate. It is not isolated routine instruction time. In particular, the
direction-dependent placement of about 0.62 ms between context lookup and
invalidation does not establish a different algorithmic cost. Disjoint stages
reconcile to END's CPU, off-Task, interrupt and elapsed totals; peer CPU plus
peer interrupts reconcile to all off-Task time.

| Entire END call | Down | Up |
| --- | ---: | ---: |
| Elapsed | 17.343 ms | 17.448 ms |
| Viewer Task CPU | 6.231 ms | 6.233 ms |
| Viewer native interrupts | 1.372 ms | 1.424 ms |
| Other Tasks, including their interrupts | 9.740 ms | 9.791 ms |
| Entry to native release return | 7.459 ms | 7.566 ms |
| Native release return to END return | 9.884 ms | 9.881 ms |

Native release return conservatively bounds ownership release; it is not a
timestamp of the store clearing the owner. No SCRENMGR CPU occurs before
that boundary. Before it, the test controller accounts for 0.683/0.733 ms
off-Task, including interrupts. It runs the fixture's Yield-based rendezvous;
this is test workload, not a GUI worker.

## Caller sequence and CPU

The synchronous C binding enters
[AESLOCAL.Call](../../lib/aes/aeslocal.act), then
[AESLOCKS.Call/Release](../../lib/aes/aeslocks.act). The final painting level:

1. Clears the window's explicit update count and consumes the paint journal
   under native UPDATE ownership.
2. Clears service ownership/count bookkeeping and **unconditionally sets
   `UPDATE_WAITING`** for final painting release.
3. Calls input-snapshot publication.
4. Under Forbid, notifies SCRENMGR and releases the native semaphore.
5. Calls Permit; SCRENMGR and the controller run before the viewer returns.

| Disjoint viewer CPU stages | Down | Up |
| --- | ---: | ---: |
| C binding/context and native dispatch | 0.793 ms | 1.415 ms |
| Lock entry/decode | 0.289 ms | 0.290 ms |
| Window update flags | 0.157 ms | 0.151 ms |
| Journal and cache checks | 3.062 ms | 2.447 ms |
| Service release accounting | 0.148 ms | 0.148 ms |
| Snapshot publication and release dispatch | 0.205 ms | 0.205 ms |
| Final guard, notification and native release | 0.886 ms | 0.885 ms |
| Post-release Permit and native return | 0.624 ms | 0.624 ms |
| Remaining binding return | 0.068 ms | 0.068 ms |

The viewer performs no Wait or blocking semaphore Obtain inside END. Its final
Permit contains **all 9.057 ms** of post-release off-Task time. Notification's
public Signal alone costs **0.722 ms CPU**; native ReleaseSemaphore costs
**0.069 ms**. These are inclusive subintervals of the table, not extra charges.
The cheap native semaphore is working; the surrounding release path does
substantially more work.

## Journal/cache work is CPU bookkeeping here

[AESWINDOWSTATE.EndUpdate](../../lib/aes/aeswindowstate.act) prepares the
change, consumes one invalidation and one accepted paint report, updates pixel
readiness, and checks operation-owned cache maintenance.

| Disjoint journal CPU | Down | Up |
| --- | ---: | ---: |
| Change preparation/touch | 0.410 ms | 0.410 ms |
| Invalidation | 1.038 ms | 0.416 ms |
| Paint completion | 0.259 ms | 0.259 ms |
| Existing cache completion | 0.020 ms | 0.020 ms |
| Cache candidate scan | 0.779 ms | 0.785 ms |
| Remaining journal control/readiness | 0.557 ms | 0.557 ms |

There is **no cache capture or patch**. `DESKCACHE.EndChange` returns without
updating a slot. The later candidate scan reaches `DESKCACHE.Fits`, whose
observed width argument is **635** and result is zero. Its source requires an
even width for packed pixels. This is a width/alignment rejection, not evidence
of insufficient VRAM capacity. `DESKCACHEWORK.Capture` and `Maintain` return zero;
neither calls a physical capture/patch routine or submits a display copy.

`AESSNAPSHOT.Publish` also returns **zero**: the paint-only handoff changes
neither layout nor input routing, so it does not rebuild/copy the publication.
That whole call costs **0.188/0.189 ms CPU**, already included above.

## What SCRENMGR does after release

[SCRENMGR.Run](../../lib/aes/screnmgr.act) consumes the wake, calls
`AESHOST.Service`, calls `DESKINPUT.Present`, checks for interaction, calls
`Present` again, checks again and enters Wait. Both interaction checks return
zero; there is no `SystemBegin`, Obtain or scene mutation in this cycle.

| Disjoint SCRENMGR CPU during END | Down | Up |
| --- | ---: | ---: |
| Signal collection | 0.015 ms | 0.015 ms |
| Service/input refresh | 1.827 ms | 1.821 ms |
| Two mouse-presentation passes | 4.183 ms | 4.189 ms |
| Interaction checks | 0.075 ms | 0.075 ms |
| Wait entry/resume accounting | 0.620 ms | 0.622 ms |
| Other loop/control work | 0.090 ms | 0.088 ms |
| **Total** | **6.809 ms** | **6.810 ms** |

Within these phases, `AESMOUSE.RefreshSnapshot` costs **1.75–1.76 ms CPU**.
The cycle calls 22 native Forbid/Permit pairs, costing **2.43–2.44 ms CPU**
in total; these are included in the phases, not additive. C mouse guards
inside the adapter are included in its own charge.

Drawing leaves `CONSOLEBITMAP.drawingChanged` set. The first `Present` consumes
that hint and invokes one `CONSOLEBITMAP.Mouse`/`GemDrawingMouse` operation.
The C adapter costs **1.798 ms CPU**, including **0.335–0.336 ms** of display-owner
entry/end. It completes with status OK but performs **no VBXE submission,
read, write, copy or fence**. The pointer remains parked at (639,0). The
second `Present` repeats recipient selection/readiness checks without another
mouse-adapter call. This is bookkeeping for an unchanged physical result.

SCRENMGR's 6.81 ms CPU plus 1.45 ms interrupts accounts for 8.26 ms of the
9.06 ms post-release off-Task interval. The controller's 0.663 ms CPU and
0.132–0.133 ms interrupts account for the rest. No input.device, console backend
or competing application drawing executes in that interval in these samples.

## MagiC comparison and next boundary

At pin `28cfdd29aa16fef692cc287bad3046b44ddcce3d`,
`AESEVT.S:1508–1519` implements final `end_update` as decrement, then
`free_semaphore`, **`appl_yield`**, return. `free_semaphore` at 1532 selects the
oldest semaphore waiter and publishes readiness without switching inside that
helper. There is no END paint journal, cache scan or routing publication there.
`AESMAIN.S:4235–4287` shows SCRENMGR waiting on key, button, menu-rectangle and
message events, then acquiring UPDATE for the interaction. See the
[pinned source model and source links](../architecture/magic.md).

Exec therefore agrees on recursive ownership, native FIFO handoff and the
possibility that other Tasks run before END returns. **Off-Task time by itself
is not a MagiC mismatch.** Its normal Task preemption remains required.

The extra work is the pre-release journal/cache protocol and the unconditional
painting-release notification that drives an otherwise idle SCRENMGR through
snapshot and mouse work. No new platform service is required to explain either
cost: public semaphores, Signal, Forbid/Permit and Wait already provide the
necessary coordination.

The next proposed slice is to make this release wake depend on actual pending
manager work or an armed blocked continuation. Check the completed-drawing
hint against caller-side cursor restoration so a finished operation does not
create a redundant mouse turn. Preserve genuine interaction/cursor/device wakes,
native FIFO handoff and normal Task preemption. Audit the journal/cache contract
as a separate slice; removing it changes the extra paint/cache protocol and
requires an explicit design decision. Neither proposal is implemented here.
The observations do not establish how much latency either would save: useful
painting precedes END and the viewport observer samples PAL/COP boundaries.

## Development checks and resource delta

The final capture keeps baseline phase timings, both viewport hashes, the entire
672×240 scanout and all **140,526 final window pixels** identical. Each scroll
retains one viewport copy, one exposed-row draw, six physical borrower admissions
and eight raw submissions. Three Process lifetimes and heap/ownership restoration
pass in each capture; stack/domain guards remain intact. Host attribution tests
cover stage reconciliation across post-release scheduling, ambiguous release
rejection and clipping peer CPU/interrupts. The host suite passes **729 tests,
four skipped**.

No target compilation, QED, Counter, catalog, demo or release qualification ran.
The only native execution is the two passive MGVIEW captures described above.
No ABI, Task, buffer, heap reservation or gateway operation changes. Reserved
bank-zero delta is **0 fixed, root, kernel, idle and per-public-Task bytes**,
including guards, alignment and unused capacity. These are development audit
results, not hosted-system qualification.
