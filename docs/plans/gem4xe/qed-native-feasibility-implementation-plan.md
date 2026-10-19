# QED native build and runtime feasibility implementation plan

[GEM plans](README.md) · [Feasibility design](qed-native-feasibility-design.md) ·
[Initial scope](qed-scope-and-dependencies.md) · [Port strategy](qed-port-strategy.md)

Status: QF1–QF6 proposed; implementation has not started. These slices implement
strategy step 2. They establish a real native runtime, source/layout evidence
and a stack/admission decision before the QED resource/window work in step 3.
The final editor remains subject to the later editing and saving gates.

Commit each coherent slice after its selected development checks pass. Keep
the pinned QED/cflib inputs and first-editor scope. New tool, fixture and source
paths below are proposed implementation locations, not existing commands.

## Slice order and completion gates

| Slice | Deliverable | Gate |
| --- | --- | --- |
| QF1 | Reproducible native work copy, ABI probe and source/dependency ledger | Target ABI probes execute in raw and optimized modes; every source candidate and exclusion has an explicit disposition. |
| QF2 | Owned runtime entry, allocation and cleanup with real QED text storage | Optimized loaded APP passes normal/failure/reuse cases with private state, correct data and restored resources. |
| QF3 | Native file/stdio adapters and required metadata/time behavior | Real file operations and terminal errors pass on disposable fixtures; unsupported calendar or optional facilities remain explicit. |
| QF4 | Complete selected-source compilation, QED layout and any justified image-profile extension | A measured complete graph and explicit future allowances fit the selected bounded layout; executable packaging rejects analysis artifacts. |
| QF5 | Measured stack requirements and reliable Process admission | Selected runnable paths meet headroom/guard requirements in eligible pools; unexecuted paths have explicit frame bounds or remain unresolved. |
| QF6 | Reconciled feasibility record and step 3 handoff | All step 2 gates and material budgets are supported by identified evidence; remaining GEM and save work is listed accurately. |

QF1 precedes runtime work. QF2 and QF3 supply the real runtime closure measured
by QF4. Gather stack observations from QF1 onward; QF5 consolidates them after
the retained source graph and layout are known. A compiler, image or stack
blocker is resolved at its owning boundary before a dependent slice proceeds.

## QF1 Prepare sources and prove the ABI boundary

Add a preparation entry point such as `tools/prepare_qed.py` using
[inputs.json](../../../ports/gem4xe/apps/qed/inputs.json). Verify the original
source/tree and file hashes, preserve line endings, copy notices and apply
ordered patches under `ports/gem4xe/apps/qed/patches/` to a separate work tree.
Keep fetched originals and generated work under `build/qed-native/`. Never
patch the upstream cache or a separate donor checkout in place.

Add native compatibility declarations and adapters local to the port, using
the current public Exec/GEM records. Retain unsigned-char compilation for QED,
explicit word typedefs and the native huge-data model. Record changes to donor
record access, near declarations, entry and deferred feature paths. Do not
replace the native public headers with the donor SDK.

Create a small emitted ABI fixture, provisionally
`tests/programs/qed_native_abi.c`, and a selectable runner such as
`tools/test_qed_native.py --group abi --output DIR`. Cover:

- Target-emitted widths/offsets for used pointer-bearing records, huge/native
  pointer conversions, function pointers and legacy word types.
- Bank-boundary pointer arithmetic, copies and actual accesses, plus character
  values above 127 and the donor/native event-call argument shape.
- Ordinary native Process entry/return and C workspace/context restoration
  under actual IRQ/NMI activity.

Use small raw and optimized executions for these compiler-facing cases. Reuse
the current layout/bridge fixtures where possible. Record actual compiler,
assembler, linker, runtime archive and relevant system-header hashes.

Compile the source candidates far enough to produce a ledger of translation
units, diagnostics, required symbols and explicit exclusions. Preserve genuine
errors and distinguish missing later GEM declarations from compiler defects.
The ledger must account for all original candidates; a count of successfully
compiled files alone is not its completion criterion. Full retained-source
compilation is the QF4 gate.

Bank-zero target: **0 fixed, 0 per-public-Task, 0 private idle**. The fixture
uses existing execution pools and records any observer storage separately.

## QF2 Implement entry and allocation ownership

Add runtime sources under `ports/gem4xe/apps/qed/native/` and a bounded loaded
fixture, provisionally `tests/programs/qed_native_runtime.c`. Add a runtime
group to the QF1 runner. Use normal C application loading and Process start,
return and collection; the test must not install a private launch path.

