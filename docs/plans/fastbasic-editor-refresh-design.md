# FastBasic editor incremental repaint design

Status: implemented, 24 October 2026. See the
[ER0–ER4 plan](fastbasic-editor-refresh-implementation-plan.md) and
[development record](../history/fastbasic-editor-refresh.md).

[Plan index](README.md) ·
[Workbench design](fastbasic-workbench-design.md) ·
[Current workbench contract](../reference/fastbasic-workbench.md) ·
[AES repaint completion](../reference/aes.md#optional-repaint-completion) ·
[VDI drawing contract](../reference/gem-vdi.md#resident-application-workstations)

Make editing in `C:BASIC.APP` update the cells whose appearance changes. Keep
the caret and status strip independent of source repainting, and overwrite
changed glyphs without first clearing their entire rows. Adopt the console's
retained cell model, row damage spans and bounded presentation work through
the editor's existing GEM AES/VDI interface.

This change belongs to the native editor. FastBasic language semantics,
persistent interpreter sessions, Check/Build, document storage, undo and file
transactions retain their current contracts. Source debugging and BASIC
graphics remain separate work.

## Baseline redraw costs

Before ER0, [BasicEditorDamage](../../examples/gem-basic/editor.c) retained one
range of whole rows. Ordinary character edits marked their row, and caret
movement marked the old and new rows. Selection and several status helpers
marked the viewport. Combining distant changes also repainted rows between them.

[BasicEditorPaint](../../examples/gem-basic/editor-paint.c) cleared the damaged
rectangle, emitted every column of each affected row and restored selection and
caret marks. Its final slice cleared and redrew the bottom status strip,
including padded spaces and unchanged status text on repeated keystrokes.
The separate clear exposed an incomplete row before its glyphs returned.

Every damage request also set `publish`. The event loop published an empty
UPDATE before drawing. Under the
[window preservation contract](../reference/aes.md#opt-in-window-preservation),
this invalidates the saved client image and leaves a full client repair
obligation. That operation is necessary for changes deferred across a wait,
but an ordinary edit completed immediately can publish and draw together.

The [console core](../../lib/console/consolecore.act) already accumulates
column intervals independently for each row and acknowledges completed work.
Its [presenter](../../lib/console/consoledisplay.act) limits each quantum and
avoids stores for a settled caret. Reuse these mechanisms in application-owned
C state; keep the console's private records and worker ownership intact.

## Expected editing behavior

| Action | Required drawing |
| --- | --- |
| Append a character with unchanged syntax colouring | The changed character and cells affected by the old/new caret; the unsaved marker only when it changes. |
| Move the caret without changing the viewport or selection | Repair the old caret cell and draw the new caret. |
| Insert or delete within a line | Changed cells in the shifted suffix, including spaces that erase an old tail. |
| Complete a keyword or change a quote/comment delimiter | Every cell whose glyph or colour changes, including cells before the insertion point. |
| Extend or clear a selection | Cells whose selection mark or caret changes. |
| Change a status message | Changed status cells, with spaces replacing a shortened message's old tail. |
| Receive exposure damage | Reconstruct the exposed pixels even when cached text is identical. |
| Scroll, resize, fold or replace a document | Recompose the affected viewport and repair its geometry in bounded turns. |
| Remain idle with settled pixels | No drawing or repaint timer. |

Painting must reproduce the existing syntax colours, selection underline and
caret shape. Small edits should not blank a whole row or change unrelated
status pixels.

## State and ownership

The editor Task owns a retained image of the viewport: one character and one
attribute byte per source cell. The attribute records the syntax pen, selection
mark and caret presence. Keep the existing single-row text/colour scratch for
composition. Retain a separate status character row because it has uniform
colour and no source selection.

The cache describes the latest composed **logical appearance**. It does not
prove that screen pixels or an AES saved image are complete. In particular,
composing a covered cell does not mean it has been drawn. AES remains the
authority for visibility, saved images and pending exposure repair.

Maintain these independent kinds of state:

- Candidate rows need recomposition after a document, selection or layout change.
- Changed column spans need presentation after composition finds a difference.
- Forced repair spans need reconstruction after exposure or geometry changes,
  regardless of equality with the logical cache.
- Publication state records drawable changes still needing an UPDATE before
  the next event wait.

Each source row has separate half-open changed and forced column intervals.
Merge intervals within a row; leave intervening clean rows untouched. Keep a
pending interval until presentation even if a later edit reverses its logical
change: this cache does not retain a second complete image of presented cells.
Conservative extra drawing within that row is acceptable. Keep source row
composition validity separate from pending presentation.

Include caret, selection, status and layout changes in a private presentation
generation. The document generation alone misses these changes. New input
invalidates any prepared work that refers to an older presentation generation;
pending damage is merged with the new work rather than discarded.

All state belongs to the existing application image and stays live through AES
detach. No additional Task, signal, periodic timer, resident editor service,
kernel operation or public ABI change is required. Prepare rows outside UPDATE;
the editor Task performs painting and model mutation sequentially. Existing
Exec scheduling and driver interrupt protocols continue to apply.

## Composing changed cells

Keep document operations independent of display coordinates. Edits nominate
source rows; the presenter maps them through folding, `first` and horizontal
`left` into viewport rows. Newline edits and multi-line replacements nominate
the remaining affected viewport. Navigation with a stable viewport nominates
the rows containing the previous and new caret/selection.

Compose the complete candidate row, including tab expansion, padding, lexical
colour, selection and caret attributes. Compare it with the retained logical
row, then merge the differing columns into pending presentation. Reusing
`BasicLexLine` on an affected source line is appropriate: the 255-byte source
line bound already limits its work, and a changed token can recolour earlier
characters. Restricting damage to bytes after the insertion point is incorrect.

Coalesce adjacent changed cells with the same syntax pen into text runs.
Status setters in file, assistance and build handling nominate only the status
row when the bounded message changes. Compare the composed unsaved marker too:
the first edit after Save changes it, while subsequent unsaved edits usually do
not. Source damage never automatically schedules status drawing.

Caret changes nominate both its previous and current cells. Reconstruct each
affected base glyph and selection mark before drawing the final caret. Changes
queued before a paint may include several old caret positions; their pending
spans must survive until those pixels are repaired. Keep the existing caret
visibility policy; this work adds no blink timer.

## Drawing through VDI

Use the current `MD_REPLACE` text mode. Its glyph paper is pen zero, so a changed
cell can overwrite its old glyph directly. Clear a deleted tail by drawing
spaces. Apply selection and caret marks after the base glyphs, and report
completion only after all cell layers succeed.

Whole-area fills remain appropriate for newly exposed margins, gutters and
status padding after initial creation or geometry changes. Ordinary source and
status changes use cell-sized reconstruction. Every operation remains clipped
to the current `WF_FIRSTXYWH`/`WF_NEXTXYWH` visibility and the requested repair.

Use bounded presentation turns, initially capped at 96 cell reconstructions
across at most four rows, counting status and repeated visible fragments.
This allows a maximum-width 80-cell source row plus the small caret/marker work
to fit a common edit. A clipped fragment or repeated overlay restoration still
counts as work; the budget measures presentation, not just source bytes.
Large margin fills use the existing bounded VDI fill path.
The implementation additionally limits each turn to eight margin-fill fragments.

Recompose at most four source lines per turn. Release UPDATE before yielding
or returning to event handling, and obtain fresh visibility for the next turn.
Treat the initial ceilings as private tuning parameters: measure input and
pointer response before accepting them. Preserve progress for large repairs
without holding UPDATE through their entire lifetime.

## UPDATE and repair protocol

### An ordinary completed edit

Prepare the candidate cells and damage before taking UPDATE. A fast update is
eligible when all changed cells and overlays can be completed within the
current visible coverage and work budget. Determine coverage using the fresh
UPDATE snapshot, including any partially clipped cells.

Begin one window-specific UPDATE, draw the changed spans, report completed
pixels, and end UPDATE. This scope publishes the change as well as painting it;
omit the preceding empty publication. When every drawable change in this scope
has finished, `ExecAESPaintedChanges` can acknowledge their bounding span. Its
existing `pixelsReady` condition preserves any older exposure obligation. Use
exact `ExecAESPainted` reports for reconstructed cells when that broader
completion shortcut is unavailable.

A key that changes no rendered cells and has no pending repair needs no UPDATE.
Only acknowledge local presentation work after successful drawing and
`END_UPDATE`. A failed operation must not leave the cache treated as proof of
completed pixels; retain repair state or follow the existing orderly failure
and detach path.

### Deferred or hidden changes

If the complete change cannot be drawn before waiting, publish the model change
through an empty window-specific UPDATE. This includes hidden or partially
hidden changed cells for which drawing visible fragments alone would omit part
of the logical change. The resulting full client repair obligation is the
existing conservative fallback; this design adds no partial-invalidation ABI.

Publish once for each newly queued presentation generation that will cross an
event wait. Continuations of the same repair do not publish additional empty
updates. If new input changes pixels already repaired during an unfinished
batch, publish that new deferred change before waiting again.
Publication is required even when only some candidate rows have been composed;
an invalid row must be recomposed before its cached cells can supply a repair.

Reconstruct visible portions in bounded drawing scopes and report only actual
completed regions. Respect the eight-entry AES paint journal; split work or
leave excess repair obligations pending instead of widening a claim across
unfinished pixels. The final slice must include status, gutters and padding
where the full repair requires them.

When a window is fully covered or iconified, publish the change and stop
requesting paint timers solely for hidden pixels. Keep the logical model
current and let AES request repair when visibility returns. With partial
coverage, finish all currently visible fragments before retiring their local
work; hidden portions remain subject to AES exposure repair. A partial glyph
draw never proves that its hidden pixels are current.

### Exposure and layout changes

Translate each `WM_REDRAW` rectangle into forced cell repairs plus any affected
margins or status padding. Forced repair bypasses equality with cached logical
cells. Complete it using fresh visible rectangles and matching UPDATE reports.
Never use unchanged text, row validity or exhausted rectangle enumeration as
evidence that exposure has been satisfied.

Changing geometry, scroll position, horizontal pan, fold mapping or document
identity invalidates the corresponding row composition. Reconstruct affected
visible content and borders in bounded turns. The first delivery may rebuild
the viewport for these operations; preserved scrolling copies can be considered
after typing and exposure correctness are established.

## Memory budget

Reserve at most **5,120 additional upper-RAM bytes per editor image**, including
alignment and unused capacity. Keep this block in private application image
data, alongside the existing editor model, so it does not consume Task stack
space or introduce a new allocation in the keystroke path.

| Storage | Reserved bytes |
| --- | ---: |
| 80 columns × 30 source rows × character and attribute | 4,800 |
| Changed and forced endpoints, four byte arrays of 30 rows | 120 |
| Row composition validity | 30 |
| Retained status characters | 80 |
| Generations, flags, status endpoints, alignment and spare capacity | 90 |
| Total additional application reservation | 5,120 |

The current fixed 8×8 face and 640×240 display fit these bounds. Enforce the
private structure's size against the reservation at build time; report actual
image data, loader allocation rounding and stack peaks during implementation.
The reservation itself includes spare bytes even when the viewport is smaller.
Application image admission and teardown continue to own allocation failure
and resource retirement.

Composition reuses cached base text and syntax for caret/selection-only changes.
Source generations invalidate nominated base rows; whole-viewport nominations
also invalidate them for fold-map changes. The procedure index resets its count,
scan state and fold bits after edits; each reused procedure entry initializes its
own bounds and terminated name before becoming visible. This avoids clearing
the entire procedure table on every keystroke.

Additional reserved bank-zero bytes are **0 fixed, 0 root/kernel, 0 per each of
the twelve public Task slots, and 0 idle**, including guards, alignment and
unused reserved capacity. The editor's stack requirement must be checked
against emitted code; the cache does not justify a larger stack pool.

## Validation and acceptance

Use the [development testing tier](../contributing/testing.md). Documentation
checks apply to this proposal; implementation requires focused optimized
emitted-code coverage of the real painter and loaded application. Existing
logical editor tests alone cannot establish repaint correctness or latency.

Exercise these acceptance cases:

- Append, Backspace and Delete; insertion and deletion in a long line; tabs
  and horizontal pan; keyword completion and quote/comment recolouring.
- Caret-only motion, selection growth and removal, drag selection and input
  loss; old caret pixels and shortened line tails must disappear.
- First edit after Save, subsequent unsaved edits, Undo back to the saved
  generation, shortened status messages and build/file/assistance status
  changes. Unchanged status must produce no status drawing.
- Newline insertion/join, Undo/Redo, folds, Find/Replace, document replacement,
  resize and scrolling while repair is pending; new generations must supersede
  stale prepared work without losing damage.
- Full and partial exposure with identical cached text; occlusion through a
  glyph, caret and selection; popup restoration, hidden edits and return from
  iconification. Verify pixels owned by other windows remain unchanged.
- A change larger than one quantum, newer input between quanta, limited paint
  report capacity and a drawing failure. Never acknowledge unpainted pixels or
  spin on a fully hidden window.
- Check/Run/Stop/Build, retained interpreter state, Save, canceled Quit and
  final detach while editor damage exists. Preserve cleanup and stack guards.

Compare final pixels against an independent complete reconstruction of the
document, viewport and overlays. Record text-cell counts, filled pixels, VDI
calls, UPDATE scopes, empty publications and status draws. Routine caret motion
must touch only the old/new cells; a simple append must avoid a full-row clear,
unchanged status drawing and an empty publication. An idle settled editor must
perform no drawing.

Measure input through visible scanout on the same pinned ROM, emulator,
accelerator, VBXE and native build configuration before and after the change.
Include repeated-key bursts, syntax-heavy lines, another active console and
pointer movement. Report median and tail latency, worst UPDATE hold time,
bounded completion and memory/stack costs. Operation-count reductions alone
do not establish smoother input or qualify the hosted platform.
Acceptance requires lower median and 95th-percentile key-to-scanout latency for
routine typing and caret movement, with pointer responsiveness and completion
of large repairs preserved. Establish the matched baseline before freezing
numeric latency ceilings in the implementation plan.

When the implementation lands, update the workbench contract and guide and
record the measured development evidence separately. Refresh demos through
`tools/build_demo.py`, retaining OF816, its five-second autoboot, the matching
combined system ATR, separate QED ATR, ROM, `licenses/` and checksums. Keep
measurement output and build intermediates outside the boot ZIP.
