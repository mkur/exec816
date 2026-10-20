# QED editing implementation

[Editing design](../plans/gem4xe/qed-editing-design.md) ·
[QE1–QE7 plan](../plans/gem4xe/qed-editing-implementation-plan.md) ·
[Startup baseline](qed-startup.md)

Status: QE1–QE4 implemented with development evidence; QE5–QE7 remain. The
[QE1 development record](../development/qed-editing-qe1.json) binds the ordinary
executable, source audit, actual-source core probe and loaded editor session.

## QE1 Keyboard editing and retirement

The native adapter interprets special cursor scans before donor Control-arrow
semantics: the Atari chord producing an arrow must still move one character
or line. Enabled menu shortcuts precede insertion; other Control letters do
not insert text. Return splits, Tab inserts a literal tab, Backspace/Delete
remove a byte or join lines, and Insert/Overwrite share one application state.
Escape clears selection rather than invoking deferred macro expansion.
New documents use LF, eight-column tabs and no automatic indentation or wrap.

Insertion, deletion, split and join prepare replacement donor-arena lines
before changing the live ring. Failed preparation leaves text and cursor
intact; an overlong line is rejected at 1,023 stored bytes. Required line Undo
state is captured before retiring the previous line. Split/join retain the
donor's interim Undo limitation, addressed by QE4.

Modified Close, Quit and cooperative Stop use the native Cancel-default
Discard/Cancel alert. Alert dismissal/interruption is not consent. Save/Save As
and their automatic dispatch paths are refused. New/Open, clipboard/Undo,
selection and donor MDIAL dialogs stay unavailable until their owning slices.
Document arguments report their interim limitation and leave an empty document.
The final Save/Discard/Cancel workflow remains strategy step 5.

| Native input | Current action |
| --- | --- |
| Printable unmodified byte, Tab, Return | Insert/overwrite, literal tab, split line. |
| Backspace, Delete scan `$53` | Backward/forward deletion, including boundary joins. |
| Cursor scans `$48/$50/$4B/$4D` | Up/down/left/right, including Control-bearing Atari chords. |
| Home/End scans `$47/$4F` | Line start/end; Control selects document start/end. |
| Page scans `$49/$51` | Page up/down. |
| Insert scan `$52`, Mode menu | Toggle or select Insert/Overwrite. |
| Escape/BREAK | Clear selection; native dialogs retain their own cancellation rules. |
| Enabled Control menu shortcuts | Perform their action before ordinary insertion. |

The table defines application interpretation. Executed physical and focused
source cases are recorded separately; an injected/logical scan does not prove
that the pinned keyboard can produce every listed combination.
The physical run uses Control-Minus for Up, Control-Asterisk for Right and
Control-Backspace for forward Delete. The pinned bridge has no Plus-key input
for Left; no physical Left/Home/End/Page/Insert claim is made by QE1.

The development fixture copies the unchanged serialized APP from SYS: to RAM:
through public DOS calls, then starts fresh normal loaded Processes. Its
control word coordinates the supervisor's Stop and ownership checks; it never
inserts document data. Read-only observations use target-emitted field offsets,
actual donor-ring bytes and independent native font/pixel comparisons. A
fixture-only line-allocation wrapper forwards successful calls unchanged and
can refuse one selected acquisition. Production has no test mode or controls.
A forwarding key-dispatch counter lets the observer await the real command's
return, including its redraw. It records native key/qualifier values without
changing document state. Native popup positions include the bar's 128-pixel
application origin and are recomposed from the source resource tree.

The separate emitted core probe links the actual text allocator, mutators and
line Undo code. Notification sinks record requested errors without claiming GUI
behavior. It covers the line ceiling and actual upper-heap refusal after donor
arena fragments have been exhausted. The loaded APP supplies real GUI evidence.

QE1 development checks pass: 529 host tests with four expected historical skips,
four optimized loaded-editor lifetimes (7,867 supervisor checks), and two
optimized actual-source core lifetimes. Checks cover logical text and independent
native pixels, line/heap refusal, Close/Quit/Stop Cancel/Discard, ordinary collection/unload,
exact warm heap reuse, native IRQ/NMI and guards are included. These are
development checks; hosted-system and release qualification remain separate.

Against QS5, the production APP has 21,046 fewer code bytes, 813 more initialized
plus BSS bytes and 1,448 fewer container-metadata bytes. It serializes to 132,731
bytes and requires 248,652 bytes of aligned image backing. The native provider
is unchanged. Observed private heap peak remains 53,351 bytes including its
allocation headers, before underlying allocator rounding; native GUI/resource
owners are separate. Incremental row drawing now uses UPDATE, with caption
updates preceding visible-rectangle enumeration and painting.

