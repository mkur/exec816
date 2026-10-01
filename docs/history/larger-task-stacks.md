# Two larger Task stacks

[History](README.md) · [Task capacity](../architecture/task-capacity.md) · [GEM integration](../plans/gem4xe/exec816-integration-assessment.md)

Status: implemented on 2026-10-01 against Exec816 `d8dbea4`, with focused
development checks recorded in [larger-task-stacks.json](../development/larger-task-stacks.json).
The original design discussion below retains its planning language. Current
placement and admission guidance live in [Task capacity](../architecture/task-capacity.md).
This work does not qualify a GEM port or the full hosted release.

Give two of the existing eight public Task slots **2,560-byte stacks**. Keep
the root at 1,536 bytes, five ordinary worker stacks at 1,024 bytes and private
idle at 512 bytes. Each Task retains its own 256-byte DP. The two larger pools
are available through the existing Task API to any admitted program, including
a GEM service and a second C worker or GUI client.

This costs **3,072 additional bank-zero bytes**, leaving **9,408 contiguous
bytes** after startup. It preserves the current boot arena, VBXE aperture,
root/kernel stacks and eight-Task capacity. The proposed layout replaces the
current eight-Task map; four-Task builds retain their existing map and use the
same implementation and API. GUI application selection remains separate from
the standard OF816 shell/prime demo.

## Stack size and available call space

