# Caller-local AES UPDATE

[Plan](../plans/gem4xe/caller-local-update-plan.md) · [History](README.md)

## UL1: shared policy

`AESLOCKS.Attempt` owns decoding and completed transitions, including snapshot,
cache and synchronous paint-journal accounting. RPC admission retains the pending
queue; its eligible-waiter scan shares acquisition. Public UPDATE remains RPC.

Development checks: the unchanged optimized lock fixture passes 138 assertions
before and after, covering recursion, TRY, wrong-owner release, overflow, MCTRL
and pending clients. The historical fixture timeout did not reproduce on the
current pin. Stack/domain guards and cleanup pass. Host checks: 487 tests,
four historical-source skips. No full qualification matrix was run.

The clean parent `f37d5f6` was frozen with OF816 in
`build/caller-local-update/before` before production edits. Its idle dialog trace
and Files initial-window capture are retained for UL4. Both application runs
complete normally, including package boot and exit.

UL1 reserves **0 additional bank-zero bytes**: fixed 0, per public Task 0, idle 0,
including guards, alignment and unused capacity. No upper-RAM state or VRAM is
added; existing stack reservations are unchanged.

## UL2: presenter handoff

The worker claims the private policy gate before its loop condition and closes
it across input, controls, painting, settlement, caching and readiness checks.
It computes the scheduling action before publishing availability. Stop exits
retain closed ownership. Clients cannot execute policy across that boundary;
a preempted caller makes the presenter wait on its existing AES signal.

The small optimized emitted gate fixture passes **24 assertions**, forcing
claim exclusion, inherited Forbid nesting, natural VBI preemption, peer Task
progress, release before/after waiter publication, shutdown/retained-work
rejection, preservation of unrelated pending input and complete cleanup. The
real presenter still passes the **138-assertion** optimized lock fixture.
Host checks pass 487 tests with four skips. Guards remain intact; no full
qualification matrix was run.

UL2 adds **two upper-RAM service bytes**. Reserved bank-zero delta is **0 fixed,
0 per public Task, 0 idle**, including guards/alignment/capacity. There is no
new signal allocation, Task, VRAM storage or stack reservation.

```sh
python3 tools/test_aes_gate.py --output build/caller-local-update/ul2-gate
```

## UL3: caller-local BEGIN/END

The resident binding calls one private C/Action entry. A gate miss or blocking
contention releases transient ownership and submits the unchanged RPC operation.
Handled TRY failure does not submit. Local calls leave transport sequence numbers
unchanged; MCTRL remains RPC. Final END consumes the existing journal and sends
the service wake after publishing the released policy gate.

The faster path exposed an existing dependency cycle: an exiting client could
wait for a mouse owner while that owner's UPDATE upgrade waited for the pending
exit. Shared eligibility now permits the existing mouse owner to upgrade past
pending window/exit work, while retaining native readiness checks. This extends
the existing owner exception to work that itself depends on that owner. The
second contention round in the lock fixture exercises the formerly stuck case.

Development checks:

- Small raw/optimized bridge probe: full 32-bit argument, native result, both C
  stack parities, S/D/DBR, preserved C DP and VBI preemption.
- Optimized lock fixture: **181 assertions**, including zero-message nested
  local pairs, both mixed local/RPC pairs, inherited Forbid, an older unadmitted
  request, TRY, MCTRL overlap/upgrade, two contention orders, six open owned
  windows, detach and resource restoration.
- Optimized binding fixture: **324 assertions**, including ordinary/PB calls,
  multiple contexts, registration reuse and lifecycle.
- Optimized cache fixture: **220 assertions** plus 31 physical observations,
  including hidden edits, scoped sibling eligibility and exact restored pixels.
- Host suite: **487 tests, four skips**. This is development coverage, not full
  qualification or hardware qualification.

