# Classic Exec task API

Status: implemented by `--tasks`, currently reporting version `$0800`.
The native call packet tag remains `$0600`; it is not the feature version.
This is the only Task implementation; development ABI changes require rebuilding callers.
[Build and storage instructions](../guides/tasks.md) describe the hosted configuration;
the [migration record](../history/tasks-exec-update.md) tracks implementation and validation.

Use classic Exec names, Task pointers, managed or caller-prepared Task storage,
and removal semantics. The scheduler ignores priority. Signals and Wait are implemented; see the
[signal contract](signals.md).
Those simplifications do not change task identity or introduce parent ownership.
This is a native 65816 adaptation, not an Amiga binary ABI.

## Public Task

Expose `EXEC.Task`, beginning with the full [EXECLISTS.Node](lists.md). The
initial supported subset retains these classic fields in their original
relative order:

```action
PUBLIC TYPE Task=[
  EXECLISTS.Node tc_Node
  BYTE tc_Flags,tc_State,tc_IDNestCnt,tc_TDNestCnt
  LONGCARD tc_SigAlloc,tc_SigWait,tc_SigRecvd,tc_SigExcept
  ADDRESS tc_SPReg,tc_SPLower,tc_SPUpper
  EXECLISTS.List tc_MemEntry
  ADDRESS tc_UserData,tc_ExecPrivate
]
```

This subset occupies 62 bytes in emitted native code. ADDRESS scalars have
two-byte alignment, unlike the one-byte alignment of typed pointers in Node and
List; use the generated offsets and size, including padding. Address fields
are 24 bits, including stack addresses even though native stacks occupy bank
zero. There is no public slot number, generation, parent, join target, or exit
result. Direct-page ownership and saved processor context belong to a separate
private execution record.

| Field | Contract |
| --- | --- |
| `tc_Node` | Scheduler linkage; `ln_Type = NT_TASK` (1), borrowed optional `ln_Name`, signed-byte `ln_Pri`. The caller initializes type, name and priority before admission. |
| `tc_Flags` | Zero in this subset; exception and switch/launch hooks are unsupported. |
| `tc_State` | Kernel-maintained classic state vocabulary below. |
| `tc_IDNestCnt` | Reserved at `$FF`; public Disable/Enable support is deferred. It is not a reflection of temporary IRQ masking inside the adapter. |
| `tc_TDNestCnt` | Scheduling exclusion count: `$FF` means permitted, 0 through 127 encode one through 128 nested Forbid calls. Stored as a BYTE using signed two's-complement conventions. |
| `tc_SPReg` | Initial native S value before admission; saved S when suspended. Not a continuously updated reading of the running task's hardware S. |
| `tc_SPLower`, `tc_SPUpper` | Lower and exclusive upper bounds of the reserved stack allocation. Interrupt headroom reduces the portion available to ordinary calls. |
| `tc_MemEntry` | Initialized, empty Exec List. Automatic memory-list reclamation is deferred; nonempty lists are unsupported in this subset. |
| `tc_UserData` | Application-owned pointer-sized value; Exec does not interpret or free it. |

Use `TS_INVALID=0`, `TS_ADDED=1`, `TS_RUN=2`, `TS_READY=3`, `TS_WAIT=4`,
`TS_EXCEPT=5`, and `TS_REMOVED=6`. `TS_ADDED` is an internal admission
transition; `TS_WAIT` can describe the existing sleep extension.
`TS_EXCEPT` is reserved. Pool vacancy is private bookkeeping, not a Task state.

