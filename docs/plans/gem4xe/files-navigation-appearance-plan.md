# Files navigation and appearance implementation plan

[Plans](../README.md) · [Current AES and desktop contract](../../reference/aes.md) ·
[Compact Files results](../../history/compact-files.md)

Status: implementation in progress. FR1–FR4 pass development checks; final
FR5 integration and packaging are in progress. The parent-folder artwork is approved.

Make Files denser and easier to navigate at 640×240: distinct GEM window
gadgets, a thin directory summary below the title, colour icons and an in-grid
parent item. Ordinary navigation reuses the current window. Keep the existing
bounded models, renderer and desktop Task.

## Agreed behaviour

| Action or element | Result |
| --- | --- |
| Double-click a directory or press Return on it | Enter it in the same window. |
| Parent item labelled `..` | First grid cell or list row in a subdirectory; double-click or Return goes up. It scrolls with the contents. |
| File → Parent, Esc | Go up in the same window. At a volume root, disable the menu command and make Esc a no-op. |
| Esc during a dialog or drag | Cancel that interaction and consume the key; do not also navigate. |
| File → Refresh, Ctrl+L | Reread the directory, retaining surviving file selection and the applicable viewport. |
| Close gadget | Close the window, at every directory depth. |
| Summary | Fixed 10–12-pixel strip below the title, normally `42,840 bytes in 10 items`; the same strip shows selection counts and temporary browsing/drop messages. |

Remove the Up/Refresh toolbar and the directory's bottom status strip.
Backspace remains available for editing and no longer navigates in the normal
folder view. Esc replaces the current clear-selection shortcut; View → Select
None and clicking empty content remain available.

Use the approved [parent-folder artwork](assets/files-parent-icon.svg), with
its exact [32×16 logical-pen pixels](assets/files-parent-icon.json). The SVG
preview doubles pixel height to show the intended display proportions.
The production label is `..`, using the existing GEM font.

Existing independent folder windows and Desk → New Window remain available
for drag-and-drop. This work adds no automatic window spawning, navigation
history, filesystem notifications, generic icon registry or new AES operation.
An additional Open in New Window command is outside these slices.

## Current implementation constraints

- Both title gadgets currently draw the same inner square in
  [desktop-frame.c](../../../lib/desktop/desktop-frame.c).
- Files uses 20 pixels above the grid, 16 below and a 40-pixel icon row pitch.
  Its default 360×184 outer window has a 336×152 work area and shows two rows.
- File cells already use `G_CICON`, but their three stock designs contain
  monochrome artwork. The desktop's coloured folder and application designs
  are already in the same resource.
- Selection belongs to the real directory snapshot, with 256 entries and a
  32-byte membership bitmap. Sixteen visible OBJECTs are reused while scrolling.
- Browser input, selection, scrolling and drag code currently assume that a
  displayed index is also a real entry index. Parent navigation must update
  those consumers together.

The top-summary decision supersedes the earlier bottom-status proposal. Three
rows fit by changing Files' own layout; retain the shared work-area insets,
scrollbar and resize geometry in this plan. Reclaiming the frame's full-width
bottom reservation would be a separate shared-geometry change.

Keep validation at the current public boundaries and report normal operational
errors. Parent handling is a small local navigation branch; it does not justify
another validation layer around every object or directory operation.

## FR1 Distinct GEM close and full gadgets

Replace the duplicated inner squares with the close/full symbols from the
existing GEM font: glyph 5 for close and glyph 7 for full. Keep the current
neutral gadget backgrounds, frame borders, hit rectangles and full/restore
semantics. Use the existing bounded frame-rendering path and font assets.

Check both gadgets in active and inactive windows at the intended display
aspect ratio. Through emitted code, verify close, full, restore and exposure
beside the shell; compare pixels with an independent expectation. There is no
public ABI or geometry change.

## FR2 Compact content and top summary

Remove the two toolbar objects and their click dispatch. Update the resource
tree and object constants together, retaining only objects still used by the
view and keyboard-focus decoration. Keep unrelated dialog/resource cleanup
outside this slice.

Start with a 12-pixel summary strip, content starting at y=16, a 36-pixel icon
row pitch and a 2-pixel bottom content margin. Keep 104-pixel columns for
12-character labels, 32-pixel cell height and the current list typography.
The default work height then admits three complete icon rows. Preserve user
window dimensions during navigation and the current minimum/full/restore sizes.

Move browsing summary painting and changed drag-target feedback to the top
strip. Scrolling repaints the content region; selecting an item repaints the
changed cells and summary. Update content hit tests, clipping and drag target
bounds with the same layout constants. Editable/progress dialogs retain their
own form layout and message placement.

Change the Parent menu label to advertise Esc. Replace the old Esc selection
handler and remove the browsing Backspace alias. Dialog and drag cancellation
take precedence. Keep Ctrl+L for Refresh. Root Parent is disabled and does not
trigger a redundant disk read. On root status, retain the existing meaning of
the byte total and count; directories count as items, not files.

