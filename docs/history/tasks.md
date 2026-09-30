# General task management

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/tasks.md) and [history index](README.md).

`--tasks` builds the single current Exec Task implementation: pointer-based
Tasks, the six classic core calls, signals, Wait, memory allocation and lifetime
services. `EXEC.Version()` currently returns `$0700`. The native packet tag
remains `$0600`. There is no API selector or compatibility build. During active
development, rebuild programs with the kernel when its ABI changes.

Tasks share one loaded image and have separate native stacks and direct pages.
The FIFO scheduler stores but ignores priority. Root counts toward the public
capacity; a separate private idle context runs when all public tasks wait.

## Capacity target and memory budget

The [eight-task configuration](../architecture/task-capacity.md) meets the required baseline for
asynchronous SIO and DOS. Select `--task-capacity 8`; twelve/sixteen tasks remain
future qualification targets. Plain `--tasks` uses the four-task layout. Both
capacities run the same policy, ABI and adapter, with different storage bounds.

A waiting Task retains its execution storage. Removing it makes that storage
reusable; preparing extra descriptors does not increase simultaneous capacity.
The [complete budget](../architecture/task-capacity.md#complete-bank-zero-budget) counts fixed
storage, root, workers, idle, guards, padding and loading/runtime reservations.
Public Tasks and private scheduling metadata live in upper RAM where possible.

## Build and run

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console \
  --task-capacity 8 --source examples/tasks.act --output build/tasks
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console \
  --task-capacity 8 --source examples/signals.act --output build/signals-eight
```

Task builds select banked loading and VBI preemption on the
[pinned 1 MiB machine](../../toolchain/altirra-1m.json). The examples print
`TASKS EXEC OK` and `SIGNALS OK`, respectively, through `DOS.Write` on `CON:`.
Press Return to exit and restore the OS display. Their small
[output helper](../../examples/example-output.inc) owns and closes the console
handle and releases the root Task's DOS context. Root occupies slot 0 and the
boot console worker slot 1; example workers start at slot 2. The Task example
uses three workers; the signal example uses six.

Both select the existing eight-slot profile. No fixed or per-Task bank-zero
reservation changes. Selecting eight instead of four for the Task example
increases its runtime reservation by 3,568 bytes, including guards, alignment
and unused capacity; see the [profile budget](../architecture/task-capacity.md#complete-bank-zero-budget).
The Amiga message example still fits the four-slot profile with its console.

`hello.act`, `cooperative.act` and `preemptive.act` remain low-level launcher
and ROM-coexistence probes using `EXECOS.Write`. Use these current Task examples
or [disk commands](../../examples/commands/hello.act) as application I/O examples.

The [generator](../../tools/generate_tasks.py) reads [tasks.json](../../abi/tasks.json)
and packages [taskpolicy.act](../../lib/exec/taskpolicy.act) with the native
[adapter](../../platform/altirraos/tasks.s). There is one generated public
[Task type](../../lib/exec/exec-task-types.inc).

## API and preparation

| Call | Behavior |
| --- | --- |
| `EXEC.AddTask(task, initialPC, finalPC)` | Admit a prepared Task and stack; return the same pointer or null on validation failure. |
| `EXEC.RemTask(task)` | Remove a live Task. Null or self removes the caller without returning. |
| `EXEC.FindTask(name)` | Case-sensitive lookup among live tasks; null name returns self. |
| `EXEC.SetTaskPri(task, priority)` | Store a BYTE priority and return its previous representation. Scheduling ignores it. |
| `EXEC.Forbid()` / `EXEC.Permit()` | Nest and release task-local scheduling exclusion; interrupts continue. |
| `EXEC.RetainTask(task, lease)` / `EXEC.ReleaseTask(lease)` | Acquire and consume an address-bound removal hold. See the [lifetime contract](../reference/resident-drivers.md#task-admission-and-lifetime). |
| `EXEC.RegisterResident(stopMask)` / `EXEC.UnregisterResident()` | Request notification when no ordinary Task remains; the service handles its own shutdown. |
| `EXEC.Yield()` / `EXEC.Poll()` | Request a switch / deliver a pending request at a safe boundary. |
| `EXEC.AllocSignal` / `EXEC.FreeSignal` | Allocate or free one of the calling task's signal bits. |
| `EXEC.SetSignal` / `EXEC.Signal` / `EXEC.Wait` | Update pending bits, notify a known Task, or block for any requested signal. See [signal semantics](../reference/signals.md). |
| `EXEC.AllocMem` / `EXEC.FreeMem`, `EXEC.AllocVec` / `EXEC.FreeVec` | Allocate and explicitly release shared upper RAM. See the [memory contract](../reference/memory.md) and [example](../../examples/memory.act). |
| `EXEC.AvailMem` / `EXEC.TypeOfMem` | Query matching heap capacity or a registered region's attributes. |
| `EXEC.Allocate` / `EXEC.Deallocate` | Manage a caller-owned MemHeader pool under caller-owned synchronization. |
| `EXECTASKS.Sleep(ticks)` | Timed extension: zero yields, 1–`$7FFF` waits; returns zero, `ERROR_TICKS` or `ERROR_LOCK`. |

See the [public contract](../reference/tasks.md) for field ownership, pointer lifetime,
raw call layouts, finalizer requirements and misuse faults. `EXEC.Task` occupies
62 bytes; use `EXEC.TASK_SIZE`. `ln_Pri` represents signed priorities as a BYTE.
An initialized empty `tc_MemEntry` is required; automatic memory reclamation is
not implemented.

A minimal statically allocated worker uses the generated `TASKSTACKS` platform
configuration. Global records start zeroed:

```action
MODULE EXAMPLE
USE EXEC
USE EXECLISTS
USE TASKSTACKS

EXEC.Task worker
PROC POINTER defaultFinalizer()

PROC WorkerEntry()
RETURN

PROC Main()
  EXEC.Task POINTER admitted
  worker.tc_Node.ln_Type=EXEC.NT_TASK
  worker.tc_SPLower=ADDRESS(TASKSTACKS.LOWER1)
  worker.tc_SPUpper=ADDRESS(TASKSTACKS.UPPER1)
  worker.tc_SPReg=worker.tc_SPUpper-SIZE(2)
  EXECLISTS.NewList(@worker.tc_MemEntry)
  admitted=EXEC.AddTask(@worker,@WorkerEntry,defaultFinalizer)
RETURN
ENDMODULE
```

The root may return while workers remain alive. An admitted worker can finish
before AddTask returns; use Forbid across admission and any setup requiring a
live target. Reusing a removed record requires resetting its state to
`TS_INVALID` and preparing its initial stack fields again. Task/name storage
must outlive every application reference.

## Scheduling and storage

The dispatcher changes ready links and sleep deadlines. IRQ signal posting
updates the known target and its private pending-wake node; a safe kernel drain
publishes readiness. NMI records ticks and follows the
[context-transition protocol](vbi-preemption.md). Forbid, an active OS call and
the interrupted I flag defer switching. A blocking Wait allows other tasks to
run and restores its caller's Forbid nesting when resumed.

Sleep uses a modular 16-bit VBI counter; removal cancels a sleeping task's
deadline. Idle uses a protected pending-wake check and WAI. After all public
tasks are removed, shutdown restores vectors and MEMLO and parks in AltirraOS
emulation mode. This is a controlled launcher completion, not a DOS return.

### Storage and loading lifetime

Private contexts occupy 64 bytes each in upper RAM. Metadata includes the root
Task, ready and pending-wake queues, counters and entry bindings: 512 bytes
for four public tasks plus idle, or 768 bytes for eight plus idle. Public
62-byte Task records belong to application storage; the root record is kernel-owned.
Lifetime state uses ten formerly unused context bytes, with no reservation
increase. Each caller-owned `EXEC.TaskLease` occupies 12 bytes.

The four-task layout uses these bank-zero pools:

| Context | Direct page | Stack allocation | Compiler floor / initial S |
| --- | --- | --- | --- |
| 0 (root) | `$2200` | `$4200-$47FF` | `$4300 / $47FE` |
| 1 | `$2400` | `$5200-$57FF` | `$5300 / $57FE` |
| 2 | `$2E00` | `$6900-$6EFF` | `$6A00 / $6EFE` |
| 3 | `$5A00` | `$7100-$76FF` | `$7200 / $76FE` |
| 4 (idle) | `$5C00` | `$7900-$7EFF` | `$7A00 / $7EFE` |

The [eight-task map](../architecture/task-capacity.md#checked-placement-and-lifetime) uses
smaller worker/idle stacks and reclaims the bank table's bank-zero reservation.
Use generated `TASKSTACKS.StackLower(slot)` and `StackUpper(slot)` or the
`LOWERn`/`UPPERn` constants; UPPER is exclusive. Each stack includes 256 bytes
of interrupt reserve and has 16-byte external guards at both ends. The kernel
retains its own DP `$2600` and stack `$4A00-$4FFF`.

Pools reusing loader/staging memory become active only after standard
`EXECMEMORY.Init` adoption. The packager checks all reservations and admits
only exact registered application procedure entries and writable public Task
storage. Removal does not release shared image banks or free borrowed storage.
Dynamic stack allocation and nonempty memory-list reclamation remain future work.

## Validation

```sh
python3 tools/test_tasks.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/test_signals.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/generate_tasks.py --check
python3 -m unittest discover -s tests
```

The suites exercise raw/optimized emitted calls, admission and reuse, full-width
pointers and masks, Wait/Forbid, real IRQ delivery, injected NMI transitions,
register restoration, guards, OS coexistence and bounded completion. Small
single-program/two-task launcher probes remain platform tests, not supported
alternative Task APIs. Older qualification JSON records describe their original
commits; the [signal implementation record](signals-implementation.md) records
current functionality and timing limits.

The restricted IRQ byte pump passes the 125 kbaud target. Normal concurrent
kernel activity still needs shorter masked sections before general SIO can be
qualified. This consolidation does not change that result.

The [consolidation checks](../qualification/task-consolidation.json) cover the
single implementation, current core/signal ABI probes, admission, far Tasks,
Wait/Forbid, IRQ drain races, native contexts, OS transitions and eight-task
builds at kernel banks 1 and 3. The rebuilt long serial-pump image is identical
to its previously qualified binary; no new baud measurement is claimed.

Consolidation changes bank-zero reservations by **0 fixed bytes, 0 per public
task and 0 for idle** compared with the former signal implementation. Complete
runtime totals, including OS ranges, remain **57,968 bytes** for four tasks and
**61,536 bytes** for eight; loading totals remain 58,560 and 57,232 bytes.
The [capacity budget](../architecture/task-capacity.md#complete-bank-zero-budget) includes all
fixed/per-task storage, guards, padding and unused reserved space.
