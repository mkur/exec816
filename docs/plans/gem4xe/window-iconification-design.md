# Window iconification

Status: implemented, 2026-10-14. [Plan](window-iconification-plan.md) ·
[Development results](../../history/window-iconification.md).

Shell and every ordinary desktop window need a reversible way to get out of
the way without closing their application. The presenter owns that operation,
as it already owns frames, stacking, keyboard routes and the Windows menu.
Application tasks, handles, timers and models keep their existing lifetime.

## Interaction

A small outlined iconify gadget sits at the right of the title, immediately
left of the fuller when present. Its mark is a small window with a filled
lower corner, distinct from close and full. Frames narrower than 64 pixels
use the menu instead. The active-window menu and Windows menu offer Iconify;
Shell retains its disabled Close command. The borderless desktop is excluded.

Iconification replaces the window with an 88 by 16 pixel labeled tile at the
bottom of the desktop. A miniature window glyph identifies the tile; its short
label is clipped, while Windows retains the fuller title prefixed with `* `.
Each existing window slot has a fixed tile position, starting at x=104, y=222;
six slots end at x=632. This avoids the desktop's left icon column and needs
neither another layer nor an allocator. The tile may be covered by another
window; Windows always remains a recovery route. A click and release in the
tile restores the window. Release outside, Escape and lost input cancel.
Ctrl+Tab cycles ordinary windows, leaving iconified windows asleep visually.

Restore returns the exact accepted outer rectangle, raises the window and
restores keyboard focus. Iconify restores focus to the nearest ordinary shown
window. A tile never receives application keyboard or pointer input. Closing
or exiting an iconified application removes its tile and releases resources
through the existing teardown. There is no extra task, signal or wait loop.

## Application contract

This is Exec816 presenter policy, not an implementation of the later GEM
WM_ICONIFY/WF_ICONIFY negotiation. Existing GEM applications require no new
message handler. Their window handle, open epoch, kind and reported normal
geometry remain unchanged; visible-rectangle enumeration is empty while
iconified. Thus normal timer-driven updates change the model without painting
over the desktop. `WF_TOP` also restores an iconified window. A programmatic
geometry change while iconified updates its saved normal rectangle. Native
SHOW/RAISE/FOCUS restore; HIDE and close remove the tile.

The presenter stores the normal rectangle and one iconified byte in each
existing window record. The Layers rectangle describes only the currently
visible representation. AES publication explicitly separates these two facts.
No synthetic WM_MOVED or WM_SIZED is sent merely because a tile was created.
A real restore exposes the current model through the ordinary redraw/cache
path. Completed AES snapshots remain reusable unless the application changed
its model while iconified; existing update revision tracking invalidates them.
Shell keeps its retained text model and its fixed backing allocation. Hidden
output is allowed to accumulate model damage; restore updates the backing
before copying it to the screen. It must never mark that damage clean merely
because the tile was painted.

## Ordering and costs

Commit only at the existing native-ready boundary: no scene paint/read/move,
DMA, console scroll batch, AES UPDATE/MCTRL owner, or outstanding lock/window
mutation. Input holds a stable window identity until this boundary. Resolve it
again before committing; close/reuse cannot target a new occupant. Keep the
existing release and input-loss protocol. Do not add pointer or geometry
validation to inner drawing loops.

Reuse the existing strip compositor for tile and gadget pixels. Exclude tiles
from snapshot capture and application repaint delivery. Restore invalidates
the appropriate client area before ordinary repaint. The popup capacity must
cover six windows plus Next, Close and Iconify (the borderless desktop normally
occupies one slot); reserve nine rows so non-desktop fixtures also fit.

Bank-zero reservations: fixed +0, each public Task +0, idle +0. No VRAM growth.
The desktop heap grows by the generated per-window field cost; static menu
storage grows by three item records. Record emitted sizes and stack margins
with development results. No application ABI, compiler pin, scheduler or
kernel service change is needed; the private native desktop record version
changes and all resident code is rebuilt.

Movable tiles, application-supplied tile art, task suspension, saved desktop
positions and standard negotiated GEM iconification are outside this slice.
