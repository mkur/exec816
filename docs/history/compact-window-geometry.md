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
