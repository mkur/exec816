# MagiC window geometry execution

[Plan](../plans/gem4xe/magic-window-geometry-plan.md) ·
[Design](../plans/gem4xe/magic-window-geometry-design.md) ·
[Inputs and evidence](../development/magic-window-geometry.json)

The user authorized WG0–WG6 on 2026-11-16. MGVIEW alone is the application
acceptance target. This is development testing, without hosted qualification.

WG0 establishes one generated definition of OBJECT, TEDINFO and GRECT, with
MagiC's sixteen frame IDs, the chosen 8×8 character/16×11 box metrics, the
inline frame record and the stable drawing descriptor. Menus use the same
OBJECT as frames and the public C bindings. New geometry helpers cannot become
Task admission entries. The viewer loader and scroll observer require only
MGVIEW; the former Counter APP and process dependency is removed.

The initial gross upper allocation budget is 798 bytes per created window
(306 existing + 492 frame), before removing retired scalar fields. The pointer
table reduces the service from 11,102 to 9,284 bytes. These are record sizes,
not allocator charges. The tree and two TEDINFOs account for 440 of the frame's
492 bytes. No new bank-zero reservation, Task, signal or VRAM reservation is
introduced; fixed, root, kernel, idle and per-public-Task deltas are all zero.

WG0 validation uses `tools/test_gem_geometry.py`: a tiny C/native layout and
argument probe in raw and optimized modes, with stack guards checked by the
existing native harness. This does not build a desktop, application catalog,
QED, Counter, release image or demo.
