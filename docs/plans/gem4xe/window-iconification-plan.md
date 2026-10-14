# Window iconification implementation plan

[Design](window-iconification-design.md) · [GEM plans](README.md)

Status: IC1–IC3 implemented and development-checked, 2026-10-14.
[Results and memory accounting](../../history/window-iconification.md).

## IC1 — state, geometry and lifetime

Add saved normal bounds and iconified state to the generated desktop record.
Implement presenter iconify/restore/forget operations using existing Layers.
Keep AES geometry and open lifetime stable, publish no visible rectangles for
tiles, restore on WF_TOP and accept saved geometry changes while iconified.
Preserve Shell output/model damage and backing; suppress tile cache capture,
application painting and caret. Close, HIDE, delete and exit release tile state.
Use existing lock/DMA admission and identity checks only.

Completed: generated window records grow by ten bytes each. Shell retains
model damage while iconified; AES reports normal geometry and an empty visible
region. Native and AES lifecycle/geometry checks pass in emitted code.

## IC2 — frame, tile and menus

Draw the iconify gadget and compact labeled tiles in the current compositor.
Capture press/release through DESKDRAG, including cancellation and deferred
commit. Add Iconify to the native menus, list iconified windows with `* ` and
restore them on selection. Keep normal cycling and focus restoration off tiles.
Increase native menu capacity to nine; update independent pixel models.

Completed: title gadget, tile press/release and both native menus restore
windows without application changes. Exact packaged-demo pixels cover normal
restoration and recovery when all ordinary windows are iconified.

## IC3 — development checks and demo

Run host tests and generated-layout checks. Exercise emitted optimized desktop
code with Shell and AES clients: iconify and restore exact bounds, hidden model
updates, no input leakage, tile/menu recovery, release-outside/Escape, focus,
close/exit and slot reuse. Cover generated record access in a small raw/opt
probe if the existing layout fixture cannot isolate it. Preserve guard and
ownership checks. No compiler test suite or full qualification matrix.

Refresh the OF816 desktop demo through tools/build_demo.py with matching disks,
pinned ROM, notices and five-second autoboot. Exercise the exact packaged image
with real pointer and keyboard input, including Shell output and Counter timers
while iconified. Record actual test scope, memory delta and remaining limits;
provide the ZIP and launch command. Update desktop/AES contracts and indexes.

Completed: 459 host tests (four existing skips), 113 layout/access checks in
each raw/optimized build, 362 optimized native checks and 280 optimized AES
checks plus four native fixture checks. Both walkthroughs of the final OF816
ZIP pass, including hidden Counter/Shell progress and clean EXIT. Bank-zero
and VRAM reservations are unchanged. These are development checks, not release
or hardware qualification; the results record the exact scope and artifacts.