Implement bounded zero/one-argument parsing with quoted native paths and
upper-memory ownership. Implement the allocation family and ownership chain
selected by the design, including the real `Malloc(-1)` query. If required,
add the existing public AvailMem operation to the ordinary C imports and
regenerate/rebuild the matched provider and applications in this slice.

Link actual QED text-storage routines from the prepared source into the fixture.
Exercise allocation, insertion/growth, content preservation, release and
`kill_memory` rather than duplicating that logic in a host model. Fixture-only
notification callbacks may record error outcomes instead of drawing QED's
unimplemented UI; identify them explicitly and keep them out of application
sources and sizing claims.

Adapt retained allocation-error and exit paths to unwind through their owners.
Verify that the executable dependency closure does not select donor board
termination or require a nonlocal escape through a native call.

Optimized cases cover allocation failure at acquisition boundaries, failed
realloc with preserved contents, calloc overflow, bank containment, partial
initialization, ordinary return, repeated text-store release and final cleanup.
Run two privately loaded probe instances to check mutable-state isolation and
repeat launch/collect/unload to check pool and allocation reuse. Retain guards,
bounded completion, context restoration and native asynchronous-entry checks.
Use a small existing-subset window only where needed to exercise cooperative
Stop through the real wrapper.

Run a focused raw/optimized bridge probe only if the slice changes that
boundary. Bank-zero target remains **0/0/0**; report upper allocation metadata,
rounding and peak backing separately.

## QF3 Implement and exercise the file runtime

Implement the single descriptor table and retained GEMDOS/C-library hooks over
public DOS operations. Record the real hook signatures from the pinned runtime
headers and list the mapped native errors, C errno values and GEMDOS results.
Keep owned descriptors above 2 and borrowed standard streams distinct.

Add file/runtime cases to the native fixture. Include native volume prefixes,
relative paths and quoted names; EOF, short transfers, read/seek/write,
new-position seek results, rejected seeks, descriptor exhaustion and Open
rollback. Verify exact data and cursor positions, not merely successful calls.
Use the existing native operation semantics for create/update, rename and
delete; replacement policy is not introduced here.

Cover ordinary and terminal-error Close, including failure after confirmed
writes. Check that descriptors retire exactly once, the original error survives
cleanup and the shared wrapper, and borrowed standard handles remain owned by
their native context. Expose ordinary SetIoErr if native secondary-result
restoration needs it; test any shared-wrapper preservation change separately.
Exercise the actual retained stdio path as well as direct file adapters; a
passing direct Fwrite does not verify fclose error propagation.

Start with RAM for focused iteration, then execute one bounded optimized native
file round trip on each of MyDOS and SpartaDOS, reusing emission where possible.
Use existing failure-injection facilities to reach short transfer, full-media
and late-close boundaries without running full transport matrices. Check the
persisted fixture bytes and ownership after failure.

Prove exact-length metadata handling on MyDOS and explicit unavailable date
handling. Implement only required time/formatting support; keep monotonic timer
ticks separate from calendar time. Audit the remaining linked stdio, environment,
assertion and exit dependencies. Remove deferred callers or provide correct
runtime behavior; a required unresolved helper prevents completion.

When a missing C import is needed, expose the existing public operation through
the normal machine-readable ABI and binding generation. Do not route around
the provider via a private address table. Rebuild affected applications and
record deliberate native-input changes against the step 1 baseline.

QF3 proves runtime semantics using disposable files. The QED Save/Save As/backup
workflow remains strategy step 5. Bank-zero target remains **0/0/0**.

## QF4 Measure the full QED graph and bound the image profile

Add a build entry point such as `tools/build_qed.py`, reusing the ordinary
compiler/emission and relocation machinery. With the QF2/QF3 runtime, compile
every retained QED/cflib unit and record the actual link closure. Exclude
deferred behavior consistently across startup, menus, keys, timers and teardown;
retain needed default initialization and editing-core state.

Produce a complete native layout report. If later GEM functions remain missing,
use the design's separately marked analysis ELF and enumerate every trap
binding, caller and planned resolution. Unclassified runtime helpers must not
be hidden in that set. Add a packaging rejection for analysis artifacts that
survives renaming or a direct packer call. Test that none can appear in media.

Report code, initialized data, BSS, runtime helpers, import/trap bytes, relative
bank placement, padding, file bytes, complete span, heap alignment backing and
allowances for later local code. Identify remaining resident-provider growth
separately from private QED image growth. The runtime fixture's size and donor
G4A size are not substitutes for this report.

If the measured graph does not fit, make the smallest general bounded layout
change justified by those measurements. Update the linker placement, image
metadata/ELF reader, packer, machine-readable limits and loader together. Check
data/BSS placement and segment count as well as code capacity. Preserve one
current C application profile; regenerate definitions and rebuild callers when
the contract changes.

