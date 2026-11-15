# Native semaphore implementation plan

[Plan index](README.md) · [Service design](native-semaphore-design.md) ·
[Task contract](../reference/tasks.md) ·
[Platform contract](../reference/platform.md) ·
[Testing policy](../contributing/testing.md)

Status: NS0–NS3 complete, NS4–NS5 pending, 2026-11-15. Basis: `831ed463`.
[Execution record](../history/native-semaphores.md). NS0–NS5 deliver the native
semaphore service described by the design. Progress and executable evidence are recorded in the execution record. Complete and commit each slice before
starting the next; record its actual scope and reservation deltas.

## Delivery boundary

Deliver `InitSemaphore`, `ObtainSemaphore`, `AttemptSemaphore` and
`ReleaseSemaphore` to ordinary Action! and C Tasks, including the loaded C
provider. Keep one native implementation of ownership and waiting. Init is
ordinary library initialization with no COP. The other operations use one
public `COP #$50` request each; contention continues within that activation.

Preserve the design's 12-byte object, recursive exclusive ownership, FIFO
direct handoff, signalless waiting, Task-removal gates and normal preemption.
Use the current compiler pin and existing complete-context/IRQ/NMI protocol.
Add no private GUI selector, worker Task, per-call allocation or signal bit.

AES UPDATE/MCTRL, scene/display ownership and cursor wake-order migration are
separate work. This plan supplies their reusable foundation without changing
their current policies. Shared readers, cancellation, timeout, owner-death
recovery and priority inheritance remain outside the delivered subset.

Use small executable Task fixtures throughout. No QED build, demo/package
refresh, MagiC image build or release matrix is required. Leave existing
packages intact; never replace their provider with one requiring different
APP imports. A later requested package refresh must rebuild its ABI consumers
together and follow the normal OF816 packaging rules.

## Slice order

| Slice | Executable result | Public surface after the slice |
| --- | --- | --- |
| NS0 | Frozen minimal composition baseline and guarded-entry map. | Existing Exec APIs only. |
| NS1 | Native try/recursive/release paths and owner-removal protection. | Action! Init, Attempt and Release; Obtain remains unavailable. |
| NS2 | Blocking obtain, FIFO handoff and waiter-removal protection. | Complete Action! semaphore service. |
| NS3 | Emitted C bindings and matching loaded-provider consumer. | Complete Action!/C service. |
| NS4 | Deterministic asynchronous-entry and return-boundary evidence. | Same service, corrected where required. |
| NS5 | Measured cost gate, small coexistence case and current documentation. | Development acceptance of the delivered service. |

Do not declare/import a function as callable before its behavior exists. In
particular, NS1 does not offer an Obtain that only works when free, spins or
returns success while still contended. Reserving a selector in the ABI input
does not advertise an implemented call. Advance feature versions as functions
become available, retaining one current API rather than compatibility profiles.

## NS0 — Freeze the baseline and continuation protocol

Add a small `tests/programs/semaphores.act` fixture and
`tools/test_semaphores.py`. Initially they exercise only a fixture-local
Forbid/Permit semaphore composition. Cache the Task identity, establish Task
leases and allocate any comparison waiter storage/signals before timing. Use
the same owner/depth/FIFO semantics as the proposed native service. Do not
write private Task metadata from the comparison library.

Measure optimized free and recursive obtain/release pairs, plus a short
contended handoff. Keep output outside the measured intervals. Include a peer
counter, complete-call boundaries, IRQ/off-Task attribution, guards, cleanup,
actual ROM/emulator/compiler hashes and resolved memory maps. Reuse the
[existing timing approach](../history/kernel-fast-path-implementation.md)
without importing its old timings as the new baseline.

Map native entry, validation, `fast_complete`, `fast_general`, `dispatch_frame`,
TaskPolicy Dispatch/FinishDispatch, Ready/Select/Switch and final restoration.
Record this implementation rule before wiring new services:

