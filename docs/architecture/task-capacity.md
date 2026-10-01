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

Moving state to `$0800`, placing globals in upper RAM and retiring the manifest
after startup recovered **10,240 fixed bank-zero bytes; 0 bytes per Task**;
see the [relocation record](../development/bank-zero-relocation.json).
The subsequent [VBXE aperture reservation](../development/vbxe-aperture.json)
assigns 4,096 of those bytes to `$8000–$8FFF`, leaving a net recovery of
6,144 bytes. Pool sizes and public Task capacity remain unchanged.

| Reservation after startup | Four public Tasks | Eight public Tasks |
| --- | ---: | ---: |
| OS ranges | 30,720 | 30,720 |
| Fixed Exec runtime, including aperture, guards and slack | 11,824 | 10,560 |
| Public and idle pools | 9,280 | 14,112 |
| Total reserved | 51,824 | 55,392 |
| Unreserved across all holes | 13,712 | 10,144 |

The manifest still occupies 2 KiB during loading. Total loading reservations
are 54,464 and 53,136 bytes respectively. The eight-Task worker DP stride remains
512 bytes: 256 usable DP bytes, 32 guard bytes and 224 bytes of reserved spacing.
Worker stacks remain 1,024 bytes plus 32 external guard bytes, with 256 bytes of
interrupt reserve inside the stack. Root and idle retain their separate sizes.

The eight-Task allocator prefers the established arena above `$2000`, then the
low RAM after boot staging. Slot 7 uses `$0D20–$111F`, with a complete guarded
reservation of `$0D10–$112F`; idle uses `$7CB0–$7EAF`, guarded at
`$7CA0–$7EBF`. Root, slots 1–6 and all DPs keep their previous addresses.
Starting the low pool after staging also keeps the diagnostic eight-Task
register capture at `$0900–$097F` clear of live pools. That probe adds 128
temporary runtime bytes in instrumented builds only; it runs after loading.
The production map reserves the full VBXE aperture but does not yet map it.

The [capacity implementation record](../history/task-capacity.md) preserves exact
maps, before/after totals and experiments for its recorded revision. Its old code
origins and serial timing limits are historical, not current build metadata.