Validate the changed format/placement through host rejection cases and emitted
code. Retain independent relinks at every legal base in the bounded profile;
verify symbol positions and reconstructed bytes. Execute a real runtime probe
at representative separated placements, including any newly enabled extent.
Add focused layout/bank-boundary failures rather than duplicating whole system
walkthroughs in raw mode.

Relevant existing checks include `tests/test_calypsi_image.py`,
`tests/test_c_program_package.py`, `tools/test_c_program.py` and selected cases
from `tools/test_c_process.py`. Extend their selection only where necessary.
Run both build modes for changed ABI/extraction/bridge behavior, keeping the
larger runtime scenarios optimized.

Completion requires a bounded fit decision with every remaining allowance
identified. An unresolved essential component or incomplete link keeps this
gate open. No analysis-only ELF is called a runnable QED build.

Bank-zero target remains **0/0/0**. Record complete upper-memory/image costs,
including unused holes and the loader's alignment allocation.

## QF5 Establish stack feasibility and admission

Use the accumulated runnable scenarios to locate deep startup, allocation,
stdio/file, error and cleanup chains. Extend the existing stack observers only
as needed to attribute minima to the live Process, actual pool and lifetime.
Observe S after emitted frame reservations and corroborate it with listings;
do not rely on a fill watermark or sparse entry samples alone.

Check the ordinary pools that normal Process admission can select. Include
bridge/native frames, interrupt reserve, kernel use and existing guards. Require
at least 128 bytes above the interrupt floor in selected executable cases.
Account separately for unexecuted QED/GEM chains using emitted frame/call data;
unbounded recursion or an unexplained allowance remains a blocker. Record which
later GUI paths still require measurement once implemented.

First remove donor near-data assumptions and move persistent/large automatic
state into owned upper storage where that preserves natural ownership. If the
measured requirement still exceeds ordinary pools, write the design addendum
specified by the feasibility note before implementing a general pool change or
minimum-stack admission. Define the exact public/serialized metadata and ABI
migration, compatible pool selection, failure result and ownership rollback.
Do not reserve a QED slot or depend on launch order.

For changed admission, execute compatible-pool selection, larger-pool occupancy,
exhaustion/rejection before entry, rollback, retirement and reuse. Preserve the
current native/loaded Process behavior and rebuild affected callers together.
Use focused raw/optimized layout/bridge cases if the ABI changes; keep the
ownership and load cases optimized. Reuse the existing Process, large-stack
and C Process checks where applicable.

Pool selection alone must add **0 reserved bank-zero bytes**. Any actual pool
growth requires a complete generated map/budget check before adoption: fixed,
each public Task and private idle, guards, alignment, reserve, unused capacity
and loading/runtime overlap. Record the delta from the immediately preceding
layout; do not reuse a historical budget comparison.

## QF6 Reconcile evidence and hand off to startup work

Record detailed outputs under `build/qed-native/`. Add a concise development
record and an implementation history page when these slices actually execute,
updating their indexes. Preserve the step 1 upstream pins and historical source
audit; record new adaptations, native input changes, tool/header/runtime hashes,
platform identities and exact executed cases in the new evidence.

Reconcile all gates with one source/build baseline. Record actual runtime
and text-storage results, the full layout and future allowances, stack/admission
decision, upper-memory costs and complete bank-zero deltas. A fit based on an
analysis ELF remains conditional on its explicitly listed future bindings and
allowances; it is not editor execution evidence.

Run host checks, affected generators and the selected optimized native cases
under the [two-tier policy](../../contributing/testing.md). Do not repeat passing
cases without changed inputs or a new concern. Full qualification is reserved
for a release or an explicit request.

If shared profile/provider changes require a demo refresh, use
`tools/build_demo.py`, include OF816, matching disks and pinned ROM/notices, and
preserve the five-second standard shell/prime autoboot. Rebuild packaged
applications together and run the affected ordinary launch/close smoke on that
exact package. Keep QED proof fixtures, analysis ELFs and development reports
outside the distributed ZIP. Strategy step 7 remains the actual QED delivery.

Update the strategy with the achieved step 2 result and link the evidence. The
handoff to step 3 lists the remaining resource/menu/workstation interfaces,
their measured budgets and any unexecuted stack paths. Mark step 2 complete
only when the design's runtime, layout and admission gates are met.

This plan itself changes **0 fixed, 0 per-public-Task and 0 private-idle reserved
bank-zero bytes**, including guards, alignment and unused capacity.
