# Editable dialogs implementation plan

[Design note](editable-dialogs-design.md) · [GEM integration](README.md)

Status: planned; follows the window gadgets and Files scrolling milestones.

| Slice | Implementation | Development gate |
| --- | --- | --- |
| ED1 | Caller-local editing, form traversal, clipped text/caret rendering and editable RSC capacity | Host/resource tests, raw/optimized context-layout probe, focused emitted edit behavior |
| ED2 | Files Path/New Folder/Rename trees and event-loop integration | Disposable-media success/error/cancel, keyboard/pointer, overlap and lifetime checks |
| ED3 | Integrated desktop and OF816 distribution | Exact ZIP walkthrough, checksums, current docs and compact evidence |

Commit each passing slice. Keep donor changes reproducible through extraction
patches. Update public declarations, aes_call dispatch and loadable-GEM exports
together, rebuilding applications against the single current ABI. Do not add
a compatibility profile or a second event-loop service.

Use existing optimized object and desktop fixtures for behavioral checks;
raw/optimized runs are limited to changed shared contexts/layouts. Independent
pixel expectations must cover caret clipping and redraw after exposure. Test
Files with more entries than fit, size changes, dialog cancellation and a live
child beside the other demo applications; retain the four-window/eight-Task
capacity. Record exact memory/stack costs and **zero reserved bank-zero delta**
for every slice. Keep generated intermediates outside the distributed ZIP.