The [current Task contract](../reference/tasks.md#managed-creation) defines
`CreateTask`'s `stackSize` as the minimum whole stack allocation: interrupt
headroom and native frames are included, external guards are excluded. A
2,560-byte request therefore needs 2,592 physical stack bytes after adding
the two 16-byte guards. Including its existing DP, that Task reserves 2,848
bank-zero bytes.

The 256-byte interrupt reserve leaves 2,304 bytes above the compiler floor,
before subtracting initial/native frames and adapter call depth. GEM's assessed
standalone engine reserves 2,048 stack bytes. A 2,560-byte Exec pool is a
reasonable first measurement target, not proof that the adapted engine fits.
Measure the actual linked C call chain, bridge entry and asynchronous entry
before accepting a GEM workload. More stack does not enlarge the caller's
128-byte DP workspace or make GEM's old stack/DP switching safe.

The alternatives below enlarge slots 6 and 7 and pack idle immediately after
them. Costs include the unchanged guard and DP reservations. Free bytes are
calculated for runtime; the boot restrictions in the last column still apply.

| Stack bytes in each larger pool | Total added bank-zero bytes | Free bytes after startup | Consequence |
| --- | ---: | ---: | --- |
| 2,048 | 2,048 | 10,432 | Only 1,792 bytes above the interrupt reserve, before frames; below the standalone engine's 2,048-byte allocation. |
| **2,560** | **3,072** | **9,408** | Leaves 2,304 bytes before frames and keeps every stack clear of the entire boot arena. Recommended first slice. |
| 3,072 | 4,096 | 8,384 | Reaches `$5F3F`, overlapping retired staging storage. Phase checks permit this, but it needs an explicit staging-reuse decision and evidence. |
| 4,096 | 6,144 | 6,336 | Reaches `$673F`, overlapping the manifest while Task initialization still needs it. Requires a different placement or initialization design. |

The larger options are comparisons, not additional supported configurations
in this proposal. If measured use exceeds the proposed budget, revisit placement
and bootstrap lifetimes explicitly. Avoid assuming that all memory free after
startup is safe to fill during Task initialization.

## Proposed physical layout

Addresses below are in bank zero. Guard ranges are inclusive; public stack
upper bounds remain exclusive. Slots are build-time storage indices, not new
public Task identities. Keep all DP addresses unchanged.

| Owner | DP | Stack base | Stack bytes | Reservation including guards |
| --- | --- | --- | ---: | --- |
| Root, slot 0 | `$0B00` | `$2410` | 1,536 | `$2400–$2A1F` |
| Kernel | `$0A00` | `$2A30` | 1,536 | `$2A20–$303F` |
| Public slot 1 | `$0C00` | `$3050` | 1,024 | `$3040–$345F` |
| Public slot 2 | `$0D00` | `$3470` | 1,024 | `$3460–$387F` |
| Public slot 3 | `$0E00` | `$3890` | 1,024 | `$3880–$3C9F` |
| Public slot 4 | `$0F00` | `$3CB0` | 1,024 | `$3CA0–$40BF` |
| Public slot 5 | `$1000` | `$40D0` | 1,024 | `$40C0–$44DF` |
| Public slot 6 | `$1100` | `$44F0` | 2,560 | `$44E0–$4EFF` |
| Public slot 7 | `$1200` | `$4F10` | 2,560 | `$4F00–$591F` |
| Private idle | `$1300` | `$5930` | 512 | `$5920–$5B3F` |

The persistent block ends at `$5B3F`. A 176-byte gap at `$5B40–$5BEF`
separates it from staging at `$5BF0–$5FFF`. The manifest remains at
`$6000–$67FF`, and the loader at `$6800–$7BFF`. After `startup_complete`,
the entire `$5B40–$7FFF` range is unreserved; it is not automatically registered
with the heap. The VBXE aperture stays at `$8000–$8FFF`.

Root, kernel and the first worker keep their current addresses and sizes, so
the bootstrap and OF816 borrowed stacks retain their layout. Slot 6 grows in
place; slot 7 and idle move upward. No live Task is relocated. Boot constructs
all pools from the new map before admitting ordinary Tasks. Diagnostic scratch
at `$7C00` and above remains clear of every proposed live phase and must still
be checked separately in instrumented builds.

## Complete reservation cost

These figures use the current eight-Task profile with its bank table and Task
metadata in upper RAM. All guards, DP reservations and unused stack capacity
are counted. Stack bases retain 16-byte alignment with no additional padding.

| Reservation | Current bytes | Proposed bytes | Delta |
| --- | ---: | ---: | ---: |
| OS ranges | 30,720 | 30,720 | 0 |
| Fixed Exec runtime, including kernel stack and VBXE aperture | 10,528 | 10,528 | 0 |
| Root stack, guards and DP | 1,824 | 1,824 | 0 |
| Five ordinary worker pools | 6,560 | 6,560 | 0 |
| Two larger worker pools | 2,624 | 5,696 | +3,072 |
| Private idle stack, guards and DP | 800 | 800 | 0 |
| Total runtime reservation | 53,056 | 56,128 | +3,072 |
| Unreserved after startup | 12,480 | 9,408 | −3,072 |

Per enlarged Task, the full reservation changes from 1,312 to 2,848 bytes:
**+1,536 bytes each**. Fixed storage and every other Task cost **0 additional
bytes**. Moving idle does not change its reserved size. Upper Task metadata
does not grow because the number of contexts, managed records and DPs is unchanged.

Phase totals, including OS reservations, are 52,592 bytes during loading
(unchanged), 58,176 during initialization (+3,072), and 56,128 at runtime
(+3,072). Loading only reserves the bootstrap Task pools; initialization adds
all pools while retaining the 2,048-byte manifest. For this slice, also require
the union of persistent stacks and temporary boot storage to be disjoint,
preserving the stronger property established by bank-zero compaction.

## Admission and availability

Keep `CreateTask`, `AddTask` and removal semantics unchanged. The existing
[creation policy](../../lib/exec/taskpolicy.act) already selects the smallest
free fitting pool, breaking ties by slot order. A registered C or Action!
entry requesting 2,560 bytes can occupy slot 6 or 7. A third such request fails
even when smaller pools are free. Root and idle remain excluded from managed
creation. `AddTask` continues to require the exact generated bounds of a free
pool and a valid initial S.

This extends Exec816's existing adaptation of classic Exec creation to fixed
bank-zero pools. It retains the familiar stack-size request while making the
scarce near-memory cost predictable. General dynamic stack allocation and its
fragmentation/lifetime policy remain outside this slice.

Requests of at most 1,024 bytes consume ordinary free pools first. When those
are full, they may consume a larger pool. This is intentional: two capable
pools do not guarantee that two large Tasks can start at any arbitrary time.
The larger pools are neither GEM-only reservations nor a separate scheduler
class. Keep all existing `SlotFree` checks for Process reservations, uncollected
Processes and exhausted incarnations; do not add another ownership bitmap.

Console and SIO admissions scan generated stack bounds in slot order; DOS and
Process admission also select the first free worker slot. Keeping the five
smaller pools first preserves their preference for smaller storage in this
layout. Test these paths together with managed creation. A future configurable
ordering would require reviewing every admission path, not only `CreateTask`.
The current Process launch API has no stack-size request; this slice does not
promise large-stack selection for dynamically launched commands.

A GUI launcher that needs both large Tasks should start them before admitting
optional workloads. If either creation fails, shut down the already-created
worker through a bounded startup/stop protocol and report failure. A child can
run or retire before `CreateTask` returns; use the existing lifetime and
notification rules, rather than retaining an unprotected managed pointer.
Guaranteed reservation or atomic multi-Task admission would be a separate,
general API proposal if a real use case requires it.

Both large Tasks count toward the existing eight public slots. The standard
demo uses five and a two-command pipeline raises that to seven. Adding both
large Tasks to those five leaves only one free slot; running both plus the
pipeline would require nine. The first GUI workload must budget its actual
resident Tasks and reject excess admission cleanly. More windows need not
imply more Tasks.

## Execution and lifetime invariants

The current policy derives the compiler floor as `base + 256`, initial S as
`base + size - 2`, and the DP stack ceiling as `base + size - 1`. Preserve those
conventions and the public exclusive upper bound of `base + size`. Generate
all values from each resolved pool; never infer a size from slot number or a
shared worker constant. Reject wrapping extents and invalid alignment before
emitting an image.

Each larger Task remains in the same registered stack/DP domain for its whole
activation. Keep the current frame validator, full native register restoration,
stack checks and guard handling. The dispatcher owns `SWITCHING` during
selection and admission; preserve its IRQ/NMI protocol. `SEI` alone cannot
protect a partial context transition. A larger pool does not authorize GEM's
standalone CRT, alternate stack swapping or concurrent access to its globals.

Normal return, self-removal and permitted external removal release the same
pool only after execution has moved to the kernel domain and ownership gates
allow retirement. No stack heap, stack copying, on-demand growth or separate
reaper is needed. The kernel stack remains 1,536 bytes: deeper kernel nesting
must be measured independently of caller stack capacity.

The [C binding's current limits](../guides/calypsi-c.md#current-limits-and-development-checks)
still apply: Calypsi C functions do not have Action!'s compiler-inserted overflow
checks. Keep C workloads bounded and inspect their emitted frames and measured
peaks. Guard and domain observations cannot promise a fault before an arbitrary
C stack overflow. Exercise the controlled overflow path with checked Action!
or assembly reservations; adding C entry checks would require separate work.

## Implementation slices

The [implementation plan](../plans/larger-task-stacks-implementation-plan.md) expands
these boundaries into ordered changes, executable checks and completion gates.

### Generate the mixed stack layout

Update the eight-Task map in
[memory-1m.json](../../platform/altirraos/memory-1m.json) and teach
[task_capacity.py](../../tools/task_capacity.py) to accept the proposed
2,560-byte entries while preserving extent, alignment, guard and phase checks.
Leave the supported four-Task map intact. Use the resolved profile as the
single source for pool sizes, generated Action!/assembly definitions and
`memory.json`; retain one current eight-Task layout.

Fix the build default in [native_program.py](../../tools/native_program.py):
it currently turns an omitted `worker_stack` into a uniform 1,024-byte override,
which would silently erase the mixed sizes. An omitted override must preserve
the profile's per-slot sizes. An explicit `--worker-stack` can retain its
existing meaning of overriding every non-root public pool, without repacking
bases; invalid overlaps must fail. Record the resolved layout and any override.
A deliberate uniform override is not evidence for two larger pools.

Check generated bounds through [generate_tasks.py](../../tools/generate_tasks.py)
and audit fixtures and observers for assumed 1,024/1,536-byte sizes. In particular,
the C preemption observer in [test_calypsi.py](../../tools/test_calypsi.py) has a
literal 1,536-byte bound and fixed expected Task slots. Extend it to observe the
selected larger workers using their actual generated bounds. Change generated
files through their generators. Public call packets and the Task record layout
need no ABI change; rebuild images containing generated pool addresses.

### Exercise two large Tasks through native code

Extend the existing creation, capacity and C-context fixtures with two live
workers whose stack use exceeds an ordinary pool's available call space.
Keep a computing peer runnable and observe actual VBI preemption in both large
workers. Include a bounded nested call/bridge workload representative of the
first GEM harness. Avoid padding the stack without checking the data and
return path that occupy it.

Measure peak stack use, remaining space above the compiler floor, guard state,
DP preservation and progress for both workers and the kernel. Fill scans must
use a fresh initialized pool or an explicitly tracked lifetime; boot fill is
not reset at every admission. Separate observed peaks from worst-case bounds.
The proposed size is accepted for a workload only when its selected call paths
and asynchronous entry cases pass.

### Integrate the layout and record its limits

Update the Task capacity and platform references only when the implementation
is present. Add a development record with exact input hashes, generated maps,
fixed/per-Task costs and executed cases. Update the GEM assessment with the
measured C result; a stack fixture alone does not establish GEM compatibility.

Rebuild and smoke-test the standard demo through
[build_demo.py](../../tools/build_demo.py), retaining OF816, its five-second
shell/prime autoboot, matching disk and pinned ROM. Check a two-command pipeline
and normal shutdown. Package only the usual boot files, guide, licences and
checksums in `exec816-demo.zip`; keep maps and test output in the development
directory. The GUI itself remains a separately selected workload.

## Development acceptance

Follow the [two-tier testing policy](../contributing/testing.md). Implementation
requires host checks and focused emitted-code cases below; use raw and optimized
NIR for compiler-facing behavior, and the selected pinned ROM/emulator. Full
release matrices and mapped VBXE qualification remain separate work.

| Area | Required evidence |
| --- | --- |
| Map and generation | Exact proposed bases, sizes, guards, DP ownership, phase totals and free range; default build preserves mixed sizes; explicit overrides are recorded; reject overlaps, wrapping, invalid alignment and unsupported capacities. Four-Task layout remains unchanged. |
| Managed admission | Two simultaneous 2,560-byte requests succeed with free pools; third fails without side effects; 2,559 rounds to 2,560; 2,561 and oversized/overflowing requests fail. A 1,025-byte request selects a larger pool. Small requests prefer small pools and may fall back to larger ones. |
| Shared admission | Mixed AddTask/CreateTask/Process and service occupancy; exact AddTask bounds and nondefault valid initial S; Process reservations and uncollected slots remain unavailable. Starting a large Task fails cleanly when a small workload already owns each large pool. |
| Native execution | Two distinct large stacks and DPs, checked nested calls, actual VBI in both workers, a computing peer, signal/message waits, bounded completion and complete register restoration. Exercise IRQ/NMI checkpoints across admission, switching and removal. |
| Overflow and reuse | Checked Action!/assembly reservation failure reaches the controlled fault path before invalid writes; all guards remain intact. Bounded C runs preserve guards but do not establish automatic C overflow detection. Cover return, self-removal, permitted external removal, ownership rejection and repeated pool reuse without stale DP or Process ownership. |
| Platform coexistence | One focused native SIO/console workload alongside the large workers; measured kernel/caller peaks; intact aperture sentinel and normal OS restoration. This does not test mapped VBXE. |
| Demo | OF816 handoff, unchanged shell/prime startup, a two-command pipeline and EXIT cleanup using rebuilt images. |

No measured performance claim is implied. The pool scan still visits at most
seven worker entries, context-save size is unchanged, and boot stack filling
touches 3,072 more bytes. Record any emitted code growth, measured initialization
cost and observed stack peaks when implementing; do not hide a kernel-stack
regression by increasing its reservation.

## Original design preparation

Preparation inspected the current generator, native build defaults, Task
creation/removal and service/Process admission paths. A host calculation started
from the generated eight-Task map, substituted the proposed stack reservations
in memory, and ran the existing phase and diagnostic-overlap validator. It
confirmed the three phase totals, the 9,408-byte free range and disjoint boot
storage. The larger alternatives above were calculated using the same placement.

This was a design calculation, not successful generation through the current
1,536-byte stack-size limit. No compiler, emulator or GEM execution was performed
for this note. Documentation content and links are checked separately. The
documentation-only change reserves **0 new fixed bytes and 0 bytes per Task**;
the proposed implementation had a separate +3,072-byte cost.

## Implementation outcome

The implemented map has two 2,560-byte worker stacks, 9,408 free bank-zero
bytes after startup and no additional fixed reservation. Slots 6 and 7 each
add 1,536 bytes; guards, DP sizes, root/kernel stacks and four-Task placement
remain unchanged. Existing Task policy handles admission and retirement without
a new ABI operation.

Raw and optimized fixtures exercise simultaneous admission, small-pool
preference, Process collection, repeated reuse, checked compiler/assembly
failure and deep Action!/C calls. Selected NMI checkpoints and physical
SIO/console coexistence pass. The Action! fixture peaks at 1,334 bytes per
larger worker; the C fixture peaks at 1,140, leaving 970 and 1,164 bytes above
the interrupt floor respectively. These are measured cases, not worst-case
bounds. C function entries remain unchecked.

The standard OF816 distribution was rebuilt and its five-second autoboot,
clock wrap, Forth handoff, shell disk/pipeline and exit cases passed. See the
[implementation completion record](../plans/larger-task-stacks-implementation-plan.md#completion-record)
for commands and the machine-readable evidence for exact inputs and scope.
