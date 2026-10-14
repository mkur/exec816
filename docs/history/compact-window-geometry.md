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
