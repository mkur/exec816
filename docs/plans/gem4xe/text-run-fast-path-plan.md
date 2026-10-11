# GEM rendering performance implementation plan

[GEM plans](README.md) · [Drawing traces](../../history/g4bench-drawing-traces.md) ·
[Earlier text optimization](text-viewer-performance-plan.md)

Status: TX1–TX2 implemented and development-tested; TX3–TX7 pending. Continue in
executable slices, committing each after its focused development checks pass.
See [slice results](../../history/gem-rendering-performance.md).

Increase text batches from 32 to 80 characters and extend the native uploader
to fully visible odd-X text. A complete screen row should need one display
borrow, command upload and blitter launch when it lies within one visible
rectangle. Keep ordinary GEM calls and synchronous completion semantics.

Draw caller-local AES objects up to 32 pixels high, including their borders,
in one display borrow per visible rectangle. Larger objects retain 16-row
strips. This keeps ordinary buttons together without enlarging every repaint.

Give solid rectangles a direct command path and split them by the existing
blitter work budget. A rectangle that fits that budget should use one borrow
and list per visible intersection, even when it is taller than 16 or 32 rows.

Render opaque boxes and buttons with an outer border-colour fill followed by
an interior background fill, replacing repeated one-pixel border outlines.
Apply text and state decorations afterwards in their existing order.

## Starting evidence

The existing G4BENCH traces provide the baseline; no separate baseline slice
is needed. Its 39-character strings currently split into 32 and seven characters.

| Idle desktop workload | Elapsed mean | Task CPU mean | Borrows and launches |
| --- | ---: | ---: | ---: |
| Even X | 24.011 ms | 13.277 ms | 2 each |
| Odd X | 39.349 ms | 25.850 ms | 2 each |
| 100×50 solid rectangle | 28.102 ms | 16.662 ms | 4 each |

These means include application protocol and scheduling; they are not bare
renderer timings. The odd-X path adds 12.573 ms of Task CPU, mostly in renderer
and command construction. It already uses blitter glyphs, but reaches them
through the general donor text path. The even-X uploader constructs records
directly in VRAM.

The existing shifted atlas stores an odd-X glyph in five bytes per row instead
of four. Widget glyph runs already use it. Extend the native uploader using
that storage; no new atlas or CPU pixel-shifting loop is needed.

The rectangle is split into 16, 16, 16 and two rows. Each strip repeats donor
workstation setup, coordinate ordering/clipping, ownership and submission.
Ownership alone costs 3.784 ms of Task CPU; renderer setup, construction and
upload add 1.837, 1.622 and 0.515 ms. Completion polling costs 0.342 ms, which
does not measure the entire DMA interval. The complete rectangle fits the
current work budget: 5,000 accesses at even X or 5,500 with two odd edges.

The current AES object loop also splits drawing at 16 rows. Files directory
entries are 12 pixels high including borders and already fit in one unit.
Standard exit buttons occupy 20 rows and default buttons 22 rows, so each
currently requires two units. The G4BENCH dialog has ten borrows: four for its
64-row root, one each for the label and coloured box, and two per button.

That dialog currently emits 75 rectangle fills: 24 for the root, five for the
coloured box, 26 for OK and 20 for Cancel. The label adds none. Nested outlines
and their repetition across strips account for these counts. Renderer and
command-construction CPU together cost 51.494 ms per dialog in the idle trace;
the whole amount is not attributable to fills alone.

## Scope and bounds

- Set the VDI chunk and native text limit to 80. At X=0, 80 complete cells
  cover the 640-pixel screen. At X=1, only 79 complete cells fit; an 80-character
  public call must clip correctly rather than entering the complete-cell path.
- Optimize fully visible, opaque 8×8 text at either X parity. Preserve fast
  runs when only the horizontal ends are clipped: skip hidden cells, batch the
  complete middle and use existing code for partial edge glyphs. Vertically
  clipped rows retain their fallback. Multiple visible rectangles can still
  require multiple borrows.