Verify three columns by three rows at the default size, fixed summary during
scrolling, icon/list switching, clipped resizing, full/restore, selection,
Refresh and Esc precedence. Update existing compact-view observers alongside
the code, including their old Esc-clears-selection expectation.

## FR3 Parent item and upward navigation

Add one virtual display item before the real entries whenever the current path
has a parent. Keep real entries, their ordering and the selection bitmap
unchanged; all 256 real-entry slots remain available. Use a small Browser-local
mapping between display positions and real entry indices, with an explicit
parent sentinel. Reuse the existing sixteen visible objects and colour-icon
descriptors. No second directory list or public object abstraction is needed.

Apply that mapping to layout, row scrolling, slider extent, mouse/keyboard
focus, Open, selection painting, refresh remapping and drag source/target hits.
The parent contributes to scrolling extent but not to directory counts, byte
totals, sorting or file membership. A full snapshot can therefore have 257
display items while retaining the existing 256-entry storage limit.

The parent can receive a single highlight and keyboard focus. Focusing it
clears ordinary file membership; modifier input cannot add it to a batch.
Open is enabled for it, while Rename, Copy, Delete and Stop do not acquire
parent-item semantics. Stop retains its existing running-command behaviour.
Select All covers only real entries. The parent is
neither a drag source nor a drop destination: its hit must not fall through
to the surrounding directory-background drop target.

Route the parent icon, File → Parent and Esc through one upward-navigation
routine. After a successful upward scan, select and reveal the directory just
left, even when it falls on a later row. Retain only that child name during the
transition, using existing scratch where its lifetime permits; no history
stack is needed. If it is absent from the new snapshot, leave an ordinary
unselected view. Preserve the current path on an operational navigation error.

Import the approved pixel array into the existing RSC source as a `G_CICON`
stock asset. Give its label the file-window background and the same inverse
selection treatment as other entries; preserve the artwork on selection.

Focused checks cover an empty subdirectory, volume roots, a child beyond the
first page, name/disk ordering, refresh with parent focus, the 256-entry bound,
Select All and mutation exclusion. Run drag cancellation and real-file copies
with the parent present, including a rejected drop directly on the parent.
Exercise both desktop-owned folders and standalone Files.

## FR4 Colour directory and application icons

Use the existing beige folder bitmap for real directories. Reuse the desktop
artwork for PANEL.APP, CALC.APP, TEXT.APP and COUNTER.APP. Add a console-command
bitmap with a clear `>_` prompt in the existing muted blue-gray palette, and a
generic GUI-application fallback for other `.APP` entries. Retain a neutral
document design for ordinary files, including `.RSC`.

A small static filename-to-stock-icon table is sufficient for the bundled GUI
applications. Follow the existing executable naming convention for console
commands; do not open executables or scan resources to determine their icons.
Icon classification remains presentation policy and does not change launching.
Share resource bitmap pointers; set file-window label geometry/background in
the existing per-cell descriptors. Keep the current palette and label-only
selection, with the dotted outline reserved for keyboard focus.

Check every icon category at the actual display proportions, in selected and
unselected states, at clipped window edges and after scrolling. Confirm the
four known GUI applications still launch normally and generic icons do not
change file associations. No renderer or resource-format extension is required.

## FR5 Integration and distributable demo

Extend the existing compact Files walkthrough and independent pixel oracle;
do not create a parallel desktop test framework. Cover the final parent,
summary, colour and gadget behaviour together, one real-file drag/copy with
independent byte readback, and standalone Files cleanup. Keep stack/domain
guards, ownership checks, bounded completion and return to the shell/OS.

Build through `tools/build_demo.py`, including OF816, the five-second autoboot,
matching system/work disks, pinned ROM, guide, notices and checksums. Rebuild
both Files and Desktop with their matching resource. Exercise the exact
extracted ZIP. Keep manifests, pixel evidence and logs in the development
directory; distribute only `exec816-demo.zip`. Provide a screenshot and the
launch command with the implementation results.

Update the current AES/desktop reference and packaged user guide for Esc,
Refresh, virtual parent entries and the top summary. Add a history record and
development evidence; update the relevant indices and this plan's status.

## Validation and memory

Use the development tier: host checks and focused optimized emitted-code
tests for changed behaviour. Run small raw/optimized private-layout probes
only if record layouts change, updating observers at the same time. Keep the
recorded compiler pin; compiler qualification and full platform matrices are
outside this work.

Target reserved bank-zero delta for every slice: **0 fixed, 0 per Task and
0 idle bytes**, including guards, alignment and unused reserved capacity.
No Task stack/DP or VRAM reservation increase is planned. Report actual linked
code/resource sizes and any upper-memory Browser growth after implementation.
New icon data uses the existing loaded resource; share bitmaps across cells.

Keep each slice executable and prepare one focused commit after its selected
checks pass. FR5 completes the combined package and records actual results;
it does not imply release qualification.
