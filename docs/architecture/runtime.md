# Tasks and execution contexts

Exec816 shares code and memory between Tasks while giving each Task its own
execution state. A module, a device, a port and an open file are not scheduling
units. The kernel schedules Tasks.

For the larger picture, start with the [system overview](overview.md).
The [filesystem guide](filesystems.md) follows one request through
several of these contexts.

## What runs in a typical demo

After the shell has mounted its system disk, the standard shell/prime demo has
five persistent public Tasks:

| Task | Work |
| --- | --- |
| Shell/root | Read commands, execute built-ins, load external programs and collect children. |
| Prime computation | Compute independently and write to its console instance. |
| Console worker | Service all console instances and update the physical display. |
| `dos.filesystem` | Serve filesystem packets for every mount and open disk file. |
| SIO worker | Own queued serial transactions and their completion. |

One external command temporarily adds one Task; a two-command pipeline adds
two, taking this demo to seven of its eight public slots. A separate private
idle context runs when no public Task is ready. It is outside that eight-slot
count. The kernel's own stack/direct-page context is also separate; it is used
for service entry rather than being another independently scheduled Task.

This is an example configuration, not an unconditional boot inventory.
Console support and mounts are configurable, filesystem startup is lazy, and
service lifetime can change the number of active workers. Plain Task builds
default to four public slots; the standard demo uses eight. Both capacities
use the same kernel implementation.

## What creates another Task?

| Operation | Execution storage | Other state |
| --- | --- | --- |
| Admit a Task or start a Process | Uses one public slot and its stack/direct-page domain. | Task record; a Process also owns command and DOS lifetime state. |
| Mount another configured volume | Shares the existing filesystem and SIO workers. | Volume records, request port, geometry and device-open request. |
| Open another disk file | Shares the filesystem worker. | Handle wrapper and file backing/cursor. |
| Create a directory lock | Shares the filesystem worker. | Metadata, ancestry, canonical name and enumeration identity. |
| Create a console instance | Shares the console worker. | Retained cells, input and presentation state. |
| Create a pipe | Runs through its callers; no worker. | Buffer, endpoint wrappers and waiting-caller state. |
| Create a message port | Uses its receiving Task. | Queue and notification state. |

The first use of an enabled service may start its worker. The rows above describe
the additional cost of another object once that service exists.

A sleeping Task still occupies its slot. Removal makes the execution storage
reusable; waiting for disk, a key or a message does not temporarily give that
slot to another Task. This is why a per-file or per-window Task would be costly.

## Kernel entry and ordinary calls

Kernel services use **`COP #$50`**. The native gateway preserves the interrupted
context, validates the call and enters either a short native handler or the
general dispatcher. Short handlers use the same public gateway and semantics.
The kernel can choose another ready Task before returning to application code.

Ordinary resident routines remain ordinary calls. For example:

- A DOS call prepares its request in the application Task's context.
- The filesystem worker executes path traversal and filesystem parsing on its
  own stack and direct page.
- The loader validates, allocates and relocates in the loading caller's context.
- List and string helpers execute in the context of whoever calls them.

These routines enter the kernel when they need a service such as allocation,
message delivery or waiting. They do not cross COP for every calculation or
helper call. Resident service Tasks share the system's address space; this is
not a protected user/kernel address-space split.

Native interrupt handlers are another execution context. SIO IRQ code handles
byte timing and publishes completion; it is not a Task or a place to run DOS
filesystem parsing. VBI drives preemption through the platform's context-switch
protocol. See the [platform contract](../reference/platform.md) and
[gateway implementation](../history/kernel-fast-path-implementation.md).

## Messages carry work; signals announce it

A message port contains a queue. Its signal wakes the receiving Task, which
then removes messages and processes them. One Task can receive through many
ports, and several ports can share an arrival signal. Filesystem mount ports
use that arrangement.

A signal is a pending bit, not a request count or a payload. Several arrivals
can set the same bit; the queue preserves the actual work. `WaitPort` waits for
an available message, `GetMsg` removes one, and `ReplyMsg` returns it to the
sender's reply port. The sender must retain message and borrowed buffer storage
until the receiver is finished and the reply has been collected.

Device requests follow the same lifetime principle. A caller can submit queued
I/O and wait for completion while other Tasks run. For synchronous DOS disk
calls, the application waits for the filesystem reply; the filesystem worker
may itself wait for an SIO reply. Waiting releases CPU time, not ownership of
the in-flight request or its buffers.

`Forbid`/`Permit` provide nested scheduling exclusion for Task-side updates.
They do not disable interrupts. IRQ/NMI interaction still requires the native
protocol; Forbid alone is not a general interrupt lock. See
[signals](../reference/signals.md) and [ports](../reference/ports.md).

## Memory and lifetime

Native stacks and direct pages must fit in bank zero. Most code, object records
and buffers live in upper RAM. Task capacity is therefore a build-time memory
decision, while adding file handles or cached sectors primarily consumes heap
space. Generated memory maps are authoritative; the
[Task capacity guide](task-capacity.md) gives the reserved costs, including
guards, padding and unused capacity.

A Process gives a command a managed lifecycle around an ordinary Task. It
receives copied arguments, its own DOS context and owned inherited handles.
On normal return, the Process finalizer closes its DOS objects and releases
that context. The parent waits for actual Task retirement before collecting
the result and releasing retained image ownership.

That cleanup does not free arbitrary Exec allocations made by an application.
Plain Tasks must also release their DOS resources before removal. Shared memory,
Task records and callback code must outlive their users. There is no general
forced-termination mechanism that safely repairs arbitrary ownership.

Resident command globals are shared. Separate loads of a disk program have
separate mutable data; restarting the same retained image preserves its data.
Inherited file handles have distinct ownership wrappers but share the open
position. These distinctions matter when a command runs more than once; see
[Processes](../reference/process.md) and [loaded images](../reference/program-loading.md).

For source navigation, start at [Task policy](../../lib/exec/taskpolicy.act),
[DOS callers](../../lib/dos/doscalls.act), [Process](../../lib/dos/process.act),
[filesystem worker](../../lib/fs/fsworker.act),
[SIO driver](../../lib/io/siodriver.act) and
[console driver](../../lib/console/consoledriver.act).
