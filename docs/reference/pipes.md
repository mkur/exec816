# Anonymous DOS pipes

`DOS.Pipe(@pair)` fills a `DOS.PipePair` with owned `reader` and `writer` handles.
It returns DOS true on success, or zero with IoErr and both outputs null on
allocation failure. The output record must be mapped writable storage. The caller retains
ownership of its DOS context if allocation fails after creating that context.
There is no named PIPE: namespace.

Use normal Read, Write, Close and stream selection. Handles belong to their
creating Task; Process inheritance creates separate owned wrappers referring to
the same buffer. Raw handle pointers cannot be passed to another Task. Read on
the writer or Write on the reader fails with ERROR_OBJECT_WRONG_TYPE; Seek fails
with ERROR_SEEK_ERROR. IsInteractive returns false. A zero-length transfer on the
correct end succeeds without waiting.

The buffer holds 1,024 bytes. Read returns available bytes, waiting only while
empty and at least one writer exists. EOF follows the last writer's close after
all buffered bytes have been read. Write completes the requested transfer while
readers remain, waiting when full. Closing the last reader wakes blocked writers
with ERROR_BROKEN_PIPE (310). Both operations can return a committed positive
prefix with a secondary error; an error before any bytes returns -1. No text or
line-ending translation occurs.

Foreground cancellation wakes a blocked transfer with ERROR_BREAK. Close and
Process cleanup retire references even while cancellation is pending. An early
consumer exit therefore cannot leave its producer asleep on a full pipe. The
parent must close unused inherited ends: any retained writer postpones EOF.
Duplicated endpoints share byte order; this first contract makes no promise of
atomic multi-writer records or ordering among competing waiters.

Each transfer retains its owned wrapper until it returns. A blocked call borrows
one signal from its Task and publishes a stack-local waiter while holding Forbid.
It clears the signal and rechecks the condition under that same exclusion before
sleeping. Close/copy publishes the condition and signals linked waiters under
Forbid, preventing lost wakeups. Waiters unlink before their signal or stack can
be reused. Copies are at most 64 bytes per critical section; IRQs remain enabled
and the existing NMI scheduling protocol applies. No wait holds Forbid and no
new IRQ pointer or service Task is introduced.

The backing buffer and metadata occupy upper RAM and are freed after the last
endpoint reference retires. Active calls necessarily retain an endpoint; a
nonempty waiter list at final release is an invariant failure. Signal/allocation
exhaustion returns an ordinary resource error with ownership intact. Reserved
bank-zero delta is **0 fixed and 0 per Task**, including guards and unused capacity.

The [foreground group](process.md#two-member-foreground-groups) supplies
two-child lifetime and cancellation. The [shell](../guides/shell.md) uses it to execute
one two-stage external pipeline; pipe handles also remain usable independently.
