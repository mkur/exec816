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
idle stacks and places the bank ownership table in upper RAM. Persistent pools
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
| OS ranges | 30,720 | 30,720 |
| Fixed Exec runtime, including aperture, guards and slack | 11,552 | 10,528 |
| Public and idle pools | 9,120 | 11,808 |
| Total reserved | 51,392 | 53,056 |
| One contiguous unreserved range | 14,144 | 12,480 |

The manifest still occupies 2 KiB during loading. Total loading reservations
are 54,128 and 52,592 bytes respectively. Every DP now reserves exactly 256
bytes. Eight-Task worker stacks remain 1,024 bytes plus 32 external guard bytes,
with 256 bytes of interrupt reserve inside the stack. Root has 1,536 stack bytes
and idle 512; every four-Task stack has 1,536 bytes.

[Bank-zero compaction](../development/bank-zero-compaction.json) packs the
persistent reservations together, with no additional eight-Task byte savings.
It removes the obsolete 240-byte near context reservation in four-Task builds;
current Task metadata remains in upper RAM. Per-Task costs do not change.

Kernel DP is `$0A00`. Public slot `i` has DP `$0B00+i*$100`; idle is slot
`capacity`. The four-Task DP area ends at `$0FFF`, followed by the full near
bank table at `$1000–$13FF`. The eight-Task DP area ends at `$13FF`. Both
capacities then place the resident adapter at `$1400–$23FF`.

Stack placement is explicit in the platform profile. Four-Task bases, including
idle, are `$2410`, `$3050`, `$3670`, `$3C90`, `$42B0`. Eight-Task bases are
`$2410`, `$3050`, `$3470`, `$3890`, `$3CB0`, `$40D0`, `$44F0`, `$4910`, `$4D30`.
Kernel stack starts at `$2A30`, with 1,536 bytes. Every stack retains 16-byte
guards at both ends; adjacent guarded reservations have no extra padding.

After startup, the free range is `$48C0–$7FFF` for four Tasks or `$4F40–$7FFF`
for eight. Staging, manifest and loader temporarily occupy `$5BF0–$7BFF` inside
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
