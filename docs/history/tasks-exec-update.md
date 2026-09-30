# Task API review and migration

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

Historical record of the initial 42-byte Exec-style Task implementation.
The [current Task kernel](../guides/tasks.md) supersedes it with signals and a 62-byte
Task. Its old build profiles and implementations have been removed; source
links below point to the recorded development state in Git.

The [original integration qualification](../qualification/tasks-exec.json)
records 64 raw/optimized cases, and the
[platform/Lists record](../qualification/tasks-exec-regressions.json) records 14.
These results describe their original commits, not a current compatibility API.

Completed commits: `8f45a18` qualifies the layout and native calls; `82d78bc`
implements the isolated core; `bbe4081` pins the independently tested
[emulator interrupt correction](emulator-native-irq-fix.md). The final integration slice adds lifecycle,
misuse and interrupt qualification, switches the default profile, and updates
the example and documentation.

## Review decisions

The previous design turned an initial pool implementation into a public model of
generation handles, creator-owned children and retained completions. Those are
not requirements of the 65816. Replace that model with classic Task pointers
and task admission/removal, retaining the already qualified context adapter.

| Previous design | Adopted decision | Reason |
| --- | --- | --- |
| MinNode-prefixed private TCB is also task identity | Public Task starts with full Node; private context is separate | Restores names/type/priority without tying a public object to its bank-zero execution slot. |
| Create(entry) owns all storage choices | AddTask(task, initialPC, finalPC) accepts prepared Task and stack fields | Matches the low-level Exec operation and works without waiting for a heap. |
| CARD generation handle; Self/TaskId | Task POINTER; FindTask(NULL) | Restores the core object model and avoids leaking fixed-pool geometry into API identity. |
| Creator owns completion; Join/Reap/Detach | Independent lifetime with RemTask; no retained completion | Keeps core task semantics close to Exec. Completion can be a later library facility. |
| Only the caller may exit | RemTask(NULL), RemTask(self), and RemTask(other) | Implements the original operation, with explicit resource-cleanup responsibility. |
| Lock/Unlock with CARD statuses | Forbid/Permit procedures and classic nesting state | Makes scheduling exclusion recognizable; blocking semantics are specified before adding Wait. |
| No priority field | Node.ln_Pri plus SetTaskPri; scheduler ignores values | User-authorized simplification with no future signature change when priority scheduling arrives. |
| No signal facility | Defer signals and their API entirely | User-authorized staging; Sleep and Join must not masquerade as Wait. |

The cost of Task pointers is loss of generation-based stale-reference detection.
The contract requires pointer lifetime synchronization and says so explicitly.
The benefit of keeping a separate private context is that a small bank-zero
pool can remain an implementation limit while Task objects live in ordinary
image data. The initial pool still has four user execution contexts and one
private idle context; it no longer retires capacity after 255 generations.

Retain stack/direct-page guards, registered procedure validation, complete
native register saves, COP `$50`, OS COP `$00`, serialized OS calls, and NMI-safe
stack/domain transitions. These are established platform requirements, not
arguments for retaining the old lifecycle API.

## Implementation boundaries

