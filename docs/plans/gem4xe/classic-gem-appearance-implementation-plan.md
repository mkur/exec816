# Classic GEM desktop appearance: implementation plan

[Design note](classic-gem-appearance-design.md) · [GEM integration](README.md) ·
[Roadmap](../../roadmap.md#next-desktop-milestones)

Status: GA1–GA3 implemented and passing development checks; GA4 integrated checks follow.

Implement the design in four executable slices, committing after each passing
slice. The current runtime baseline is the completed
[application menu milestone](../../history/application-menu-bars.md); record
the actual source/toolchain revisions at implementation start. Reuse its
evidence and runnable fixtures without a separate baseline-only slice.

The design chooses flat GEM decorations at 640×240 with the existing Atari ST
8×8 font. Work-area insets stay at left 8, top 16, right 8 and bottom 8 pixels
for this milestone; thin visible outlines and white margins replace the grey
surround. Resizing and actual inset changes follow through the same geometry
helpers.

## Sequence

| Slice | Deliverable | Completion gate |
| --- | --- | --- |
| GA1 | Shared geometry and classic window frames | Frames, left closer, drag regions and local window queries agree; focus and clipped title repair work. |
| GA2 | Menu and control consistency | Native and GEM menus compose correctly; bundled controls retain their mouse/keyboard behavior. |
| GA3 | Patterned desktop | Moving/closing windows and popups repairs the same screen-anchored pattern in bounded work. |
| GA4 | Integrated evidence and OF816 package | The exact packaged desktop and calculator scenarios pass interaction, pixel, guard and cleanup checks. |

GA2 and GA3 build on GA1; execute in the listed order. Each slice should leave a
usable desktop and update its relevant current documentation when behavior
changes. No selectable legacy appearance or temporary public drawing API.

## Rules for every slice

- Follow the [platform contract](../../reference/platform.md),
  [Action! style](../../contributing/style.md) and
  [testing policy](../../contributing/testing.md). Use the compiler and renderer
  pins; record any explicit override. Inspect donor sources read-only and keep
  imported assets/source reproducible with notices.
- Preserve the current presenter, application-owned content/menus, GUI locks,
  input capture, scene ownership and display completion. Keep validation at
  creation/admission and normal operational failures; do not add per-pixel or
  per-command safety wrappers around trusted internal output.
- Report reserved bank-zero delta for each slice: target **0 fixed, 0 per public
  Task and 0 private idle**, counting guards, alignment and spare capacity.
  Record upper data/code, heap, stack high-water marks and VRAM separately.
- The menu package already approaches its global-arena and manifest capacity;
  inspect build reports early in GA1. Place new state/tables in upper memory and
  keep public-Task stack use small. Cartridge compression is separate; size
  alone is not an acceptance gate. Actual loader/segment limits remain enforced.
- Use focused optimized emitted-code checks. Add small raw/optimized probes
  only if shared C/native layouts, calling conventions or pointer packing change.
  Update independent pixel expectations from the design, not captured output.
  Reuse passing evidence unless a changed input or concrete concern warrants
  rerunning it. Full release matrices and HY4/PI4 closure are not prerequisites.
- Record results in `docs/history/classic-gem-appearance.md` and compact
  `docs/development/classic-gem-appearance-gaN.json` files as slices land. Add
  the history-index entry then; keep images, traces and intermediates in `build/`.

## GA1 — Shared metrics, classic frames and the left closer

Primary areas: `abi/desktop.json`, `tools/generate_desktop.py`,
`lib/desktop/deskpaint.act`, `deskdrag.act`, `deskcore.act`, `deskcache.act`,
`deskmove.act`, `deskwidgets.act`, `lib/aes/aeswindow.act`,
`aeswindowstate.act` and `c/calypsi/aes-windows.c`.

1. Generate frame/work/title/closer constants for Action! and the small C
   geometry consumer. Add a small native geometry helper and replace the
   corresponding duplicated coordinate arithmetic. Keep current work bounds,
   `wind_calc` results, menu height and shell alignment. Include native content
   admission/translation and snapshot bounds in the audit, not just painting.
2. Replace the colored frame with a black outline, white margins and separator.
   Center/truncate the title in the usable span. Draw the active title pattern
   with an opaque white text backing; draw inactive titles plain. Use the
   existing font's closer glyph in the left box and omit it for the shell.
3. Add only the fixed pattern drawing support needed by the title. Use current
   display ownership and clipped strip publication, retaining bounded text and
   paint steps. Reuse the presenter's offscreen strip for each disjoint frame
   fragment and publish only after its background, pattern and text are ready;
   never copy scratch across application work pixels. Serialize use with native
   widgets and menus. Put small immutable pattern data in upper storage; reuse
   the existing atlas/raster/blitter path. Record any private drawing-packet
   change through its generator and rebuild both sides together.
4. Move close hit testing to the same rectangle used by painting; exclude it
   from dragging. Preserve inactive AES top-first handling, release-outside
   cancellation, Escape/loss/retirement, shell non-closure and existing messages.
   Old right-corner clicks must follow the title drag behavior, never close.
5. Update frame pixel oracles and physical fixture coordinates together. Test
   the specified rectangle edges explicitly as well as deriving ordinary test
   clicks from the agreed geometry. Update the desktop interaction reference
   and user-guide closer location; leave broader AES capability claims intact.

Focused development checks: adapt `tools/test_desktop_presentation.py` and
`tools/test_desktop_drag.py`, plus the affected AES window fixture in
`tools/test_aes_windows.py`. Cover empty/long/minimum-width titles, active and
inactive frames, odd-position and partial exposure, border/closer hit edges,
release outside, first-click topping and shell dragging. Assert unchanged
work rectangles and `wind_calc` round trips. Check register/DP restoration where
the drawing bridge changes, guards and bounded completion.

Build the integrated GUI profile at this point to expose upper-arena, code-bank
or manifest growth early. Record affected frame paint work and the maximum
uninterrupted unit; a more decorative frame must retain the existing input
service boundaries. No full GUI latency matrix is required.

Exit: ordinary native and GEM windows use the new frame and remain fully usable.
Suggested commit: `Render classic GEM window frames and left closers`.

## GA2 — Consistent menus and bundled controls

Primary areas: `lib/desktop/deskmenupaint.act`, `deskmenu.act`,
`deskappmenu.act`, `ports/gem4xe/aes/menu-render.c`, shared object-rendering
patches only where required, and bundled Files/panel resources or source trees.

1. Align native fallback/Windows menu text, selection and disabled appearance
   with the existing GEM menu rendering. Keep the current menu-bar height and
   Windows reserved area. Draw popup outlines within their allocated layer
   bounds and exclude the border from item hits without changing command IDs.
2. Preserve installed OBJECT geometry, enabled state and selected-title
   acknowledgment. Check top/bottom and side clipping so a border cannot paint
   outside its admitted area. Preserve focus-selected ownership, withdrawal,
   keyboard navigation and held-gesture cancellation.
3. Review bundled Files, GEM Control Panel, Counter and calculator using the
   new frames. Correct inconsistent application spacing/background choices in
   their source resources, maintaining work-relative layout. Keep standard
   selected/default/disabled/radio rendering and keyboard-focus marks. Reuse
   behavior that already matches the design; do not rewrite controls for style.
4. Keep object-state changes caller-local and repaint only affected objects.
   Update independent application/menu expectations and any changed resource
   fixture. Do not normalize arbitrary clients' colors or move their trees.

Run affected cases in `tools/test_aes_menus.py`,
`tools/test_gem_menu_instances.py` and `tools/test_gem_desktop.py`, with native
fallback and application menus, enabled/disabled entries, title inversion,
Tab/Shift-Tab/Space/Return, radio/default behavior and press cancellation.
Verify popup exposure repair over another window and restoration to the shell
menu. Broaden to object-renderer tests only if shared drawing changes.

Exit: menus and bundled controls share the visual conventions while preserving
their existing application semantics. Suggested commit:
`Align desktop menus and controls with classic GEM appearance`.

## GA3 — A fixed patterned desktop with correct exposure repair

Primary areas: background painting in `lib/desktop/deskpaint.act`, the small
pattern helper from GA1, its existing C/raster adapter boundary and the desktop
pixel oracles.

1. Replace the solid grey desktop fill with the design's light-grey/white
   stipple. Anchor the pattern to absolute screen coordinates using constant
   phase arithmetic; clipping and repaint order must not change the result.
   Keep title pattern phase window-relative.
2. Use bounded repeated tiles or raster strips through the current drawing
   path. Reuse existing scratch where its ownership/capacity allows; otherwise
   account explicitly for a small fixed upper/VRAM allocation. Do not modify
   live application glyphs, snapshot storage or palette entries to obtain a tile.
3. Paint only damaged desktop regions. Preserve scene/pointer serialization and
   strip completion; resume long patterned regions between existing input
   service points. Avoid per-dot calls or new periodic repaint work.
4. Extend the independent raster model to compute expected stipple from screen
   coordinates. Test several damage splits against the same complete expected
   scene, including odd X/Y edges and overlapping window/menu retirement.

Use affected cases in `tools/test_desktop_background.py`,
`tools/test_desktop_presentation.py` and `tools/test_desktop_drag.py`. Exercise
native copied moves/cache repair where eligible, AES redraw-driven moves,
outline cancellation, popup dismissal and closing overlapping windows. Observe
paint-unit cost under shell output and pointer movement; retain bounded input
service and investigate any new long unit before accepting the slice.

Exit: all exposed desktop pixels return to the same pattern, without a new
clear-then-pattern flash. Suggested commit:
`Add bounded patterned GEM desktop painting`.

## GA4 — Integrated desktop evidence and tested OF816 demo

1. Run the selected host/generator checks and affected optimized integration
   fixtures against the final inputs. Use two four-window sessions: shell,
   Files, Counter and GEM Control Panel; then the calculator scenario alongside
   the shell and other applications supported by that fixture. Do not increase
   the window or Task capacities to fit every application at once.
2. Exercise pointer and keyboard menus, window switching, title movement,
   close/focus restoration, buttons/radio/default activation and cancellation
   during Counter updates and shell/disk activity. Include resource reload and
   shutdown/collection checks already covered by the packaged walkthroughs.
3. Compare complete settled scenes to independent expectations and inspect
   intermediate strip publication for new frame/background flashes. Capture
   native-pixel and normal-display-aspect views showing active/inactive frames,
   both menu paths, controls and repaired overlap. Distinguish existing flicker
   from any new appearance regression.
4. Record matched before/after costs for affected frame/focus and control
   interactions, with the same input sequence and load. Report median/p95 and
   maximum uninterrupted presenter work for that limited comparison. Preserve
   input-service bounds and resolve new regressions attributable to these
   changes; do not interpret this as a rerun or closure of HY4/PI4.
5. Check guards, stack margins, heap/ownership return, fixed/per-Task bank-zero
   deltas, upper-memory/VRAM reservations and executable loader limits. Package
   with `tools/build_demo.py`, always including OF816, the matching system disk,
   pinned ROM and license notices. Preserve the five-second standard shell/prime
   autoboot. Execute the exact extracted ZIP with the existing desktop and
   calculator walkthroughs; distribute only boot files, short guide, notices
   and checksums.
6. Complete the history/evidence files and update the desktop reference, guide,
   plan indexes and roadmap status. Link the tested ZIP and screenshots from
   the implementation record. Keep resizing, actual client-inset changes,
   icons and editable dialogs clearly separate pending work.

Exit: the new appearance is the single current desktop implementation, with
development evidence and a tested distribution. Suggested commit:
`Verify and package the classic GEM desktop appearance`.