The six-window lock case peaks at 709 caller stack bytes, leaving 571 bytes above
its protected floor. The binding case peaks at 827, leaving 453. Guards remain
intact and reservations are unchanged. UL3 bank-zero delta is **0 fixed, 0 per
public Task, 0 idle**, including guards/alignment/capacity; no VRAM is added.
The bound native entry pointer uses three upper-RAM bytes. The optimized native
local entry is 783 code bytes; the common owner-upgrade fix adds 54 bytes.
UL1's shared lock refactor adds 282 native code bytes. UL2's gate routines total
1,243 native code bytes, plus their worker boundary calls.

```sh
python3 tools/test_aes_update_bridge.py --output build/caller-local-update/ul3-bridge
```

## UL4: measured safe idle handoff

The first local implementation still sent most idle BEGIN calls through RPC:
only 31 of 120 complete dialog pairs were local. Outer END woke the presenter,
whose mostly idle turn occupied about 12 ms of Task CPU before reopening the
gate. Local END alone did not make the following BEGIN reliably local.

The final worker recognizes an AES-only notification with no queued messages,
lock/window waiters, pending publication, input, console output or native GUI
work. It keeps the gate closed, performs normal cache maintenance, and publishes
availability before returning to Wait. A started cache continuation takes the
normal worker path. All other wakes retain the full protected turn. Signals
arriving during the checks remain pending for Wait. There is no early metadata
access past publication, polling loop, deferred journal, new priority or change
to preemption/display ownership.

Passive trace helpers now distinguish local calls, complete local pairs and
fallbacks during presenter execution, retained native work, ownership/gesture
conflicts and older queued requests. They charge relocated policy CPU to the
caller. Loaded C callers use observed RTL boundaries as well as linked JSL
return sites; no diagnostic hooks or counters enter the target image.

The bounded concurrent setup exposed a Windows-menu focus failure with Counter
running, reproduced on the unchanged parent as well as the candidate. Its cause
is not established here. The matched load sequence uses exposed title-bar
clicks to select Shell, Counter and Control Panel. This keeps the unresolved
menu issue outside the UPDATE comparison; it is not a claim that the menu issue
is fixed.

### Matched application results

[Compact measurements and input hashes](../development/caller-local-update.json)
retain the clean `f37d5f6` parent and final package. Both use the pinned
`05c01f39` compiler, the same AltirraOS ROM/emulator, PAL, 8x CPU, accurate disk,
geometry and pointer inputs. The table uses passive cycle-derived means across
three measured batches, not input-latency percentiles. The benchmark's normal
calibration chose 200 rather than 100 operations per batch for the final
unclipped text rows; normalized drawing calls per operation are identical.

| Workload | Before ms/op | After ms/op | Complete local pairs after |
| --- | ---: | ---: | ---: |
| Solid bars | 17.846 | 13.430 | 113/150 |
| Text, even X | 20.972 | 19.546 | 17/150 |
| Text, odd X | 21.018 | 20.073 | 0/150 |
| Clipped text | 27.850 | 22.720 | 62/75 |
| Five-object dialog | 91.999 | 70.430 | 76/120 |

The specified idle dialog workload now completes most pairs locally; its UPDATE
messages fall from 240 to 44. This is **not universal local admission**: the
unclipped text loops repeatedly arrive during an occupied presenter turn. Their
remaining fallbacks and modest whole-operation gains are recorded explicitly.
Do not infer a local-pair percentage for other workloads from the dialog.

| Dialog component, mean ms/op | Before | After |
| --- | ---: | ---: |
| BEGIN elapsed | 18.925 | 9.060 |
| END elapsed | 15.086 | 12.904 |
| BEGIN + END elapsed | 34.011 | 21.965 |
| Whole operation caller CPU | 44.186 | 46.737 |
| Whole operation presenter CPU | 31.609 | 11.281 |
| Whole operation caller off-Task time | 38.385 | 13.691 |
| Interrupts while caller runs | 9.427 | 10.002 |

