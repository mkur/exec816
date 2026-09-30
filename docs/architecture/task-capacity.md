# Task capacity and bank-zero storage

[Architecture index](README.md) · [Runtime model](runtime.md)

The current layouts support four or eight public Tasks plus private idle on the
pinned AltirraOS platform. Root and service workers count toward public capacity;
the kernel's service-entry context and idle do not. Plain Task builds default to
four; the standard demo selects eight. Both run the same kernel and API.

## Slots and lifetime

A waiting Task retains its slot, native stack and direct page. Removal makes
those pools reusable; extra prepared descriptors do not increase simultaneous
capacity. Files, mounts, ports and console instances allocate state without
adding execution pools once their shared service exists.

Select `--task-capacity 8` when packaging a suitable resident application. The
[signal example](../guides/tasks.md) fills that profile with root, console and six
workers. A ninth admission is rejected. Larger candidate layouts accepted by a
generator are not thereby qualified configurations.

Use generated `TASKSTACKS.StackLower(slot)` and `StackUpper(slot)` values, with
an exclusive upper bound. Prepare `tc_SPReg=tc_SPUpper-SIZE(2)` as required by the
[Task API](../reference/tasks.md). Never copy a historical stack address or assume
all slots have the same size.

## Checked placement and lifetime

Stacks and aligned DPs require bank zero; public records and private scheduling
metadata can live in upper RAM. The eight-slot profile uses smaller worker and
idle stacks and places the bank ownership table in upper RAM. It reuses selected
loader/staging memory only after image adoption has retired bootstrap use.

The packager rejects image/reservation overlap. Kernel-bank selection changes the
resident image placement, not the fundamental bank-zero CPU requirement. Stack
checks and canaries cover tested use; arbitrary call depth can still exceed a
configured stack. Scheduling is FIFO even though Task priorities are retained.

## Complete bank-zero budget

Read the build's `memory.json`, especially `runtime_reservations`, `task_pools`
and `bank_zero_budget`. Account separately for:

- OS and fixed Exec reservations, including kernel/interrupt storage.
- Root, each other public slot and private idle.
- Each DP's alignment, external guards and unused reserved padding.
- Stack allocations, guards and interrupt reserve.
- Loading-only ranges and the later runtime ranges that reuse them.

Payload bytes and reserved bytes answer different questions. A small live object
inside a larger reserved arena does not make the rest of that arena free.
Implementation slices must report fixed/per-Task reservation deltas, including
zero; see the [platform budget rule](../reference/platform.md#bank-zero-memory-budget).

The [capacity implementation record](../history/task-capacity.md) preserves exact
maps, before/after totals and experiments for its recorded revision. Its old code
origins and serial timing limits are historical, not current build metadata.