| Location | Required change |
| --- | --- |
| [tasks-v2.json](https://github.com/mkur/exec816/blob/499f1b0/abi/tasks-v2.json), [generate_tasks_v2.py](https://github.com/mkur/exec816/blob/499f1b0/tools/generate_tasks_v2.py) | Generate the public Task subset, classic constants, private context/bindings, import shapes and service definitions separately. |
| [exec.act](https://github.com/mkur/exec816/blob/499f1b0/lib/exec.act), [exectasks.act](https://github.com/mkur/exec816/blob/499f1b0/lib/exectasks.act) | Expose the new core through EXEC in the new task profile. Keep Sleep clearly identified as an extension; remove handle/completion bindings from that profile. |
| [taskpolicy-v2.act](https://github.com/mkur/exec816/blob/499f1b0/lib/taskpolicy-v2.act) | Replace handle lookup and parent/result transitions with Task admission, pointer membership, named lookup, removal and nesting operations. |
| [tasks-v2.s](https://github.com/mkur/exec816/blob/499f1b0/platform/altirraos/tasks-v2.s), [cooperative.s](https://github.com/mkur/exec816/blob/499f1b0/platform/altirraos/cooperative.s) | Marshal 24-bit Task/entry/finalizer pointers; start/finish tasks through the private context; remove assumptions that public identity is a 32-byte record index. |
| [native_program.py](https://github.com/mkur/exec816/blob/499f1b0/tools/native_program.py) | Bind the new imports and exact procedure entries; generate static stack configuration and a public root Task; version the selected profile. |
| [test_tasks.py](https://github.com/mkur/exec816/blob/499f1b0/tools/test_tasks.py), [task package tests](https://github.com/mkur/exec816/blob/499f1b0/tests/test_tasks_v2_package.py) | Replace lifecycle oracles, retain context/interrupt/OS checks, and qualify the new public call shapes in raw and optimized code. |
| [tasks example](../../examples/tasks.act), [task documentation](../guides/tasks.md) | Demonstrate static prepared Tasks, named lookup, Forbid/Permit and normal/custom finalization without join/reap. |

The old 240-byte bank-zero arena was sized for five 32-byte records and entry
bindings. Do not grow public Tasks into it by overwriting the adjacent DP guard.
Allocate public Task objects in image data and recalculate private context,
queue, counters and binding footprints. If the private arena cannot fit,
explicitly revise the platform reservations and overlap tests before execution.
Generated symbols replace hard-coded multiply-by-32 assumptions in both policy
and assembly.

The ready queue links public `tc_Node` fields, with no priority ordering in this
subset. A bounded private context table maps Task pointers to execution storage
and includes sleeping tasks for FindTask. An object's Node cannot simultaneously
be a ready-list node and an independent all-task-list node. Membership checks
use the context table; removed nodes' stale links are not evidence of membership.

## Version and gateway migration

The default general profile now uses `EXEC.Version() = $0200`. The initial
design-only commit left the previous runtime version unchanged.
Keep the current compatibility launch profiles and their service meanings.
The new `--tasks` profile must reject imports of the retired handle/completion
API, rather than accept calls with misleading meanings.

Retain `$00` Version, `$01` Yield, `$06` Poll and `$0B` Sleep with their existing
semantics. Reserve `$0F/$10` for the already planned heap services. In the new
profile reject `$02-$05`, `$07-$0A` and `$0C-$0E` as unsupported legacy services.
Do not reinterpret their CARD arguments as Task pointers.

Assign new core selectors in the v2 machine-readable ABI:

| Selector | Service |
| --- | --- |
| `$11` | AddTask |
| `$12` | RemTask |
| `$13` | FindTask |
| `$14` | SetTaskPri |
| `$15` | Forbid |
| `$16` | Permit |

Ordinary source calls follow the pinned compiler's native ABI, including
three-byte pointer results. The six new raw services require M=X=0. Unsupported
entry widths or calling domains take a defined context fault before mutation;
pointer/void results must not disguise an error status as a result. Legacy
services keep their existing width and error contracts.

The following raw call shapes are checked against emitted imports and hosted
execution. A's low byte contains the selector. Unused bits of A and the pointer-bank
argument must be zero; Forbid/Permit do not consume X or Y.

| Service | Inputs | Results |
| --- | --- | --- |
| AddTask | X = low word, Y = zero-extended bank of a nine-byte argument block containing task, initialPC, finalPC at offsets 0/3/6 | A = Task low word, X = zero-extended bank; both zero on admission failure |
| RemTask | X = Task low word, Y = zero-extended bank; both zero means self | No result; self-removal never returns |
| FindTask | X = name low word, Y = zero-extended bank; both zero means self | A = Task low word, X = zero-extended bank; both zero on a miss |
| SetTaskPri | X = Task low word, Y = zero-extended bank, A high byte = priority representation | A = zero-extended old priority byte |
| Forbid / Permit | None | No result |

Preserve the complete saved context except the specified result registers.
The AddTask wrapper can reference its native argument area, whose three pointer
arguments have alignment one, offsets 0/3/6 and total size nine. Its
lifetime covers the call; copy values into kernel invocation storage before
publication. No global scratch packet is permitted. FindTask/RemTask each take
one three-byte pointer. SetTaskPri's native arguments occupy four bytes
(pointer at 0, priority at 3), with a fifth outgoing byte required by the native
call alignment. Qualify these shapes rather than overriding the
compiler's ABI if emitted offsets differ. Void-call precondition failures take
a defined launch fault, rather than a silently discarded status value.

Generated allocator prototype metadata targets `$0201`, following the `$0200`
Task core. Heap services remain pending. At Task migration, its `$0F/$10`
selectors and argument layouts were unchanged. The later
[classic Exec allocation design](../reference/memory.md) supersedes that
prototype API and requires a new heap ABI qualification before integration.
Earlier `$0103` probes remain historical evidence for the old call shapes.

## Executable slices

Commit each completed major slice, with its own validation evidence. Compiler
defects exposed by the work belong in actionc with focused regressions; use the
[pinned toolchain](../../toolchain/actionc.json) unless a recorded update is needed.

### 0. Record the reviewed design

Add the public contract and this migration plan. Link them from the current
task documentation and roadmap, distinguishing target from implemented behavior.
Check content, references, and agreement with the allocation plan. No execution
qualification is claimed for this documentation-only slice.

### 1. Freeze public layout and native call shapes

Status: complete. The [ABI qualification](../qualification/tasks-exec-abi.json)
records passing raw and optimized hosted probes, all public field offsets,
all priority byte values, far/bank-crossing storage and native import layouts.
The emitted Task is 42 bytes; SetTaskPri needs five outgoing bytes. Those initial probes did not enable any v2 gateway service; the default
profile was switched in the final integration slice.

Add the v2 ABI and generated definitions in an isolated build/profile path.
Exercise Task/Node embedding, pointer arguments/results and signed-byte priority
representations with emitted raw/optimized probes. Include odd and upper-bank
Task addresses and names. Confirm the emitted Task size (42 bytes; the original estimate was 38) and all offsets,
not just host-side packing arithmetic. AddTask's three-pointer call and null
finalizer must reach a probe without truncation. Record exact wrapper stack
costs and raw gateway marshalling before wiring policy.

### 2. Admit and remove caller-prepared Tasks

Status: complete. The first core commit passed raw/optimized hosted
execution with normal return, self-removal, custom finalization, named lookup,
priority storage and scheduling exclusion. Expanded tests cover rejection,
external removal, root-context reuse and more than 255 lifetimes.

Add the private context mapping and public root Task, preserving the existing
stack/DP pool reservations. Implement AddTask, normal-return/default removal,
custom finalizers, and RemTask for self and another live task. Reuse released
execution storage only on the kernel stack after detaching the old activation.
Leave caller-prepared stack data outside the initialized frame intact.

Use a minimal executable profile fixture while the old public profile remains
available. Qualify successful admission, null-result failures without partial
mutation, exhaustion/reuse beyond 255 lifetimes, entry/finalizer validation,
self-removal without returning, external removal without running a finalizer,
root removal with surviving tasks, and final shutdown. Borrowed public records
must remain readable after removal but cease to be discoverable or runnable.

### 3. Complete lookup, priority storage and scheduling exclusion

Status: complete; included in the passing raw/optimized qualification matrix.

Implement FindTask, SetTaskPri and Forbid/Permit. Qualify exact case-sensitive
lookup across running/ready/sleeping tasks, unnamed/duplicate names, and lookup
protected against self-removal. Cover all priority byte patterns, unchanged
FIFO behavior after priority changes, and round-robin progress without voluntary
yields. Changing a field must not accidentally enable priority scheduling.

Cover nested exclusion, pending VBI and Yield delivery only after the outermost
Permit, self-removal while forbidden, external removal preserving caller nesting,
and invalid count operations. Preserve the existing Sleep extension's duration,
wrap and protected-call behavior. RemTask must cancel a sleeping task so no
deadline can resurrect a removed or reused context.

### 4. Cut over the public profile and qualify integration

Status: complete. The default profile, example and documentation are switched;
all 64 Task cases and 14 compatibility/Lists cases pass on the corrected pinned
emulator. All 36 host package tests and the Exec, Task and heap generators pass.
The example and documentation snippet compile in both modes. The earlier
two-task launch APIs remain unchanged.

Switch `--tasks` to the new EXEC core and `$0200` version. Migrate examples and
fixtures away from handles and retained completion. Finish import rejection and
legacy raw-selector checks. Keep earlier qualification records as historical
evidence, not proof of the changed lifecycle.

Run the complete new task matrix in raw and optimized modes on the pinned ROM
and emulator, including NMI entry at context-transition checkpoints, timer IRQs,
all native M/X combinations in running tasks, decimal mode, hidden B, DBR/D/PBR,
I-state deferral, stack/domain guards, OS console coexistence and bounded
completion. Restricting new raw service entry widths does not relax context
preservation for arbitrary interrupted task widths. Regress unchanged launch
profiles and Lists; retain the runner's completion guard that checks published
status as well as the sampled PC.
Record final linked sizes, stack bounds, input hashes and the new qualification.

## Explicitly later work

Priority-based selection; signals and Wait; Disable/Enable; traps/exceptions and
switch hooks; AllocEntry/FreeEntry and nonempty tc_MemEntry; CreateTask and dynamic
stack/DP allocation; optional managed-completion helpers. None is a prerequisite
for the initial core described here. Preserve familiar signatures when adding
these facilities, and document any necessary native adaptations.

The shared [allocation design](../reference/memory.md) remains independent:
AllocMem and AllocVec do not enroll memory for task-exit cleanup. Future
tc_MemEntry support requires explicit enrollment and reclamation semantics, with self-removal freeing
owned stack/Task storage only after abandoning the old activation.
