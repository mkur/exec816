# Compact window geometry refactor

[GEM plans](README.md) · [Desktop contract](../../reference/desktop.md) ·
[AES contract](../../reference/aes.md)

Status: CF1–CF3 complete; CF4 pending, 2026-10-14.
[Development record](../../history/compact-window-geometry.md).

## Outcome and reference

Recover vertical work space and make the frame controls look proportional on
the 640×240 display. Preserve the current flat GEM/Exec appearance, 8×8 font,
desktop/file icon artwork and application behavior.

The inspected GEM4XE 0.11 revision, `fbfea9b`, derives flat title height from
the eight-row font plus three rows: 11. Its flat gadget cells are 12×11; its
optional 3D frame expands them to 16×15. Sources are `src/aes/graf.c:gsx_start`,
`src/aes/wind.c:w_bldactive/wm_calc`, and `src/vdi/vdi.c:fill_workout` in the
donor checkout. AES includes a pixel-aspect calculation, but this VDI reports
equal pixel dimensions, so copying its gadget width does not correct our
displayed proportions.

When 640×240 fills an approximately 4:3 picture, a pixel is about twice as tall
as it is wide. Our 16×16 cells consequently look tall. Use 22×11 cells for
approximately square displayed controls, while keeping font and icon pixels
unchanged. This is one fixed geometry profile; it needs no runtime aspect-ratio
or theme machinery.

## Target metrics

All values are framebuffer pixels; dimensions are width × height.

| Element | Current | Target |
| --- | ---: | ---: |
| Title / top work inset | 16 | 11 |
| Title gadget cell | 16×16 | 22×11 |
| Vertical scrollbar width | 16 | 22 |
| Scroll arrow / sizing corner | 16×16 | 22×11 |
| Additional INFO inset | 12 | 10 |
| Bottom inset with SIZER | 16 | 11 |
| Plain bottom inset | 8 | 2 |
| Global menu bar | 16 | 11 |
| Native popup row | 16 | 11 |
| Iconified tile | 88×16 | 88×11 |
| Ordinary left/right work insets | 8 / 8 | 8 / 8 |

Place eight-row title/menu text at y+1; keep the lower separator outside the
glyph cell. Center short, wide gadget marks, approximately 14×7, in their
cells. Preserve the meanings of the GEM closer/full symbols and the new
iconify mark; shrinking a surrounding box alone leaves the old square glyph
looking stretched. Keep the existing colors and thin outlines.

Retain tile x positions and eight-character labels. With a two-row lower
margin their new y is 227. Tiles remain ordinary coverable layers, with
Windows-menu recovery; they do not reserve a taskbar across the screen.

The default Files window grows from 456×196 to **462×196**. The extra six
columns compensate for the wider scrollbar, keeping its 432-pixel work width
and four icon columns. Its work height grows from 164 to **174**. Preserve the
four complete rows, icon size, labels, summary and scrolling behavior.

Files currently draws the summary inside its client, without the AES INFO bit.
Its maximized work height therefore grows from 192 to **207** (+15, 7.8%),
assuming it uses the full reported desktop work rectangle. A window that also
requests INFO grows from 180 to **197** (+17). These are geometry targets,
not a promise of an additional icon row or a measured rendering speedup.

## CF1 — separate horizontal and vertical metrics

First separate metrics without changing displayed dimensions. Edit
`abi/desktop.json` and `tools/generate_desktop.py`; regenerate Action! and C
definitions. Replace `FRAME_GADGET` with width and height constants and export
menu/tile metrics through the same generator. Remove the old constant once
callers migrate; no compatibility aliases or new configuration layer.

Audit the frame painter, `DESKGEOMETRY`, drag capture, slider calculations,
`wind_calc`, published work rectangles, native widget coordinates, frame damage
and menu drawing. A horizontal closer boundary currently uses TITLE_HEIGHT:
replace that coupling explicitly. Keep draw and hit rectangles in agreement.

Retain existing 16-row frame strips and 32-row widget capacity; these are
rendering budgets, not minimum control heights. Do not add validation in hot
paths. Expected reserved bank-zero delta: fixed 0 / each public Task 0 / idle 0;
VRAM 0. Check generated definitions and focused emitted geometry with unchanged
pixels before proceeding.

## CF2 — compact frames, Shell and iconified tiles

Apply the target frame metrics and marks together with work-area publication,
hit testing, slider arrows/track/thumb and resize-corner positioning. Preserve
the existing eight-row minimum thumb. Use fixed drawing spans or masks in the
current frame renderer; no new object framework or drawing service.

With 22-pixel controls, three gadgets do not fit a 64-pixel title. Compute
availability from the actual reserved gadget widths, identically in rendering
and input. Omit iconify when it would overlap the closer/full controls, retaining
the menu route. Truncate the title to the remaining space without underflow.
Keep the existing minimum window sizes unless a focused case proves a conflict.

