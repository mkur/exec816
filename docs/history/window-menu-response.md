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

## GAT2 Title gadget copies

Close, full-size, iconify and iconified-tile marks now append atlas records to
the existing frame batch. The helper clips once, selects the original X phase
and maps either ordinary or compact scratch coordinates. Aligned opaque images
use one copy; partial packed bytes retain their neighboring pixels. No separate
admission, upload or fence is added per gadget.

The optimized atlas fixture passes 20 assertions and five independent full-screen
pixel comparisons: active and inactive titles, odd X, clipped marks, Shell's
title and an iconified tile (`build/window-menu-response/gat2/results.json`).
The fixture supplies explicit clip coordinates; an initial Calypsi 5.18 local
struct-expression build produced incorrect stack loads for derived clip bounds.
No production renderer change was made to accommodate that fixture issue.

The seven descriptors add 42 bytes of immutable upper-image data. Reserved
bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including guards/padding/
capacity. GAT2 uses GAT1's VRAM page without further reservations.

## GAT3 Scrollbar and resize copies

Arrows and the resize grip use the same atlas helper; tracks, thumbs and shared
separators retain their existing solid fills. The optimized fixture passes
36 assertions and nine independent full-screen pixel cases, including both X
phases, full scrollbars, clipped marks, a 240-row compact fragment with scratch
canaries and a subsequent ordinary title batch. Ownership and stack checks pass
(`build/window-menu-response/gat3/results.json`). Renderer and whole-interaction
measurements follow in the combined packaged-image observations.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards, alignment and unused capacity. No further VRAM or persistent state is
reserved.

## UI3 Bounded menu continuation

A completed foreground save/restore retires before unrelated control admissions.
Ready menu strips continue within the worker's existing four-step allowance,
with input between units and unchanged control/output budgets. The existing
two-menu-transaction fairness rule remains. Idle captures use their old path.
No additional hardware polling, completion identity, Task or priority is added.

The optimized menu fixture passes its seven physical phases, acknowledgement,
menu replacement, disabled entry, ownership and guard checks
(`build/window-menu-response/ui3-menus`). The passive observer now records
C call returns and native completion/continuation boundaries, separating Task
CPU charge from elapsed time. The observed baseline View transition has about
8 ms from blitter IRQ completion to polling; this alone does not justify an
extra immediate probe. Combined latency acceptance follows in UI5.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards/alignment/capacity. No additional persistent state or VRAM is allocated.

## UI4 Plain menu-row selection

Clean, fully visible application popups invert up to two disjoint plain enabled
rows in one synchronous admitted batch. Eligibility is limited to ordinary
white menu paper and unadorned `G_STRING` children inside the border, at most
16 scanlines high. Source changes, unfinished pixels and other styles retain
normal painting. The existing selection becomes committed only after the paint
transaction finishes; failed drawing retains ordinary damage, not an XOR retry.
No glyph rendering, staging upload or popup-cache mutation occurs in this path.
The private widget operation adds a constant, without changing packet layout.
Native fallback menus keep their normal row renderer.

The optimized physical menu fixture passes all seven phases. Added independent
pixel comparisons cover A→B→A, repeated input without a second inversion, entry/
exit and both odd packed edges. The fixture observes exactly four inversion
batches for four changes. Its existing checked/disabled long-label, replacement,
cache reopen, keyboard and cleanup cases pass as well
(`build/window-menu-response/ui4-menus/results.json`). Generated widget
definitions and the focused widget contract host checks pass.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards/alignment/capacity. No persistent selection storage, new CPU staging or
VRAM reservation is added; the existing widget packet carries two rectangles.