| Native classification | Continuation |
| --- | --- |
| Free/recursive operation or busy Attempt | Commit once in native code, then ordinary fast completion; pending work uses post-operation Poll. |
| Busy blocking Obtain | Decide before mutation; continue the original validated semaphore operation inside general policy, enqueue and return Select's frame. |
| Final Release with waiters | Decide before mutation; continue the original validated operation, transfer ownership and publish Ready, then use normal scheduling. |
| Invalid call shape, wrong owner or exhausted counter | Existing fault path, with semaphore/queue state unchanged. |

A blocked caller must never fall through ordinary Poll/Switch as if runnable:
Switch can reinsert its caller into the ready queue. Only the dedicated
semaphore operation may park it and return another Task's frame. Completed
native operations must never re-enter their original selector after mutation.

Keep service-shape validation at one admitted boundary. All new selectors
enter the native classifier; its internal general-policy continuation must
retain that admission without a second wrapper/descriptor validation pass.
Shared internal helpers and scheduler continuations do not create another
public selector or an unchecked caller entry. No activation-local scratch
remains live at that handoff.

Check all `services` and `private_services` maps. Proposed low-A service values
are `$50` Obtain, `$51` Attempt and `$52` Release, currently unused in those
maps; confirm again when allocating them. These are selectors, not additional
COP signatures. Freeze field/import shapes from the design, including the
three-byte native pointer and four-byte Attempt result.

**Exit:** reproducible optimized baseline, real peer progress, agreed native
transition table and unchanged runtime APIs/reservations. Use the existing
PAL 8x/4 MiB configuration with its exact matching pin; do not mix the differing
emulator hashes in the signal and shell-paced pins.

**Commit:** `Record semaphore composition cost and native handoff protocol`.

## NS1 — Native Attempt, recursion and Release

Create `abi/semaphores.json` as the source for object size/alignment, field
offsets, selectors and import/result shapes. Extend generation through the
existing Task/native/C-layout generators; a small semaphore-specific helper
may generate shared definitions, but no binding may hand-copy offsets or
selector numbers. Check collisions across all public/private service maps.

Reassign TaskControl padding to `semaphoreOwned` at 50 and `semaphoreWait` at
52, preserving the 64-byte stride and remaining padding at 55–63. Initialize
them in root/worker admission and pool reuse. Keep the 62-byte public Task and
all stack/DP pools unchanged. Add owner-count removal rejection to the common
RemTask/default-finalizer path before removal can mutate scheduling or reuse a
pool. Include waiter-field initialization now; actual waiting lands in NS2.

Provide Action! Init as ordinary initialization. Add native Attempt and Release
beside `fast-services.s`, using its complete-frame entry and final pending-work
checks. Resolve the admitted current Task once. Implement free acquisition,
recursive acquisition, busy zero result, nested release and final empty-queue
release. Ownership-count/depth overflow and wrong-owner/extra release fault
before mutation. Do not add heap scans, object tags or repeated pointer checks.

Make the same generated definitions visible to TaskPolicy, native assembly and
the loader's import checks. Quiescent operations must avoid the Action!
dispatcher and any public Forbid/Permit call. Keep scratch within the proposed
existing 20-byte budget and preserve the full saved context. Publish only the
three working functions in the Action! interface; Obtain is not yet imported.

Add the current `docs/reference/semaphores.md` subset description and link it
from the reference index. It must identify supported functions and unsupported
blocking acquisition accurately. Record results in a new
`docs/history/native-semaphores.md` and machine-readable development record,
updating their indexes when created.

**Validation:** host checks and affected generator checks; one small raw and
optimized emitted native layout/import/LONG-result probe; optimized free,
recursive, busy Attempt, nested/final release, multiple-owned-object, overflow,
owner-removal and pool-reuse cases. Include a bank-crossing object and Task,
guarded full-context restoration, a preserved outer Forbid depth and one
pending-work completion showing no replay. Introduce no blocking API stub.
Take an early optimized timing sample to detect a free-path dispatch mistake.

**Exit:** a useful native try/release subset with removal protection and
truthful public documentation. Report fixed/root/kernel/idle/per-Task bank-zero
deltas separately, plus consumed upper padding, code and scratch.

**Commit:** `Add native semaphore try and recursive release`.

## NS2 — Blocking Obtain and direct FIFO handoff

