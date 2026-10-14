# Compact window geometry

[Plan](../plans/gem4xe/compact-window-geometry-plan.md) ·
[Machine-readable evidence](../development/compact-window-geometry.json)

## CF1 — independent dimensions

Gadget width and height now have separate generated constants. Menu and tile
metrics use the same machine-readable definition. Drawing, hit testing,
scrollbar geometry, work-area conversion and menu bounds consume these metrics;
the old single gadget constant is removed. Displayed dimensions are unchanged
in this slice.

Development checks pass: 459 host tests (four existing skips), 362 optimized
native desktop checks, and 117 optimized presentation checks across nineteen
independent full-screen pixel scenes. The record layout is unchanged; no raw
compiler-facing probe or compiler test suite was needed. Builds select the
release host compiler at the unchanged recorded pin.

Reserved bank-zero change relative to the iconification build is **0 fixed /
0 per public Task / 0 idle bytes**, including guards, alignment and unused
capacity. VRAM growth is zero. This is development evidence, not release or
hardware qualification. CF2–CF4 remain pending.

## CF2 — compact frames and preserved content

Frames now use eleven-row titles and 22×11 gadgets. Plain bottom borders are
two rows, SIZER eleven and INFO ten. Short, wide marks preserve the distinct
closer/full/iconify actions. Iconify admission reserves the actual controls
and one text cell; fixed FULLER windows now require width 44.

Shell retains its 64×20 model and 512×160 backing, with the original text
origin (40,40). Its initial outer rectangle is (32,29,528,173); movement aligns
the text origin. Iconified tiles are 88×11 at y=227. The optional retained
native panel still has a 176×120 client area. No icon artwork or fonts changed.

Development checks: 459 host tests (four skips), 362 optimized native checks,
117 presentation checks over nineteen complete pixel scenes, and 280 C plus
four native AES window checks. The AES run checks the complete scrollbar
strip, arrow/page events, thumb endpoints, deferred resize/move, cancellation,
and hidden move/restore. Independent widget roots and input coordinates were
updated for the accepted work geometry. Both native-panel/Shell retirement
orders pass with exact recomposed pixels, including keyboard interaction and
output behind the panel. The same presentation fixture has 549 more Action!
code bytes and unchanged static data; reserved pools are unchanged.

Reserved bank-zero delta is **0 fixed / 0 per public Task / 0 idle bytes**;
VRAM growth is zero. No record or language bridge layout changed. Menus remain
sixteen rows until CF3.

## CF3 — menus and application layout

The bar and native popup rows are eleven pixels high. Bundled application
menus use matching coordinates; custom caller-owned dropdown rows retain their
own sizes. The native hit/paint lookup uses at most nine subtractions instead
of division. Popup continuation states no longer collide with cache-transfer
states when an eleven-row entry straddles a sixteen-row paint strip.

AES reports desktop work (0,11,640,229). Default Files is 462×196, preserving
its 432-pixel client width; full/restore, folder cascades, the borderless desktop
and standalone forms use the reported geometry. Temporary form windows also
include the complete root border when their left edge rounds to even X.
Application icons and fonts are unchanged.

Development checks pass: 459 host tests (four skips), 291 optimized C menu
checks plus four native checks, and 198 C form checks plus four native checks.
The menu run includes seven exact pixel states, native highlights/border hits,
long/checked/disabled/custom rows, cached reopening, pointer/keyboard selection,
owner changes and cancellation. Forms include 35,332 independently checked
pixels, editable fields, borrowed/owned windows, fault cleanup and retirement.
Guards remain intact and both fixtures return cleanly to the OS.

Reserved bank-zero delta is **0 fixed / 0 per public Task / 0 idle bytes**;
VRAM growth is zero. Record layouts and the compiler pin are unchanged. CF4
checks the matching packaged applications and records final image size.

## CF4 — integration and final evidence

The focused native suite now has 377 checks, including boundary pixels for
narrow titles and optional iconify admission. The AES suite has 285 C plus
four native checks, including the 44-pixel FULLER minimum and the 197-row
maximized INFO work area. The presentation suite passes 117 checks over
nineteen exact complete-screen scenes. Host checks pass: 459 tests, four skips.

The packaged geometry walkthrough checks default Files at 432×174, all sixteen
32×16 icons in 104×32 objects, full/restore at 610×207, a smaller 2×2 layout,
multiple folders, path editing, selection and a physical drop into RAM:.
`CMP` confirms the copied bytes. A clean move causes zero client repaints;
four File/View transitions cause zero client repaints and zero background
recaptures, while restoring the saved background each time.

Shell reaches outer rectangles (0,13,528,173) and (112,61,528,173), keeping its
text aligned at both screen limits. Exact pixels pass for covered output,
scrolling, caret, moves, iconification and restoration. Counter keeps ticking
while iconified; tile cancellation, Windows recovery, reused slots, disk
commands and orderly EXIT pass. Nineteen packaged scenes were compared against
independent models. A 640×480 presentation of the raw 640×240 image confirms
square displayed controls; font and icon pixels are unchanged. `DESKTOP.RSC`
is byte-identical to the iconification baseline.

The integration check found that Control Panel's old outer height left eleven
unpainted client rows below its fixed tree. It now uses `wind_calc` to size the
outer window from its 192×136 tree: 208×149, with no extra layout machinery.
Its standalone image grows by 105 bytes. The Calculator adapter also now adopts
its accepted work rectangle and OBJECT root after a cached move; previously it
relied on a later redraw, leaving button hit coordinates behind. The integration
probe moves it and enters 7×6=42 through physical button clicks. The calculator
image grows by 75 bytes.

The final package rebuild changes Panel, Calculator, the build banner and guide.
All 1,836 native routines, the shared C runtime and the remaining application
binaries are unchanged from the geometry walkthrough. Both package hashes are
recorded separately.

The final ZIP walkthrough passes eleven independently recomposed scenes:
Panel mouse/keyboard input after moving, Calculator arithmetic after moving,
Text load/content hash, copied movement and scrolling, file-selector cancel,
Counter timer progress, client close restoration, a disk command and EXIT.
Both packaged runs retain intact guards, positive interrupt headroom and zero
live Tasks at return. The lowest public-Task margin in the geometry run is
183 bytes, and 97 bytes in the application run; the full per-slot observations
are in the evidence record.

The same presentation fixture uses 1,099 more Action! code bytes and 169 more
C image bytes than CF1, with unchanged Action! static data and C BSS. CF3's
portion is +550 Action! / −3 C bytes. Reserved bank-zero delta is **0 fixed /
0 per public Task / 0 idle bytes**, including guards, alignment and unused
capacity; the complete memory budget and Task pools compare equal. VRAM delta
is zero. There are no record-layout, compiler-pin or kernel ABI changes.

Reproduce the focused packaged checks with:

```sh
python3 tools/test_compact_window_geometry.py --bundle build/compact-window-geometry/demo
python3 tools/test_cache_desktop.py --bundle build/compact-window-geometry/final
```

The final OF816 ZIP and local launcher are under
`build/compact-window-geometry/final/`. The build uses `tools/build_demo.py`,
the pinned ROM and unchanged compiler revision with the release host compiler.
The five-second autoboot, SYS/WORK media, licenses and checksums are retained;
intermediates and diagnostic images stay outside the ZIP. This is focused
emulator development evidence, not hardware or release qualification.
