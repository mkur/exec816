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
metadata can live in upper RAM. The eight-slot profile uses five ordinary worker
stacks, two larger worker stacks and a smaller idle stack, and places the bank
ownership table in upper RAM. Persistent pools
are packed below the temporary boot arena, so initializing a later slot does
not overwrite loader/staging storage.

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
- Loading-only ranges and the free area available after their retirement.

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
| OS/loader ranges | 31,232 | 31,232 |
| Fixed Exec runtime, including aperture, guards and slack | 11,552 | 10,528 |
| Public and idle pools | 9,120 | 14,880 |
| Total reserved | 51,904 | 56,640 |
| One contiguous unreserved range | 13,632 | 8,896 |

The manifest still occupies 2 KiB during loading. Total loading reservations
are 54,128 and 52,592 bytes respectively. Every DP now reserves exactly 256
bytes. Eight-Task slots 1–5 have 1,024 stack bytes; slots 6–7 have 2,560 bytes.
Each adds 32 external guard bytes and includes 256 bytes of interrupt reserve.
Root has 1,536 stack bytes and idle 512; every four-Task stack has 1,536 bytes.
Initialization retains the 2 KiB manifest in addition to the runtime budget.

`CreateTask` chooses the smallest free pool that fits the rounded request,
breaking equal-size ties by slot order. A 2,560-byte request uses one of the
two larger pools; a third fails while both remain owned. Small requests use
ordinary pools first but can consume the larger ones. Root and idle are never
creation candidates. Process launch still selects its first free slot and has
no stack-size parameter. These are shared pools, with no reservation for GEM.

The larger allocation leaves 2,304 bytes above the interrupt floor before
native frames and nested adapter use. Passing a larger size to `CreateTask`
does not allocate bank-zero memory. Explicit build-time `--worker-stack`
overrides replace every worker size without moving bases; the packager rejects
overlap, including overlap with boot storage. Omitted overrides use the profile.
The [development record](../development/larger-task-stacks.json) measures the
two-pool change: fixed delta 0, slots 6–7 +1,536 bytes each, total +3,072.

[Bank-zero compaction](../development/bank-zero-compaction.json) packs the
persistent reservations together, with no additional eight-Task byte savings.
It removes the obsolete 240-byte near context reservation in four-Task builds;
current Task metadata remains in upper RAM. Per-Task costs do not change.

The current map starts at `$0A00`, protecting 512 more bytes for the OS or
binary loader. Fixed Exec runtime and per-Task costs are unchanged. Reducing
unused temporary loader capacity by 512 bytes keeps loading totals unchanged;
see the [platform contract](../reference/platform.md#bank-zero-memory-budget).

Kernel DP is `$0C00`. Public slot `i` has DP `$0D00+i*$100`; idle is slot
`capacity`. The four-Task DP area ends at `$11FF`, followed by the full near
bank table at `$1200–$15FF`. The eight-Task DP area ends at `$15FF`. Both
capacities then place the resident adapter at `$1600–$25FF`.

Stack placement is explicit in the platform profile. Four-Task bases, including
idle, are `$2610`, `$3250`, `$3870`, `$3E90`, `$44B0`. Eight-Task bases are
`$2610`, `$3250`, `$3670`, `$3A90`, `$3EB0`, `$42D0`, `$46F0`, `$5110`, `$5B30`.
Kernel stack starts at `$2C30`, with 1,536 bytes. Every stack retains 16-byte
guards at both ends; adjacent guarded reservations have no extra padding.

After startup, the free range is `$4AC0–$7FFF` for four Tasks or `$5D40–$7FFF`
for eight. Staging, manifest and loader temporarily occupy `$5DF0–$7BFF` inside
this area. The manifest remains live until `startup_complete`. Generated
`phase_reservations` and `runtime_free_ranges` describe these lifetimes; free
space remains unregistered with the heap.

The diagnostic eight-Task register capture stores its additional 128 bytes
at `$7D00–$7D7F`, clear of boot state and production pools. Other observer
scratch is declared in `diagnostic_scratch` and checked against every phase.
Instrumented builds account for this temporary borrowing separately. The
production map reserves the full VBXE aperture but does not yet map it.

The [capacity implementation record](../history/task-capacity.md) preserves exact
maps, before/after totals and experiments for its recorded revision. Its old code
origins and serial timing limits are historical, not current build metadata.