The source-frame bound is 1,064 bytes. With the conditional 768-byte continuation
allowance, 256-byte interrupt reserve and 128-byte headroom, the 2,560-byte
admission has 344 bytes of margin. The loaded editor's lowest ordinary/frame
sample retains 1,334 bytes above the interrupt reserve. Future drawing,
selection, dialogs and file chains must extend this evidence; a measured larger
stack is authorized when needed.

Measured reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle
bytes**, including guards, alignment and unused capacity. Complete Task-pool
and region maps equal QS5. No shared provider changed, so QE1 needs no demo
refresh. QED remains outside distributed demos and reliable saving is pending.


## QE2 Viewport and transparent text

The [QE2 development record](../development/qed-editing-qe2.json) binds the
production image, viewport sessions, small raw/optimized VDI boundary probes
and separate instrumented VDI pixel fixture. `MD_TRANS` writes glyph foreground
pixels while preserving the background. Replace remains the default;
unsupported modes retain the previous attribute, solid bars remain solid and
attributes remain local to each workstation. The machine-readable internal
VDI records are version 2; the unchanged APP import contract needs no ABI bump.
Matched provider/callers are rebuilt.

QED paints explicit row and selected-run backgrounds, draws bounded foreground
runs transparently and restores replace mode. Expanded columns and absolute
pixels use widened arithmetic. The fixed-font mouse mapping and desired-column
navigation use the same tab interpretation; shortened text and resized windows
clamp the origins. Full/Restore uses desktop bounds and a retained previous
rectangle, because native AES does not implement the donor FULL/PREV queries.
This adds eight upper-memory bytes per QED window. Tabs left of the viewport are skipped by spans, and a running
tab phase avoids a long division for each tab during every redraw.

The independent observer checks logical donor-ring bytes, viewport origins,
normal text and caret pixels. Physical keyboard input constructs a 513-tab line
whose final display column exceeds a signed WORD when multiplied by eight.
Separate short-line geometry checks exercise move, full/restore, resize,
vertical arrows/pages/thumb and cursor revelation. An independently loaded
ordinary GEM client covers and exposes the document; its pixels are also
checked. Each session retires through ordinary Process collection/unload and
checks exact warm heap reuse. These are development checks, not hosted-system
or release qualification.

QE2 development checks pass: 529 host tests with four expected historical skips;
two optimized loaded-editor sessions with four editor lifetimes each; two
lifetimes each for the raw/optimized C boundary probe; and 463 checks in the
separate two-workstation VDI pixel fixture. The long session repeats geometry
and scrolling with the 513-tab line and directly checks sixteen visible caret
pixels at each caret checkpoint. Supervisor check counters are native CARD
values and can wrap during long sessions; their final values are not cumulative
assertion counts. Native IRQ/NMI, context restoration, guards and normal
retirement remain part of each runner.

The source-frame bound remains 1,064 bytes, with the same 344-byte conditional
margin under the 2,560-byte admission. Passive selected-PC/S/D tracing covers
entire owned lifetimes. The collector immediately stops the unused aggregate
profiler: the pinned emulator retains CPU history sampling after aggregate
collection stops. Recorded traces still include later mutations, drawing,
caret and retirement samples.

Against QS5, the production image has 19,062 fewer code bytes and 974 more
initialized plus BSS bytes. It serializes to 134,847 bytes and requires 250,640
bytes of heap backing after bank-alignment capacity and eight-byte rounding. The production provider adds 221 code bytes, with
no table or static-data growth. Each workstation grows from 378 to 382 logical
upper-memory bytes; both round to 384 bytes in the allocator. The observed
private heap peak is 53,359 bytes including private allocation headers, eight
bytes above QE1 for the retained full/restore rectangle; underlying rounding
and native GUI/resource owners are charged separately. Shared-provider
demo refresh and exact-package smoke checks remain QE7 work.

Measured reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle
bytes**, including guards, alignment and unused capacity. Complete Task-pool
and region reservations equal QS5. No stack increase was required by QE2.
Selection commands remain disabled until QE3.

## QE3 Event-driven selection

The [QE3 development record](../development/qed-editing-qe3.json) reconciles
four loaded-editor lifetimes, focused raw/optimized actual-source navigation
and shortcut probes, and separate emitted AES pointer/focus and lock fixtures.
The recorded images and traces match the current source/ABI inputs. This closes
the selection slice; clipboard/Undo, dialogs/Find and checked document
replacement remain QE4–QE6. Editing an active selection still reports that the
operation is unavailable until QE4 establishes coherent replacement/Undo.

