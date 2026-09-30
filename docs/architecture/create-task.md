# CreateTask for Action! and C

Status: **implemented, including the same-source Amiga runtime demonstration**.
[Development results](../development/create-task.json). This extends the current
[Task API](../reference/tasks.md) and replaces the public C-only
`ExecPrepareTask` helper. The compiler pin is unchanged.

The [implementation plan](../plans/create-task-implementation-plan.md) divides
the completed delivery into shared service, lifecycle checks, C binding, example migration and
the unchanged-source Amiga demonstration.

## Purpose and scope

Applications should create an ordinary Task by supplying a name, priority, entry
and stack size. Exec selects execution storage and returns it for reuse when the
Task retires. Action! and C use the same operation and ownership rules.

The source model is classic Amiga's `CreateTask`, supplied there by `amiga.lib`.
It creates the Task and arranges reclamation of its creation resources on removal.
Exec816 uses its existing fixed stack/DP pools and a small pool of resident
Task records. This deliberately replaces dynamic allocation with bounded resource
allocation; callers still receive a Task pointer or NULL.
[Amiga CreateTask contract](https://developer.amigaos3.net/autodocs/amiga.lib/CreateTask.html)

Keep `AddTask` for caller-prepared records, explicit stack placement and custom
finalizers. CreateTask adds no Process, argument passing, return status, join,
parent ownership, DOS inheritance or general heap tracking. Those remain separate
from ordinary Task creation.

## Public interfaces

Action! declaration in the generated `EXEC` interface:

```action
PUBLIC EXTERNAL Task POINTER FUNC CreateTask(
    CSTRING name LONGINT priority PROC POINTER entry() LONGCARD stackSize)
```

Application use:

```action
LET worker=EXEC.CreateTask(c"worker",0,@Worker,1024)
IF worker=NULL THEN
  ; No Task was created.
FI
```

The C header follows the classic declaration's argument widths and address form:

```c
struct Task *CreateTask(CONST_STRPTR name, LONG priority,
                        APTR entry, ULONG stackSize);
```

Supply it through a small `<clib/alib_protos.h>`, with the calling-convention
annotation in our header. A common C application includes it alongside
`<exec/tasks.h>` and `<proto/exec.h>`. Inside main, with Worker declared as
`void Worker(void)`, it can use:

```c
struct Task *worker = CreateTask("worker", 0L, (APTR)Worker, 1024UL);
```

The classic header uses an APTR for the entry; accepting it does not permit an
arbitrary data address to execute. The native admission checks still apply.
Our header need not reproduce unrelated amiga.lib interfaces.
[Classic alib_protos.h](https://d0.se/include/clib/alib_protos.h)

| Argument/result | Contract |
| --- | --- |
| `name` | Borrowed NUL-terminated text; NULL gives an unnamed Task. Keep its storage alive throughout the Task's lifetime. No copied name or fixed name buffer. |
| `priority` | Signed 32-bit argument, validated in -128..127 before storing the signed-byte representation. Current FIFO scheduling still ignores priority. |
| `entry` | Registered zero-argument procedure: an Action! PROC or C `void function(void)`. Returning uses the default self-removal path. |
| `stackSize` | Unsigned 32-bit minimum stack allocation, in bytes; details below. |
| result | Task pointer on admission, NULL on ordinary creation failure. No DOS context or IoErr side effect. |

Validate range and rounding before narrowing to native stack addresses. Bad
priority, zero/overflowing size, null/unregistered entry, exhausted capacity or
no sufficiently large pool returns NULL. Arbitrary unreadable pointers remain
caller misuse in the shared address space.

## Stack allocation

Use the resolved build's pool map, including each pool's actual size. Do not
duplicate the C helper's current four-slot/1536-byte assumptions. Eligible pools
are free public worker pools: exclude root, private idle and kernel/interrupt
contexts. Console, filesystem, SIO and Process Tasks already using a pool compete
for the same capacity. Incarnation exhaustion also makes a pool unavailable.

Round a positive request up to even bytes with checked 32-bit arithmetic. Choose
the smallest available pool large enough, with pool order breaking ties. The
chosen pool must also pass the existing native-frame/headroom admission checks.
Give the Task the whole pool; do not split pools, move live stacks or resize DPs.

`stackSize` describes the stack allocation between tc_SPLower and tc_SPUpper,
excluding external guards. It includes the platform's interrupt reserve and
entry frames, just as the existing pool sizes do. It is not a promise of that
many bytes for application locals. A 1024-byte pool can satisfy a 1024-byte
request; a larger request fails unless a larger pool is available. A smaller
request can receive more storage. Small requests never remove required headroom.

For C, retain the existing per-Task lower-DP workspace and zero-initialization.
This feature does not add compiler stack checks to C functions. The
[platform contract](../reference/platform.md) and [C binding](../guides/calypsi-c.md)
continue to define context and calling-convention limits.

## One shared implementation

Publish CreateTask as a **general public Task operation through COP #$50**.
Both language bindings marshal the same documented request to the same policy.
Choose its selector from the shared ABI allocation during implementation; generate
Action! declarations, native packet definitions and C constants together.

This is an implementation difference from Amiga's library helper. The kernel
already owns pool availability, entry validation, incarnation state and retirement.
A bounded public operation can select, initialize and admit a Task atomically
without exposing private slot operations or duplicating creation policy in C.
No helper-to-Action! calling-convention bridge or general memory-list allocator is
needed for this first implementation.

Reuse common admission/context setup from AddTask. CreateTask supplies a trusted
pool-owned Task record; AddTask continues to validate caller-owned image storage.
Keep their storage checks distinct while sharing the actual admission work.
Caller-supplied AddTask records must not overlap the managed-record reservation;
do not make all kernel-reserved memory generally writable application storage.

Selection and publication occur within the existing kernel transition protocol.
IRQs stay enabled except for existing bounded native transactions; NMI entry and
stack changes retain their current protection. No allocation, waiting, ROM call
or application callback occurs while preparing the bounded record. On failure,
publish no Task and retain no pool claim. On success, preserve the caller's
Forbid nesting and request scheduling as AddTask does.

The C wrapper converts huge C pointer values to the native 24-bit request and
converts the returned pointer back. Validate representability before narrowing;
do not truncate a nonzero high address byte. Action! uses its normal native
pointer representation. Registered C Task entries remain explicit build inputs;
CreateTask does not register arbitrary callbacks or make unloadable command code
safe to use as a Task entry.

## Record ownership and retirement

Reserve one managed Task record per eligible worker pool in upper RAM. A record
belongs to Exec, is used only while that pool hosts its CreateTask Task, and is
reset before reuse. Existing private TaskControl membership is authoritative;
there is no second live-slot bitmap, heap allocation or reaper Task.

All exit paths use common removal: normal entry return, `RemTask(NULL)` and
permitted removal by another Task. Preserve removal leases, producer bindings,
DOS/Process ownership checks and the nonempty-memory-list rejection. CreateTask
does not make forced removal safe or clean up application ports, handles and
ordinary AllocMem blocks. The Task must release those resources first.

Only after the kernel has detached the Task and ceased all use of its old stack,
DP and record may the slot and managed record be reused. Preserve the existing
kernel-stack self-removal and IRQ/NMI protocol. No cleanup may depend solely on
a return finalizer: direct RemTask bypasses it. Caller-supplied AddTask records
remain borrowed and are never reclaimed by this facility.

Reclamation here means returning resources to their fixed pools. The reservation
remains resident and is not added to AvailMem. `tc_MemEntry` stays empty; general
AllocEntry/FreeEntry and automatic user-allocation reclamation remain deferred.
This differs from Amiga's memory-list implementation while retaining creation
resource reuse on every successful removal path.
[Amiga RemTask contract](https://developer.amigaos3.net/autodocs/exec.library/RemTask.html)

## Pointer and executable lifetime

A returned Task pointer is borrowed. Never FreeMem it or poll it after removal;
even if the pool's bytes remain mapped, the record can already represent another
Task. Creation is not a join operation or an ownership reference.

The new Task may run and finish before CreateTask returns. To initialize shared
state or acquire a supported lifetime lease before it can run, hold Forbid across
creation and that setup, then Permit. Use signals/messages for normal coordination.
The entry code, globals and borrowed name must outlive the worker; a creator's
exit neither stops the worker nor independently retains its executable image.

For the portable message example, a completion notification must also establish
that worker code has stopped before main exits. After releasing its resources,
the worker can use `Forbid(); Signal(parent, doneMask); RemTask(NULL);`.
The parent cannot resume between notification and self-removal. Do not substitute
a signal followed by an unprotected return, or a tc_State polling loop. This
uses existing Exec operations on both targets, without adding a public join API.

## Memory cost

Target **zero additional fixed or per-Task bank-zero reservation**, including
guards, alignment, interrupt reserve and unused pool capacity. Task capacity,
native stacks and 256-byte DP reservations do not grow.

Use a 64-byte upper-RAM stride for each current 62-byte Task record, including
two reserved padding bytes. With root excluded this reserves 192 bytes for a
four-slot build or 448 for an eight-slot build. Align the table to two bytes and
account for any leading alignment byte in the generated memory report. This is
an explicit resident cost even when no managed Task is live. It avoids heap
bookkeeping and a deferred-free queue; existing TaskControl size need not grow.

Generate the reservation and its address from the resolved configuration. Report
actual emitted code growth, full upper reservations and fixed/per-Task bank-zero
deltas during implementation. These are design budgets, not measured results.

## Integration and validation

Remove public ExecPrepareTask when CreateTask is available. Update ordinary
Action! and C examples together; retain low-level AddTask coverage for explicit
storage and custom finalizers. Generate the new ABI from one definition and
advance the reported feature version. No language or compiler semantics change
is planned, and no separate C Task implementation or hidden gateway is introduced.

Focused development checks should cover both bindings, raw/optimized Action!,
and the relevant C modes: argument bounds, exhaustion, mixed AddTask/CreateTask
occupancy, nondefault pool sizes, failed admission without capacity loss,
return/self-removal/external removal, lease rejection, repeated reuse and creation
under Forbid. Retain native guards, full context/DP restoration, bounded completion
and existing worker coexistence checks. Verify that a child can finish before the
creator resumes without a wrapper touching its retired record.

The source-compatibility demonstration uses the same C file on Exec816 and a
pinned classic Amiga SDK/runtime: CreateTask, signals and message/reply exchange,
with no ExecPrepareTask, ExecYield or Task-state polling. Use named types and
sizeof, since record layouts and pointers differ. Remove global free-memory
equality as an application assertion; unrelated Amiga activity can change it.
Record actual builds and runs before claiming compatibility. Output bindings and
broader C library support remain separate work. Follow the
[two-tier testing policy](../contributing/testing.md); this design note needs only
content and link checks.
