# QED native feasibility implementation

[History](README.md) · [Design](../plans/gem4xe/qed-native-feasibility-design.md) ·
[Implementation plan](../plans/gem4xe/qed-native-feasibility-implementation-plan.md) ·
[Source inputs](../../ports/gem4xe/apps/qed/README.md)

This is development evidence for strategy step 2. It does not qualify the
hosted system or establish that the complete QED editor runs. Detailed logs,
listings and generated work copies stay under `build/qed-native/`.

## QF1: sources and native ABI

The preparer verifies all 260 pinned QED/cflib input files and keeps fetched
originals separate from its patched native work copy. Ordered patches preserve
the upstream notices and switch the header boundary to the current public GEM
records. Port-local declarations remove the donor's near-data placement and
supply legacy word names, raster descriptor and event-timer argument adaptation;
they do not install the donor SDK or board runtime.

The source ledger accounts for 37 QED and 120 cflib compilation candidates,
21 donor-excluded cflib units and four donor board-support reference units.
With the initial header adaptation, 52 candidates compile and 105 retain their
actual diagnostics for later adaptation. Successful units record undefined
symbols; all units record compiler commands and diagnostic hashes. This is a
compilation inventory, not a complete source closure or layout result.

The ABI fixture checks target-emitted huge/native pointer and word widths,
OBJECT/TEDINFO layout, unsigned characters, a function-pointer call, actual
accesses and copies across a bank boundary, and a real native timer call with
the legacy argument shape. It enters and returns through the ordinary loaded
C Process and shared AES wrapper. The raw cohort selects two ABI/return cycles;
the optimized cohort also checks concurrent private loads, reuse, malformed
images and allocation rollback through the existing Process fixture. Native
support remains optimized in both cohorts.

The [QF1 record](../development/qed-native-qf1.json) identifies the actual tools,
runtime/header hashes, platform, selected cases, guards, asynchronous entries,
context/ownership checks, source inventory and artifacts. The selected cases use actual native SIO IRQs and VBI NMIs. An additional
continuous synthetic timer-1 stimulus caused cold graphics admission `$F731`
and a later graphics device fault `$FF93`; those exploratory failures remain
under the detailed outputs and do not qualify graphics under that stimulus.
Native inputs changed
deliberately from the fixed step 1 baseline are reported there; the original
manifest remains unchanged.

Reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle bytes**,
including guards, alignment and unused capacity. Existing guarded execution
pools serve the fixture. Stack watermarks remain lower bounds; QF5 still needs
frame/call bounds and actual stack observations for retained QED paths.

QF2–QF6 remain open: owned entry/allocation with real text storage, file/stdio
semantics, complete retained-source layout, stack/admission and reconciled
handoff evidence. No QED APP or demo is published by QF1.