The four 32-bit signal masks and private context link are described in the
[signal lifetime contract](signals.md#delivery-and-lifetime).
`tc_SigExcept` is reserved at zero; signal exceptions, traps and switch/launch
callbacks remain unsupported. Use generated fields and `EXEC.TASK_SIZE`.

## Core calls

These calls live in `EXEC`. Entries and finalizers are native zero-argument
procedures. The signatures and native import layouts are generated from
[tasks.json](../../abi/tasks.json) and checked against emitted code.

| Call | Result and behavior |
| --- | --- |
| `CreateTask(CSTRING name, LONGINT priority, PROC POINTER entry(), LONGCARD stackSize)` | Returns a borrowed managed Task pointer, or NULL on failure. Selects the smallest free worker pool that meets the requested stack allocation. |
| `AddTask(Task POINTER task, PROC POINTER initialPC(), PROC POINTER finalPC())` | Returns the same Task pointer on successful admission, or null on failure. Zero finalPC selects Exec's default self-removal finalizer. |
| `RemTask(Task POINTER task)` | Procedure. Null removes the caller and never returns. Passing the current Task pointer has the same effect. A different live Task is removed before the call returns. |
| `FindTask(BYTE POINTER name)` | Returns a Task pointer. Null name selects the caller; a nonnull name searches live public tasks and returns null if absent. |
| `SetTaskPri(Task POINTER task, BYTE priority)` | Stores priority and returns its previous BYTE representation. Pass a live Task pointer, including `FindTask(NULL)` for oneself. |
| `Forbid()` | Procedure. Nests scheduling exclusion for the current task without disabling hardware interrupts. |
| `Permit()` | Procedure. Releases one nesting level; the outermost release permits pending rescheduling. |

`NULL` in descriptions means a correctly typed zero pointer. `ln_Pri` and
SetTaskPri values encode -128 through 127, as in Lists. In this first subset,
changing priority neither reorders the ready queue nor triggers a priority
preemption. All runnable user tasks receive equal round-robin treatment. This
is the explicit temporary departure from classic
[SetTaskPri](https://developer.amigaos3.net/autodocs/exec.library/SetTaskPri.html).

### Managed creation

```action
LET worker=EXEC.CreateTask(c"worker",0,@Worker,1024)
```

CreateTask validates a signed 32-bit priority in -128..127 and a nonzero unsigned
32-bit stack size. Positive odd sizes round up to even; overflow, unavailable
capacity and unregistered entries return NULL without changing `IoErr` or pool
ownership. The smallest fitting free worker pool wins, with slot order breaking
ties. Root, private idle, live Tasks, Process reservations and uncollected Process
slots are unavailable. Priority is stored; scheduling remains FIFO.

`stackSize` is the minimum **whole reserved stack**, excluding guards but including
256 bytes of interrupt headroom and native frames. The actual pool can be larger.
Names are borrowed C strings; NULL creates an unnamed Task. Keep the name, code
and shared data alive until the Task retires. Creation does not retain an Image
or inherit a Process/DOS context.

The returned Task belongs to Exec. Never FreeMem it, prepare it for AddTask, or
inspect it after removal. It can already be retired when CreateTask returns.
Use Forbid across creation and initial setup when you need a live pointer. For
completion, allocate a signal before creation and have the child clean up, then
perform `Forbid(); Signal(parent, doneMask); RemTask(NULL)`. The parent can resume
only after retirement. Do not poll `tc_State` through a managed result.

A returning entry uses the existing default self-removal finalizer. Return,
self-removal and permitted external removal make the same managed record and
stack/DP pool reusable, without a heap allocation or separate reaper. Resource
ownership gates still apply; the application must release its ports, memory,
leases and DOS state. `tc_MemEntry` remains empty. Use AddTask for a custom
finalizer or explicit stack placement.

In C, include `<clib/alib_protos.h>` and use
`CreateTask(name, priority, (APTR)Worker, stackSize)`. The shim checks huge-pointer
representability and marshals the same service; it allocates no separate pool.
See the [C guide](../guides/calypsi-c.md) and
[design](../architecture/create-task.md).

### Admission and storage

The public lifetime extensions `RetainTask`, `ReleaseTask`, `RegisterResident`
and `UnregisterResident` are specified in the
[resident contract](resident-drivers.md#task-admission-and-lifetime).
They support ordinary Tasks and drivers through the same public gateway.

[AddTask](https://developer.amigaos3.net/autodocs/exec.library/AddTask.html)
registers caller-prepared storage. It does not allocate a Task or stack. The
caller zero-initializes the Task, sets its Node metadata and stack fields, and
initializes `tc_MemEntry` with NewList. The kernel initializes nesting counts
and scheduling state after validation. A previously removed Task must be
prepared again before reuse.

The Task and its name must remain valid until removal and until all application
references have ceased. In particular, storage in a creator's activation cannot
outlive that activation. An active Task's name, stack fields, type, memory list,
and links must not be changed directly. Priority changes go through SetTaskPri;
state and nesting fields are observations, not controls. UserData belongs to
the application and follows its own synchronization rules.

The hosted kernel accepts stack allocations from build-reserved ranges, each
with an associated private direct page. Four- and [eight-task layouts](../architecture/task-capacity.md)
use the same Task API, with root included and idle additional. Generated
TASKSTACKS bounds describe storage, not public identity. An occupied range
cannot be admitted again. General bank-zero allocation and twelve/sixteen-task
qualification remain future work.

Supply the complete reserved stack bounds. `tc_SPReg` identifies the initial
native S, rather than being discarded in favor of the upper bound. Its default
is `tc_SPUpper - 2` to satisfy native call alignment. An initial S must be even,
within the pool bounds, and at least 32 bytes above the compiler stack floor.
Admission constructs the one-byte caller area and initial frame at and below S;
prepared data above S is preserved. Lower starting values must retain the same
alignment and required headroom.
Validate all addresses at full width before narrowing hardware S or D. The
kernel initializes its direct page and initial frame; admission must not erase
the caller's prepared stack data above the frame/caller area.

Task objects and names may occupy writable/readable image data in any supported
bank; they need not live beside their execution record. They cannot overlap
active stack/domain storage or kernel reservations. Initial/final PCs must be
exact registered zero-argument application procedure entries in the loaded
image, except the kernel's default finalizer. The packager's bounded entry table
is an initial loading restriction, not a Task-pointer encoding.

For readable caller-supplied storage, admission rejects null task/initialPC,
duplicate active Task pointers, unavailable or invalid stack ranges, invalid
entries, invalid Node type/state, unsupported flags, and nonempty memory lists
with a null result. A valid new record starts in TS_INVALID. The public record
must fit wholly in writable application storage; its full range, not just its
first address, is checked against live stack/domain and kernel reservations.
Failed validation leaves the Task, stack, ready queue and execution capacity
unchanged. This is a trusted shared address space: arbitrary unreadable pointers
are caller misuse, not a recoverable protection boundary. No global last-error
or status disguised as a pointer is introduced.

Publication occurs only after all context initialization succeeds. Admission
requests scheduling subject to Forbid and the platform's existing safe-entry
rules. The new task can execute, and even remove itself, before AddTask returns.
Use Forbid across creation and any setup that requires the task still to be live.

### Entry, finalization and removal

Returning from initialPC transfers control to finalPC, or to default self-removal
when finalPC was null. A custom finalizer runs in the task's ordinary context;
it must ultimately remove itself and must not return. An unexpected finalizer
return is a defined launch fault. RemTask does not invoke finalPC: the finalizer
is the continuation of a normal entry return, not a cancellation callback.

[RemTask](https://developer.amigaos3.net/autodocs/exec.library/RemTask.html)
supports another task as well as self-removal. There is no creator check.
The target is detached from scheduling and any sleep deadline, marked removed,
and its private execution context becomes reusable. Self-removal first switches
to the kernel stack/domain, so reuse cannot overwrite a live removal activation.
Forbid does not prevent self-removal; its task-local nesting state is discarded.
Removing another task preserves the caller's nesting state. IRQ-masked, OS,
interrupt and reentrant-kernel removal calls remain unsupported contexts.

A live removal lease or producer binding rejects removal, including the default
finalizer. Release each lease and quiesce/release/drain the producer before
removal. Use Forbid across the final lease release and removal when another Task
could otherwise reuse the target. When removal leaves no ordinary Task, Exec
signals registered residents; each resident decides when its resources permit
shutdown.

Caller-provided Task/name/stack storage is borrowed, not freed. There is no
zombie, exit code, join, reap, or parent-exit action. Other tasks continue after
their creator or the root exits. Removing a task does not release the shared
image or shared heap allocations. Applications must arrange cleanup of resources
that the removed task was using. Passing a nonlive, idle or kernel Task to
RemTask is misuse, diagnosed as a launch fault. SetTaskPri likewise requires a
currently admitted public Task; null is not shorthand for oneself in that call.

`tc_MemEntry` must stay empty throughout this first subset. AddTask rejects a
nonempty list; removal must diagnose an unsupported nonempty list before
detaching the task rather than silently leaking or freeing unknown records.
Later AllocEntry/FreeEntry support will give this field its classic reclamation
behavior. Ordinary shared heap allocation will not automatically populate it.

### Lookup and pointer lifetime

[FindTask](https://developer.amigaos3.net/autodocs/exec.library/FindTask.html)
uses case-sensitive, zero-terminated names; unnamed tasks are skipped and the
empty string is a valid name. Duplicate names are allowed, with no promised
choice among matches. Search includes the running, ready, sleeping and signal-waiting public
tasks; idle and removed tasks are excluded. Lookup allocates nothing and does
not retain the returned Task.

Forbid before finding another task and keep exclusion through its use when
that task could otherwise remove itself. Without such synchronization a pointer
may already be stale on return from a scheduling boundary. A later task at the
same address is indistinguishable: pointer identity deliberately replaces the
old public generation guarantee. Checking private membership can diagnose some
invalid references; it cannot make a raw pointer generation-safe.

### Scheduling exclusion

Follow [Forbid](https://developer.amigaos3.net/autodocs/exec.library/Forbid.html)
and [Permit](https://developer.amigaos3.net/autodocs/exec.library/Permit.html)
nesting semantics. Only the calling task's count changes. An unmatched Permit
or nesting overflow is a diagnosed misuse; do not wrap a BYTE counter. Neither
call provides interrupt exclusion or an application mutex against interrupt
handlers. NMI continues to record ticks and the established context-transition
protocol remains required.

Signal, Wait, AllocSignal, FreeSignal and SetSignal are implemented as described in the
[signals and Wait contract](signals.md).
SetExcept remains deferred; there are no success-returning stubs. A blocking
Wait allows other tasks to run while retaining the caller's Forbid count
for its resumption, following the classic
[Wait contract](https://developer.amigaos3.net/autodocs/exec.library/Wait.html).

The existing `EXEC.Yield()` and `EXEC.Poll()` remain explicit extensions. Yield
under Forbid records a pending request without switching. `EXECTASKS.Sleep`
remains as the existing timed-delay extension, including ERROR_LOCK under
Forbid; it is not presented as Wait or a substitute for signal synchronization.
Disable/Enable, task exceptions, switch hooks and asynchronous I/O remain out
of this initial contract.

## Development policy

[CreateTask development checks](../development/create-task.json) cover native
raw/optimized calls, lifetime boundaries, C layouts and real VBI coexistence.
These focused checks are separate from release qualification.

Exec816 is under active development and maintains one Task API. Changes update
the kernel, generated definitions, examples and tests together. There is no
backward-compatibility promise or old-API build switch; rebuild callers when
layouts or call conventions change. Historical implementations remain in Git.
