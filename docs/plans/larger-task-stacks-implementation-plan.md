# Implementation plan for two larger Task stacks

[Implementation plans](README.md) · [Design note](../history/larger-task-stacks.md) · [GEM integration](gem4xe/exec816-integration-assessment.md)

Status: implemented on 2026-10-01 against Exec816 `d8dbea4`; L0–L4 passed
focused development checks. See the [completion record](#completion-record)
and [evidence](../development/larger-task-stacks.json). This plan delivers two 2,560-byte worker stacks in
the existing eight-Task layout and validates their use through the public Task
API. The [design note](../history/larger-task-stacks.md) owns the placement and
admission decisions; this page defines the execution order and acceptance gates.

The resulting default eight-Task sizes must be
`[1536, 1024, 1024, 1024, 1024, 1024, 2560, 2560, 512]`, including root first
and private idle last. Public capacity remains eight. Four-Task builds retain
their current map. Use one implementation and the existing CreateTask/AddTask
contracts, with no GEM-specific admission service or alternate Task ABI.

## Sequence and cost

Complete each executable slice with its focused development checks before
continuing. Reuse passing images only when their recorded inputs still match.
The [testing policy](../contributing/testing.md) does not require full release
matrices for this work.

| Slice | Deliverable and dependency | Incremental bank-zero reservation |
| --- | --- | --- |
| L0 | Capture the current map, pinned inputs and comparison artifacts. | Fixed 0; every Task 0. |
| L1 | Generate, boot and run the mixed stack layout. Requires L0. | Fixed 0; slots 6 and 7 +1,536 bytes each; other Tasks and idle 0. |
| L2 | Prove admission, rejection and safe reuse across both sizes. Requires L1. | Fixed 0; every Task 0 beyond L1. |
| L3 | Prove deep Action! and C execution, asynchronous entry and device coexistence. Requires L2. | Production fixed 0; every Task 0 beyond L1. Account for observer borrowing separately. |
| L4 | Refresh the OF816 demo, current references and development evidence. Requires L3. | Fixed 0; every Task 0 beyond L1. |

The cumulative production increase is **3,072 bytes**, entirely in the two
worker stacks. The target runtime reservation is **56,128 bytes**, including
OS ranges, leaving **9,408 bytes at `$5B40–$7FFF`**. Loading remains 52,592
reserved bytes; initialization becomes 58,176 while the manifest is live.
Count full guards, alignment and unused capacity. This plan does not assign
the remaining free range to a heap.

## L0 Capture a reproducible baseline

Read the [platform contract](../reference/platform.md), design note and current
Task references before editing. Record the source revision and working-tree
diff, [actionc pin](../../toolchain/actionc.json), platform profile, kernel
configuration, generated maps and their hashes. Record local toolchain
overrides explicitly. Use the fixture's pinned emulator and ROM and verify
their actual hashes; the paced C/demo configuration is recorded in
[altirra-shell-paced.json](../../toolchain/altirra-shell-paced.json).

Generate current four- and eight-Task maps and retain their phase totals,
per-pool bounds and complete reservations. Preserve matching raw/optimized
creation-fixture code sizes and kernel/Task stack measurements when available;
otherwise obtain them with the smallest relevant existing fixture. Historical
qualification records are not a current baseline unless every relevant input
matches. No baseline release matrix is needed.

Keep development builds and logs below `build/larger-task-stacks/`, separating
baseline, raw, optimized and demo outputs. The eventual tracked summary is
proposed as `docs/development/larger-task-stacks.json`; do not create a passing
record before executing its cases.

**Exit gate:** the baseline reproduces 53,056 runtime reserved bytes and
12,480 free bytes for eight Tasks. The source/tool inputs and comparison scope
are explicit. There is no production change in this slice.

## L1 Generate and execute the mixed layout

### Profile and build defaults

Update only the eight-Task stack map in
[memory-1m.json](../../platform/altirraos/memory-1m.json), using the design's
complete layout. Slot 6 keeps base `$44F0` and grows to 2,560 bytes; slot 7
moves to `$4F10` with 2,560 bytes; idle moves to `$5930` with 512 bytes.
Root, kernel, slots 1–5, all DPs and the temporary boot arena retain their
current placement and size.

In [task_capacity.py](../../tools/task_capacity.py), accept the proposed
larger per-slot sizes while retaining integer, minimum-size, 16-byte alignment,
bank-zero extent and overlap checks. Do not simply raise the numeric limit
and assume placement follows. Validate the complete guarded extent of every
resolved pool against fixed reservations, other pools and diagnostic scratch.
Enforce the design's additional requirement that persistent stacks and the
entire temporary boot arena are disjoint, even across different phases.
Reject unsupported Task capacities as before.

In [native_program.py](../../tools/native_program.py), pass an omitted worker
or idle override through as `None` so the profile supplies individual sizes.
Remove the implicit uniform 1,024-byte worker override. Keep explicit
`--worker-stack` semantics: override every non-root public stack without
repacking its base, validate the resulting extents and record the override.
Keep the existing four-Task restrictions. Invalid enlargements must fail;
silently shrinking the proposed larger stacks is not a default build.

Audit other `configure(...)` callers for explicit `1024,512` arguments used
as implicit defaults, including
[DOS packaging tests](../../tests/test_dos_package.py) and
[port packaging tests](../../tests/test_ports_package.py). Default-layout
coverage must exercise the new profile; deliberate uniform-override coverage
must be labelled as such.

### Generated consumers and reporting

Regenerate pool arrays and bounds through
[generate_tasks.py](../../tools/generate_tasks.py); do not edit generated
Action! or assembly by hand. Verify `poolSize`, `poolStack`, `TASKSTACKS`,
private stack floors/tops, DP metadata and package reservations agree with
the resolved map. Inspect initialization and frame construction in
[taskpolicy.act](../../lib/exec/taskpolicy.act); keep their existing per-pool
formulas and the IRQ/NMI transition protocol.

Audit capacity, relocation, OF816 and native execution observers for old size
or address assumptions. Derive observations from each build's `task_pools`;
retain literal expected values only in tests specifically asserting the new
platform map. Root/kernel OF816 borrowing stays unchanged.

The reports in [test_create_task.py](../../tools/test_create_task.py),
[test_calypsi.py](../../tools/test_calypsi.py),
[build_demo.py](../../tools/build_demo.py) and
[test_demo.py](../../tools/test_demo.py) currently contain literal zero deltas.
Make new reports distinguish a slice's incremental cost from the cumulative
change against the L0 baseline. Record fixed delta 0, public-slot deltas
`[0,0,0,0,0,0,1536,1536]`, idle delta 0 and total delta 3,072 for the default
eight-Task map. Derive other configurations from their actual maps. A scalar
`per_task=0` is insufficient for the cumulative mixed-layout comparison.
Update affected report consumers; preserve historical records unchanged.

### Validation and completion

Extend [capacity packaging checks](../../tests/test_capacity_package.py) and
affected relocation/OF816 packaging checks to assert the exact sizes, moved
bases, guard ranges, unchanged DP/metadata capacity and all three phase totals.
Check the 176-byte gap before staging and the `$5B40–$7FFF` free range.
Keep four-Task totals and addresses unchanged. Include invalid sizes, wrapping,
misalignment, bootstrap/aperture/manifest overlap and unsupported capacities.
Check an explicit supported shrinking override and rejection of a uniform
enlargement that overlaps the next pool.

Exercise the normal build entry point as well as direct `configure` calls so
the omitted-override bug cannot survive a passing generator test. Build and
run the existing eight-Task capacity fixture in raw and optimized mode on
kernel bank 1, with one focused register-restoration case. Select modes and
bank explicitly: [test_task_capacity.py](../../tools/test_task_capacity.py)
otherwise expands to both compiler modes and banks 1 and 3. Run one four-Task
creation control through the same build path.

**Exit gate:** emitted code boots the new default map, all eight public slots
and idle operate with intact guards and correct DP/register restoration, and
the recorded production delta is exactly the L1 budget. Rebuild generated
callers; no public packet or Task-record ABI change is expected.

Suggested commit: `Add two larger stacks to the eight-Task layout`.

## L2 Prove shared admission and retirement

Extend [create_task.act](../../tests/programs/create_task.act) and its
[runner](../../tools/test_create_task.py) with individually selectable cases
for the mixed map. Keep children alive behind signal/message rendezvous while
examining occupancy; a child that already retired cannot prove simultaneous
admission. Inspect managed Task fields only while the documented lifetime and
Forbid rules make the pointer valid.

| Case group | Assertions |
| --- | --- |
| Two large workers | With both pools free, two 2,560-byte requests select slots 6 then 7. A third fails while smaller slots remain free. Both admitted Tasks are simultaneously live. |
| Size boundaries | 2,559 rounds to 2,560; exact 2,560 fits; 2,561 fails. A 1,025-byte request uses a large pool. Zero, full-width oversized values and rounding overflow retain rejection. |
| Small-pool preference | Small requests use slots 1–5 first, then may use slots 6–7. Large creation fails cleanly when small Tasks occupy the only fitting pools. Freeing a fitting pool permits the next valid request. |
| Shared ownership | Mix caller-owned AddTask storage, managed Tasks, service workers and Process reservations. Reject occupied, preparing, retired-but-uncollected and incarnation-exhausted slots without bypassing `SlotFree`. |
| Explicit bounds | AddTask accepts complete generated bounds and a valid nondefault initial S; rejects stale pre-move bounds, truncated extents, invalid S/alignment and invalid entries without changing existing Tasks. |
| Retirement and reuse | Cover normal return, self-removal, permitted external removal, lease/resource ownership rejection and repeated reuse of both larger pools. Preserve notification ordering, cleared DP metadata and Process ownership rules. |
| Competing creators | Nested Forbid and actual preemption preserve unique ownership; failed creation changes no ready queue, live count, managed record or remaining capacity. Follow each rejection with a valid admission. |

Use the existing fixtures' diagnostic access to private Process state where
needed; keep such controls out of production policy. Include a real Process
reserve/collect path to validate that a retired slot remains unavailable until
collection. Test console/SIO/DOS first-free admission with the smaller slots
preceding the larger ones. Do not introduce a separate reservation class or
change Process launch into a stack-size API.

The production selection/removal policy should already handle heterogeneous
sizes. Change it only for a demonstrated defect, preserving public semantics
and the single ownership predicate. Add a focused regression for any such fix.
Compiler defects belong in actionc with emitted-code regressions.

**Exit gate:** the selected groups pass through raw and optimized emitted code,
with bounded completion, intact guards and no retained resources. Retain a
small four-Task control and the existing explicit-override path. Report actual
executed cases rather than claiming the full lifetime or platform matrix.

Suggested commit: `Cover admission and reuse of mixed Task stacks`.

## L3 Validate stack depth and asynchronous entry

### Action and assembly execution

Add a focused native depth fixture, proposed as
`tests/programs/large_stacks.act` with `tools/test_large_stacks.py`, reusing
the existing build/execution and guard-reporting helpers. Two workers request
2,560 bytes and keep distinct checked local data live across nested calls,
waits and preemption. Their measured call depth must exceed the ordinary
1,024-byte pool's 768 bytes above the interrupt reserve, while remaining within
the larger pool's bounds. Check data and return values so optimization cannot
remove the workload. A separate computing peer must make progress.

Run in raw and optimized mode. Include controlled Action! entry/call and
handwritten assembly reservation failures, following
[test_stack_checks.py](../../tools/test_stack_checks.py). Target an actual
larger worker, not only the unchanged root. A bounded logical-floor injection
may exercise the failure path while preserving physical interrupt space;
restore diagnostic mutations before normal domain verification. Require the
expected fault, unchanged physical guards and controlled OS restoration.

### Two C workers

Extend [build_calypsi.py](../../tools/build_calypsi.py) and
[test_calypsi.py](../../tools/test_calypsi.py) with an explicit eight-Task
large-stack fixture selection, retaining the existing ordinary C example.
That selector is test configuration, not a second Task implementation.
The current C context fixture runs on root and one worker in a four-Task
build; changing its requested size alone does not demonstrate two large Tasks.

Adapt [calypsi_context.c](../../tests/programs/calypsi_context.c), or add a
dedicated bounded fixture when that keeps the current message assertions
clear. Create two worker activations requesting 2,560 bytes and register every
required C entry through the existing foreign-image admission mechanism.
Have root or an ordinary worker provide the computing-peer check. Keep
per-worker progress, checksum, startup and completion observations distinct.

Use nested C frames with live local data and kernel bridge calls, then verify
the data after actual VBI switches. Read the compiler listings and observe
stack depth; a source array declaration alone does not prove stack use.
Replace fixed `(0,2)` slot assumptions and the literal 1,536-byte bound in the
observer with the selected workers' actual bounds. Observe an interrupt from
inside each worker's C code, validate the full saved S and D, and preserve the
existing lower-DP, native-register and kernel-workspace assertions.

Run the paired raw/optimized configurations, recording both Action! NIR mode
and actual Calypsi flags/runtime hashes. Keep one existing four-Task C message
or context control after refactoring shared harness code. Calypsi functions
still lack Action!'s automatic entry checks: bounded C success and intact
guards do not establish general C overflow protection.

### Interrupt and device boundaries

Select existing IRQ/NMI transition checkpoints covering admission, save/restore
and removal; add fixture-only observation where necessary to target both larger
pools and the moved idle stack. Preserve the SWITCHING protocol, Forbid nesting,
OS-busy behavior and pending scheduling. Exercise full A/X/Y, D, DB, S and
status restoration, including the hidden accumulator byte and width flags.
IRQ masking must not be treated as protection from NMI.

Run one bounded physical SIO/console workload while both large workers are
live. Use the chosen pinned disk profile, verify exact I/O completion and
continued worker progress, then release resources and restore OS state.
Check the reserved VBXE aperture sentinel. This test does not enable VBXE.
Budget every participating Task within eight slots; do not combine the five
standard demo Tasks, both large workers and a two-command pipeline.

For every relevant workload, report peak use and remaining space for each
large worker, the ordinary peer, idle and kernel. Use a fresh boot fill or
explicit lifetime tracking; do not refill a live stack or mistake reuse-era
high-water marks for a single call's peak. Record observer borrowing separately
from production reservations. Keep the kernel stack at 1,536 bytes.

**Exit gate:** both languages demonstrate two simultaneous large-stack Tasks,
actual preemption, bounded deeper calls, correct data/contexts and cleanup.
Checked overflow cases and the selected device/transition cases pass. These
results establish the stack facility for the measured fixtures; GEM's adapted
engine still requires its own measured link map and call-chain tests.

Suggested commit: `Validate larger stacks under C execution and interrupts`.

## L4 Refresh the demo and publish development evidence

Update [Task capacity](../architecture/task-capacity.md), the
[platform contract](../reference/platform.md), applicable
[Task guidance](../guides/tasks.md) and
[C guidance](../guides/calypsi-c.md) to describe the implemented mixed map,
size requests, guard/headroom costs and availability limits. Replace obsolete
current-layout descriptions; retain historical evidence unchanged. Update
the GEM assessment's current reservation totals and stack-limit discussion,
linking the new evidence without claiming a working GEM port.

Build the standard distribution through [build_demo.py](../../tools/build_demo.py)
using the new default map. Include OF816, the matching disk and pinned ROM,
upstream notices, guide and checksums. Keep the five-second shell/prime autoboot.
Use [test_of816.py](../../tools/test_of816.py) for its existing bounded monitor
handoff/exit coverage and packaged shell smoke. Reuse that shell run where it
already verifies disk commands, a two-command pipeline and normal EXIT; avoid
repeating an unchanged full demo walkthrough solely to collect another pass.

Verify the ZIP's allowlisted contents and hashes using the existing packaging
checks. The distribution is `exec816-demo.zip`; build manifests, compiler
outputs, logs, machine-state dumps and test reports remain outside it. A demo
refresh is development integration evidence, not a release qualification claim.

Assemble `docs/development/larger-task-stacks.json` from completed reports.
Include baseline/final source and profile hashes, compiler/ROM/emulator inputs,
overrides, generated phase maps, fixed and per-slot reservation deltas, case
identifiers/results, image hashes, full compiler modes, bounds/guards, register
and DP observations, measured stack peaks, elapsed time and artifact sizes.
Record emitted Task-policy/gateway/C-shim sizes against matching L0 inputs.
Measure the added initialization work on a matching instrumented build if a
timing figure is reported; otherwise mark it unmeasured. Do not infer runtime
cost from the 3,072 additional bytes filled at boot.

Mark the design and this plan implemented only when L1–L4 gates pass, linking
the evidence and stating its development scope. If inputs are missing or a
required case fails, report that gate as pending; do not substitute a host-only
pass or silently widen a stack. Update the [plan index](README.md) last.

Suggested commit: `Integrate and document the larger Task stacks`.

## Required checks and completion record

After each coherent code slice, run the host suite and affected generators:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/generate_tasks.py --check
python3 tools/generate_exec_abi.py --check
python3 tools/generate_calypsi.py --check
```

Generation of resolved four/eight maps is additionally covered by the packaging
checks and actual builds. Run native cases selected above with explicit modes,
configuration and output directories. Any new fixture selector must be documented
with its actual command when implemented; this plan does not pretend that those
selectors already exist. Reuse unchanged images for scenario variants and keep
routine runs bounded. Alternate kernel banks, baud/media matrices and broad
release qualification are outside this development pass unless a failure points
to a specific boundary that needs deeper coverage.

Completion requires all of the following:

- Default eight-Task builds contain exactly two 2,560-byte worker pools, use the
  designed addresses and cost +3,072 bytes with 9,408 bytes left after startup.
- Four-Task behavior and the public Task ABI remain intact; admission and reuse
  share existing ownership rules across ordinary, larger and Process-held pools.
- Raw/optimized native and C fixtures, controlled checked-overflow cases,
  selected IRQ/NMI/device cases and the refreshed OF816 demo pass their gates.
- Current documentation, actual per-slot cost reports and reproducible
  development evidence agree with the generated and executed images.

## Completion record

L0 captured the compact four/eight maps and raw/optimized creation baseline.
L1 changed the eight-Task profile and omitted-override handling, tightened
boot-arena overlap checks and derived per-pool cost reports. L2 extended the
existing creation fixture; production selection/removal policy needed no change.
L3 added bounded Action!/C depth, Process collection, logical-floor injection
and device fixtures, using existing NMI transition checkpoints. L4 rebuilt
the standard OF816 ZIP and passed boot/shell/exit checks.

Development scope: 257 host tests (four historical source audits skipped),
three generator checks, 43 focused native cases, plus the OF816 integration
cases in the [record](../development/larger-task-stacks.json). Production
bank-zero delta: **fixed 0; slots 6 and 7 +1,536 bytes each; total +3,072**.
Initialization timing remains unmeasured. No public Task ABI, compiler shim
or kernel scheduling policy changed. General C overflow protection, GEM call
chains, mapped VBXE and full release qualification remain outside this result.

The new selections are reproducible with the pinned inputs under
`build/larger-task-stacks/`:

```sh
# Run each command with MODE=raw and MODE=opt.
python3 tools/test_create_task.py --mode "$MODE" --capacity 8 \
  --suite large-bounds,large-order,large-return,large-self-removal,large-concurrent,large-reservations,large-held-removal,large-producer-removal,large-memory-removal \
  --output "build/larger-task-stacks/admission-$MODE"
# CASE: depth, overflow, compiler, assembly, coexistence, process.
python3 tools/test_large_stacks.py --mode "$MODE" --case "$CASE" \
  --output "build/larger-task-stacks/$CASE-$MODE"
python3 tools/test_calypsi.py --mode "$MODE" --large-stacks \
  --output "build/larger-task-stacks/c-$MODE"
# CHECKPOINT: 9 (guarded dispatch), 11 (selected restore),
# 15 (tick consumption), 17 (restored D, remaining registers on stack).
python3 tools/test_large_stacks.py --mode opt --case depth --nmi "$CHECKPOINT" \
  --output "build/larger-task-stacks/nmi-$CHECKPOINT"
python3 tools/build_demo.py --output build/larger-task-stacks/demo
python3 tools/test_of816.py --output build/larger-task-stacks/demo/of816
```

The evidence also includes the raw/optimized ordinary boundary cases, kernel
bank-1 capacity/register checks, a four-Task return control, an explicit
512-byte worker override and the existing optimized four-Task C context probe.
All original build reports and intermediate files remain outside the ZIP.
