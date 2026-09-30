# Process lifetime implementation plan

Status: P1–P3 implemented with development checks, 2026-09-24. Full release
qualification remains pending. See the [P1 development record](../development/process-p1.json)
and [P2/P3 development record](../development/process-p23.json).
Baseline: `407df9d`. Implementation requires console slices S0 through B5 first.

Scope: resident child execution, arguments/results, inherited streams/current
directory, and safe cleanup, Task retirement and collection. Apply the
[shared delivery and validation rules](interactive-programs-implementation-plan.md#baseline-ownership-and-delivery-rules).
The current public contract is defined separately in [Process design](../reference/process.md).

Start after [foreground cancellation](console-interaction-implementation-plan.md#b5-shell-behavior-and-interruption-limits).
Console windows are not a prerequisite. Resident fixtures exercise this plan;
the [o65 loading plan](o65-loading-implementation-plan.md) starts after P3 and
adds disk-loaded commands.

## Sequence and dependencies

| Slice | Executable outcome | Depends on |
| --- | --- | --- |
| P1 | A resident command runs in a managed child Task and returns arguments/results | [B5](console-interaction-implementation-plan.md#b5-shell-behavior-and-interruption-limits) |
| P2 | Child-owned stream handles and directory locks implement inheritance | P1 |
| P3 | Process cleanup, retirement, capacity and reuse pass adversarial tests | P2 |

## P: Process lifetime and inheritance

### P1: resident Process, Task admission and result collection

Implemented by `PROCESS`, generated `PROCESSSTATE` and guarded Task-policy
admission/retirement. Raw and optimized fixtures each passed 7,841 assertions
over 273 Task lifetimes, including 260 repeated command lifetimes, seven live
children alongside the parent, copied 255-byte arguments, independent contexts,
32-bit results, stale/foreign identities, setup failure injection and slot leases.
The shell smoke also passed after the shared service-admission changes. Stack/DP
guards, heap/bank ownership, native entry/return flags and OS restoration passed.
These are development checks on the current pin; compiler and release
qualification remain deferred. P3 adds focused parent-removal/teardown adversaries
and combined services; the full placement matrix remains release work.

Define a DOS-owned Process above the unchanged public Exec Task. Use the existing
eight static stack/DP pools and an upper-RAM Process/Task slot table sized for
the configured capacity. Public Task records must occupy admitted writable
storage: AddTask's current range checks do not admit an arbitrary heap pointer.
Introduce a checked internal slot lease so preparation reserves a free context
atomically and cannot race an ordinary AddTask or another process start. Roll
back that lease on every preparation failure.

Enter through a resident, registered zero-argument Process trampoline and
resident finalizer. Preserve AddTask's registered-entry check. The trampoline
looks up its Process association, establishes its DOS context and invokes only
the validated command entry held by that Process. No bank-zero stack allocator,
extra reaper Task or dynamic AddTask entry table is needed for this first path.

Freeze the native Process-facing API in the separate design and generated
definitions: create/start, wait/collect, borrowed argument string and setting
primary/secondary exit results. Start with a bounded 255-byte argument tail,
copied before admission. A zero-argument void command entry returns normally;
default status is success, or it sets its result explicitly before returning.
This fits the existing native entry ABI without inventing C argc/argv registers.

Model preparing → running → quiescing → retired → collected. Parent ownership
of the completion record lasts through collection. A completion signal/reply
alone does not prove the Task stopped using its stack or code: retirement must
include the kernel's removal acknowledgement before reuse/reclamation.

**Acceptance:** run a resident child with arguments and results, then start it
again using the released slot. Inject failure at every allocation, signal and
admission step. Exhaust all eight public slots and reject the next start with
unchanged state. Cover parent waiting before/after completion, child entry/return
registers and DP, nonzero PBR, finalization, and at least 256 slot lifetimes.

### P2: inherited streams and current directory

Implemented by transactional `DOSINHERIT` wrappers, shared file-position backing,
retained RAW endpoints/CON sessions and `PROCESS.StartForeground`. The foreground
path suspends parent DOS transfers until collection, installs the child's break
scope, and restores the parent with a fresh input route. Retired routes reject
keys captured during handoff as well as stale breaks. See the
[API and ownership rules](../reference/process.md#inherited-resources-and-foreground-input).

Duplicate ownership into the child's DOS context; copying the parent's opaque
FileHandle/FileLock pointers is invalid. Child handles remain distinct owned
objects and selections. Introduce reference-counted backing where needed:
duplicated file handles share the open file position, RAW handles share their
endpoint, CON handles share their cooked session, and NIL handles retain null
stream semantics. Serialize access to each shared backing and define busy-close
behavior without blocking the filesystem on console input.

Duplicate the current-directory lock and mount reference without reparsing its
name. A child's CD and Close cannot alter the parent's selection or invalidate
its handles. Inheritance is transactional: retain all references, construct the
child context and publish it only when complete. If Input and Output name the
same parent handle, preserve that alias with one child handle and one close.
Each Task still owns its own reply port, transfer request and IoErr.

Transfer the foreground binding to the child only after it can receive breaks;
restore it only after its outstanding I/O and captured input route retire.
The shell has no concurrent prompt Read while the child owns foreground input.
Keep CD and other shell-state built-ins in the shell; external commands execute
in child Processes. The shell supports one foreground child at a time, while
the Process API and test harness can admit independent children within capacity.

**Acceptance:** verify file-position sharing, CON buffered-line/EOF sharing,
independent selections/errors, inherited redirection, directory inheritance and
parent/child close ordering. Fail each duplication step and prove reference
counts, selected handles, mount ownership and task capacity return to baseline.
Use two live children to check mutable-state and reply-port isolation.

### P3: teardown and failure qualification

Implemented by `DOSPROCESS.Cleanup` and the guarded retirement/collection path.
The focused resident fixture covers returned unclosed DOS objects, break
cancellation with exact I/O collection, child setup failures, rejected parent and
child removal, and retained ownership after restoration or final-close errors.
It combines eight live Tasks with console, filesystem/SIO, signals, messages and
heap reuse. Raw/optimized development runs cover kernel banks 3/1 respectively;
the complete mode-by-placement and service matrices remain release qualification.

The resident finalizer settles accepted I/O, detaches foreground ownership,
clears selections/current directory, closes Process-owned DOS objects, releases
its context/signals and removes the Task. The parent then collects results and
releases argument/Process storage. Keep completion storage outside the child's
stack and future unloadable image. Reject parent removal while any child or
completion remains owned, unless an explicit ownership transfer is implemented.

Process cleanup owns only resources in its defined ledger. Ordinary Exec heap
allocations retain their existing shared explicit lifetime; tc_MemEntry remains
empty. Do not claim general automatic reclamation or safe forced termination of
arbitrary programs. Stack/ABI faults retain the platform's existing fault policy;
isolating a corrupted Process is outside this milestone.

**Acceptance:** normal return, cooperative break, setup failure, cleanup error,
late/double collection, parent removal attempts, full-capacity reuse and stale
identities. Resources whose retirement fails retain ownership and cannot be
reused or unloaded. Run raw/optimized tests with kernel banks 1/3 and combined
eight-task signals, memory, messages, console and SIO.

## Integration and memory

| Area | Existing integration points / proposed additions |
| --- | --- |
| Process admission | `lib/dos/process.act`, `abi/process.json`, `task-process.inc`, Task/service admission, generated upper-RAM bindings and lifecycle tests |

Inheritance also updates `lib/dos/dosclient.act`, `dosobjects.act`, `dosstreams.act`
and endpoint/file backing ownership. Keep Process layouts machine-readable,
generate definitions and rebuild callers; preserve the public Exec Task contract.

Target reserved bank-zero delta: **zero fixed and zero per Task**, including
all guards, alignment and unused capacity. Use the existing eight context slots;
root/shell and three services occupy four, and a foreground child uses a fifth.
No reaper Task or new stack/DP pool is added. Preserve the
[shared memory gates](interactive-programs-implementation-plan.md#memory-gates).

| Resource | Planning budget / accounting requirement |
| --- | --- |
| Process | Existing stack/DP slot plus a build-sized upper Task/association table; target 256 bytes of Process control plus up to 256 argument bytes, excluding inherited DOS objects and completion storage |

P1 actual: 128 bytes per configured slot plus a four-byte identity counter
(1,028 upper-RAM bytes for eight slots), including the Task, results and unused
root row. Each active/retired child retains up to 256 argument bytes and one
parent completion signal; its running DOS context/port uses existing allocation
paths. Console-enabled builds also add 12 alignment bytes before console
metadata. Reserved bank-zero delta is **0 fixed and 0 per Task**.

P2/P3 add **0 fixed and 0 per-Task reserved bank-zero bytes**, and no upper static
reservation beyond P1. They consume 19 reserved bytes per Process row, two padding
bytes per DOS context and one reserved byte per console route. File wrappers grow
from 112 to 116 bytes and share a new 94-byte backing allocation; cooked sessions
grow from 400 to 402 bytes. Inherited wrappers, lock names and foreground scopes
use upper heap storage, detailed in [Process memory accounting](../reference/process.md#memory).

Completion requires P1–P3 with resident raw/optimized fixtures, exact retirement
acknowledgement, failure rollback and full-capacity reuse. Disk loading belongs
to the next plan. Automatic reclamation of arbitrary shared heap allocations,
forced termination and Process fault isolation remain outside this milestone.
