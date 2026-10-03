# Task and signal examples

[Guides](README.md) · [Build prerequisites](../contributing/building.md)

The current Task API uses pointer-based Tasks with separate native stacks and
direct pages. Root and workers share the loaded image. Scheduling is FIFO;
stored priorities do not change selection. See the [Task reference](../reference/tasks.md)
for the contract and the [runtime model](../architecture/runtime.md) for ownership.

## Build and run

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console \
  --task-capacity 8 --source examples/tasks.act --output build/tasks
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console \
  --task-capacity 8 --source examples/signals.act --output build/signals-eight
```

Task builds select banked loading and VBI preemption on the
[pinned 4 MiB machine](../../toolchain/altirra-4m.json). The examples print
`TASKS EXEC OK` and `SIGNALS OK`, respectively, through `DOS.Write` on `CON:`.
Press Return to exit and restore the OS display. Their small
[output helper](../../examples/example-output.inc) owns and closes the console
handle and releases the root Task's DOS context. CreateTask selects free worker storage automatically; callers do not choose a
slot. The explicit AddTask example keeps its generated stack bounds. The Task example
uses three workers; the signal example uses six.

The [message example](messages.md) is another small starting point.
Low-level launcher probes such as `hello.act`, `cooperative.act` and
`preemptive.act` use EXECOS.Write for adapter testing; use these Task examples or
[disk commands](commands.md) as application I/O examples.

## Create a worker

Ordinary Tasks need only a name, priority, entry and minimum stack allocation:

```action
MODULE EXAMPLE
USE EXEC

CONST WORKER_STACK_SIZE=1024

PROC WorkerEntry()
RETURN

PROC Main()

  LET worker=EXEC.CreateTask(c"worker",0,@WorkerEntry,WORKER_STACK_SIZE)
  ; NULL means no suitable free pool or invalid arguments.
  ; This minimal example needs no later access to the borrowed result.

RETURN
ENDMODULE
```

Root may return while workers remain alive. The result belongs to Exec and may
already be retired on return; do not free it or poll its state. Use Forbid across
creation and setup that needs a live pointer. Use signals/messages for startup
and completion, as in [signals.act](../../examples/signals.act) and the
[message example](messages.md). Their final notification and self-removal share
one Forbid region, so the receiver cannot observe completion before retirement.

The stack request includes interrupt headroom and native frames, excludes guards,
and may select a larger existing pool. Zero, oversized or unavailable requests
return NULL. Keep borrowed names, code and shared data alive until retirement.

The eight-Task profile offers five 1,024-byte worker stacks and two 2,560-byte
worker stacks. Request `2560` for a worker that needs the larger allocation;
it includes 256 bytes of interrupt reserve, leaving 2,304 bytes before native
frames and adapter nesting. Both large workers can run together. Small requests
prefer smaller pools but may occupy a larger one, so admission still needs a
failure path. Root and private idle cannot satisfy a creation request.
Four-Task builds retain their 1,536-byte pools. Measure the actual call chain
and keep stack checks enabled; the request does not dynamically grow a stack.

[tasks.act](../../examples/tasks.act) deliberately retains AddTask: it teaches
caller-owned records, explicit generated stack bounds and a custom finalizer.
Use the [Task reference](../reference/tasks.md) for those lower-level contracts.

The [capacity note](../architecture/task-capacity.md) explains slots, idle and
bank-zero reservations. The [signal reference](../reference/signals.md) explains
Wait and notification ownership; the [memory API](../reference/memory.md) describes
explicit heap lifetime.

The original Task consolidation and revision-specific checks remain in the
[historical Task guide](../history/tasks.md). Choose further checks through the
[testing policy](../contributing/testing.md), rather than running every old suite
for each example change.