- Admit complete AES objects of at most 32 rows in one borrow per visible
  rectangle. Decide from the full object height including outward borders,
  before damage/visibility clipping. Keep larger AES objects and the presenter's
  offscreen widget strips at 16 rows.
- Route solid VDI rectangles directly to a trusted fill encoder. Bound their
  units by the existing 8,192-access budget, including odd-edge masks. Keep
  generic callback bounds separate from this fixed-operation path.
- Simplify opaque `G_BOX` and `G_BUTTON` painting to an outer fill and interior
  fill. Keep transparent frames, patterned interiors and other object types on
  their existing paths; preserve exact border geometry and state decorations.
- Preserve the generic list limits of 64 records and 8,192 estimated bus
  accesses. Give the trusted text generator its own explicit bounds rather
  than enlarging every drawing work unit.
- Keep one owner admission for the run, dependency/completion fences, pointer
  handling, IRQ/NMI coordination and timeout recovery. Generate trusted
  records without rescanning them or repeating geometry checks per glyph.
- Use shifts/adds or fixed constants for the two atlas geometries. Keep caller
  pointer validity and API use as caller responsibilities; add no validation
  framework, rendering Task or new scheduling policy.

For odd X, fill the background once across the run: one whole-byte interior
fill and an AND/OR pair at each outer nibble. Then draw shifted glyph masks.
This preserves both neighbouring pixels, including when the paper colour is
zero. Nonzero ink uses the nibble stencil; zero ink keeps the inverse-mask AND
semantics. Establish the paper before drawing any glyph, including spaces.

The following conservative bounds count every glyph, including blanks. They
assume two accesses per copy byte and three per read/modify/write byte, matching
the existing accounting. The optional trailing fill retains its current
3,072-access cap.

| Complete run | Records without trailing fill | Arena bytes | Work without trailing fill | Work with trailing fill |
| --- | ---: | ---: | ---: | ---: |
| 80 characters, even X | 81 | 1,701 | 12,800 | 15,872 |
| 79 characters, odd X | 84 | 1,764 | 14,616 | 17,688 |

Even text costs at most `160*n` accesses. Odd text costs at most `184*n+80`:
`120*n` for glyphs, `64*n-16` for the interior fill and 96 for the four edge
commands. A common conservative generator capacity of `80+5+1` records is
1,806 bytes, below the existing 4 KiB arena; its work ceiling is 17,872
accesses including the trailing fill. This bound does not admit an offscreen
80-character odd-X run.

Decouple `VBXE_TEXT_FILL_WORK` from the old expression
`VBXE_LIST_WORK-32*160`. Retain the explicit 3,072-access allowance and prove
the combined text/fill bound. Substituting 80 into the old expression would
underflow unsigned arithmetic.

## TX1 Increase complete even X runs to 80 characters

Completed. [Development evidence](../../development/gem-rendering-tx1.json)
records native 39/80-character single launches, the 80-character/max-fill case,
public VDI clipping/preemption, console/caret checks and matched G4BENCH runs.
The benchmark's complete 39-character call uses one borrow/upload/launch.
Current framed windows cannot expose a full 640-pixel work row: complete
80-character pixels/launches are checked at the native entry, while public VDI
tests exercise 80-character input clipped to its work area.

Update [the VDI ABI input](../../../abi/vdi-client.json), its generated
workstation layout and the streaming loop together. The private `WORD intin`
buffer grows from 32 to 80 elements. Regenerate through
[`generate_vdi_client.py`](../../../tools/generate_vdi_client.py), and check
that the VDI and driver limits agree. Confirm the shared donor scratch has
room for both the byte fast path and 80-word fallback.

Update the limits, comments and budget proof in
[`vbxe.c`](../../../platform/altirraos/vbxe.c),
[`vbxe-map.s`](../../../platform/altirraos/vbxe-map.s) and the private upload
contract. Keep the direct-to-arena assembly loop and optional final fill.
Use build-time capacity checks, not repeated hot-loop budget calculations.
Rebuild linked callers and loadable applications for the changed private layout.

