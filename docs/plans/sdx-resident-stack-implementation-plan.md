# SDX resident stack implementation plan

Status: implemented functional changes, 24 October 2026. RS0–RS5 have passed
their selected development checks. RS6 dispatch changes are implemented, but
the p95 ≤100 ms interaction target remains open. RS7 delivers the rebuilt
package and current contracts; this does not close the latency gate or qualify
the hosted system. See the [execution record](../history/sdx-resident-stack.md).

The BASIC parser needed an additional admission change: its grammar records
now use a bounded private-bank buffer instead of recursive CPU-stack storage.
This preserves normal array expressions within the audited ROM budget and
reports excessive grammar depth through the existing parse-error result.

[Design](sdx-resident-stack-design.md) · [Plan index](README.md) ·
[Platform and memory budget](../reference/platform.md#bank-zero-memory-budget) ·
[Testing policy](../contributing/testing.md) ·
[EDX baseline](../history/edx-interaction-baseline.json)

Deliver one active emulation-mode SDX/FastBasic guest whose page-one stack stays
resident across native services and waits. ROM entry borrows below its live
frames. Idle persistent BASIC releases page one while keeping its Process,
variables and resources, allowing EDX, ARC, MD5 and Check/Build between runs.
Then reduce EDX interaction cost through changed-column spans and bounded RAWCON
dispatch. Each slice must leave a runnable build and record its selected checks.

Keep two retained Image/private-DP slots, twelve public Task slots, native
preemption, the current guest instruction mode and the existing public kernel
interfaces. A second active guest fails with primary 20/secondary 202 before
guest execution, console changes or state mutation. An ordinary blocked guest
retains ownership; only an invocation-ending BASIC checkpoint permits parking.

## Dependencies and acceptance gates

| Slice | Deliverable | Depends on |
| --- | --- | --- |
| RS0 | Frozen comparison and audited stack bounds | Current bridge |
| RS1 | Separate private initialization from invocation setup | RS0 |
| RS2 | Shared ROM stack borrowing and transition probes | RS1 and RS0 bounds |
| RS3 | Coordinated resident-frame cutover, one lease and BASIC parking | RS2 emitted safety checks |
| RS4 | Interrupt, device and application integration | RS3 |
| RS5 | RAWCON changed-column spans | RS4; retain stack-only measurements |
| RS6 | Bounded RAWCON dispatch and matched latency acceptance | RS5 |
| RS7 | Current contracts and final distribution | RS4–RS6 acceptance |

The source/ROM bounds in RS0 and emitted borrowing checks in RS2 gate RS3.
If headroom cannot be established for an admitted application, resolve the entry
path or explicitly revise its admission in the design before cutover. Do not
substitute observed watermarks for a bound, silently drop EDX/ARC/FastBasic, add
stack copying as a fallback, or enlarge bank-zero reservations.

RS1 and RS2 prepare the current implementation; neither adds a selectable second
guest runtime. RS3 changes the internal frame ABI and all consumers together,
removes the old copy implementation, and delivers parking in the same slice.
Do not distribute an intermediate runtime that blocks Check/Build merely because
the retained interpreter is idle.

## RS0 Freeze inputs and establish stack bounds

Pin the dedicated AltirraOS 65816 ROM and actual emulator binary/configuration
used for every probe. Start from the baseline's 8× 65816, PAL, 64K base plus
63 high banks, VBXE, ST mouse on port 2, SIO patches/burst off and accurate
`generic56k` transport. Use the compiler selected by
[actionc.json](../../toolchain/actionc.json); record any local override explicitly.

Retain the unchanged native image, guest binaries/overlays, system fixture and
source identity outside the ZIP. Promote the existing development observer into
`tools/measure_sdx_editor.py`, adding a reusable independent scanout oracle and
separate input-ready timing. Before changing runtime code, collect at least
20 samples for insertion, horizontal caret and vertical caret operations on the
same 64×20 desktop, with warm loading excluded. Keep the original five-sample
record unchanged. Record key-hold duration, observation cadence, sample counts,
median/p95, request counts and observer hashes for the new matched baseline.

Audit the pinned ROM listing, adapter and admitted guest binaries. Record maximum
guest live-stack depth, absolute page-one uses, earliest hardware/veneer pushes,
ROM COP `$00`/VBI paths, permitted nesting and the lower guard. Account for hidden
register saves, synthetic frames and return reconstruction. Classify every
`OS_STACK_TOP` site as runtime borrowing, boot/final return or test-only code.
Ordinary native SIO retains its existing exclusion of ROM serial services.

Produce a machine-readable bound record and a short derivation identifying each
reachable path and its maximum consumption. Specify the checks that establish
`Sg - R >= $0110` before borrowing and the admission bound covering pushes before
software can inspect S. Reproduce deepest permitted ROM paths in a small emitted
probe; reserve forced borrowing/transition checks for RS2.

Exit: reproducible comparison inputs, a source-derived bound for every admitted
guest/profile, and a complete stack-entry inventory. A failed bound keeps the
cutover pending. Runtime reservations and shipped behavior remain unchanged.

## RS1 Separate initialization and invocation lifetime

Refactor [sdxstate.act](../../lib/dos/sdxstate.act),
[sdxprogram.act](../../lib/dos/sdxprogram.act),
[fbprogram.act](../../lib/dos/fbprogram.act) and
[fbservice.act](../../lib/dos/fbservice.act):

- Allocate/patch the retained Image and initialize its private DP/bank without
  constructing an invocation frame. Move frame construction to invocation entry.
- Separate interpreter initialization/reset from Run. Initial attachment and
  Restart prepare private state while the native Process waits for requests.
- Make invocation completion an explicit native boundary after requests/output,
  console restoration and diagnostics have settled. No live frame reference may
  remain in the request/reply protocol at that boundary.
- Keep BASIC data across ordinary Run completion, and preserve current one-shot
  FB/FBI and FBC/FBCI initialization. Reusing an SDX Image still resets the
  application-specific BSS and invocation state required by its audited profile.

Keep the existing copying bridge as the sole runtime during this preparation.
Test loading/resetting one Image while another executes, repeated invocation,
allocation/setup failures and normal Process/Image collection. Extend the small
raw/optimized shape fixture for changed state access; run optimized interpreter
session and loader cases. Do not add a public admission hook to Process creation.

Exit: load, attach, reset and parked native waits have no dependency on a live
invocation frame; existing guest behavior passes focused regressions. This is
the lifecycle foundation for lease acquisition and parking in RS3.

## RS2 Centralize ROM borrowing and prove transition mechanics

Add the upper-memory resident descriptor and atomic phase definitions to
[abi/sdx.json](../../abi/sdx.json); generate Action!/assembly definitions through
[generate_sdx.py](../../tools/generate_sdx.py). Keep descriptor storage within
the existing upper bridge bank. A lifetime lease, a complete borrow anchor and
the CPU's interrupted context must be represented separately.

Implement one stack-selection helper in the platform adapter. Ordinary entry
uses the controlled OS top when no resident frame exists. A complete resident
frame supplies its S as the downward borrow anchor. Nested entry already on
page one preserves its current S. Route runtime OS calls, interrupt forwarding
and runtime diagnostics through this rule, preserving boot/final-return lifetime
rules and native SIO ownership.

Specify atomic phase publication, multi-byte field visibility, pending NMI
handling and exclusion of guest resume/lease changes while ROM is active. Keep
the current guest runtime on its existing path until RS3; only synthetic probes
publish resident frames in this slice. No production compatibility flag or
alternate scheduler policy is needed.
Initialize the descriptor to FREE before enabling entry hooks, and retire every
guest/ROM activation before removing hooks or releasing descriptor storage.

Add `tools/test_sdx_resident_stack.py` with bounded `--group bounds|rom|transition`
selection, `--case raw|opt` and `--output DIR`. These are new planned selectors.
Exercise the real helper with synthetic complete frames and native callers at
the minimum permitted headroom. Check live bytes above the anchor, lower guards,
all saved registers, native S/D and nested return frames. Dead scratch below the
anchor is allowed to change.

Force NMI at publication, S changes and partial restores; include nested
bank-zero entry and early emulation stubs. Reject insufficient headroom before
unsafe pushes. A host canary check after execution does not establish that fault
ordering. Corroborate RS0 bounds against the actual emitted helper and ROM paths.

Exit: shared ROM entry passes optimized borrowing/nesting/failure probes and
focused raw/optimized descriptor/frame access checks. No Task switch or wait
occurs across a live ROM activation or incomplete transition.

## RS3 Cut over all guests and park idle BASIC

Make the internal ABI change as one coherent slice across the generated
definitions, [sdx-runtime-probe.s](../../platform/altirraos/sdx-runtime-probe.s),
`SDXRUNTIME`, `SDXSTATE`, SDX service/trap/overlay consumers and all FastBasic
frame consumers. Distinguish two retained Image slots from one active context;
replace upper-page snapshot addressing with physical frame addressing. Preserve
the generated 13-byte frame contract unless an explicit change is required.

Acquire the exclusive lease before first frame construction, initialize the
physical invocation stack and keep it resident through native waits/preemption.
Retain complete context, guard, ROM-shadow and bank-classification checks.
Integrate pending-VBI return reconstruction with the RS2 protocol. Update
nonlocal trap frame relocation and ARC overlay return handling under the same
gate. Remove host/guest page images, copy loops, copy-specific IRQ polling and
the old two-active-context execution branches.

Wire the RS1 interpreter boundary to release the lease after retiring guest
continuations. A Run reply means output/results are complete and page one is
available. Preserve private DP/bank, variables, arrays, strings, modes, RNG,
native channels and Process identity. A later Run reacquires before parsing and
creates a fresh frame; busy Run reports 20/202 without resetting state. Initial
attachment, Restart and Quit remain native while parked and never write another
guest's stack. Live BASIC input/delay/checkpoint waits retain the lease.

Add `--group lease` to the new resident-stack runner. Cover simultaneous
activation attempts, two loaded Images, prompt busy rejection, blocked owner
with native-peer progress, owner cancellation, failure after acquisition,
Image unload/collection and repeated reuse. Check a Run reply followed immediately
by another guest's acquisition. Rewrite affected current two-active-guest tests
to assert the new contract, keeping their guard/register/error checks and
preserving historical results.

Exit: optimized SDX and integer/FP interpreter smoke/session tests pass on the
single implementation, including parked BASIC → transient guest → BASIC Run.
Raw/optimized shape/access probes pass after rebuilding all consumers. Capture
the stack-only EDX measurements against RS0 before changing RAWCON behavior.

## RS4 Exercise asynchronous entry and real applications

Extend `test_sdx_tasks.py` and the resident-stack transition probes to inject NMI
at every distinct entry, anchor-publication, frame-relocation, return and release
phase identified in the emitted control flow. Retain early-stub bank checks and
complete hidden-B/register/DP restoration. Exercise native ROM entry from a
different Task while the guest is blocked; lease ownership alone must never be
used to classify that Task as guest code.

Use the delivery's twelve-Task layout for the integrated case. Run actual sector
I/O and port-2 pointer IRQ activity during guest computation and service waits.
Select the delivery's `generic56k` profile plus the existing stock-810 traced
case because stack-entry changes affect interrupt latency and deferred work.
Compare their existing deadline/sample-gap limits, exact sector bytes, pending
work completion and OS restoration. This is targeted deeper development coverage,
not an automatic sweep of all transport/profile axes.

Update current application fixtures for sequential guest execution and explicit
busy errors. Cover MD5 verification/cancellation; ARC empty-argument help,
overlay return, extraction and one mutation/rollback case; and EDX editing,
save/reopen, traps and BREAK. Native apps and shell peers continue to make
progress while the active guest waits.

Extend `test_fastbasic_interpreter.py --group session` for integer/FP repeated
Run, arrays/strings, channels/modes/RNG, recoverable errors, Stop and Restart.
Exercise parked BASIC with EDX, MD5/ARC and actual Check/Build, then Run again.
Test busy Run during another active guest, live BASIC waits excluding another
guest, and Reset/Quit while a different guest owns page one. Verify Process
identity, preserved values, correct reset, final resource collection and no
outstanding page-one borrows.

Exit: selected application, interrupt and device cases pass with bounded
completion and intact guards. Record exact injected phases, tested stack
depths, measured IRQ gaps and profile identities; do not generalize beyond them.

## RS5 Flush changed RAWCON spans

Replace `screenDirty(30)` in `SDXSTATE.Session` with byte first/end columns for
each row. Use an explicit empty-span value. In
[sdxscreen.act](../../lib/dos/sdxscreen.act), mark only changed cells, including
software inverse-caret changes; clear/scroll mark the affected spans. Preserve
fixed invocation geometry, exact ATASCII cell readback and private-buffer ownership.

Issue the existing public synchronous `WRITE_CELLS` with row/column offsets and
the span length. Flush before returning a key, and clear damage only after its
full request succeeds. Preserve request FIFO, causal errors, cancellation and
console-mode restoration. Do not change the console driver or reach into its
private backing state to save crossings.

Extend emitted EDX/screen fixtures with narrow and separated changes, unchanged
status writes, horizontal/vertical scroll, maximum geometry, partial/failed
writes and retirement errors. Compare complete cell models and independent
pixels, rather than testing only the nominated damage. Confirm idle waits have
no output requests and no changed span is lost on failure.

Exit: exact rendering/error checks pass, ordinary cell/caret edits use bounded
spans, and a separate matched measurement records their costs. Report the
30-byte Session growth before alignment and actual upper-heap allocation.

## RS6 Bound RAWCON dispatch and meet the interaction target

Use the resident complete-frame contract for nonblocking cell operations that
can take a short native path without the general yielding dispatcher. Preserve
domain guards, full register restoration, event/error semantics and BREAK
checkpoints. Blocking input, DOS I/O, rendering and allocation remain outside
the transition gate. Clear/scroll work must retain bounded IRQ/cancellation
opportunities at maximum geometry; do not mask a whole-screen operation.

Measure entry/return, guards, guest execution, native dispatch, public console
requests and completed presentation separately. Select the fast path only where
these measurements justify it. If spans and the resident bridge already meet
the target and leaf dispatch has no useful gain, record that result instead of
adding another execution path. The ordinary public service contract stays current.

Run the RS0 cohorts against the same pinned optimized system and observer, with
at least 20 samples per insertion/caret operation. Report baseline, stack-only,
span and final median/p95, input-ready and visible-scanout times separately.
The design target is p95 ≤100 ms for ordinary insertion/caret interaction; keep
the key-hold/observation method fixed and report any timing floor. Scrolling and
large-document workloads have separate completion/fairness bounds.

Exit: matched measurements demonstrate the target with functional, pointer and
native-peer behavior preserved. If it remains unmet, identify the remaining
measured cost and keep the latency goal open; do not re-label software completion
as scanout or relax guards/deadlines to make a result pass.

## RS7 Update contracts and deliver the checked package

Update the platform/SDX runtime references, generated service reference, FastBasic
session contract, user guidance and affected development records. Record the
one-active-guest restriction, busy result, parked-state behavior and actual stack
bounds. Keep old measurements/qualification JSON unchanged and link them as
historical evidence. Add a current execution record with artifact hashes,
executed development scope, latency results and remaining qualification limits.

Build the standard graphical programming demo through `tools/build_demo.py`.
Retain OF816, its five-second standard autoboot, the combined writable D1
SYS/WORK disk, bundled SDX tools, separate QED ATR, port-2 mouse, matching ROM,
license organization and checksums. Rebuild all internal ABI consumers; stale
native images and refreshed media must not be mixed. Use a fresh native build,
not a media-only refresh around the old kernel.

```sh
python3 tools/build_demo.py --desktop --basic-workbench --fastbasic --sdx --qed --output build/sdx-resident/demo
```

Test the extracted final ZIP: cold combined-ATR boot, the matching XEX using
combined D1, supported cartridge launch/return, and the parked BASIC/tool/Run
walkthrough. Verify ARC without arguments and EDX/MD5 in the graphical shell,
actual saved output, SYS/WORK resolution, native peer progress and final cleanup.
Keep the ZIP limited to boot files, the short guide, notices and checksums;
build manifests, sources and test output belong in development/source delivery.
Preserve user-written writable FujiNet media when installing a new distribution.

Exit: final artifact hashes, package checks and executed walkthroughs are recorded.
Do not mark the entire plan complete while a required stack, interrupt or latency
gate remains open. Full hosted release qualification is still a separate tier.

## Validation commands and evidence

For each coherent code slice, run the host suite, affected generator checks and
the selected emitted tests. Start with the failing/changed case; do not rerun
passing unrelated matrices. Existing entry points include:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/generate_sdx.py --check
python3 tools/test_sdx_service_shape.py --case raw --output build/sdx-resident/shape-raw
python3 tools/test_sdx_service_shape.py --case opt --output build/sdx-resident/shape-opt
python3 tools/test_sdx_loader.py --case opt --output build/sdx-resident/loader
python3 tools/test_sdx_tasks.py --sio --trace --output build/sdx-resident/devices
python3 tools/test_sdx_edx.py --bitmap --output build/sdx-resident/edx
python3 tools/test_sdx_arc.py --group a1 --output build/sdx-resident/arc-help
python3 tools/test_fastbasic_interpreter.py --group session --output build/sdx-resident/session
```

Adapt those fixtures' expectations in RS3/RS4 before using them as acceptance for
the new runtime. The new resident-stack runner's groups are introduced in RS2
and RS3; add the smallest selected raw/optimized case for changed language/ABI
access and use optimized mode for system, failure and performance scenarios.
The new editor measurement runner accepts `--bundle DIR --output DIR`; RS0 must
record its precise physical input/scanout protocol for reproducible later use.

Every result records pins/overrides, optimization, source/image/media identities,
assertions, guards, completion bounds, actual stack use and OS/resource restoration.
Report instrumentation and replay scope explicitly. Tests for asynchronous
entry are required here because ownership and stack transitions change; they
do not turn focused development results into hosted-system qualification.
Fix any demonstrated compiler defect in actionc with a focused regression;
do not add Exec-routine special cases or silently change the pinned toolchain.

## Memory accounting for every slice

Compare each emitted `memory.json` with the preceding runnable slice and report:

| Reservation | Allowed added bank-zero bytes in every slice |
| --- | ---: |
| Fixed, including all guards/alignment/spare capacity | 0 |
| Root/kernel | 0 |
| Each of the twelve public Tasks | 0 |
| Idle | 0 |

Retain the complete 544-byte fixed two-DP reservation and existing physical
page-one guard. All descriptor additions fit the reserved 64 KiB upper bridge
bank. Deleting page images does not reduce that reserved bank's size. RS5 adds
30 upper Session bytes before alignment; record actual allocations, code extents,
stack headroom and any upper-memory change in every implementation result.
Documentation-only preparation adds no reservation and requires content/link
checks rather than an executable build.
