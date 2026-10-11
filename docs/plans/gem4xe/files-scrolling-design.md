# Files: adaptive list and continuous scrolling

[GEM integration](README.md) · [Implementation plan](files-scrolling-implementation-plan.md)

Files becomes the first application of the [window gadgets](window-gadgets-design.md).
It owns a directory snapshot, selected filename and first visible row. The AES
owns only geometry, clipping and input delivery. Scrolling never re-enumerates
the directory and does not perform disk I/O for each pointer gesture.

Allocate one upper-heap array for at most 256 entries (name and file kind).
Directory enumeration runs at open, navigation and Refresh, releases its lock,
and reports enumeration errors or truncation in the status line. This explicit
capacity is sufficient for the current desktop and avoids an unbounded allocator
or filesystem iterator surviving namespace mutations. Retain selection by exact
filename during refresh; clear it if absent or when changing directories.

The window uses SIZER, UPARROW, DNARROW and VSLIDE. Its OBJECT tree has sixteen
reusable row objects, with unused rows hidden. Work width sets row width and
label truncation; work height sets the number of complete twelve-pixel rows.
Keep a small header with File, Up and Refresh, and a bottom status line. Clamp
accepted sizes to a useful application minimum and the available screen.
Recompute layout from WF_WORKXYWH after movement/resize; retain selection and
clamp the first row. Keyboard up/down scrolls selected items into view.

WM_ARROWED moves by one row or one visible page. WM_VSLID maps 0..1000 to the
valid first-row range. Publish WF_VSLSIZE from visible/total rows and WF_VSLIDE
from first/max-first, using a full thumb and position zero when everything fits.
Use widened arithmetic only on state changes. No rendering loop performs disk
enumeration or a proportional conversion per object.

Repaint only through the existing visible-rectangle/object drawing path under
BEG_UPDATE. Geometry acknowledgment triggers ordinary WM_REDRAW. Selection and
scroll changes redraw the current work area; partial object optimization is
deferred until a measurement warrants it. Existing launcher, menu, child Stop
and cooperative cleanup semantics remain unchanged.

Bank-zero reservation delta is **0 fixed, 0 per public Task and 0 private idle**.
The entry array is explicitly allocated/freed by Files; report its exact upper
heap cost and application image size. Test more than one visible page, scroll
endpoints, shrink/grow, selection refresh/removal, empty/error/truncated lists,
overlap repair, launching and child cleanup. The combined OF816 desktop test
retains shell, calculator/counter/panel coexistence within four window slots.