Extend the smallest relevant emitted fixtures around
[`test_vdi_client.py`](../../../tools/test_vdi_client.py) and the native text
entry. Exercise lengths 0, 1, 31, 32, 33, 39, 64, 79 and 80, plus a longer
public string that clips. Cover named `v_gtext` and parameter-block word input,
bank-crossing source bytes, spaces, foreground/background colours and the
optional trailing fill. Do not mistake the older service benchmark's input
limit for the caller-local VDI limit.

**Gate:** independent pixel comparison passes; complete 39- and 80-character
even-X runs use one upload/launch, and the single-visible-rectangle public call
uses one borrow. The console's text-plus-caret operation remains correct and
fits the arena. Record intermediate G4BENCH results to isolate the batching gain.

## TX2 Add the native odd X run

Extend the existing private packet with only the geometry needed to select
the shifted atlas and encode nibble edges. Select parity once per run; preserve
the simple even-X loop. The odd atlas uses stride 1,280 and five bytes per
glyph row; destination cells still advance four bytes. Keep the glyph offset
calculation to shifts/adds.

Encode the background edges, interior fill and glyphs directly into the same
arena. End the chain correctly with or without the optional trailing fill.
Preserve the public trailing-fill rectangle restrictions; odd text does not
require arbitrary odd-X trailing fills.

Route complete odd-X units through the uploader in
[`GemVdiPaint`](../../../ports/gem4xe/hosted/hosted-dispatch.inc), and update
the existing native bitmap-text entry consistently. Make donor changes through
the maintained extraction patches, leaving the donor checkout untouched.
Keep ordinary clipping and colour mapping intact. No whole-run fallback is
needed merely because X is odd.

Update the C/assembly packet layout probe and uploader scratch documentation.
Use the existing call-clobbered DP reservation; report actual stack use and
preserve registers/context across interrupts and mapped command writes.

**Gate:** compare pixels at X=1, other odd positions and the right screen edge,
including the maximum 79-cell run and a clipped 80-cell public call. Use a
nonuniform surrounding framebuffer to detect damaged neighbour nibbles.
Cover hardware-zero/nonzero ink and paper, blank glyphs, mixed strings, glyph
byte 255 through parameter-block input, bottom-row placement, and partial
horizontal/vertical clips. A complete 39-character odd-X call must use one
borrow/upload/launch without donor `vdi_v_gtext` or per-character `vbxe_glyph`
dispatch. Relevant mapping/interrupt, fence-failure and clean-exit checks pass.

## TX3 Preserve fast runs under horizontal clipping

Extend `GemVdiPaint` to split an admitted text intersection into hidden cells,
at most two partial edge cells and a contiguous run of complete cells. Skip
hidden cells, send the complete middle through the native even/odd uploader,
and draw only partial edges through the existing clipped-glyph routine. Keep
all parts inside the original display borrow, with correct replacement paper,
colour-zero behavior and drawing order. A narrow clip inside one glyph draws
that glyph once. Retain the existing fallback if the clip cuts the glyph rows
vertically, or if no complete middle remains.

The clipped G4BENCH row currently costs 27.682 ms of Task CPU and 41.618 ms
elapsed, dispatching all 39 glyphs individually. For its full-height rows,
only the two end cells need the partial-glyph path. Avoid a new clip engine,
per-glyph ownership calls or a separate background pass over the entire string.

**Gate:** independent pixels match for clipping on either/both ends, boundaries
exactly on cells, single-pixel clips, empty intersections, negative starting X,
strings crossing a source bank, both X parities and hardware-zero ink. Partial
vertical rows still match the fallback. A complete middle stays on the native
run path and only the partial cells enter the old glyph path. Compare the
unchanged clipped workload against TX2, recording CPU, elapsed time, borrows,
uploads and launches separately; fewer glyph calls alone is not the gate.

## TX4 Draw small AES objects in one unit

Change the strip selection in
[`objc_draw`](../../../c/calypsi/aes-objects.c). Use a single height comparison:
objects whose complete extent, including borders, is at most 32 rows draw
their whole intersection with each visible rectangle in one callback. Objects
above that limit keep the existing 16-row loop even when damage exposes only
a short part. Preserve object order, clipping, selected/disabled states and
the existing UPDATE snapshot.