The outer event dispatcher now owns pointer selection, release rearming and
outside-work autoscroll. Stable byte anchors produce normalized half-open
ranges across tabs, blank lines and newline cells. Release coordinates are
accepted before a gesture ends. Shift-click, logical Shift-navigation and
Select All share the range representation; plain navigation collapses a range.
Escape, geometry/focus changes, native input loss, Close and cooperative Stop
cancel the gesture and require release before another press can start it.
Donor word/brace/column selection and block drag/drop remain disabled.

The physical keyboard's Control-bearing arrow chords do not expose every
logical Shift-navigation combination. The loaded session verifies Shift-click
and records that physical Shift-Right is unavailable on the pinned mapping;
raw/optimized actual-source probes cover the logical navigation operations.
The [shortcut record](../development/qed-shortcuts.json) separately covers all
Control-letter encodings, their printable counterparts, modifier rejection and
disabled commands. No claim is made that every logical scan is physically
reachable.

Inside work, a held stationary pointer sleeps with key/button/pointer interest,
no active timer and no UPDATE or MCTRL ownership. An independently loaded GEM
client completes another paint during that wait. General AES lock policy now
allows a short UPDATE during another client's work capture while preserving
the captured input recipient, explicit MCTRL exclusion and native frame-gesture
exclusion. Optional [`WF_EXEC_FOCUS`](../reference/aes.md) notifications let QED
cancel on a focus transition through the ordinary event queue.

Outside work, QED requests a nonzero 100 ms deadline and advances at most one
row/column per axis per step. The observer first waits for QED to consume the
outside position, then requires progress within 250 PAL frames and checks the
rate bound. This accommodates an already running selection repaint; it does
not establish a 100 ms end-to-end response time. All four directions pass,
including tab-expanded horizontal endpoints. A selected clock failure retains
the document, exits the gesture and permits subsequent selection.

The ordinary loaded session checks forward/backward ranges, selected tab spaces
and newline cells, fast press/release, held-button rearming, focus/geometry and
input-loss cancellation, exposure repair and sixteen independently checked
caret pixels. Close/Stop Cancel and subsequent Discard retire through normal
Process collection/unload. Four editor lifetimes return exact warm heap
availability. Native IRQ/NMI, context restoration and guards pass. The final
supervisor CARD value is 22,047; it can wrap and is not a cumulative assertion
count. Separate AES fixtures pass 168 pointer/focus checks (including 21 boundary
checks) and 181 lock checks. Host checks pass 536 tests with four expected
historical skips, and the affected AES/QED generators match their inputs.
These are development checks, not hosted-system or release qualification.

Two Calypsi 5.18 issues were resolved before the final loaded run. The inlined
Ctrl-End path accessed the wrong TEXT field, so the retained QED profile keeps
`-O2` and disables C inlining uniformly. CF-Lib's conditional byte increment
left the generated CPU width inconsistent at a join; patch 0012 keeps the
normalized shortcut character word-wide. The original source fails the isolated
optimized shortcut probe, while corrected raw and optimized probes pass. These
are port/Calypsi profile restrictions; the actionc compiler pin is unchanged.

Passive stack observation now includes emitted native AES frame reservations
and distinguishes Process.Run entry from its after-TCS reservation. Counting
both as new lifetimes previously excluded later application samples. The
loaded editor retains **1,382 bytes above the 256-byte interrupt reserve** in
its existing 2,560-byte pool at the lowest ordinary/frame sample. Corrected
shortcut-trace interpretation retains 705/713 bytes in the separate optimized/raw
probes. Their original result files and frozen shortcut record remain unchanged;
explicit stack-only derivatives bind the original result and trace hashes and
the current observer. They are reanalysis of those executions, not new runs.

The source-frame bound is 893 bytes. With the conditional 768-byte continuation
allowance, 256-byte interrupt reserve and 128-byte required headroom, admission
has 515 bytes of margin. Future clipboard, dialog and file paths must extend
this evidence. No stack increase is required for the executed QE3 workflows.

Against QS5, the production APP has 14,073 fewer code bytes, 1,112 more
initialized plus BSS bytes and 576 fewer container-metadata bytes. It serializes
to 140,686 bytes, spans 190,089 bytes and requires 255,624 bytes of aligned heap
backing including eight-byte allocator rounding. The C provider remains 221
code bytes above QS5, with no table/static-data growth; 15,183 code bytes remain
within its frozen allowance. Observed private heap peak remains 53,359 bytes
including private headers; underlying rounding and native GUI/resource owners
are charged separately.

