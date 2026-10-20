# QED port strategy

[GEM plans](README.md) · [Implementation plans](../README.md) ·
[QED gap analysis](qed-gap-analysis.md)

Bring QED to Exec816 by first proving that its native build and runtime fit,
then making the real editor usable, then establishing reliable document saving
and everyday coexistence. Use each result to decide which compatibility gaps
need general platform support and which can be closed by adapting QED or cflib.

Status: [step 1 scope and source baseline](qed-scope-and-dependencies.md) fixed;
step 2 has a [design](qed-native-feasibility-design.md) and
[QF1–QF6 plan](qed-native-feasibility-implementation-plan.md), with
[QF1–QF6 implemented](../../history/qed-native-feasibility.md). The
[reconciled foundation](../../development/qed-native-qf6.json) closes step 2;
its complete-source image remains analysis-only, with conditional GUI budgets.
Step 3 is implemented through its [design](qed-startup-design.md),
[QS1–QS5 plan](qed-startup-implementation-plan.md) and
[startup development evidence](../../history/qed-startup.md). A runnable private
APP passes the empty-document/resource/menu/lifecycle gate. Steps 4–7 remain;
step 4 has a proposed [editing design](qed-editing-design.md) and
[QE1–QE7 plan](qed-editing-implementation-plan.md), with implementation pending.
Editing and reliable Save are not established by startup checks.

## First usable editor

Target a native, disk-loaded QED application using the existing Process, AES,
VDI and DOS services. Start with one document window, the built-in fixed font,
open and save, selection, internal copy and paste, undo, find, and an
unsaved-changes prompt. It should remain usable beside the shell and another
GEM application within the available Task and window capacity.

Defer multiple document windows, printing and GDOS, external fonts, AV and MiNT
integration, and desktop-wide clipboard exchange. Record each deferral so
completion means that this agreed editor works, without implying complete
compatibility with every donor feature.

## Recommended order

| Step | Outcome before advancing | Reason for this position |
| --- | --- | --- |
| 1. Fix scope and dependencies | Fixed in the [scope and dependency record](qed-scope-and-dependencies.md), with pinned source inputs. | Avoid expanding GEM for code paths the first editor will not use. |
| 2. Prove native build and runtime feasibility | A measured QED build, an executable native runtime foundation, and a viable memory and stack approach. | Image layout, pointer assumptions and runtime requirements can change the whole port. |
| 3. Start the real QED application | Its adapted resource and menu load, an empty editor window opens, and close returns resources. | Establish an actual application before broadening drawing and interaction. |
| 4. Make editing work | A document can be opened, edited, navigated and redrawn correctly, including the required dialogs. | Settle input and display semantics before allowing document replacement. |
| 5. Make saving trustworthy | Save, backup, failed save and close behave correctly on the selected filesystems. | A useful editor must preserve documents and report finalization errors. |
| 6. Establish practical coexistence | The complete workflow remains responsive, fits its resource budget and survives repeated use. | Measure realistic behavior before choosing performance work or larger capacities. |
| 7. Deliver the supported port | The packaged application passes its intended launch and editing workflow, with remaining gaps explicit. | Validate what users receive and close the agreed scope against evidence. |

### Establish scope and dependencies

The [scope and dependency record](qed-scope-and-dependencies.md) fixes the
first editor, required source paths and notices. The [source manifest](../../../ports/gem4xe/apps/qed/inputs.json)
selects an explicit QED/cflib pair and records the donor's source selection.
The donor leaves its external cflib revision unpinned; this source baseline
does not reconstruct its historical tested build. Keep the existing Exec
compiler and GUI pins unless a demonstrated requirement justifies changing them.

Trace startup, opening, editing, dialogs, saving and exit through the selected
source paths. Classify each dependency as already supported, requiring reusable
AES, VDI or runtime support, requiring an application adaptation, or deferred.
Include failure and cleanup paths in this inventory. Identify the save and
backup assumptions now, especially rename and close behavior, so they do not
become a late surprise.