Raise the maximum callback height admitted by
[`GemDrawingBorrow`](../../../ports/gem4xe/adapter/gem-vbxe.c) to 32, keeping
the caller and adapter bounds consistent. Retain its ownership, pointer and
outline handling, fences, failure cleanup and synchronous return. Update the
[display contract](../../reference/display.md) when this behavior is implemented.

One borrow does not require one hardware command list. Keep
`VBXE_CHUNK_ROWS=16`, the existing geometry tables and generic list/work budgets;
the builder may split rectangles and drain lists inside that borrow. Leave
`EXEC_VDI_STRIP_ROWS`, `GemDrawingBatch`, `GemDrawingWidgetBatch` and the
640×16 presenter scratch reservation unchanged. Caller-local objects draw
directly to the screen and require no new scratch buffer.

Use existing object-rendering fixtures with independent pixel comparisons for
full extents of 16, 17, 31, 32 and 33 rows. Include normal, EXIT and DEFAULT
buttons, Files selection changes, selected/disabled objects, odd X, border
clips, separate visible rectangles and an intersecting pointer. Check a wide
32-row object that needs multiple internal lists, with normal completion and
the affected error/cleanup path. Do not add per-object scans or budget
heuristics to decide whether to combine rows.

**Gate:** a fully visible 20- or 22-row button uses one borrow; a Files entry
still uses one. A 33-row object remains split into 16, 16 and one rows. The
unchanged G4BENCH dialog uses eight borrows instead of ten, with its root still
split into four strips. Pixels and overlay restoration remain correct. Record
borrow durations and interaction timing; one ownership unit reduces repeated
setup but does not provide atomic or flicker-free screen publication.

Keep border construction unchanged until TX6 so the effect of combining
small-object strips can be measured independently.

## TX5 Add a direct solid rectangle path

Give the supported solid replacement fill in
[`GemVdiPaint`](../../../ports/gem4xe/hosted/hosted-dispatch.inc) a direct path
from the caller's admitted rectangle and colour. Avoid saving/selecting the
donor workstation, filling `ptsin`, calling `vdi_vr_recfl` and repeating the
ordering/clipping already done by [`vdi.c`](../../../c/calypsi/vdi.c).
Preserve inclusive public coordinates, colour mapping, UPDATE ownership and
the visible-region snapshot.

Add a small trusted fill encoder at the existing
[VBXE drawing adapter](../../../ports/gem4xe/adapter/gem-vbxe.c). Aligned
interiors need one constant-source record; each partial outer byte needs the
existing AND/OR pair to preserve its neighbouring pixel. Handle a single
partial byte without emitting duplicate edges or an empty interior. Construct
these fixed records directly instead of calling the generic builder once per
edge. Keep geometry and capacity accounting once per rectangle, with no record
rescan or repeated caller validation.

Reuse this encoder for uniform widget fills inside their existing batch. Append
records and drain only for capacity/dependency or the caller's completion
boundary; do not turn every box edge or interior into a separate submission.
Preserve presenter scratch redirection. XOR, patterned fills and unrelated
copy/glyph operations retain their existing paths.

Replace the unconditional VDI solid-fill strip loop with work-bounded units.
For an admitted row containing `B` complete bytes and `E` partial edge bytes,
the conservative cost is `2*B + 6*E` accesses. Choose the maximum rows fitting
8,192 accesses, capped by the remaining screen rectangle and hardware height.
Use a compact generated row-capacity lookup or equally cheap bounded arithmetic;
do not introduce a division per row/record or a rectangle-sized lookup bank.
Compute work after selecting the bounded height so large screen rectangles
cannot overflow a 16-bit area calculation. Include both edges in the budget.

Use a narrow internal solid-fill borrow, sharing the existing grant, overlay,
fence and cleanup lifecycle. It can cover the taller work-bounded rectangle;
arbitrary drawing callbacks keep TX4's 32-row ceiling. Add no public GEM opcode,
kernel operation or renderer Task. Update the private display contract with
this distinction. Larger fills release access between work-bounded units.

