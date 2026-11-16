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

WG1 allocates each window at a stable upper address, with an inline frame and
text specifications. Six native pointer slots replace the inline windows; slot
scans admit a non-null pointer before access. Close retains storage. Delete
withdraws both lookup entries after existing synchronous physical work and route
retirement, then frees the allocation. Queued manager targets remain identity/
epoch/endpoint records, with no Window pointer or manager-drain wait under UPDATE.

The optimized storage fixture passed 77 checks: hidden/current-empty defaults,
kind links, owned strings, one/two live allocations, allocation failure after
consuming 58 free heap extents, and complete reclamation. The 798-byte window
charges **800 bytes** after allocator rounding; two charge **1,600 bytes**. The
service is **9,284 bytes**. Guards passed. Reserved bank-zero growth is zero
for fixed, root, kernel, idle and each public Task. Rendering and query consumers
still use temporary legacy projections until their planned cutover.
