# Signals and Wait

[Reference index](README.md) · [Task API](tasks.md)

Signals are 32-bit, per-Task notifications. Repeated posts of a bit coalesce;
use a message queue or other state to retain individual work items. Public calls
belong to `EXEC`; exact declarations and selectors are generated from
[tasks.json](../../abi/tasks.json).

## Public API

| Call | Contract |
| --- | --- |
| `AllocSignal(number)` | Allocate a caller-owned bit. Pass 0–31 or `$FF` for any available bit; return its number or `$FF` on failure. |
| `FreeSignal(number)` | Release a caller-owned bit. `$FF` is a no-op. |
| `Signal(task, mask)` | OR bits into a live Task's received mask and make a matching waiter eligible to run. `NULL` does not mean self. |
| `SetSignal(new, mask)` | Replace the selected received bits and return the entire previous mask. `(0, 0)` takes an atomic snapshot. |
| `Wait(mask)` | Return and consume matching received bits, blocking if none match. Unrelated bits remain pending. |

Bit numbers use `BYTE`; masks use unsigned `LONGCARD`. Check allocation failure
before forming a mask. Bit 31 is valid. Bits 0–15 are reserved for system use;
applications allocate from 16–31. Each Task owns an independent namespace.
Allocation clears old received state for that bit; freeing does not promise to
clear it. Stop producers before freeing or reusing a bit.

A reserved, already allocated or invalid requested bit causes allocation failure
without mutation. Freeing an unowned/reserved bit is misuse. The allocation mask
is ownership bookkeeping, not a delivery filter: subsystem owners may use their
reserved bits through the same full-width operations.

## Waiting and scheduling

`Wait` wakes on any requested bit, not all of them. It has no timeout parameter.
`Wait(0)` parks indefinitely; it is neither a yield nor a poll. A blocking wait
allows other Tasks to run even inside `Forbid`, then restores the caller's
nesting on resumption. Code relying on exclusion must recheck its state after
such a wait.

A signal means that work may exist. Drain the associated queue before waiting
again; a stale notification is harmless. Further posts before a pending wait
consumes its result may join that result. There is no event-count guarantee or
promise that the target runs immediately.

Only live Task pointers are valid. Do not write active signal fields directly
or use multiword field reads as atomic snapshots. Use the public calls from Task
context. Native interrupt producers use the platform's documented posting path;
they do not call ordinary Task wrappers from IRQ/NMI context.

## Delivery and lifetime

Posting identifies the target directly. An IRQ can retain that Task in the
pending-wake queue until a safe kernel boundary publishes readiness; it does not
scan unrelated Tasks. Removal and reuse follow the [Task lifetime contract](tasks.md).
The [platform contract](platform.md) defines interrupt and context-transition
rules.

Try the [signal example](../guides/tasks.md). The original design, ABI migration
and revision-specific timing discussion remain in the
[historical signal design](../history/signals-wait-design.md) and
[delivery review](../history/signals-delivery-review.md). Use the
[testing policy](../contributing/testing.md) for present qualification scope.
