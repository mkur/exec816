# QED editing and document replacement design

[GEM plans](README.md) · [Strategy](qed-port-strategy.md) ·
[Initial scope](qed-scope-and-dependencies.md) ·
[Implementation plan](qed-editing-implementation-plan.md) ·
[Startup evidence](../../history/qed-startup.md)

Status: strategy step 4 is implemented through QE1–QE7 with
[development evidence](../../history/qed-editing.md#qe7-editing-gate-and-saving-handoff).
The gate is
an actual loaded QED APP opening one document, editing and navigating its text,
selecting, copying/pasting, undoing and finding, with correct redraw and
cancellable dialogs. New/Open must retain the current document on failure or
cancellation. Reliable writing remains step 5; realistic workload coexistence
and distribution remain steps 6–7.

## Starting point and ownership

Use the [reconciled startup baseline](../../development/qed-startup-qs5.json),
the existing pinned QED/cflib inputs and ordinary Process loading. Preserve the
actual QED text store, editor actions and window callbacks. CFLIB continues to
own one workstation, borrowed by QED. One Process owns one document window,
an internal clipboard and the donor Undo state. A replacement candidate has
private storage, without another registered document or window.

The startup checks establish empty-document drawing and retirement. They do
not establish the following retained source paths:

| Source under the prepared QED/cflib work copy | Gap addressed here |
| --- | --- |
| QED `event.c`, `tasten.c`; cflib `nkccinit.c` | Native scan/character/modifier interpretation, shortcut precedence, repeated button levels and loss handling. |
| QED `ausgabe.c`, `edit.c`, `window.c` | Selection-aware drawing, cursor repair, horizontal viewport movement, geometry and exposure. The startup row renderer does not draw selection. |
| QED `edit.c:wi_click` | A synchronous drag loop requests unsupported `MU_M2`, holds MCTRL and omits ordinary window-message handling. |
| QED `block.c`, `clipbrd.c`, `memory.c` | Real selection, internal clipboard, grouped Undo and allocation failures through the application. |
| QED `find.c`, `global.c`, `menu.c`; cflib `mdsimple.c`, `mddo.c`, `mdopen.c` | Selected dialogs still use donor assumptions. Negative dialog results can be masked into positive object indices; donor button handling does not implement native release semantics. |
| QED `file.c`, `edit.c`, `menu.c`, `main.c`; native `gem-helpers.c` | Open/New can retire the old document or create another window. The loader converts unsupported bytes, ignores negative reads/final Close and has incomplete allocation cleanup. The selector adapter uses donor path bounds rather than native buffer capacities. |

Implement adaptations as ordered patches and native application helpers under
[the port](../../../ports/gem4xe/apps/qed/README.md). Generate resource changes
and matching identifiers together; leave verified upstream caches unchanged.
Use public Exec/GEM operations. A reusable drawing capability belongs in VDI;
editor policy belongs in QED. No QED-specific kernel service, extra Task or
private presenter access is selected. Compiler defects remain with actionc.

## Editing commands and document state

Resolve keys once at the application input boundary. Dispatch an enabled menu
shortcut before text insertion. An unhandled Control chord must not insert its
letter. Use the native translated scan/ASCII word and qualifiers; do not query
TOS keyboard tables or invent Alt support. Native cursor-producing chords can
carry Control: classify their special scan before applying donor Control-arrow
word/page behavior, so physical arrows still move one character or line.

| Input/action | Selected behavior |
| --- | --- |
| Ordinary printable byte | Insert, or replace one byte in Overwrite mode; overwrite at line end appends. |
| Return / Tab | Split the line / insert a literal tab. Use fixed initial defaults, without automatic indentation or reformatting. |
| Backspace / Delete | Remove the preceding/following byte; join adjacent lines at their boundary when the result fits. |
| Arrows | Move by character/line, preserving the desired display column during vertical navigation. |
| Home/End, Page Up/Down | Line start/end and viewport-page navigation where native translated keys exist. Document start/end use explicit normalized commands; record their actual reachable native bindings. |
| Shift-navigation / Shift-click | Extend a contiguous selection from a stable anchor. Plain navigation collapses an existing selection toward the direction of movement. |
| Insert or Mode menu | Select Insert/Overwrite, with the same state and caret shape. |
| Escape/BREAK | Cancel a current gesture/dialog; in the ordinary editor clear selection. Do not enter deferred macro expansion. |

Publish the resulting key table with the implementation and test it against
the pinned physical keyboard. The native matrix cannot produce every logical
modifier combination; do not claim physical coverage from injected GEM words.
Mouse selection and Select All provide selection independently of those chords.
Alt, column selection, brace selection, block drag/drop and macro entry remain
deferred. Double-click may use the same ordinary placement/selection behavior;
word/line double-click extensions are outside this gate.

Keep stored byte offsets distinct from tab-expanded display columns. Tabs use
eight-column stops. Soft wrap, whitespace trimming, encoding conversion and
format-on-load/paste are off. Keep the donor's 1,023-byte logical-line ceiling;
reject insertion, join or paste that would exceed it without splitting or
truncating the operation. Compute expanded columns, pixel differences and
serialized byte/line counts with checked widened arithmetic before narrowing.
Total counts must fit positive signed LONG values; memory exhaustion can occur
earlier and is an ordinary reported failure. Record practical tested document
sizes and backing cost rather than implying that every representable size fits.

Only successful text mutations mark the document modified. Navigation, copying,
Find, failed commands and cancelled dialogs do not. Keep a conservative dirty
state after Undo unless equality with the loaded/new baseline is established;
never clear it merely because the Undo buffer is empty. The title and command
availability must follow the same committed state. Read-only file metadata does
not prevent editing a private copy; later Save/Save As decides write access.

Stage required line/clipboard/Undo backing before destructive list changes.
On failure retain a coherent document and its cursor/selection; reject a change
whose required Undo backing cannot be acquired. Check complete affected line
lengths before multi-line operations. This is application-owned allocation
policy, not repeated validation of live public pointers.

## Viewport, drawing and selection appearance

Keep the built-in 8×8 font and redraw from the actual text store. One row painter
must handle normal text, selection, tabs, blank rows and the steady caret, so
incremental repairs and a complete exposure produce the same pixels. Expand
only the visible cells into bounded private upper-memory scratch. Convert
top-based coordinates to the native baseline explicitly.

Retain vertical native gadgets and `doc.x` as a horizontal display-column
origin. Cursor movement and Find pan horizontally to expose the target, with
Home returning to the line start. Dragging beyond a side can pan too. No
horizontal native gadget or soft wrapping is required. Compute
`(display_column - viewport_origin) * 8` in a widened type before clipping;
an absolute tab-expanded pixel position can overflow a signed WORD even within
the stored-line limit. Clamp viewport origins after edits and resize. Use
accepted native geometry and fresh visible rectangles after move/size/full.

Paint selected text with distinct foreground/background pens, including spaces
expanded from a selected tab. Use normalized half-open byte ranges; a selected
line break receives one visible end-of-line cell where it lies in the viewport,
not the entire unused row. A blank line can therefore show a selected newline.
Paint the caret last, erase its old position through the same row painter and
preserve it correctly after blink, focus, scrolling and exposure.

The current VDI text operation uses replace mode, which can overwrite a prior
selection fill. Add the standard `MD_TRANS=2` mode through public `vswr_mode`
and VDI parameter-block dispatch. In this mode glyph foreground pixels are
written and background pixels are preserved. Solid `v_bar` has the same result
in modes 1 and 2 because its pattern is fully set. Default/new workstations
retain replace mode; mode is private to each workstation. Unsupported XOR and
reverse modes continue to fail without changing attributes.

QED fills row/selection backgrounds, draws foreground runs transparently, then
restores replace mode before returning to other application drawing. Keep
clipping, damage reporting, bounded physical drawing units, preemption and
display-grant ownership intact. Extend the machine-readable VDI record inputs
and regenerate shared definitions where the new mode travels to the renderer.
Rebuild affected component/provider callers together. This is a general VDI
capability, with independent pixel and ownership tests, not an editor-only hook.

## Pointer gesture protocol

Replace the nested `wi_click` wait with application gesture state serviced by
the main event dispatcher. Existing native capture retains the work-area
recipient through release; selection needs no long-lived UPDATE or explicit
MCTRL ownership.

QE3 inspection found that `AESMOUSE.LockReady` currently excludes both lock
classes while another client owns that work capture. Amend general AES
admission so UPDATE may paint during another application's work-area capture;
MCTRL continues to require capture compatibility. Keep update ownership,
explicit mouse holds, native frame gestures, pending window mutations and
queue ordering in the existing shared policy. UPDATE's short implicit mouse
hold must not replace the captured input recipient. Exercise held-pointer
peer painting, recipient/release retention and the existing lock regressions.
This change uses the current public operation and adds no driver-specific
service or bank-zero reservation. Drawing takes short UPDATE sections only.

QE3 also requires a reusable focus-notification subscription because the
initial native AES profile publishes top-window identity but sends no GEM
focus notices. `WF_EXEC_FOCUS` opts one window into `WM_ONTOP`/`WM_UNTOPPED`
through the existing bounded GUI delivery. Pending changes coalesce to the
latest focus level; QED cancels a gesture on either notice, including a rapid
loss and regain. Keep the default unsubscribed for existing clients. This
adds no kernel operation, polling timer or bank-zero reservation.

| State | Wait/transition |
| --- | --- |
| Ready | Wait for left down. Place the cursor, establish/extend the anchor, then switch the button predicate to release. |
| Selecting | Wait for release, `MU_M1` outside the last 1×1 pointer rectangle, keyboard and messages. Update the endpoint from eligible coordinates and redraw affected rows. |
| Selecting outside work | Also request a nonzero timer for bounded autoscroll. Request 100 ms between steps, subject to native VBI rounding; advance at most one row/column per axis per step. Preserve the next deadline across motion wakes instead of a zero-timer loop. |
| Release | Apply its retained coordinates before finishing, including when motion and release arrive together. Return to down interest. |
| Loss/cancellation | Stop selection at its last accepted endpoint, release transient state and require a released level before rearming. Fatal wait failures leave the interaction through reported cleanup, without retrying an unsupported mask forever. |

`MU_M2` is removed from the live source path. A held down level cannot restart
the gesture. Handle redraw, geometry, focus and close/Stop during selection;
geometry changes recalculate bounds, while close/commands end the gesture
before dispatching policy. Deliver each selected event bit once, including
combined message/key/button results. No source event is replaced by repeated
`graf_mkstate` polling, and unrelated events remain available to their owner.

## Clipboard and Undo

Use the donor's private rings and bounded operation-group Undo representation.
Provide Cut, Copy, Paste, Select All and Undo through both enabled menu actions
and their native shortcuts. Copy/Cut require a nonempty selection; remove the
implicit Copy-current-line fallback from this initial scope. Paste replaces
the selection or inserts at the cursor, preserving logical line boundaries and
tabs while using the destination document's line-ending convention.

Acquire a complete replacement clipboard before retiring the old one. Cut
deletes text only after copying and required Undo preparation succeed. Paste
and Undo must not publish partial list surgery on backing failure. Preserve
the donor's single completed operation-group semantics, including its group
toggle behavior where applicable; five internal operation tags are not five
independent Undo levels. Document the emitted behavior, with no new Redo API.
Reset Undo and selection on successful document replacement; retain the internal
clipboard across New/Open. Retire all three owners on exit.

QE4 audit amendment: the donor Cut deletes before its clipboard copy and the
block insertion/deletion helpers perform fallible reallocations after list
surgery. Prepare a complete replacement chain for the affected **whole lines**
using the donor LINE allocator, then exchange it with the live span in one
non-failing ownership transfer. Keep the displaced span in the donor private
Undo ring. Undo exchanges that span back without allocating and swaps the
saved cursor/range metadata, preserving the single-group toggle semantics.
Adjacent ordinary edits on the same line retain the original group; a block
operation, split/join, or edit after Undo starts a new group. This replaces the
unsafe operation-tag replay inside the existing block/clipboard owners; it
adds neither a second text store nor whole-document snapshots. Peak backing is
the old Undo span, prepared new affected lines and any prepared clipboard until
commit; measure those owners separately. Failed preparation retains all prior
editing state. Reserved bank-zero change remains zero.

## Dialogs, Find and command interruption

QE5 audit amendment: native `form_do` previously used Escape only to disarm a
held press. Add general idle-Escape dismissal as -1 / AES_OK for borrowed and
temporary forms; held-press cancellation/release rearming stays unchanged.
This reuses the existing public operation and negative-result contract, with
no wire/layout or bank-zero reservation change. Rebuild matched providers and
exercise the reusable form behavior alongside QED's Cancel/Escape paths.

Use native `form_do`, `form_alert` and `fsel_exinput` for the selected workflows,
retiring the donor MDIAL loop from their live call graph. Forms borrow the
document window/workstation. Fit and recenter retained resource trees within
accepted work geometry, or report a capacity error without changing the
document. Do not acquire UPDATE/MCTRL across an interactive wait or DOS call.
The native dialog loops already provide release-based controls and scheduling
of other clients; QED owns application-message policy after interruption.

Represent accepted, cancelled, interrupted and failed results separately in
private application helpers. Check signed form results before masking flags
or indexing an object. Alert zero is never permission to discard. Respect the
selector's path[128] and filename[13] capacities even though donor PATH is 256;
reject overlong joined paths instead of truncating them. Preserve Exec volume
prefixes, relative paths and inherited current directory.

On `AES_PENDING`, retire the dialog session before returning to the outer
dispatcher. Consume its exact deferred message once through the normal AES
wait; do not repost it or run Close/New/Open recursively from the dialog stack.
Keep at most one active command and its draft in private upper storage. Geometry
interruption can resume the same draft after policy/redraw; replacement, Close,
Quit or Stop cancels the draft before entering its own decision. Admission,
cleanup or display failures must not be reported as an accepted button.

Adapt the retained REPLACE resource to an honest Find form: a 50-byte literal
field, Find and Cancel. Hide/disable replacement fields/actions and history,
wildcard, case, direction, whole-word and wrap controls that the selected
implementation does not honor. Preserve retained local IDs and writable TED
capacity. Find is byte-exact, case-sensitive and forward, starting at the
cursor; Find Next starts beyond the current match, without automatic wrap.
An empty pattern does not replace the accepted pattern; Find Next is disabled
until a nonempty pattern is accepted. Cancellation preserves that pattern.
A found range becomes visible/selected without modifying text. Not
found reports that outcome and preserves cursor/selection. Search proceeds in
bounded chunks with message/cancellation opportunities between chunks, without
retaining invalid line pointers across a replacement command.

## Reading and single-document replacement

QE6 audit amendment: the native reader owns one detached donor ring, a 4 KiB
heap read buffer and a 1,024-byte heap line buffer. Each read step consumes at
most one buffer, then returns to normal event handling. The controller prepares
Open/New from that outer loop, rather than running DOS on a menu callback stack.
Selector policy interruption cancels that Open draft: the native selector only
publishes edited strings on acceptance, so its unaccepted field contents cannot
be resumed through the existing public interface. Find retains its resumable
draft. Compatible window geometry/focus-gain messages retain an active read;
other policy or document input cancels it before acting on the old document.

The imported window-title formatter also assumed a short GEMDOS filename and
could overflow its 128-byte backing for native paths. Bound that owning
formatter to the native 65-byte title contract; retain the exact path in TEXT's
256-byte filename. Explicitly refresh
the title even when replacing a clean document with another clean document.
No file dates/protection are synthesized: the initial read baseline keeps date
unknown and permits editing a private copy; Save must obtain its own write
metadata in step 5. Invalid launch arguments reach the editor as argc=0 so it
can report them beside an empty, editable document. Allocation failure still
fails startup. This private runtime convention changes no public Process ABI.
Startup argument/error notices also run from the outer controller. A notice
interrupted by compatible policy retains its cause and resumes after the exact
deferred message; Close/Stop cancels it. Initial window notifications must not
silently consume the diagnostic.

All launch-path, Open and New requests use one document controller. Accept zero
or one native document argument; report extra/invalid arguments. Launch without
a path creates an LF document. A failed launch-path load reports the error and
leaves an empty editable document; it must not silently create a file at the
failed path. Menu Open selects one file; remove the donor multi-file callback
and automatic binary-extension path from this workflow.

Read into a detached candidate using the existing native descriptor ownership.
Keep unavailable dates/attributes explicit; do not synthesize calendar metadata
from the native timer clock.
Continue after short positive reads, distinguish EOF from a negative read, and
check terminal Close. Validate uniform LF or CRLF across read boundaries.
Reject NUL, CR-only, mixed endings and overlong lines before publishing any
conversion; do not replace NUL with a space or split an overlong logical line.
Other non-NUL/non-newline bytes retain their byte values and fixed-font glyphs;
this is byte-oriented text, without Unicode decoding. Preserve an absent final
newline using the donor's logical-line/trailing-empty-line representation.
Empty files contain one empty logical line. New and newline-free files use LF
as the convention for newly inserted breaks.

| Phase | Ownership and failure result |
| --- | --- |
| Choose/prepare | Keep the current document and its Undo/selection/viewport intact. Create a complete candidate, including bounded name and metadata. Selector Cancel, read/format/Close/allocation failure frees only candidate state. |
| Modified decision | After candidate preparation, ask whether to discard the current changes. Cancellation frees the candidate and preserves the complete current editing state. |
| Commit | Transfer the candidate ring and metadata into the existing document/window, repair sentinel links, reset cursor/viewport/selection/Undo and mark the new baseline clean. All fallible preparation precedes this transfer. Keep borrowed title/info storage live. |
| Retire | Free the old ring after transfer and repaint/update title and menu. A presentation error must retain the committed document for repair, not roll back through freed storage or mark a failed load successful. |

Use the same preparation/commit sequence for New with a fresh empty ring.
Peak memory includes both documents; insufficient space retains the old one.
Do not introduce a destructive low-memory replacement fallback. Process
events/cancellation between bounded read/search steps, releasing each DOS call
before dispatch. A pending destructive action cancels and frees the candidate
before the outer dispatcher handles it. No directory lock, descriptor or
candidate pointer escapes its owner on cancellation.

## Modified Close and the step 5 boundary

Throughout step 4, disable Save/Save As menu shortcuts and remove automatic
save paths from live replacement/retirement decisions. The development editor
offers **Discard / Cancel**, with Cancel as the default, for modified New/Open,
Close, Quit and cooperative Stop. Dismissal, interrupted alerts and errors
preserve the document. A cancelled Stop is a declined cooperative request;
the Process remains live and must not be collected as though it exited.

This is an explicit interim restriction, not completion of the final scope's
Save/Discard/Cancel workflow. Step 5 implements that workflow and enables the
write actions only after checked save/backup/finalization behavior exists.
Step 4 must not use the donor's unchecked save result to authorize destruction.
Read-only fixture sessions and private text observations establish this gate;
successful persisted output is not its oracle.

## Memory, stack and evidence

QE3's actual-source navigation probe exposed a Calypsi 5.18 C inlining defect:
the inlined Ctrl-End path loaded the cursor row at TEXT offset 66 where the
source reads the line count at offset 44, producing row -1 in a three-line
document. The outlined optimized function emits the correct field access.
Disable C inlining uniformly in the retained QED compilation profile, keeping
`-O2`, rather than changing an individual navigation routine to accommodate
the compiler. Exercise the actual routines with this profile and with raw C,
then remeasure the complete APP's frames, size and loaded behavior. This is a
Calypsi profile restriction; it does not change the pinned actionc compiler.

Use QED's declared 2,560-byte pool as the starting point, retaining the 256-byte
interrupt reserve and 128-byte headroom requirement. The user confirmed on
2026-10-20 that a larger stack is acceptable when needed and bank-zero space
permits it. Size any increase from emitted frames and complete workflow
measurements, update ordinary image admission and the shared pool budget, and
report the complete reservation change including guards, alignment and unused
capacity. The startup source bound and 768-byte continuation
allowance are conditional for the newly reached paths. Reconcile direct and
indirect source frames and observe full emitted chains for editing, selection,
clipboard/Undo, native forms/selector/alerts, reading and cancellation. Attribute
samples to the actual Process lifetime, physical pool and DP, including emitted
frame-reservation sites. A watermark or entry-only observation is insufficient.
QE7 attribution amendment: the trace may include sites from all legal APP
relocation candidates so capture can begin before loading. Classify those sites
using each captured owner's actual image base. Multi-bank APPs can otherwise
assign a different candidate's function name to the same PC. Exclude candidate-only
sites, retain native/provider sites, and keep historical summaries unchanged
under their recorded interpretation. New records identify this scoped analysis.
An exceeded cap requires a measured fit decision before advancing. A justified
stack increase is permitted; keep admission explicit rather than depending on
which larger pool happens to be free.

Retain the step 2 private/provider growth allowances against their frozen
baseline; use QS5 as the immediate change comparison. Charge new state,
candidate/clipboard/Undo peaks, dialog allocations, allocator backing/rounding,
image alignment and metadata separately. This design targets **0 fixed,
0 per-public-Task, 0 private-idle reserved bank-zero bytes**, including guards,
alignment and unused capacity. Every slice reports actual deltas, including
zero, and complete upper-memory costs.

Follow the [development tier](../../contributing/testing.md). Focused optimized
checks use the loaded ordinary APP, real resource and actual public drawing,
events and DOS operations. Require independent text-store/byte observations
and native pixels, including exposure with another ordinary GEM client.
Fixture-only allocation/read/Close failures forward successful real operations;
no production test entry or successful fake binding is introduced. Preserve
guard, context, asynchronous IRQ/NMI and bounded-completion assertions. Add
small raw/optimized probes for changed VDI record/calling boundaries only.

The final editing session must cover a long tabbed document, mutations at line
boundaries, selection in both directions, clipboard and Undo, Find/Next/cancel,
Open/New cancellation and rollback, modified Close/Stop decisions, reuse and
resource return. Record exact input identities and the executed size/failure
scope. No hosted-system, reliable-save or broad latency qualification follows
from those development results.

When affected provider changes require demo refreshes, use build_demo.py with
OF816, pinned ROM/notices and five-second shell/prime autoboot, and smoke the
exact ZIPs. Keep QED and private editing fixtures out of distribution until
step 7. This design/plan work itself changes no executable or reservation.
