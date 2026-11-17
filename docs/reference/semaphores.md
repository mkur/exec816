# Task semaphores

[Reference](README.md) · [Tasks](tasks.md) ·
[Design](../plans/native-semaphore-design.md) ·
[Development evidence](../history/native-semaphores.md)

Action! provides `InitSemaphore`, `ObtainSemaphore`, `AttemptSemaphore` and
`ReleaseSemaphore` through `USE EXEC`.
C provides the same functions in `<exec/semaphores.h>` (also included by
`<proto/exec.h>`). Current loaded APP/provider ABI is 48; rebuild both together.

`SignalSemaphore` is an opaque 12-byte, two-byte-aligned caller-owned object.
Initialize it once before publication and keep its address live while used.
Init is ordinary library code and must not race with use of the object.
Do not copy or reinitialize a published semaphore.
Calypsi packs record members. Declare C storage with
`__attribute__((aligned(2)))`; when embedding an object, arrange its enclosing
record's alignment and offset too. The generated `EXEC_SEMAPHORE_ALIGNMENT`
constant records the required storage alignment. C pointers remain huge at the
source boundary; the object itself contains only native private fields.

Attempt returns a full LONGINT: one on acquisition, zero when another Task
owns the semaphore. Ownership is exclusive and recursive. Each successful
acquisition needs one Release from that same Task. Other Tasks continue to run
while ownership is held. The service does not allocate memory or signal bits.

Obtain sleeps on contention. Final Release hands ownership directly to the oldest
waiter before making it runnable. The resumed Obtain already owns the resource;
newcomers cannot barge. FIFO resource order does not change scheduler priority.
Normal signal Wait is permitted while owning a semaphore. Signals posted during
semaphore waiting remain pending and cannot grant or wake that waiter. A blocked
Obtain preserves outer Forbid nesting; contention with caller I set faults before
enqueue. Immediate operations preserve caller masking.

Wrong-owner or excess Release, recursion/count overflow and removal of a Task
owning or waiting for a semaphore are launch faults. Release all ownership before RemTask or
default Task retirement. There is no owner-death recovery, shared mode,
priority inheritance, timeout or interrupt-handler acquisition.

The stateful calls each issue one public COP request and use the common native
context and late-work protocol. A caller's outer Forbid nesting is preserved.
Native record offsets and selectors come from
[the machine-readable ABI](../../abi/semaphores.json); applications must use the
opaque type rather than inspect its private fields.