Add the Obtain import and selector handling. Extend the private state/reason
vocabulary with SEMAPHORE_WAIT, keeping public TS_WAIT. On contention, check
the eventual owned-count capacity before queue mutation. Reuse the waiting
Task's `tc_Node` for the FIFO, record `semaphoreWait` and park via Select within
the original gateway activation. A queue member is never on the ready queue.

Use a dedicated TaskPolicy semaphore route for the two cases classified
before mutation in NS0. Preserve the admitted frame and caller identity rather
than submitting another COP, public Wait, message or presenter request. Keep
one implementation of each ownership transition; share small native helpers
when the policy continuation needs the same record update.

On final queued release, detach the FIFO head, commit its owner/depth and
distinct-owned count, clear its wait association, and only then call Ready.
Use existing wake retirement and scheduling helpers. Finish all semaphore
access before making the recipient runnable. The old owner may be switched
out before its Release wrapper returns. The queued Task's owned-count capacity
was admitted at enqueue and cannot increase while it is blocked.

The resumed Obtain already owns the semaphore; it must not retry acquisition.
Prevent barging by committing ownership before readiness. Preserve recursive
entry by an existing owner even with older peer waiters. This resource FIFO
does not choose which ready Task receives CPU next.

Reject removal while `semaphoreWait` is nonnull, covering the enqueue-to-grant
interval. Direct handoff replaces waiter protection with owned-count protection
in one activation, including when the new owner has not run yet. Preserve all
existing Process, lease, producer and memory-list removal gates.

Keep signal masks independent: no allocation, clearing or consumption by the
service, and no Signal-triggered wake from SEMAPHORE_WAIT. Reuse WakeMatch's
SIGNAL_WAIT predicate and handle stale queued wake nodes through its existing
protocol. Preserve Forbid nesting across a blocked obtain. A contended obtain
with saved I=1 faults before publishing a queue entry.

**Validation:** optimized two/three-waiter FIFO, recursion while queued,
non-barging newcomer, final empty queue, release before a waiter runs, normal
Wait while owning a semaphore, outer Forbid, masked contention and signals
posted before/during blocking. Check independent signal bits and exact public/
private state, owner/count and queue membership. Include removal of an owner,
queued waiter and granted-but-not-run owner, plus successful removal/reuse
after release. Run a selected existing ordinary signal-wait case to ensure
new wait states cannot be mistaken for signal waits. Reuse NS1's layout probe;
repeat raw code only if its ABI/context assumptions change.

**Exit:** all four Action! calls are complete, signalless waiting is bounded
by the fixture's controlled release, and no blocked Task can be selected as
runnable or left on two queues.

**Commit:** `Add blocking semaphore obtain and FIFO ownership handoff`.

## NS3 — C bindings and loaded-provider delivery

Generate `<exec/semaphores.h>` with the opaque six-WORD record and declarations;
include it from `<proto/exec.h>`. Extend `generate_calypsi.py` with target-emitted
size/alignment/result checks and selectors. Init remains ordinary library code;
the three stateful wrappers marshal the same native public operations. Use
C's huge-pointer boundary and the native three-byte argument without embedding
four-byte pointers in the semaphore record.

Add all four functions to the resident import catalog through
`abi/c-program.json` and its normal generation/build path. Advance the provider/
APP ABI coherently; update callers and tests together. The current catalog is
version 45 at the plan's basis, but re-read it rather than assuming no concurrent
ABI work. Do not retain an old compatibility catalog.

Create a tiny C semaphore probe with a background counter. Verify all four
functions through emitted C and one matching disk-loaded APP/provider fixture.
Include a fixture-local cached-identity Forbid/Permit comparison loop for the
later C timing gate; it is not an alternate public semaphore implementation.
Build only that provider and selected small consumers; if a helper implicitly
builds unrelated APPs, add target selection before using it. Rebuild selected
APPs when the provider ABI requires it. Do not mix the new provider with cached
APPs from an incompatible version or replace the existing demo's provider alone.