Preserve Shell's 64×20 text model and 512×160 backing allocation. Keep its text
origin on the eight-pixel grid: align `outer.top + titleHeight`, rather than
`outer.top`. With an eleven-row title, outer y is 5 modulo 8. Update creation,
movement, drag snapping/clamping, `DESKPAINT.Sync` and `DESKMOVE.Rebase` together.
Its outer size becomes 528×173. Choose the initial outer y to preserve the
existing text origin; derive the size from content and frame metrics instead
of retaining the old 528×184 literal. Keep the current cell-based console
representation and backing/scroll implementation.

Compact the tiles and their hit areas in the same slice. Test ordinary and
saved iconified geometry, native show/hide/raise, AES restore and the exact
Shell text origin after moves. Preserve even-X/even-width AES placement and
completed-window copy eligibility. Expected bank-zero and VRAM deltas remain 0.

## CF3 — menus and application layout

Apply the eleven-row menu bar and native popup rows across `DESKMENU`,
`DESKMENUPAINT`, `DESKAPPMENU`, AES menu admission and frame/menu C drawing.
Update background-save, popup-image, damage and hit bounds as one contract.
Replace row-index shifts that assume sixteen rows with a bounded scan or
subtraction over the existing maximum nine native rows; avoid general division
on pointer-motion paths.

Update the bundled application menu trees and resource sources so headings fit
the new bar and dropdowns begin below it. Compact ordinary bundled menu rows
to eleven pixels; keep caller-specified custom popup layouts caller-owned.
Do not rescale or rewrite arbitrary borrowed application trees at runtime.
Rebuild matching applications/resources with the host.

Report desktop work area `(0,11,640,229)` through `wind_get(0,WF_WXYWH)`.
Replace the old `(0,16,640,224)` assumptions in the borderless desktop,
maximization, dialog placement and bundled applications with the reported
geometry. Update original/restore rectangles and drag clamps consistently.

Apply the six-pixel default Files width increase; clamp cascaded folder
positions within the desktop. Its existing layout consumes the extra height.
Check Counter, Panel, Calculator, Text, file selector and dialogs for stale
work coordinates or clipped objects. Desktop and directory icon dimensions,
font, selection style and icon grid spacing remain the same. Expected reserved
bank-zero delta: fixed 0 / each public Task 0 / idle 0; VRAM 0.

## CF4 — development evidence and packaged demo

Use the iconification build at `ff5911e` and its recorded images/results as
the comparison baseline; avoid rerunning an unrelated qualification matrix.

- Run host contract/resource/generator checks and focused optimized native/AES
  geometry and menu checks. Raw/optimized probes are needed only if generated
  record layout or the C/Action bridge changes; do not run the compiler suite.
- Update independent pixel models and physical-input coordinates. Cover all
  gadget kinds, narrow titles, active/inactive frames, long titles, menu rows,
  first/last scrollbar positions, edge clamps and resize/full/restore cycles.
- Exercise the Shell at the top/bottom limits, with output, scrolling, caret,
  overlap, movement, iconification and restoration. Check exact current text
  pixels and retained backing behavior, including covered output.
- Exercise Files at its default 4×4 layout and maximized size, smaller resizes,
  multiple folder windows, summary, selection and drag/drop. Assert accepted
  work dimensions and click coordinates, not just a screenshot's appearance.
- Check File/View switching, Windows recovery, popup dismissal and menu/cache
  invalidation after movement. Confirm that a clean eligible move still copies
  the window without a client repaint, and warm menu switching retains its
  saved background. No new broad performance campaign is required.

Compare images both in raw pixels and at the approximately 4:3 presentation
used in the user's screenshot. Verify the new proportions without shrinking
application icons. Preserve stack/domain guards, bounded completion and clean
OS return; record actual memory/stack use and any upper-memory growth per slice.

Build and exercise the final desktop through `tools/build_demo.py`, including
OF816, matching SYS/WORK media, pinned ROM and license notices, with the
five-second autoboot retained. Deliver `exec816-demo.zip` and its launch command;
keep intermediates and diagnostics outside the ZIP. Update current desktop/AES
contracts, the distribution guide and indexes, and add a concise development
record with measured dimensions and remaining limits.

## Scope and completion

Complete when geometry, rendering and input agree; default Files retains its
4×4 icons; the work-height targets are met; and Shell/cache/menu/iconification
regressions pass on the packaged image. This remains development validation,
not hardware or release qualification.

No new kernel calls, scheduling policy, Tasks, VRAM reservations, per-window
themes or general layout engine. Keep each slice executable and reviewable.
The existing public application operations remain; rebuild matching code for
changed geometry and only change ABI versions where the repository's contracts
require it. CF1–CF3 are implemented; CF4 covers the packaged integration and final evidence.
CF2 raises the fixed FULLER minimum width from 32 to 44 to fit its two
22-pixel mandatory controls.
