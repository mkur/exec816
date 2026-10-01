# Bank zero compaction plan

[Implementation plans](README.md) · [Platform contract](../reference/platform.md#bank-zero-memory-budget)

Status: implemented on 2026-10-01, against `26654ec`. The baseline is the
implemented [DP compaction](../development/dp-compaction.json).
[Development evidence](../development/bank-zero-compaction.json) records the
maps, input and image hashes, emitted checks and refreshed OF816 distribution.
The sequence below documents the implemented design; it is not a release
qualification claim.

Existing OF816 packaging already derives its borrowed arenas from the generated
layout, so rebuilding relocated the monitor without changing its source. The DP
observer now borrows only 32 bytes and compares live neighbouring contents.
Register-capture extension and far-write scratch use separately declared ranges
at `$7D00` and `$7C00`, checked against every ownership phase.

Pack persistent Exec reservations from `$0800` upward, leaving one contiguous
range below the VBXE aperture after startup. For the standard eight-Task build,
the free range is **`$4F40–$7FFF`, 12,480 bytes**. This combines the
previous nine holes; the largest was 4,592 bytes. Total eight-Task
reservations stay unchanged.

Retain the existing Task capacities, stack sizes, stack guards, interrupt
headroom and separate 256-byte DPs. Keep the full 4 KiB resident adapter arena,
including its internal padding. This slice changes physical placement and
removes one obsolete four-Task reservation. It does not enlarge stacks or
register the recovered range with the heap.

## Implemented persistent layout

All addresses are in bank zero and ranges are inclusive. This is the standard
eight-public-Task layout, including private idle:

| Range | Bytes | Reservation |
| --- | ---: | --- |
| `$0000–$07FF` | 2,048 | OS low memory |
| `$0800–$08FF` | 256 | Adapter state, unchanged |
| `$0900–$09FF` | 256 | Boot state, moved from `$2C00` |
| `$0A00–$0AFF` | 256 | Kernel DP |
| `$0B00–$12FF` | 2,048 | Public Task DPs, slots 0–7 |
| `$1300–$13FF` | 256 | Idle DP |
| `$1400–$23FF` | 4,096 | Resident platform adapter, moved from `$3000` |
| `$2400–$2A1F` | 1,568 | Root stack and guards |
| `$2A20–$303F` | 1,568 | Kernel stack and guards |
| `$3040–$4D1F` | 7,392 | Seven worker stacks and guards |
| `$4D20–$4F3F` | 544 | Idle stack and guards |
| `$4F40–$7FFF` | 12,480 | Unreserved after startup |
| `$8000–$8FFF` | 4,096 | Reserved VBXE aperture, unchanged |
| `$9000–$FFFF` | 28,672 | OS/hardware reservation, unchanged |

The persistent Exec block is exactly `$0800–$4F3F`, with no gaps between its
reservations. Internal unused capacity remains counted as reserved. Ordinary
globals, Task records and the eight-Task bank table stay in upper RAM.

Use `kernel_dp=$0A00`, `task_dp_base=$0B00`, `task_dp_stride=$0100`.
Public slot `i` owns `$0B00+i*$100`; idle uses slot `capacity`. Kernel and Task
DPs remain page aligned, without guards or padding.

Pack guarded stacks consecutively. A stack's base is its first storage byte;
reserve `[base-16, base+size+16)`. Keep 256 bytes of interrupt headroom inside
each stated stack size, plus the separate 16-byte guard at each end.

| Owner | Eight-Task base / stack bytes | Four-Task base / stack bytes |
| --- | --- | --- |
| Root, slot 0 | `$2410` / 1,536 | `$2410` / 1,536 |
| Kernel | `$2A30` / 1,536 | `$2A30` / 1,536 |
| Public slot 1 | `$3050` / 1,024 | `$3050` / 1,536 |
| Public slot 2 | `$3470` / 1,024 | `$3670` / 1,536 |
| Public slot 3 | `$3890` / 1,024 | `$3C90` / 1,536 |
| Public slot 4 | `$3CB0` / 1,024 | — |
| Public slot 5 | `$40D0` / 1,024 | — |
| Public slot 6 | `$44F0` / 1,024 | — |
| Public slot 7 | `$4910` / 1,024 | — |
| Private idle | `$4D30` / 512 | `$42B0` / 1,536 |

All stack bases satisfy the current 16-byte alignment requirement. Derive
floors, ceilings and initial S values from these bases and sizes. Validate
OF816 at the new root/kernel bases; their former page alignment must not
survive as an implicit assumption in code or observers.

### Four-Task placement

Four public DPs occupy `$0B00–$0EFF`, and idle uses `$0F00–$0FFF`. Move the full
1,024-byte near bank-table reservation to `$1000–$13FF`. Its active records
can be smaller, but its reserved capacity still counts. This fills the four
pages used by additional DPs in the eight-Task map and lets both capacities
share the adapter, root stack, kernel stack and first-worker base.

Remove the obsolete `$2D00–$2DEF` reservation inserted by
[task_capacity.py](../../tools/task_capacity.py). Current
[Task storage generation](../../tools/generate_tasks.py) places the records
in upper RAM; the old range remains in budget accounting and a diagnostic
dump. Confirm this ownership in the migration audit and remove the stale dump.
Do not relocate an unused reservation into the new pool.

The four-Task guarded stack area ends at `$48BF`. Its single free range becomes
**`$48C0–$7FFF`, 14,144 bytes**, recovering 240 bytes in addition to combining
the existing holes. Both capacities use the same kernel implementation and
public ABI. Unsupported capacities remain rejected.

## Loading and retirement

Place all three temporary loading reservations together inside the future
free range:

| Reservation | Range | Bytes | Lifetime |
| --- | --- | ---: | --- |
| Staging | `$5BF0–$5FFF` | 1,040 | Move from `$0900`; retire after adoption and final loader callback |
| Manifest | `$6000–$67FF` | 2,048 | Retain until `startup_complete` |
| Loader | `$6800–$7BFF` | 5,120 | Retire after adoption and final loader callback |

This contiguous 8,208-byte temporary arena does not overlap any persistent reservation, including Tasks that are initialized later. OF816
continues borrowing the root DP and guarded root/kernel stacks before Exec
owns them: 3,392 temporary bytes, with no additional reservation.

Keep the existing startup order: consume the manifest and capture boot
settings, complete Task initialization, then publish retirement at
`startup_complete`. The boot-state page at `$0900` remains resident. Repeated
memory adoption must use captured state and must not reread the retired
manifest. Do not clear or advertise the whole free range while any loader,
callback or manifest owner is still live.

The interval union of every persistent and temporary reservation fits without
overlap: 61,264 bytes for eight Tasks, or 59,600 for four, including OS ranges.
These conservative union sizes are a geometry check, not the phase-specific
loading budget below. Some Task pools are initialized only after adoption.

## Reservation accounting

Count guards, full arenas, alignment and unused reserved capacity. Generated
totals use the existing budget definitions; loading counts the two bootstrap
Task pools rather than every future Task pool.

| Measurement | Four Tasks: before → after | Eight Tasks: before → after |
| --- | ---: | ---: |
| Fixed runtime reservation, excluding OS | 11,792 → 11,552 | 10,528 → 10,528 |
| Public and idle pools | 9,120 → 9,120 | 11,808 → 11,808 |
| Runtime reservation, including OS | 51,632 → 51,392 | 53,056 → 53,056 |
| Unreserved after startup | 13,904 → 14,144 | 12,480 → 12,480 |
| Largest contiguous free range | 6,144 → 14,144 | 4,592 → 12,480 |
| Number of free ranges after startup | 10 → 1 | 9 → 1 |
| Loading reservation, including OS | 54,368 → 54,128 | 52,592 → 52,592 |

The fixed reservation delta is **−240 bytes for four Tasks and zero
for eight**. The delta per public Task, private idle, and kernel DP/stack is
**zero**. Upper-memory reservations do not change.

## Implementation sequence

### 1. Generate adapter placement from the platform profile

Extend the existing single source of physical layout in
[memory-1m.json](../../platform/altirraos/memory-1m.json). Generate the resident
linker layout from its base plus the current segment offsets. Migrate the
absolute `$3000–$3FFF` placement in
[hosted.cfg](../../platform/altirraos/hosted.cfg),
[native_program.py](../../tools/native_program.py) and
[generate_memory.py](../../tools/generate_memory.py), including the nonbanked
XEX path. Initially preserve the current addresses and verify the refactor
with host checks and a focused emitted startup case.

Continue generating adapter/DP/bootstrap-stack constants through
[adapter_state.py](../../tools/adapter_state.py) and the ABI generators.
Resolve public Task stack bounds from the selected capacity. The legacy
two-Task startup uses a 1,536-byte first-worker stack; the eight-Task runtime
uses 1,024 bytes at the same base. Validate these lifetimes separately so the
larger bootstrap bounds cannot overwrite the eight-Task neighbour.

Generate explicit loading, initialization and runtime ownership maps. Check
all extents, DP alignment, guarded stack bounds, full bank-table capacity,
the aperture, and the expected single free interval. Overrides must pass the
same collision and accounting checks; do not silently place an enlarged stack
in another hole.

### 2. Relocate the complete layout and its observers

Apply the proposed addresses together in the platform profile and generated
bindings. Update resident assembly entry/vector references, kernel and
cooperative startup, XEX packaging, loader staging and boot-state consumers.
Derive new resident segment addresses from the old offsets: for example,
BOOT becomes `$1400`, NMI `$1800`, IRQ `$1900` and FAULT `$2000`.
Regenerate programs and imported adapter addresses; public selectors, record
layouts and native DP field offsets remain unchanged.

Update [OF816 packaging](../../tools/build_of816.py) and its
[startup adapter](../../platform/of816/boot.s) to use the resolved borrowed
ranges. Check that no XEX payload or zero-fill extent overwrites monitor
storage before handoff, and that Exec initializes each borrowed domain only
after the monitor has returned.

Audit active handwritten addresses by ownership, rather than replacing every
matching number. Known collisions that must be resolved in this slice are:

- The far-write trampoline in [bridge_memory.py](../../tools/bridge_memory.py)
  borrows `$2000–$20FF`, which becomes resident FAULT code. Move its temporary
  scratch and derive valid rendezvous bounds from the relocated image.
- The [DP observer](../../tools/test_dp_partition.py) borrows `$2E00`, which
  becomes kernel stack storage. It also poisons the page beyond the final DP
  and the page below the kernel DP. Those neighbours become resident code or
  the bank table, and boot state. Check their existing contents at controlled
  initialization boundaries without poisoning live code or state.
- The eight-Task register capture extends into `$0900–$097F`, which becomes
  boot state. Move this test-only extension and update capture decoders.
- Replace old stack floors/ceilings, DP addresses, boot fields and adapter
  entry addresses in current fixtures and observers with generated values.

Give observer scratch explicit temporary ownership in build/test metadata.
Select scratch outside all reservations live at its observation phase,
including other instrumentation, and restore borrowed bytes. Keep its cost
separate from production budgets. An observer running before retirement must
not assume that the entire eventual free range is available. Preserve
historical evidence and independently owned standalone fixture layouts.

Remove the obsolete four-Task context reservation and its stale diagnostic
references. Keep the full near table reserved in the four-Task map. Preserve
the OS entry checks, stack guards, saved-D validation, SWITCHING protocol,
OS_BUSY rules and asynchronous context restoration throughout this relocation.

### 3. Validate the relocated system

Use the [development testing tier](../contributing/testing.md), with focused
extra coverage because interrupt stacks, entry code and boot storage move.
Pin the compiler, ROM and emulator configuration in the results.

| Check | Acceptance |
| --- | --- |
| Host suite and generated definitions | Exact maps and totals for both capacities; adjacency and overlap checks; rejection of overflow; no stale current address consumers. |
| Direct/cooperative and banked startup | Relocated entry points, guards, globals and OS restoration; cover raw and optimized emitted code where compiler-facing behavior is exercised. |
| Task capacity and DP lifetime | Four/eight public Tasks plus idle; exact initialization, neighbour preservation, interior-slot reuse and register restoration. |
| Asynchronous entry and faults | Focused VBI/IRQ cases and NMI checkpoints during stack/domain transitions; stack overflow and invalid saved-D paths retain controlled failure and cleanup. |
| C boundary | Existing Calypsi context/DP preservation case with the new stack and adapter addresses. |
| Loader and retirement | Staging chunk boundaries, invalid/replayed input, captured boot settings, upper globals, repeated adoption and manifest poison after retirement. Preserve the VBXE aperture sentinel. |
| OF816 and standard demo | Five-second autoboot and manual Forth handoff; guard integrity, shell/prime, disk commands, CAT/WC, EXIT, BYE and occupied-IOCB cleanup. |

Build through [build_demo.py](../../tools/build_demo.py), always including
OF816, the matching system disk and pinned ROM with license notices. Deliver
`exec816-demo.zip` with boot files, guide, licenses and checksums; retain
intermediates and observations in the development directory.

Record exact maps, phase ownership, fixed/per-Task deltas, input hashes and
actual execution scope in a new development record. Update the
[platform contract](../reference/platform.md),
[Task capacity explanation](../architecture/task-capacity.md),
[GEM integration assessment](gem4xe/exec816-integration-assessment.md) and
plan index only after implementation, then mark this plan complete. Focused
development evidence does not establish full hosted-system qualification.

The resulting contiguous range gives the later GEM/VBXE work a simple bank-zero
allocation boundary. Registering it for allocation, choosing a larger GUI
stack and implementing VBXE ownership remain separate executable slices.