**Validation:** small raw/optimized C/Action! ABI and calling probes for 12-byte
size, two-byte alignment, pointer bank preservation and full LONG zero/one
results. Run optimized C recursion, contended handoff, exact counter progress,
close/exit and heap/Task retirement. Check every new provider symbol resolves;
assert C Init uses zero COPs and each stateful wrapper makes one request.
Count explicit service requests separately from common late-work trampolines.
No graphical viewer or QED acceptance is needed for this binding slice.

**Exit:** source and loaded C consumers use the same service as Action!, with
matching provider provenance and no per-call allocation.

**Commit:** `Expose native semaphores to C and loaded programs`.

## NS4 — Asynchronous boundaries and fault isolation

Extend the small fixture with a runtime-selected native assembly overlay, using
the existing kernel-fast-path/signals checkpoint approach. Compile once per
needed fixture/mode, reload the same frozen image for cases, and keep forced
checkpoint waits out of production timing. Any new diagnostic state lives in
upper RAM or explicitly borrowed/restored test scratch, not a production DP.

| Boundary | Required observation |
| --- | --- |
| Free/recursive ownership update | Complete exactly once if IRQ/NMI forces post-operation Poll. |
| FIFO insertion and wait-state publication | No lost waiter, duplicate queue node or premature ready state. |
| Native-to-policy transfer and blocked Select | Complete frame, retired scratch, and no reinsertion of the blocked caller. |
| FIFO pop, owner/count transfer and Ready | Incoming Task owns the resource before it can run; removal remains barred. |
| Final pending-work check and partial restoration | Existing late-wake/trampoline handling preserves the result and never repeats the service. |
| Signal post/wake drain during semaphore wait | Bits remain pending; WakeMatch cannot grant or ready the semaphore waiter. |

Exercise both caller-masked immediate operations and unmasked operations with
real IRQ/NMI. Preserve D/DBR, widths, flags and stack ownership, including
nondefault valid contexts. Wrong-width/tag/unused-selector-byte calls must fault
before semaphore mutation through the normal gateway admission boundary.
Do not expand validation into stale-pointer diagnostics outside the contract.

**Validation:** optimized runtime-selected checkpoints and fault cases, plus a
small raw/optimized context bridge probe only where new compiler-facing shapes
require it. Select existing signal wake/claim and kernel fast-return cases
sharing the changed boundary; do not launch their full matrices. Document the
actual case list, attempted schedules, guards, OS return and memory impact.

**Exit:** no unresolved enqueue, handoff, signal-state or restore race. Correct
the common implementation here rather than adding a caller-specific workaround.

**Commit:** `Verify native semaphore interrupt and return boundaries`.

## NS5 — Cost gate and development acceptance

Measure the native service and NS0's composition in the same current optimized
fixture, switching only the fixture's selected case. Keep the original NS0
capture as history; the matched final-image comparison avoids attributing
unrelated kernel/layout changes to semaphore savings. The comparator remains
test code, not an alternate production backend.

Check complete free and recursive acquire/release pairs, including wrappers,
through both Action! and C. Each must use at least **25% less charged Task CPU**
than its same-language minimal cached-identity composition, as the design's
provisional cheapness gate. Do not compare a C wrapper against an Action!-only
baseline. Report
sample count/distribution, IRQ time, off-Task time and handoff latency separately.
If the gate fails, isolate the extra work and fix it before declaring this plan
complete; do not trade away context/IRQ safety or silently lower the target.

Trace request COPs, fast completions, pre-mutation policy continuations and
post-operation Poll separately. Quiescent free/recursive calls must stay native;
busy Attempt cannot queue, spin or wait. A blocked Obtain must resume from the
original invocation. Check there are no internal public FindTask/Forbid/Permit/
Wait/Signal calls, hidden allocation or queue scans in the service.

Run the simple owner/waiter/background-counter scene with one bounded native
timer-device completion. Counter progress must occur while ownership remains
held; timer completion and unrelated signal delivery must continue. Reuse the
existing timer fixture/helper where possible, without a serial baud matrix or
GUI desktop build. Repeat only affected regressions after a code change.

