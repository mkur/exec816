# Direct page guard removal and compaction plan

[Implementation plans](README.md) · [Task capacity](../architecture/task-capacity.md)

Status: implemented on 2026-10-01. Based on commit
`b50bb580e15893eb452501c9439324338a9eca00` and the
[VBXE aperture development record](../development/vbxe-aperture.json).
[Development evidence](../development/dp-compaction.json) records the emitted
checks, exact maps, source/image hashes and refreshed OF816 demo. The sequence
below documents the implemented design; it is not a release qualification claim.

Acceptance includes 253 host tests (249 passed, four historical-source audits
skipped), fresh generated bindings, raw/optimized DP lifetime checks for both
capacities, an eight-Task interior-slot reuse case with NMI checkpoint 15,
full-capacity IRQ/VBI/register checks, stack and saved-D fault paths, Calypsi
context checks, loader/retirement cases and both OF816-to-shell routes.
The controlled DP observer temporarily borrows 288 bytes outside production
reservations: 32 bytes for breakpoint code/state and 256 for a boundary sentinel.
It restores these bytes and the instrumented entry/exit instructions; the
production reservation totals below exclude this test-only borrowing.

Remove external direct-page canaries and the padding reserved around Task DPs.
Give every Task, private idle and the kernel exactly one aligned 256-byte page.
Place the kernel page immediately below a contiguous Task DP area. Keep the
current four/eight public Task capacities and all stack addresses and sizes.

The eight-Task layout recovers **2,336 bank-zero bytes**: 256 bytes per
public Task, 256 bytes for idle and 32 fixed bytes from the kernel DP guards.
The four-Task layout recovers 192 bytes because its previous DP reservations
had 32 guard bytes each but no additional reserved stride padding.

## Implemented layout

Use `kernel_dp=$2100`, `task_dp_base=$2200` and `task_dp_stride=$0100`.
For public capacity `N`, public slot `i` uses `$2200+i*$0100`, and private idle
uses slot `N`. Reserve only the pages present in that build. Root retains its
current `$2200` address, including OF816's borrowed bootstrap DP.

| Owner | Four public Tasks | Eight public Tasks |
| --- | --- | --- |
| Kernel and interrupt domain | `$2100–$21FF` | `$2100–$21FF` |
| Root, slot 0 | `$2200–$22FF` | `$2200–$22FF` |
| Public slot 1 | `$2300–$23FF` | `$2300–$23FF` |
| Public slot 2 | `$2400–$24FF` | `$2400–$24FF` |
| Public slot 3 | `$2500–$25FF` | `$2500–$25FF` |
| Private idle, or public slot 4 | Idle: `$2600–$26FF` | Slot 4: `$2600–$26FF` |
| Public slot 5 | No reservation | `$2700–$27FF` |
| Public slot 6 | No Task reservation; near bank table starts at `$2800` | `$2800–$28FF` |
| Public slot 7 | No Task reservation | `$2900–$29FF` |
| Private idle, slot 8 | No Task reservation | `$2A00–$2AFF` |

The complete kernel/Task DP area occupies `$2100–$26FF` for four Tasks and
`$2100–$2AFF` for eight. The four-Task near bank-table reservation remains
`$2800–$2BFF`; the eight-Task table remains in upper RAM. The boot-state page
at `$2C00–$2CFF` therefore remains clear of both layouts. Larger candidate
capacities must pass the same collision checks; reject a contiguous DP area
that reaches boot state rather than silently spilling it into other holes.
Supporting larger capacities is a separate layout change.

Keep these stack bases, in slot order including idle:

| Build | Stack bases |
| --- | --- |
| Four public Tasks | `$4200`, `$5200`, `$6900`, `$7100`, `$7900` |
| Eight public Tasks | `$4200`, `$5200`, `$6810`, `$6C30`, `$7050`, `$7470`, `$7890`, `$0D20`, `$7CB0` |

The kernel stack stays at `$4A00`. Retain every stack's current size, external
16-byte guards at both ends, checked floor/ceiling and interrupt reserve.
Make stack placement independent of DP packing so newly freed DP holes do not
cause the current first-fit allocator to move stacks as an unintended effect.

Adapter state stays at `$0800`, staging at `$0900–$0D0F`, and the VBXE aperture
at `$8000–$8FFF`. Upper image data and the manifest retirement boundary retain
their current contracts. Recovered holes remain unregistered with the general
heap. In particular, `$6000–$67FF` remains protected until `startup_complete`.

## Reservation accounting

Generated `memory.json` reproduces these totals, including all remaining
guards, alignment, unused reserved capacity and OS reservations. Host checks
verify disjoint ownership, exact DP extents, unchanged stack maps and both
loading and runtime totals.

