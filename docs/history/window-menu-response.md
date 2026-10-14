# Window and menu response work

[History](README.md) · [Implementation plan](../plans/gem4xe/window-menu-response-plan.md) ·
[Gadget atlas plan](../plans/gem4xe/frame-gadget-atlas-plan.md)

2026-10-14. Development work in progress; no hardware qualification claim.

## UI1 Menu state and folder focus

Folders raise through their ordinary `WM_TOPPED` handler before publishing menu
changes. Files compares each desired enable/check bit with its shared installed
tree and calls AES only when that bit differs. The obsolete per-folder menu
mask is removed. AES accepts repeated enable/check values without damaging the
object or advancing `menuRevision`. Menu normalization still acknowledges
selection, and text setters retain their normal behavior.

The desktop application builds with its emitted Browser layout probe, and the
five desktop contract host checks pass. The optimized menu fixture adds
unchanged/changed enable/check revision assertions alongside its existing
physical interaction and durable acknowledgement checks. All seven physical
phases pass, including independent menu pixels, disabled/replaced menus and
normal exit/ownership checks (`build/window-menu-response/ui1-menus`).
The pinned compiler's release build is used
for the runtime check; an initial slow debug-compiler invocation was stopped
before execution.

Memory: **0 fixed, 0 per-public-Task and 0 idle reserved bank-zero bytes added**,
including guards, alignment and unused capacity. Each Browser loses two bytes
of upper-RAM state. No VRAM reservation change in UI1.

## UI2 Initial folder title

Files publishes the known path before `wind_open`; directory enumeration only
updates the summary/content. Navigation still publishes an actually changed
path. The initial-frame observer now expects four batches for the new window,
without the former fifth path-title repaint.

The desktop application and emitted Browser layout probe pass in
`build/window-menu-response/ui2-desktop`. Physical open/navigation and timing
checks are shared with the final packaged-image pass. Reserved bank-zero delta:
**0 fixed, 0 per public Task, 0 idle**, including guards/padding/capacity. No
persistent data or VRAM reservation is added.

## GAT1 Immutable gadget atlas

Seven existing marks are packed at build time in even/odd X phases. Extraction
records the asset, generator, VRAM map and generated-header hashes. A display
session uploads the 2,688-byte atlas before enabling presentation, using the
existing failure cleanup and upload path. Drawing remains procedural in GAT1.

Two host checks compare both packed phases with the independent procedural
frame raster and verify deterministic generation/storage bounds. The optimized
`tools/test_frame_gadgets.py` fixture passes ten assertions: upload readback,
normal close/reopen, adjacent VRAM sentinels, injected upload failure and
successful reopening afterward. Normal ownership/context/stack checks pass;
results are in `build/window-menu-response/gat1/results.json`.

The atlas reserves **4,096 VRAM bytes** at `$39000–$39FFF`, including 1,408 bytes
unused by the images. Totals are 420,352 reserved and 103,936 unassigned VRAM
bytes. Its immutable source pixels occupy 2,688 bytes in the existing upper
table bank. Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle**,
including guards, alignment and unused capacity. No CPU staging buffer is added.
