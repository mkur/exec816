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
workers. A ninth admission is rejected. Other capacities need a new checked platform stack map; the current packager
rejects them.

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
- Each aligned 256-byte DP, with no external guards or stride padding.
- Stack allocations, guards and interrupt reserve.
- Loading-only ranges and the later runtime ranges that reuse them.

Payload bytes and reserved bytes answer different questions. A small live object
inside a larger reserved arena does not make the rest of that arena free.
Implementation slices must report fixed/per-Task reservation deltas, including
zero; see the [platform budget rule](../reference/platform.md#bank-zero-memory-budget).

Moving state to `$0800`, placing globals in upper RAM and retiring the manifest
after startup recovered **10,240 fixed bank-zero bytes; 0 bytes per Task**;
see the [relocation record](../development/bank-zero-relocation.json).
The subsequent [VBXE aperture reservation](../development/vbxe-aperture.json)
assigns 4,096 of those bytes to `$8000–$8FFF`, leaving a net recovery of
6,144 bytes. The subsequent [DP compaction record](../development/dp-compaction.json)
recovers another 192 bytes for four Tasks or 2,336 bytes for eight. The fixed
saving is 32 bytes in either layout; each public Task and idle save 32 or 256
bytes respectively. Stack reservations and public Task capacity are unchanged.

| Reservation after startup | Four public Tasks | Eight public Tasks |
| --- | ---: | ---: |
| OS ranges | 30,720 | 30,720 |
| Fixed Exec runtime, including aperture, guards and slack | 11,792 | 10,528 |
| Public and idle pools | 9,120 | 11,808 |
| Total reserved | 51,632 | 53,056 |
| Unreserved across all holes | 13,904 | 12,480 |

The manifest still occupies 2 KiB during loading. Total loading reservations
are 54,368 and 52,592 bytes respectively. Every DP now reserves exactly 256
bytes. Eight-Task worker stacks remain 1,024 bytes plus 32 external guard bytes,
with 256 bytes of interrupt reserve inside the stack. Root has 1,536 stack bytes
and idle 512; every four-Task stack has 1,536 bytes.

Kernel DP is `$2100`. Public slot `i` has DP `$2200+i*$100`; idle is slot
`capacity`. The four-Task DP area ends at `$26FF`, before the full near bank table
at `$2800–$2BFF`. The eight-Task area ends at `$2AFF`, before boot state at
`$2C00`. No compatibility map with DP guards remains.

Stack placement is explicit in the platform profile, independent of DP packing.
Four-Task bases, including idle, are `$4200`, `$5200`, `$6900`, `$7100`, `$7900`.
Eight-Task bases are `$4200`, `$5200`, `$6810`, `$6C30`, `$7050`, `$7470`, `$7890`,
`$0D20`, `$7CB0`. Kernel stack stays at `$4A00`, with 1,536 bytes. Every stack
retains 16-byte guards at both ends.

Starting the low pool after staging also keeps the diagnostic eight-Task
register capture at `$0900–$097F` clear of live pools. That probe adds 128
temporary runtime bytes in instrumented builds only; it runs after loading.
The production map reserves the full VBXE aperture but does not yet map it.

The [capacity implementation record](../history/task-capacity.md) preserves exact
maps, before/after totals and experiments for its recorded revision. Its old code
origins and serial timing limits are historical, not current build metadata.