| Reservation or saving | Four public Tasks | Eight public Tasks |
| --- | ---: | ---: |
| Old reservation per Task DP | 288 | 512 |
| New reservation per Task DP | 256 | 256 |
| Fixed runtime change, kernel DP | −32 | −32 |
| Change per public Task | −32 | −256 |
| Private idle change | −32 | −256 |
| Total runtime saving | 192 | 2,336 |
| Runtime reserved, including OS, before | 51,824 | 55,392 |
| Runtime reserved, including OS, after | 51,632 | 53,056 |
| Unreserved after startup | 13,904 | 12,480 |
| Loading reserved, including OS, before | 54,464 | 53,136 |
| Loading reserved, including OS, after | 54,368 | 52,592 |
| Loading saving | 96 | 544 |

Loading totals count the two bootstrap Task DP reservations plus the kernel
DP; other Task pages are initialized later. Do not subtract every runtime DP
reservation from the loading budget. There is no new upper-RAM reservation.

The largest eight-Task runtime hole becomes `$5610–$67FF`, 4,592
bytes, after manifest retirement. Another 4,048-byte hole lies at
`$1130–$20FF`. Total free bytes and the largest contiguous hole are separate
measurements; neither implies an existing heap allocation service for them.

The diagnostic eight-Task register probe retains its existing temporary
128-byte extension at `$0900–$097F` after loading. Its reservation delta is
zero, and it remains excluded from production totals.

## Preserve the direct page contract

The [native DP partition](../../abi/native-dp.json) stays unchanged:
caller workspace at offsets `$00–$7F`, compiler scratch at `$80–$BF`, domain
metadata at `$C0–$C7`, and reserved-zero bytes at `$C8–$FF`. Keep separate
ownership for every Task and the kernel. Initialize exactly 256 bytes on a
new ownership lifetime, then publish the normal metadata before admission.

Preserve complete D-register save/restore, the saved-D comparison with the
selected Task, stack/domain validation, the SWITCHING protocol, OS_BUSY rules,
IRQ/NMI entry handling and the OS's own DP. Temporary stack-relative D values
retain their existing rules. Guard removal does not permit sharing a Task DP.

DP canaries currently detect some neighbouring writes during test inspection;
they do not prevent invalid accesses. After compaction, an out-of-range write
can immediately affect another live domain. Tests must exercise exact page
boundaries, lifetime reset and neighbour preservation. Keep stack checks and
stack canaries enabled. No guarded-DP compatibility build is retained.

## Implementation sequence

### 1 Generate one physical layout

Make the [platform profile](../../platform/altirraos/memory-1m.json) authoritative
for kernel DP, Task DP base/stride and the supported stack placements. Generate
assembly and Action! DP addresses from that description, including an explicit
root DP constant. Migrate physical pool placement out of duplicated ABI inputs;
the public Task records and native DP field offsets remain unchanged.

Update [memory generation](../../tools/generate_memory.py),
[Task capacity placement](../../tools/task_capacity.py),
[Task generation](../../tools/generate_tasks.py),
[gateway constants](../../tools/generate_exec_abi.py),
[Task ABI input](../../abi/tasks.json),
[adapter ABI input](../../abi/exec816-v1.json) and
[budget accounting](../../tools/ports_budget.py) together. All build paths and
observers must consume the resolved layout instead of a fallback old pool map.

Represent each DP reservation as `[dp, dp+256)`, with no guard offset or stride
slack. Remove the generated `poolDpBytes` array if it no longer has a consumer;
retain `dp_reserved_bytes=256` in build metadata for explicit accounting.
Generate both four- and eight-Task layouts through the same DP formula.

Validate alignment, bank-zero bounds, distinct ownership and overlap with
loading/runtime reservations, including the full four-Task bank table and
legacy context reservation. Validate stack reservations including their
guards. Rebuild all callers and generated definitions; service selectors,
public record layouts and the compiler ABI do not need a version change.

### 2 Migrate initialization and bootstrap together

Change [PrepareDomain](../../lib/exec/taskpolicy.act) to clear only the actual
page and install its owner and bounds. Remove the `dp-16` fill and the fill
of reserved stride padding. Check boot initialization and slot reuse; both
must preserve adjacent live DPs.

Remove DP canary writes from [hosted startup](../../platform/altirraos/hosted.s),
[cooperative startup](../../platform/altirraos/cooperative.s) and
[general Task startup](../../platform/altirraos/tasks.s). Update
[layout constants](../../platform/altirraos/layout.inc) and every entry path
that selects the relocated kernel or first worker DP. Leave stack guard
initialization intact. Direct hosted, two-Task cooperative and public Task
fixtures must all use the current address definitions.