Reserved bank-zero delta is **0 fixed, 0 per-public-Task and 0 private idle
bytes**, including guards, alignment and unused capacity. Complete Task-pool
and region reservations match QS5. Shared-provider demo refresh remains QE7
work; QED remains outside distributed demos. The separate
[upstream reference setup](../guides/gem4xe-qed-reference.md) supports donor
behavior comparisons without changing the Exec port's implementation status.

## QE4 Internal clipboard and grouped Undo

The [QE4 development record](../development/qed-editing-qe4.json) closes the
clipboard/Undo slice. Menu and Control shortcuts now enable selection-based
Copy/Cut, internal Paste and one operation-group Undo. Copy without a selection
is unavailable; donor current-line Copy and Shift-append clipboard behavior
are outside this scope. The clipboard remains private to the application.

The donor's Cut copied after deleting, and its block helpers could fail after
partially changing the live ring. Patch 0013 repairs these owning routines:
Copy prepares its entire candidate before replacing the clipboard; Cut also
prepares the document replacement before publishing either owner. Paste,
selection replacement, ordinary typing, split and join prepare detached donor
LINE chains. Boundary lengths/counts are checked before allocation or mutation.
Successful commit exchanges only the affected whole-line span. The displaced
span becomes the single private Undo group; the complete document is never
snapshotted. Failed preparation retains text, cursor/range, clipboard and Undo.

Undo exchanges those chains without allocating and swaps saved cursor/range
metadata. Repeated Undo toggles the group. Adjacent ordinary edits on one line
retain the original group; split/join, block operations and edits after Undo
start a new group. Dirty state stays conservative, including Undo back to an
empty document. There is no separate Redo API, multi-level history, external
clipboard or reliable Save claim. Destination line-ending convention is
preserved when pasting, including a clipboard ending in an empty logical line.

Four optimized loaded-editor lifetimes pass independent text/range, clipboard
byte, normal/selected and caret pixel checks. They exercise menu and shortcut
operations, tabs/blank lines, newline-only selections, Cut to empty, Paste from
empty, grouped typing, Undo toggling, edit-after-Undo, selection replacement,
clipboard/Cut allocation rollback, Stop Cancel and ordinary retirement. Heap
availability returns exactly after warm reuse. The final supervisor CARD value
is 12,996, rather than a cumulative assertion count. The menu observer now
leaves a title vertically before traversing the popup row, preventing diagonal
ST motion from entering the next heading; a forwarding counter confirms the
actual selected command has returned before the next menu operation.

Two optimized actual-source transaction lifetimes cover line/clipboard
allocation failures, overlong Paste/join refusal, retained prior Undo, and
allocation-free Undo with the refusal hook armed. An 80 × 1,023-byte document
exercises multi-bank Copy/Cut/Paste/Undo and destination CRLF convention. Its
measured private heap peak is 262,136 bytes, including allocation headers and
reserved donor-arena capacity. This isolated fixture uses notification/geometry
sinks and claims no GUI behavior. Two further actual-source lifetimes retain
the prior line-limit and genuine upper-heap exhaustion regression.

Development checks pass: 536 host tests with four expected historical skips,
affected generator checks and reconciled emitted images/traces. Native IRQ/NMI,
DP/context restoration, stack/domain guards, collection and unload pass. The
loaded editor's lowest ordinary/frame sample retains 1,316 bytes above its
256-byte interrupt reserve; the two focused fixtures retain 577 and 601 bytes
in their smaller pools. The production source bound remains 893 bytes, leaving
515 bytes of conditional margin under the existing 2,560-byte admission. No
stack increase is required for these workflows; dialogs and reading must extend
this evidence in QE5–QE6.

The production APP serializes to 135,554 bytes and spans 185,730 bytes; aligned
heap backing with eight-byte rounding is 251,272 bytes. Code is 120,194 bytes,
with 1,464 initialized and 25,549 BSS bytes. The loaded GUI session's private
heap peak remains 53,359 bytes; its small document stays within the initial
donor arena. APP backing, native GUI/resource owners and the larger isolated
transaction workload are charged separately. The shared C provider is unchanged
from QE3.

Reserved bank-zero delta: **0 fixed, 0 per-public-Task and 0 private idle bytes**,
including guards, alignment and unused capacity. Task-pool and region maps
match QS5. Shared-provider demo refresh stays with QE7. These are development
checks; hosted-system and release qualification remain separate. QE5 native
dialogs/Find is next, followed by QE6 checked reading/replacement and QE7's
combined session and package handoff.
