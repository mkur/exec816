# Resizing and vertical window gadgets

[GEM integration](README.md) · [Implementation plan](window-gadgets-implementation-plan.md)

Extend the existing hybrid AES window contract. The presenter owns frame
geometry and pointer gestures; the application accepts size requests, owns its
scroll position and paints its visible work area. No new Task, timer, signal or
kernel service is needed. GEM message numbers and fields follow the donor's
`src/aes/aes.h`; this is source compatibility for rebuilt applications.

## Geometry and requests

Keep the existing NAME/CLOSER/MOVER window profile, with optional SIZER,
UPARROW, DNARROW and VSLIDE bits. Unsupported bits remain an admission error.
Existing fixed windows and the shell retain their current work insets. A
vertical gadget adds a 16-pixel right strip; SIZER adds a 16-pixel bottom strip.
The shared geometry constants drive work queries, clipping, painting and hits.
Scrollable windows have an 80-pixel minimum height, leaving arrows and a usable
track; sizeable windows have a 64-pixel minimum width and 48-pixel minimum height. Applications may impose
larger minima when accepting WM_SIZED. Bounds stay on screen.

Dragging the lower-right size box uses the present nonblocking XOR outline.
Release sends WM_SIZED with the proposed outer rectangle. Only the owner's
WF_CURRXYWH changes geometry. Resize damages old and new bounds through Layers,
updates the visible-region snapshot, and invalidates any previous redraw walk.
No scene/display token survives the application's decision. Fixed windows
continue to reject dimension changes.

WF_VSLIDE and WF_VSLSIZE are 0..1000 values, initially 0 and 1000. A thumb is at
least eight pixels; its travel is the track minus its size. Cache its pixel
geometry at mutation, keeping division out of repeated frame painting. Query
values remain application values, not rounded pixel reconstructions.

Arrow release sends WM_ARROWED with WA_UPLINE/WA_DNLINE in word 4. Track release
sends WA_UPPAGE/WA_DNPAGE. Thumb dragging sends one WM_VSLID on release, with a
0..1000 position. This bounded first version has no hold repeat or live content
scroll. The application updates its scroll state and WF_VSLIDE in response.
Coalescing retains the existing last-pending-value rule for each message kind;
separate kinds cannot overwrite one another. There is no delivery-count promise
for a client that does not consume messages.

## Painting and ownership

Flat black/white boxes, arrow glyphs, a grey track and an outlined white thumb
use the existing complete offscreen frame fragments. No clear-then-draw path,
new framebuffer or arbitrary application callback is introduced. The thumb
drag outline uses existing XOR storage and is erased before ordinary painting.
First press on an inactive gadget requests topping only. Release outside
cancels arrows; Escape, input loss, geometry changes, close and retirement
cancel captured gestures. GUI locks retain their existing serialization.

Publish trusted geometry once. Preserve operational failures and ownership
transitions, without repeated object or geometry audits in rendering. New
window/notice fields use upper memory. Reserved bank-zero delta is **0 fixed,
0 per public Task and 0 private idle**, including guards and spare capacity.
Horizontal scrollbars, full/iconify gadgets, shell resizing and live resize
are outside this slice.

## Evidence

Focused raw/optimized probes cover changed shared layouts. Optimized window
tests cover geometry round trips, independent visible rectangles, resize repair,
slider endpoints and application acknowledgment. Physical tests cover topping,
size/slider release, arrows/pages, cancellation and unchanged geometry before
acknowledgment. Preserve guard/ownership checks. Files will exercise these
gadgets in the following milestone; the final combined demo must include OF816.