This establishes the boundary for later design notes. Preserve QED's editing
core and resource identities where practical; adapt its platform assumptions
deliberately. New reusable services belong in the public interfaces, using
ordinary Exec primitives. Compiler defects belong in the owning toolchain.

### Prove native build and runtime feasibility

The [feasibility design](qed-native-feasibility-design.md) defines native
ownership and the runtime/layout/stack gates. Its
[implementation plan](qed-native-feasibility-implementation-plan.md) orders
QF1–QF6 from emitted ABI probes to the step 3 handoff.

Compile the selected source set against Exec's native C ABI and establish the
real image layout, runtime dependencies and upper-memory cost. Use those
results to decide whether the bounded application image profile needs to grow.
The donor executable size alone does not determine that decision.

Establish the minimum genuine runtime needed for startup: allocation, basic
file access and resource discovery, arguments, and normal return through the
Process lifecycle. Check the filesystem semantics needed by the eventual save
path with small native probes before adding the editor's full UI. This is a
bounded compatibility layer for the selected source paths; broader C runtime
coverage follows demonstrated needs.

If missing GEM features prevent QED startup, use a small executable to prove
the native runtime while retaining the complete QED build as the footprint
baseline. A probe passing does not count as QED running. Leave unsupported
calls explicit rather than making them return success to get past startup.

Resolve huge-pointer and donor near-data assumptions, allocator ownership and
an initial stack budget before committing to wider platform changes. Deepest
stack use must be revisited as dialogs, drawing and file operations become
executable. If the required stack cannot fit the current Process launch
contract, resolve that general constraint before building the rest of the UI;
do not depend on QED happening to receive a larger free Task pool.

The historical step 2 handoff used C APP ABI 24 and Process ABI 8. The complete source
image spans 279,860 bytes, with 345,396 bytes of alignment backing. QED declares
a 2,560-byte stack requirement through general image admission. Its conservative
source bound is 1,375 bytes; the separate 768-byte continuation cap must be
established by later full GUI measurements. The 128-byte headroom target and
existing interrupt reserve remain in force; no bank-zero reservations grew.

Step 3 keeps private code/data/container allowances of 32/16/16 KiB and resident
code/table/data allowances of 16/4/16 KiB. It must resolve the original resource's
682 objects and 32 trees, its 126-object menu, free strings and supported
object flags, plus the [explicit binding catalog](../../../ports/gem4xe/apps/qed/analysis-bindings.json).
The port already consolidates workstation ownership in CFLIB, with QED borrowing
it. Exceeding an allowance or stack cap requires a new fit decision.

### Start the real QED application

Completed by [QS1–QS5](qed-startup-implementation-plan.md). The current C APP
ABI is 25. The adapted resource has ten trees, 185 objects, 44 free strings and
a 30-object menu. Real QED startup uses one CFLIB workstation, native fixed-font
drawing and ordinary Process admission. Physical Close/Ctrl+Q and cooperative
Stop retire normally; acquisition failures and repeated launches restore owners.
See the [current baseline](../../development/qed-startup-qs5.json) for exact
artifacts, costs and development scope. The source stack bound remains
conditional for editing/dialog/file workflows not executed by this gate.

Address resources, menus and workstation ownership together. Larger resources
must be supported through loading, traversal, form storage and menu handling;
raising only the loader limit will not establish a usable application.
Decide which unsupported decorations to adapt and how the menu fits the
desktop, keeping all operations in the first scope reachable.

Settle the two-workstation assumption in QED and cflib before extending drawing.
Choose deliberate consolidation in the port or general support for independent
workstations, preserving attribute and lifetime semantics.

Advance when the actual QED startup loads its adapted resource, installs its
menu, opens an empty document window and exits cleanly. Test startup failures
and repeat launch and close at this point. Keep this executable as the base
for subsequent work.

### Make editing work

