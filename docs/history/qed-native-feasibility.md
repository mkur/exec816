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

No QED APP or demo is published by QF1.

## QF2: owned entry, heap and text storage

The native entry copies zero/one argument into owned upper storage, including
the vector and program name. It accepts quoted native paths, rejects extra
arguments and unmatched quotes, and enforces the Process 255-byte limit. The
body returns through ordinary native `main`; it releases GUI borrowers before
entry cleanup walks remaining owned allocations.

`malloc`, `calloc`, `realloc`, `free`, `Malloc` and `Mfree` share a per-image
ownership chain. Each allocation keeps its original native pointer and exact
backing size in a 12-byte header. Zero requests, overflow, failed growth and
release follow the design. `Malloc(-1)` queries public `AvailMem`, subtracts
the owned header and respects the native bank constraint. Exec AllocMem can
provide a complete 65,536-byte bank; the largest returned runtime payload is
65,524 bytes. The eight-byte AllocVec prefix is unrelated to this backing.

The existing public AvailMem binding is now an ordinary APP import. The
machine-readable C APP ABI and generated native version advance to 21; matched
providers and probes are rebuilt. No new kernel operation or bank-zero storage
is introduced. Cached probe rebuilding checks the provider/import ABI before
reusing native code.

The fixture links actual QED `memory.c`. Its patch handles failed fallback
acquisition and failed insertion growth, reports text-ring initialization
failure, and permits repeated empty-ring release. The linked fixture closure
contains no donor startup or exit routine. Test-only error notifications and
highlight callbacks are identified in its source; they are not editor UI or
layout substitutes. Error propagation through other retained editor callers
still belongs to the complete-source adaptation and later editor work.

The [QF2 record](../development/qed-native-qf2.json) records the optimized
failure, content-preservation, bank-containment, text-store, private-instance,
repeat/collection and cooperative Stop cases, plus focused raw/optimized
AvailMem import probes. It also records the host checks and exact artifacts.
The Stop case holds an owned title through a real window's borrowed lifetime,
requests native Stop, retires the window, frees owned storage and collects the
Process after the caller drops its Image reference.

The one-character fixture's observed peak is 65,572 requested backing bytes:
a 65,536-byte backing plus 36 bytes for owned arguments. Native eight-byte
rounding makes those simultaneous blocks 65,576 bytes. This includes 24 bytes
of runtime headers and four bytes of unused rounding; native heap bookkeeping
uses its existing tables. General bounded argument storage requests at most
536 bytes including its header. Final heap counters and parent free-memory
checks return to baseline. Full QED heap demand remains unmeasured.

Reserved bank-zero delta remains **0 fixed, 0 per-public-Task, 0 private idle**,
including guards, alignment and unused capacity. QF3–QF6 remain open.
