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

## QF3: native files, stdio and terminal errors

A four-slot per-image table now backs the retained GEMDOS calls and the pinned
Calypsi file hooks. Descriptors start at 3, preserve complete native identities
and retire exactly once after terminal Close. Standard output/error borrow the
native context's Output handle. Create, exclusive create and existing update
use the existing public modes; append and new-position seek preserve their
native guarantees. Metadata uses ExamineExact and explicit availability.

The [runtime contract](../../ports/gem4xe/apps/qed/native/README.md) lists error
mapping, supported hooks and remaining calendar/stdio limits. Calypsi's emitted
sizes are size_t=2, fpos_t=4 and time_t=8. Hooks preserve negated errno in size_t;
GEMDOS calls retain LONG transfer counts. The file build selects the real
integer formatter with `printf=nofloat`, including every independent relink.
The default reduced formatter left `%ld` literal and was insufficient.

The installed 5.18 `__fs_fdopen` did not initialize its FILE list link or unget
count. The [pinned runtime correction](../../toolchain/calypsi-runtime.json)
prepares a separate corrected source, retaining the original notices and
archive. The general C emitter records this explicit source override. Poisoned
allocations, two simultaneous streams, reopen/reuse and both FILE/buffer
allocation failures exercise the corrected behavior. The runtime's startup
adapter actually initializes its private standard streams; donor board startup
and default heap/termination routines are absent from the linked fixture.

SetIoErr is now an ordinary public C binding/import, and the shared wrapper
preserves the application's native cause across AES teardown. C APP ABI 22
requires matching rebuilt providers/applications. The focused raw/optimized
probe checks the complete LONG error value as well as the emitted library
widths. The current body/cleanup path distinguishes handled operational errors
from an unhandled cause and promotes a cleanup failure after a successful body.

The [QF3 record](../development/qed-native-qf3.json) identifies six selected
cohorts: both ABI modes, optimized ownership and Stop, and real RAM plus each
of SpartaDOS and MyDOS. The file cohort starts the same private image twice,
then a separately loaded failure image. It checks exact binary bytes, native
prefixes, a parsed quoted 8.3 name, inherited relative paths, EOF/short reads,
update/seek positions and rejected seeks, descriptor admission rollback,
stdio buffering/formatting, FILE/buffer allocation rollback and append.

Failure hooks perform a real confirmed-prefix Write or a real terminal Close,
then inject the tested operational result. They verify short/no-prefix writes,
actual fclose EOF/errno, single retirement, reopening the confirmed bytes and
ordinary Process result 20/secondary DISK_FULL after cleanup. These are adapter
boundary injections; they do not qualify physical media failure or recovery.
Both disk cases eject and audit the persisted ATR, including the nine exact
SAVED.BIN bytes and complete allocation consistency. The native fixture mounts
RAM explicitly and establishes its inherited current directory before entry.

Calendar time remains unavailable (`time` returns -1/ENOSYS); native DateStamps
remain separate metadata. The environment is empty. Optional calendar/autosave
and other deferred editor callers still need complete-source adaptation.
The editor's Save/Save As/backup policy is still strategy step 5.

The focused host suite reports 518 tests with four historical-source skips.
Native guards, IRQ/NMI, context restoration, heap baselines and ownership checks
pass. These are development checks, not hosted-system qualification. Reserved
bank-zero delta is **0 fixed, 0 per-public-Task, 0 private idle bytes**, including
guards, alignment and unused capacity. Descriptor/runtime metadata is private
upper-image/heap storage. The provider's DOS pointer table gains one 24-bit
entry before link alignment; no bank-zero reservation changes. QF4–QF6 remain
open.
