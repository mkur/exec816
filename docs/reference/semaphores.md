# Task semaphores

[Reference](README.md) · [Tasks](tasks.md) ·
[Design](../plans/native-semaphore-design.md) ·
[Development evidence](../history/native-semaphores.md)

The current Action! subset provides `InitSemaphore`, `AttemptSemaphore` and
`ReleaseSemaphore` through `USE EXEC`. Blocking Obtain is not yet available.

`SignalSemaphore` is an opaque 12-byte, two-byte-aligned caller-owned object.
Initialize it once before publication and keep its address live while used.
Init is ordinary library code and must not race with use of the object.
Do not copy or reinitialize a published semaphore.

Attempt returns a full LONGINT: one on acquisition, zero when another Task
owns the semaphore. Ownership is exclusive and recursive. Each successful
acquisition needs one Release from that same Task. Other Tasks continue to run
while ownership is held. The service does not allocate memory or signal bits.

Wrong-owner or excess Release, recursion/count overflow and removal of a Task
owning a semaphore are launch faults. Release all ownership before RemTask or
default Task retirement. There is no owner-death recovery, shared mode,
priority inheritance, timeout or interrupt-handler acquisition.

The stateful calls each issue one public COP request and use the common native
context and late-work protocol. A caller's outer Forbid nesting is preserved.
Native record offsets and selectors come from
[the machine-readable ABI](../../abi/semaphores.json); applications must use the
opaque type rather than inspect its private fields.