Update [OF816 startup](../../platform/of816/boot.s) in the same slice. Its
`OF_DP-16` and `OF_DP+256` canaries would now write into the kernel and first
worker pages. Remove only those writes; retain its stack, adapter and upper
data-space guards. Change [boot packaging](../../tools/build_of816.py) to
borrow exactly `[root_dp, root_dp+256)` and derive the corresponding borrowed
byte count. Its reported bank-zero borrowing decreases from 3,424 to 3,392
bytes. This lifetime measurement is not an additional permanent saving.

Audit handwritten DP literals and test scratch by meaning. In particular,
`$2400` changes from slot 1 to slot 2 and `$2600` from kernel to slot 4/idle.
Some isolated loader probes use `$2100` for results; move that scratch or
prove it is retired before kernel DP initialization. The far-write observer's
`$2000–$20FF` scratch remains outside the new area and must still be restored.
Preserve historical records and standalone probe layouts where they are
independent of the hosted platform; do not mechanically replace numeric masks
or upper-bank addresses.

### 3 Replace guard observations with page ownership checks

Update the [native runner](../../tools/native_program.py) to remove only DP
canary and padding checks. Continue checking stack guards, owner pointers,
domain kind, stack bounds, reserved-zero bytes, context restoration and OS
cleanup. Update OF816 guard observations and packaging tests accordingly.

Extend [DP preservation tests](../../tools/test_dp_partition.py) and their
[emitted fixture](../../tests/programs/dp_partition.act) for the packed area.
Use distinctive per-owner caller-workspace patterns and check metadata at
each relevant lifecycle boundary. Cover root, each public slot, idle and the
kernel, including removal and reuse of an interior slot with live neighbours.
For isolated initialization checks, seed adjacent inactive pages and verify
that clearing the target changes exactly its declared extent. During live
execution, permit compiler scratch to change as the ABI specifies.

Exercise adjacent pages without inserting test-only gaps. Check a page's last
legal byte and the next page's first byte at controlled initialization
boundaries; do not seed nonzero reserved bytes in an executing domain. Keep
full-capacity register probes and DP workspace tests as separate checks where
their scratch use differs.

Search current observers and assembly fixtures for old kernel/worker addresses,
288/512-byte DP spans and 512-byte slot arithmetic. Relevant callers include
cooperative/preemptive tests, Calypsi context tests, heap/IRQ probes, loader
policy probes and trace decoders. Read actual DP addresses from generated
metadata. Historical evidence remains tied to its original addresses.

### 4 Validate and deliver the executable slice

Use the [development testing tier](../contributing/testing.md):

| Check | Required evidence |
| --- | --- |
| Host suite and generators | Exact four/eight DP maps and reservation totals; reject misalignment, overlap and arena overflow; unchanged stack maps; fresh generated includes. |
| DP lifetime, raw and optimized | Workspace preservation, exact initialization boundaries, neighbour integrity and slot reuse for both capacities. |
| Capacity and asynchronous entry | Eight public Tasks plus idle; full register restoration; VBI switching, real IRQ delivery and targeted NMI checkpoints at context transitions and reuse. |
| Existing fault paths | Stack overflow and invalid saved-D/context cases still fail through their controlled paths with stack guards and OS restoration intact. |
| C boundary | Existing Calypsi context/DP preservation case with the relocated kernel and worker pages. |
| Loading and retired storage | Upper globals, repeated adoption, manifest poison after retirement, loader rejection/replay and the intact `$8000–$8FFF` aperture sentinel. |
| OF816 and standard demo | Five-second autoboot and manual Forth handoff; shell/prime, disk commands, CAT/WC pipeline, EXIT, BYE and occupied-IOCB cleanup; neighbouring pages untouched by monitor DP initialization. |

Build the demo through [build_demo.py](../../tools/build_demo.py), then run
[test_of816.py](../../tools/test_of816.py). Record compiler, ROM and emulator
pins, final source/image hashes, exact pool maps, measured checks and reservation
deltas in a new development JSON record. Existing pins and targeted native
fixtures supply the starting configuration; no full release qualification is
implied by these checks.

After executable acceptance, update the
[platform contract](../reference/platform.md),
[Task capacity description](../architecture/task-capacity.md),
[stack-check wording](../contributing/stack-checks.md) and
[GEM assessment](gem4xe/exec816-integration-assessment.md), and mark this plan
implemented with a link to the new record. Package the OF816 boot files,
matching disk and ROM, licenses, short guide and checksums in `exec816-demo.zip`;
leave reports and intermediate files in the development directory.

This slice changes DP placement and diagnostics. GUI stack enlargement,
VBXE mapping, GEM rendering and allocation of the reclaimed holes remain
subsequent implementation work.