The [editing design](qed-editing-design.md) and
[QE1–QE7 implementation plan](qed-editing-implementation-plan.md) specify this
gate. They order keyboard editing, viewport/drawing, selection, clipboard/Undo,
native dialogs/Find, checked reading/replacement and reconciled evidence.
The step 4 implementation will disable Save/Save As and offer Discard/Cancel
for modified replacement/retirement until step 5. This interim restriction
preserves the final scope's Save/Discard/Cancel target without depending on
unchecked donor writes.

Extend drawing and events around the editor's required operations: readable
text, cursor and selection, navigation, scrolling, exposure and ordinary window
messages. Settle button predicates and press, release and drag behavior
explicitly. Decide how users reach long lines while horizontal window gadgets
remain outside the current contract.

Prefer the existing fixed font and correct redraw-based cursor or scrolling
adaptations where they meet the workflow. Measure the resulting interaction
before deciding whether raster copies, XOR or additional text attributes are
necessary. Add each general VDI capability with its real clipping and ownership
semantics.

Introduce document reading and the dialogs needed for open, find and close.
Adapt cflib's waits so those dialogs continue processing window messages and
allow other applications to run. The gate is a real editing session with undo,
selection and internal copy and paste, correct overlap and exposure, and an
honest modified-document state. Exercise writes only with disposable fixtures
until the saving gate passes.

### Make saving trustworthy

Build on the runtime semantics established earlier and adapt QED's complete
save and backup workflow. Determine what happens to the original, backup,
partially written output and modified in-memory document at each failure.
Respect the native filesystem's rename and finalization guarantees; do not
promise atomic replacement where it is unavailable.

Require correct saved bytes and error reporting through final close, including
short writes, full media, failed close and backup collisions. A failed save
must retain the editable document and make recovery clear. Cover Save As,
cancel and the unsaved-changes prompt as part of the same workflow. Establish
the selected behavior on RAM, MyDOS and SpartaDOS rather than treating a
successful RAM save as proof of disk behavior.

### Establish practical coexistence

Use complete open, edit, find, save and close sessions to measure responsiveness,
upper-memory use, fragmentation, stack headroom and resource return. Include
another GEM application and shell or MD5/ARC activity in configurations that
fit the [shared Task capacity](../../architecture/task-capacity.md).

Use the measurements to choose the next improvement. Optimize an observed
scrolling, redraw or dialog delay before adding unrelated VDI features.
Increase stacks, image limits or shared capacities only where the supported
workflow needs them and the complete platform budget permits them.

Responsiveness and cleanup start with the first executable; this step completes
their coverage under realistic load. Repeated launch and exit, allocation
failure, cancellation and cooperative close must leave the desktop usable.

### Deliver and close the agreed scope

Package QED, its resource and required configuration with the normal native
launch path and upstream notices. Use the standard OF816 demo builder for
demo refreshes, preserving the five-second shell/prime autoboot. Validate the
actual packaged files through the intended Files and shell launch paths.

Close each gap against implemented behavior and its development evidence.
Update current contracts when general interfaces change, and keep unsupported
features visible. Apply the [two-tier testing policy](../../contributing/testing.md):
focused emitted-code checks accompany implementation; full qualification is a
separate activity for a release or an explicit qualification request.

## Work to begin next

Start QE1 in the [editing implementation plan](qed-editing-implementation-plan.md#qe1-keyboard-editing-and-safe-retirement)
when implementation is requested. The proposed design/plan follows the completed
startup baseline; its preparation does not establish editing behavior. Commit
each executable slice after its development checks, recording actual memory,
stack and failure evidence. Prepare the saving design after the editing gate,
using the file-format and replacement guarantees established there.

This strategy adds **0 reserved bank-zero bytes**, fixed or per-Task, including
guards, alignment and unused capacity. Each implementation slice must account
for its own actual reservation changes under the
[platform budget](../../reference/platform.md#bank-zero-memory-budget).
