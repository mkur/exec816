# Desktop menu and window switching

Status: DW1–DW3 implemented; development checks pass. See the
[execution record](../../history/desktop-menu-window-switching.md) and
[machine-readable evidence](../../development/desktop-menu-window-switching.json).

## Scope and decisions

Keep this first desktop menu in the existing presenter. A persistent 16-pixel
bar shows the active window's name. Its menu offers Next window and Close;
Close is disabled for the shell. A Windows menu lists all shown application
windows, including covered ones and the shell. Selecting an AES window uses
its existing `WM_TOPPED`/`WF_TOP` path; Close uses `WM_CLOSED`. Native windows
use their existing focus and close notices. No application changes or new RPC
are needed. This is desktop-owned chrome; application-defined `menu_bar` trees,
`MN_SELECTED`, accessories and cascading menus remain a later GEM API slice.

Use two ordinary opaque Layers for the bar and its bounded four-row popup.
Keep four application-window slots. Increase Layers capacity to six, retaining
96 region rectangles: at most 13 horizontal endpoint bands and seven free
intervals per band give a conservative 91-piece bound for six rectangular
occluders. The topmost chrome participates in normal visibility and damage, so
applications cannot overwrite a menu and closing it repairs the exposed area.
Keep snapshots and gesture state in upper memory; the desktop arena grows by
256 bytes, while the service allocation grows by 1,706 bytes (1,712 rounded).
The integrated image also occupies one additional 64 KiB upper bank ($1E).
There is no saved-under framebuffer,
new Task, timer, signal, task-stack or direct-page reservation.

Pointer presses/releases belong to the menu until release, including outside
cancellation. Escape and capture loss cancel. Disabled entries do nothing.
While open, menu input stays out of application input queues. Ctrl+Tab and
Ctrl+Shift+Tab cycle shown windows in stable slot order; Ctrl+Escape opens the
Windows menu, with arrow/Tab navigation and Return selection. Existing mouse,
update, display and scene ownership gates still apply. Hold only window IDs
and copied labels across presenter turns, never borrowed application pointers.

Closing/hiding the focused window restores focus to the frontmost remaining
shown, routable window; closing a background window preserves focus. Retired
AES input epochs cannot become restoration targets. New window identities make
stale menu entries harmless. Dragging leaves the title below the menu bar when
the window's height permits it to fit below the bar.

## Executable slices

1. **DW1 — focus restoration.** Share one frontmost-window selection policy
   between native hide/close and AES close/retirement. Exercise background close,
   last-window close and keyboard delivery to the restored owner.
2. **DW2 — desktop chrome and input.** Add the bar/popup, bounded drawing,
   pointer and keyboard actions, six-layer capacity and generated layouts.
   Update independent scene composition and focused emitted geometry checks.
3. **DW3 — integrated usability and packaging.** Exercise switching to a fully
   covered Counter, shell/app switching, popup cancellation, disabled Close,
   close restoration and window-slot reuse. Run host checks and focused emitted
   checks, then build and test the OF816 GEM desktop ZIP and document results.

For each slice report fixed/per-public-Task/private-idle bank-zero reservation
changes (target: **0/0/0 bytes**). Measure upper-memory growth and stack margins
from the actual build. Use development-tier checks, not a full qualification
matrix. Keep the standard five-second OF816 shell/prime default unchanged.

## Acceptance

All four windows remain reachable without dragging another window aside. The
bar follows focus, Close reaches only its captured owner, and closing the active
window leaves a useful keyboard target. Menu pixels survive concurrent counter
updates and shell output; dismissal matches independent full-scene composition.
No guard corruption, stale input delivery, resource leak or reservation growth
in bank zero. Existing Control Panel settings, Files and calculator remain
compatible. No latency or flicker-closure claim without their separate gates.

## Results

The extracted OF816 GEM desktop ZIP passes physical menu/keyboard switching,
covered-window selection, focus restoration, window-slot reuse, held-gesture
cancellation, independent pixel composition, Control Panel settings, Files
launch/Stop, shell/pipeline, heap collection and EXIT/OS restoration. Focus and
Layers emitted-code checks, raw/optimized layout probes, and 417 host tests
(four historical-source skips) pass. Every slice reserves **0 additional fixed,
0 per-public-Task and 0 private-idle bank-zero bytes**. The smallest observed
public-Task stack margin is 33 bytes above the 256-byte interrupt reserve.
This is development coverage; the existing latency/flicker gates remain open.
