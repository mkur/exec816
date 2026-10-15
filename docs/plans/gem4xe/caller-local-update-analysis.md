# Caller-local uncontended AES UPDATE

[GEM plans](README.md) · [Implementation plan](caller-local-update-plan.md) ·
[Current UPDATE contract](../../reference/aes.md) ·
[Hybrid design](hybrid-aes-vdi-design.md#shared-ownership-and-blocking) ·
[Physical ownership measurements](../../history/display-bridge-cost.md)

Status: analysis and proposed direction; no implementation. Inspected against
`8b39fc8`, with the subsequent physical-bridge measurement files in the working
tree. The current hybrid design deliberately left UPDATE in the presenter;
this is the analysis of that deferred migration.

## Recommendation

Make successful uncontended BEGIN and END ordinary library calls executing in
the application Task. Reuse the native AES lock, snapshot and cache routines.
Keep the existing message path for contention and cases where the presenter
cannot safely lend access to its metadata. Preserve the GEM entry points and
the current UPDATE/MCTRL semantics.

This is a worthwhile next performance change, with a larger opportunity than
specializing the physical display bridge. It requires an explicit presenter
handoff: changing only `wind_update()` or the owner field is unsafe. Start with
a conservative fast path at published presenter safe points; measure how often
real application updates can take it before extending its availability.

No new kernel operation, Task, scheduler priority, timer or general-purpose
semaphore is needed. Physical display ownership stays separate and remains
available to an admitted drawing caller while the presenter does unrelated
CPU work.

## What happens today

`c/calypsi/aes.c:update()` obtains the caller context, prepares an UPDATE request,
then always calls `ExecAESSubmit()`. That performs PutMsg, checks the private
reply port and waits if necessary. The presenter dispatches the request to
`AESLOCKS.Request`, performs the operation and replies. Both BEGIN and END,
including nesting, take this route.

| Phase | Required work beyond the owner field |
| --- | --- |
| First BEGIN | Check update/mouse ownership, gesture eligibility, pending waiters and native readiness; preserve the outer window scope; begin cache-change tracking; touch paint epochs; publish visible window snapshots; publish update depth and mouse eligibility. |
| Nested BEGIN/END | Preserve recursion and the outer scope, keep shared view depths and caller depths consistent, preserve explicit mouse holds. |
| Final END | Consume paint reports, account for hidden/unreported changes, settle Layers repaint obligations and cache validity, clear update ownership and release its implicit mouse hold, publish input eligibility and allow pending work to progress. |

The relevant implementation is in `lib/aes/aeslocks.act`,
`aeswindowstate.act`, `aesmouse.act` and `lib/desktop/deskcache.act`.
`AESWINDOWSTATE.EndUpdate` explicitly relies on the outstanding END reply to
freeze the caller's paint journal. A local END must instead consume that journal
synchronously before returning and allowing its next reuse.

The binding also keeps `updateDepth` and `mouseDepth`; the service and published
window views have their own corresponding state. Those are observations of
one ownership protocol, not independent locks.

## Evidence and likely benefit

The last packaged dialog trace has the following costs per complete dialog.
These are the `9926859` GUI measurements, **before removal of the drawing
preemption experiment**. They establish where work occurs, not a current-build
latency prediction. The later bridge measurement does use the preemptible code.

| Observation | Measured cost |
| --- | ---: |
| Two `wind_update` calls, elapsed | 31.550 ms |
| Caller CPU inside those calls | 6.651 ms |
| Time away from the caller inside them | 23.521 ms |
| Two `ExecAESSubmit` calls, caller CPU; included above | 5.114 ms |
| Two `AESLOCKS.Request` calls, presenter CPU | 6.098 ms |
| Two `AESSTATE.Reply` calls, presenter CPU | 2.200 ms |
| BeginUpdate snapshot/cache work; included in lock policy | 1.699 ms |
| EndUpdate repaint/cache work; included in lock policy | 1.789 ms |

Source: [packaged GUI evidence](../../development/display-ownership-entry.json),
`gui_followup`, and its retained `build/display-entry-gui/trace-idle/trace-results.json`.
These inclusive intervals overlap; do not add every row. Off-caller time includes
presenter work and scheduling, and is not all avoidable waiting.

A successful local pair removes request transport, dispatch/reply work and the
need to wait for presenter scheduling twice. It retains the lock policy and
publication work. Approximately 6.1 ms of existing presenter policy CPU would
move into the caller if reused unchanged. Caller CPU can therefore increase
while total CPU and elapsed latency fall. The present binding's context/setup
cost and the new short handoff/bridge costs also remain. Sub-millisecond UPDATE
pairs are not a credible first target with this policy unchanged.

For comparison, removing the entire client physical-display bridge would save
only about 0.56 ms CPU across the dialog's eight drawing borrows. No speedup for
the proposed UPDATE path has been measured yet.

## Why a short Forbid around the owner field is insufficient

Today the presenter serializes both UPDATE admission and its conflicting work
by executing both itself. Several readiness checks rely on that fact. For
example, `DESKPAINT.Pump()` checks `AESLOCKS.PaintBlocked()`, selects a layer and
later calls `LAYERS.BeginPaint()`.

With an independent caller-side claim, this becomes possible:

1. Presenter sees no UPDATE owner and passes its painting check.
2. VBI preempts it before the scene transaction begins.
3. Client sees no owner and `scene.busy=0`, then acquires UPDATE.
4. Presenter resumes after its earlier check and starts conflicting work.

The same issue applies to window/control mutation, cache maintenance, snapshot
publication and input eligibility. `scene.busy=0` identifies no retained scene
transaction; it does not prove that the presenter has no operation in progress.

Nor should a caller simply reuse `AESLOCKS.NativeReady()` as a pure predicate:
it calls owner-side `DISPLAY.Blocked()`, which can arm a presenter wake hint.
The presenter should establish and publish the safe opportunity itself.

Holding Forbid through snapshot construction and END processing would prevent
this race, but would make several milliseconds of policy non-preemptible.
That would bring back the scheduling restriction just removed from drawing.
Use short exclusion only for publishing and claiming the handoff.

## Smallest coherent handoff

Introduce one small, private AES policy gate in upper RAM. It distinguishes
presenter execution, an available safe point and a caller executing BEGIN/END
bookkeeping. This is not the UPDATE lock and does not last for the application's
drawing interval.

The first implementation should publish availability only at a controlled
presenter boundary:

- The current control/input/model work is settled; no function is suspended
  between a conflicting check and its mutation.
- No retained scene transaction, console fragment/DMA, gathered batch or
  visible drag outline prevents the existing UPDATE admission.
- The presenter has finished every policy query needed to decide whether to
  wait or yield. After publication it can only wait/yield or reclaim the gate
  before touching the protected state again.

Cover the presenter's whole policy turn initially, including its final settle,
cache and readiness checks. This is easier to audit than adding independent
locks around every window and cache field. Startup and shutdown keep local
admission closed. A retained transaction keeps the fast path unavailable even
while its Task sleeps; normal queued UPDATE admission continues to wait for it.

Under a short Forbid, the caller claims the available gate. It then releases
Forbid and performs the bounded, nonblocking native UPDATE work with normal
Task preemption. If the presenter runs meanwhile, it must observe the gate
before beginning another protected turn and wait on its existing signal.
Publish that waiting state before waiting; the caller releases the gate and
wakes it if needed. Preserve check-before-Wait and never clear the wake between
publication and Wait. IRQ/NMI capture and device completion retain their own
existing protocols and never acquire this Task-only gate.

While parked specifically on this gate, use the existing AES service wake bit;
do not repeatedly retry because an unconsumed input or display bit remains set.
Retain those events for normal processing after the gate is reclaimed.

The native UPDATE helper must not wait for a presenter reply, invoke application
callbacks, draw or retain asynchronous work while it owns the gate. The current
snapshot/cache bookkeeping paths do not need such work. Hardware fences and
renderer admission remain in the existing drawing path.

The gate is released before BEGIN returns and before application drawing starts.
While the application owns UPDATE, the presenter can still perform the work
already permitted by UPDATE, including input service. END briefly claims the
gate again to retire the journal. If either claim cannot be made, use the
existing message path. A busy internal gate is a fast-path miss, not a new GEM
error and not permission to spin.

This initial policy will miss when the presenter is preempted inside an otherwise
non-conflicting turn. That is an explicit limit, not a claim that every logically
uncontended call becomes local. Record this miss reason separately. Narrower
safe points are a later option if measurements show that this limit defeats the
normal idle application case.

## BEGIN, END and fallback rules

**Outer BEGIN:** after claiming the policy gate, check the existing ownership and
gesture conditions. Respect both the admitted lock queue and older requests
still in the service message port. Checking only `lockCount` would let a local
caller bypass a request waiting to be admitted. Retain the existing owner
recursion/upgrade exception for peers that depend on that owner's release.
Then execute the same acquisition, cache-begin, snapshot and publication work
used by the RPC path. Return success only when the caller can safely use those
views.

**Nested calls:** keep the outer `ExecAESBeginUpdate(window)` scope, shared
depths and caller depths. Use the same helper and fallback rules initially;
there is no need for a separate recursive-lock implementation.

**Final END:** consume the paint journal and finish cache/paint metadata before
clearing the last update hold. Preserve any explicit MCTRL hold. Release the
policy gate and notify the presenter through its existing signal so queued
locks, deferred native painting and cache work can advance. One signal does not
require a reply wait. Start with a notification on every outer END; deciding
when that signal can be omitted is a later measured optimization. If the
presenter parked on the gate, gate release must wake it regardless of operation.
Signal and ordinary preemption can still schedule another Task; the improvement
is removal of the required request/reply waits, not a promise of zero switches.

**Slow path:** drop any attempted policy claim before `ExecAESSubmit`; let the
presenter re-evaluate eligibility and retain its existing pending request/FIFO.
Do not add another waiter queue or a second signal/wait protocol for clients.
Keep `BEG_MCTRL`/`END_MCTRL` on the existing RPC path for the first change, while
preserving their interaction with local UPDATE.

**TRY:** preserve `BEG_CHECK` and its existing result/diagnostic. If the gate is
available, eligibility can be decided locally. If it is unavailable, the
unchanged TRY request can take the RPC path; do not report lock contention merely
because the internal safe point was unavailable.

**Transport and lifetime:** local operations do not consume RPC sequence numbers;
both sides advance those only for actual messages. Mark the caller context busy
during the native helper so its request and journal cannot be reused. Registration
still establishes identity/lifetime, and exit uses the existing retirement path.
Correct binding use remains the caller's responsibility. Avoid repeating the
RPC packet and pointer audit inside the direct path.

## Code and interface impact

Keep one native implementation of the lock transitions. Factor request decoding
and queue handling away from the shared acquire/release work in `aeslocks.act`.
The C binding calls a bound resident native helper, following existing library
bridge conventions; it should not mirror private `AESSTATE.Service` layouts or
reimplement the policy in C. With only four clients, the existing bounded client
lookup is adequate initially; a new registration-handle system is unnecessary.

Likely touch points are:

- `c/calypsi/aes.c`: fast attempt before RPC, one context lookup per public
  operation, common success/depth handling. Pass the context already obtained
  by `ExecAESBeginUpdate` rather than looking it up again in `update`.
- Resident C/Action binding and startup binding generation: one internal native
  UPDATE entry, with preserved C DP/register/stack context.
- `aeslocks.act`, `aeshost.act`, `aesstate.act`: shared transitions, admission
  gate and wake handling.
- `consoledriver.act` and `deskhost.act`: auditable presenter entry/exit boundaries,
  including the wait/yield tail and shutdown.
- `aeswindowstate.act`, AES and Layers documentation: the policy helper can run
  in either Task under serialized metadata access. Existing scene tokens and
  cache ownership rules remain in force.

No new public GEM function is needed. Prefer private resident state so the wire
layout and loaded application import table can remain unchanged; verify that
against the actual binding implementation. If an exposed layout changes, update
its generated definitions and rebuild callers rather than adding compatibility.

The intended reservation delta is zero bank-zero bytes, with a few bytes of
upper policy state and an upper native-entry binding. Exact sizes belong in the
implementation report. Moving native snapshot/cache code onto application
stacks requires a focused stack-headroom measurement. Increase stack reservations
if justified rather than forcing a large refactor; report any per-Task bank-zero
increase including alignment and guards.

## What must be demonstrated before accepting it

The decisive comparison is an idle window repaint: local BEGIN, unchanged
drawing, local END, then normal input and exposure. Record local success/miss
counts, caller/presenter CPU and elapsed time separately. Measure the current
preemptible parent in that focused comparison; do not reuse the older packaged
dialog as a matched before/after baseline.

Use a small emitted-code check for the C/Action boundary in raw and optimized
modes, then optimized behavioral cases for two clients, queued native output,
nesting/TRY/MCTRL, scope preservation, hidden changes and cache restoration.
Explicitly interrupt the presenter after a former readiness check, at safe-point
publication/reclaim, and around caller release/waiter publication. Check older
unadmitted requests, synchronous journal reuse, exit, guards and normal cleanup.

The older [rectangle record](../../history/rectangle-overhead.md) documents a
pre-existing standalone lock-queue fixture timeout. Resolve its relevance or
use a focused replacement that actually covers these races; do not count that
historical case as passing. Full release matrices are not required for this
development change.

Accept the fast path when idle real application updates normally avoid both
round trips, preserve pixels/cache/input behavior and reduce elapsed cost.
Report misses under pointer activity and native output rather than hiding them
in an average. Do not enlarge drawing batches, change preemption or introduce
new cache semantics as part of this migration.