Keep generic `VBXE_CHUNK_ROWS=16`, its tables, the 64-record/8,192-access limits
and the presenter's 16-row scratch buffer. The specialized fill encoder can
encode taller legal records without indexing the generic 16-row work tables.
Record any compact-table payload growth inside the existing reservation.

**Gate:** the unchanged 100×50 benchmark rectangle, at both X parities, uses
one borrow, upload and launch per visible intersection instead of four. Its
list contains one aligned fill record or at most five records with two odd
edges. Compare exact pixels for all edge parities, single-pixel rectangles,
hardware colour zero, reversed coordinates, clipped/empty rectangles, screen
edges, and heights around 16/32. Exercise work just below, at and above 8,192,
a full-screen fill, disjoint visible rectangles, pointer overlap and the
affected failure/cleanup path. Verify batch ordering and scratch publication
for widgets, and account for all list work/records.

Measure against TX4: lower rectangle CPU and elapsed time, preserved pixel
results, and no reproducible feedback regression under repeated fills. Adapt
the passive trace's routine mapping to count the new fill encoder as logical
rectangle work; disappearance of `vbxe_fill_rect` calls is not evidence that
fills disappeared. Keep the dialog geometry and border algorithm unchanged
until TX6 to separate cheaper fills from fewer fills.

## TX6 Simplify opaque box and button fills

Change the extracted `just_draw` box/button branch through the maintained
[AES extraction patches](../../../ports/gem4xe/aes/patches), then regenerate
the selected sources. Leave the donor checkout untouched. Reuse the rectangle-fill
boundary; no general command-merging layer or retained object cache is needed.
Apply the same extracted routine to caller-local applications and retained
widgets so their appearance remains consistent.

Select the fast branch for `G_BUTTON` and `G_BOX` with an opaque, uniform
interior. Preserve the hosted `IP_HOLLOW` behavior: it paints a white interior
in these objects and is eligible. A `G_IBOX` preserves its interior and must
retain its frame-only path. Patterned interiors, other object types and
degenerate geometry that cannot use the two-rectangle construction keep the
existing algorithm. Establish this choice once per object draw.

Compute the rectangles from the original object geometry before clipping:

- For positive thickness, the outer rectangle is the object bounds and the
  interior is inset by that thickness.
- For negative thickness, expand the outer rectangle by its magnitude; the
  interior remains the original object bounds. This removes the redundant
  innermost outline that the opaque fill currently overwrites.
- For zero thickness, emit only the interior fill.

Fill the outer rectangle in the border colour and then the interior in its
effective background colour, clipping each through the existing boundary.
Clipping before deriving the border would create false edges at damage/strip
boundaries. Keep label placement, colour mapping, selected XOR, disabled
stipple and focus decoration in their current order and extents. Each state
overlay must affect each covered pixel exactly once.

Retain TX4 object units and the generic builder's row/list/work limits. The
outer fill deliberately paints pixels that the interior fill replaces. Accept
that additional VRAM traffic only when the measured CPU and completion cost
improve. Internal list drains can still occur; fewer rectangle calls do not
guarantee fewer launches or flicker-free publication.

Extend the existing object pixel fixtures, including
[`test_widget_pixels.py`](../../../tools/test_widget_pixels.py), and the
caller-local application checks. Compare independently expected pixels for
inward/outward/zero borders, ordinary/EXIT/DEFAULT buttons, odd coordinates
and widths, hardware-zero/nonzero colours, tiny interiors, selected/disabled
combinations and overlapping children. Exercise clips through every border
and across strip boundaries, plus unchanged `G_IBOX`, patterned and TEDINFO
objects. Check both application drawing and presenter scratch publication,
including pointer overlap and exposure repair.