Presenter CPU is part of caller off-Task time, not an additional elapsed-time
component. UPDATE caller CPU rises from 5.613 to 9.378 ms per pair because native
policy now executes there. The unchanged dialog still makes eight drawing
borrows/submissions/uploads, 14 fill calls, 42 solid records and three glyph
runs per operation. The gain does not come from drawing less.

Files observations:

- One New Window: frame completion 741.9 → 742.2 ms; complete window
  1083.0 → 1063.0 ms, sampled once per PAL frame. One content paint, no later
  changed frame, four frame batches and two frame-side submissions remain.
  Its first content-paint interval is 193.9 → 191.7 ms; BEGIN falls back while
  the presenter is still active and END is local.
- Three settled icon-selection paint intervals: 142.0/139.0/142.4 →
  122.3/122.0/122.3 ms. All three complete pairs are local; these are BEGIN to
  END intervals, not physical key-to-pixel latency. The list selection is
  175.1 → 174.7 ms and retains one RPC BEGIN.
- The summary pixels and pointer position stay unchanged. Expected pointer
  erasure over overlapping paint remains observable. Cover/expose performs
  zero application paints, captures or patches and uses the existing cache
  restores. A no-op selection performs no paint or UPDATE.
- The deliberately uncached warm-up close regresses **401.2 → 461.3 ms**.
  About 47 ms of the extra time occurs before the desktop application's BEGIN:
  presenter CPU in that interval rises 166.6 → 205.9 ms. Actual repaint work
  is essentially unchanged (paint-pump CPU 43.5 → 43.4 ms), icons outside the
  exposure remain untouched, and the application paint interval rises
  91.9 → 108.3 ms. This is a remaining presenter/admission cost, not extra
  icon rendering. Keep it as a follow-up; this slice is not an across-the-board
  close/restore improvement.

The concurrent smoke keeps visible Counter, sustained CAT output and physical
pointer/button input active. Both builds finish normally and pass the final
pixel/ownership checks. Three button samples have median 140.5 → 140.1 ms and
maximum 180.4 → 220.5 ms; three pointer samples have median 100.3 → 100.1 ms.
The maximum button observation worsens despite the unchanged median. This small
cohort does not establish a tail-latency improvement or regression. All ten
complete pairs observed under the final loaded sequence need at least one RPC;
misses are presenter execution or retained native work. Counter and console
both advance. No priority or preemption experiment was reintroduced.

### Validation, storage and preview

Final development checks: 489 host tests with four skips, 181 optimized lock
assertions with zero failures, the specified idle/Files/concurrent captures and
normal boot/application/EXIT on the exact generated OF816 ZIP. UL3's raw/opt
bridge, gate, binding and cache evidence remains applicable. No release matrix
or real-hardware qualification was run.

UL4 reserves **0 additional bank-zero bytes**: fixed 0, per public Task 0 and
idle 0, including guards, alignment and unused capacity. The worker's used local
frame grows by four bytes within its unchanged stack reservation. Relative to
UL3, the worker adds 516 native code bytes and the settlement hint 537; no upper
persistent state or VRAM is added in UL4. Across the C-binding change, resident
C executable storage grows by 225 bytes and linked zero-fill by two bytes
(the three-byte entry pointer uses existing padding). The complete plan's
logical persistent state is two service bytes plus that pointer.

The final ordinary application capture leaves at least 296 bytes above the
protected floor in every public Task stack; the presenter leaves 1469. The
six-owned-window fixture still leaves 571 bytes in its caller and intact guards.

```sh
python3 tools/build_demo.py --gem-desktop --release-compiler \
  --output build/caller-local-update/demo-settled
build/caller-local-update/demo-settled/launch-altirra.command
```

Distribute `build/caller-local-update/demo-settled/exec816-demo.zip`. It includes
OF816, the five-second autoboot, matching system/WORK disks, pinned ROM, guide,
notices and checksums. Traces and intermediates remain outside the ZIP.
