# QED editing implementation

[Editing design](../plans/gem4xe/qed-editing-design.md) ·
[QE1–QE7 plan](../plans/gem4xe/qed-editing-implementation-plan.md) ·
[Startup baseline](qed-startup.md)

Status: QE1–QE2 implemented; QE3 is an incomplete implementation checkpoint,
and QE4–QE7 remain. The
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

## QE3 Selection checkpoint — incomplete

The current patch replaces the nested pointer wait with outer-event selection,
release rearming and an outside-work autoscroll deadline. It adds byte-based
Shift selection and enables Select All. Until QE4, editing an active selection
reports that the operation is unavailable. General AES changes permit another
client's short UPDATE during work capture and add the optional
[`WF_EXEC_FOCUS` subscription](../reference/aes.md); explicit MCTRL and native
gesture exclusion remain in place.

Development checks pass for 529 host tests with four expected historical skips,
168 emitted AES pointer/focus checks, 181 emitted AES lock checks and two
optimized actual-source navigation lifetimes. The production APP builds and
its conditional source-frame ledger fits the existing admission. The retained
QED C profile now disables inlining to avoid the observed Calypsi 5.18 Ctrl-End
field-access defect. The focused raw and optimized actual-source navigation
comparisons now both pass.

The original loaded-editor checkpoint timed out after Shift-click while
dispatching Control-A (`build/qed-editing/qe3-final/results.json`). Physical
capture and native AES delivery were correct. The C handler entered with
`$1E01` and Control; its last native menu request completed successfully.
Calypsi 5.18 emitted a conditional byte increment in CF-Lib's shortcut parser
that left M=1 at a join followed by word-immediate instructions. The CPU then
ran outside the APP. Patch 0012 keeps the normalized character word-wide.
It changes the port's character intermediate, with no kernel/compiler pin
change or per-routine Exec special case.

The [focused development record](../development/qed-shortcuts.json) binds raw
and optimized actual-source parser checks: every Control-letter encoding and
its printable counterpart, modifier rejection and disabled commands, across
two fresh Processes per mode. The previous byte-intermediate source fails the
same isolated optimized probe. The loaded editor now passes Control-A,
collapse, peer painting, and geometry/focus/input-loss cancellation.
Autoscroll and complete four-lifetime retirement evidence remain pending;
QE3 is not complete and has no reconciled passing development record yet.

Reserved bank-zero delta is **0 fixed, 0 per-public-Task and 0 private idle
bytes**, including guards, alignment and unused capacity. Complete Task-pool
and region reservations match QS5. Shared-provider demo refresh remains QE7
work; QED remains outside distributed demos.