**Gate:** exact pixels are preserved, and the benchmark's box/button border
loops are replaced by the two-fill construction. With TX4 already applied,
the expected logical fill count is **14 instead of the original 75**: eight
for the root's four strips, two for the coloured box and two per button. The
earlier estimate of 18 assumed the original two strips per button. These are
source-derived targets; confirm emitted counts and record internal blits,
launches, CPU and elapsed time. Compare TX6 against TX5 to isolate this gain,
including real Files selection and Panel button feedback.

## TX7 Measure the combined change and refresh the demo

Reuse the existing G4BENCH idle-shell and visible-counter workloads without
changing their strings, UPDATE grouping or reporting. Preserve the original
package and evidence. Record fresh source, compiler, ROM, emulator and image
identities for TX1–TX6 results; do not mix a compiler change into the comparison.

Use [`measure_g4bench.py`](../../../tools/measure_g4bench.py) for untraced
application results and [`trace_g4bench.py`](../../../tools/trace_g4bench.py)
for CPU, borrow duration, upload, fence and scheduling attribution. Include
the unchanged clipped-text, bar and dialog rows to reveal regressions. Keep
VBI batch medians separate from cycle-observed means and individual-call
latency distributions.

Add focused 64/80-character even-X and 64/79-character odd-X diagnostics using
the public path and an independent pixel oracle. Report median/p95 completion
and display-borrow duration, plus the maximum observed borrow. Measure Panel
feedback and pointer progress during repeated long-row drawing with the
existing desktop instrumentation. Add repeated complete-button updates and
Files selection changes to compare TX4 with TX3 and TX6 with TX5. Compare
solid rectangles and repeated-fill feedback at TX5 against TX4. Compare
horizontally clipped text at TX3 against TX2. Larger drawing
units must not conceal a responsiveness regression; use identical loads/input
schedules for before and after, and repeat only an ambiguous comparison.

**Gate:** the original even- and odd-X strings improve elapsed and Task CPU
cost, odd-X renderer overhead falls, and the one-upload expectations hold.
Horizontally clipped text meets TX3 pixel and fast-middle expectations.
Small objects meet the TX4 borrow counts and retain correct full/partial redraws.
Solid rectangles meet TX5's budget and submission expectations. Opaque objects
meet the TX6 fill/pixel expectations, with lower measured
dialog construction CPU and elapsed time; report any internal-drain tradeoff.
Desktop feedback median/p95 must not show a reproducible regression relative
to the matched baseline. Report any remaining gate explicitly rather than
claiming speedup from command counts alone. If the larger unit harms feedback,
revisit its implementation before accepting it; do not add priorities or a
second rendering protocol to compensate.

Refresh the GEM demo with [`build_demo.py`](../../../tools/build_demo.py),
including OF816, its five-second autoboot, matching disk/ROM and notices. Check
the exact ZIP walkthrough: G4BENCH, Files, TEXT, Panel and shell interaction,
closing/exposure repair and clean shutdown. Keep intermediates and traces in
the development directory. Provide the ZIP and launch command. Record results
under `docs/history` with machine-readable evidence under `docs/development`,
and update the plan/index status and current uploader contracts.

## Memory and validation scope

Expected reservation changes for every slice: **0 fixed, 0 per-Task and 0 idle
bank-zero bytes**, including guards, alignment and unused capacity. The larger
VDI buffer adds **96 upper-heap bytes per open workstation**, not per Task
unconditionally. TX2 may enlarge the private stack packet; TX5/TX6 may change
temporary rectangle storage and TX5 may add a compact upper-RAM lookup.
Record actual layouts, table payload and peak stack use.
Existing atlas and command-arena reservations stay unchanged, so expected VRAM
reservation growth is **0 bytes**. Report actual
resident code/data growth from the build.

Follow the [development testing policy](../../contributing/testing.md): host
and generator checks plus focused optimized emitted-code tests. Use small
raw/optimized probes for changed ABI layouts and the C/assembly bridge, rather
than duplicating the desktop suite or running compiler qualification. Extend
existing fixtures to cover affected pixels, command bounds, context, ownership
and failure cleanup. These checks do not establish release or real-hardware
qualification. The plan itself requires only content and local-link checks.