Update the semaphore reference, Task removal/signal documentation, guide
example and indexes. Complete the historical/development record with source,
compiler, ROM/emulator, image and trace hashes; exact scopes; stack/code use;
and fixed/root/kernel/idle/per-public-Task bank-zero deltas. Mark NS0–NS5 complete
only after all required gates pass. Do not claim viewer latency improvement or
hosted release qualification from this primitive's results.

**Exit:** measured cheap public service, safe preemptible ownership and a small
reproducible consumer. AES migration remains a subsequent plan.

**Commit:** `Measure and accept the native semaphore service`.

## Implementation seams

| Existing seam | Planned change |
| --- | --- |
| [Task ABI/generation](../../abi/tasks.json), [generate_tasks.py](../../tools/generate_tasks.py) | Context padding, state/reason, feature version, public native declarations and generated kernel definitions. Compose semaphore selectors without duplicating their source in two ABI files. |
| [Native import checks/build](../../tools/native_program.py) | EXEC import shapes/labels, semaphore assembly linkage and per-image provenance. |
| [Fast services](../../platform/altirraos/fast-services.s), [Task stubs](../../platform/altirraos/tasks.s) | Native classifier/bodies and pointer-service bindings; preserve common completion. A small included semaphore assembly file may hold the implementation. |
| [TaskPolicy](../../lib/exec/taskpolicy.act) | Validated semaphore continuation, direct Select/Ready/Switch integration, removal and initialization gates. |
| [Signal transactions](../../platform/altirraos/signal-atomic.s), [wake policy](../../lib/exec/task-wakes.inc) | Audit state predicates and wake retirement; change only if the new wait state requires it. |
| [C generation](../../tools/generate_calypsi.py), [Exec C binding](../../c/calypsi/exec.c) | Opaque header, emitted layouts, selectors and same-service wrappers. |
| [APP ABI](../../abi/c-program.json), [provider generation](../../tools/c_program.py) | Four exports and coherent selected consumer/provider rebuild. |
| [Existing fast-path runner](../../tools/test_kernel_fast_paths.py), [CreateTask runner](../../tools/test_create_task.py) | Reuse context overlay, saved-image case selection and stack/map reporting patterns; add no implicit broad test dependency. |

## Validation and evidence budget

Development tier is the default. Run host checks after coherent code slices,
and `--check` for affected generators. The proposed semaphore runner should
support explicit `--suite`, `--mode` and `--from-build` selection and reject
reuse when mode, source, ABI or machine inputs differ. New case names/tools
above are planned additions, not commands already available today.

| Slice | Smallest required emitted-code scope |
| --- | --- |
| NS0 | One optimized composition fixture with free/recursive/contended cases. |
| NS1 | Small raw/optimized native ABI probe; one optimized state/lifetime fixture. |
| NS2 | Reuse the updated optimized fixture for controlled contention, state and signal cases. |
| NS3 | Small raw/optimized C bridge/layout probe; one optimized selected APP/provider consumer. |
| NS4 | One frozen optimized context/checkpoint overlay with runtime selections; selected shared-boundary regressions. |
| NS5 | One final optimized matched comparison and a counter/timer coexistence case. |

Use four public Tasks where sufficient, including the barging/FIFO scenario.
Generate/check the standard twelve-Task memory layout for reservation comparison
without building a full demo. Alternate banks, capacities, NTSC, transport and
full fault matrices are not automatic development checks; select a deeper
case only for an affected boundary or observed failure.

Every implementation slice targets **0 added reserved bank-zero bytes** for
fixed, root, kernel, idle and each public Task, counting guards, alignment and
unused capacity. Report the five repurposed upper context bytes separately
from reservation growth; count each 12-byte caller object and allocator rounding
where used. Measure fast scratch and slow-continuation stack peaks. Fit native
code into existing upper capacity first and report any necessary reservation
change explicitly; do not enlarge Task pools to mask call-depth problems.

Retain ordinary and diagnostic artifacts under `build/native-semaphores/`;
commit concise source-pinned evidence and current docs per slice, not compiler
intermediates or emulator logs. A reused build must match the affected inputs;
unchanged captures may be reanalysed without another build/run.

Plan preparation itself is documentation-only: source/ABI/link checks, zero
builds or guest runs, and zero changes to runtime reservations or public APIs.
