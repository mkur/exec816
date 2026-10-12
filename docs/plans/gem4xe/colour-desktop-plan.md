# CG3 implementation plan

[Design](colour-desktop-design.md) · [Roadmap](../../roadmap.md#colour-gem-desktop-roadmap)

Status: implemented; focused development checks pass. This is not release qualification.

1. Separate presenter window records from client registrations. Extend generated
   window views and the caller context to track several handles. Update mutation,
   snapshot, locks, GUI delivery, input, menu selection and exit together.
2. Raise bounded scene/window capacity to eight layers/six client windows.
   Implement the borderless desktop role using existing layer ordering,
   redraw and input, with no extra kernel operation or display worker.
3. Reuse Files' window logic in one desktop event loop. Give each directory an
   independent snapshot and tree; share menu, workstation and stock resources.
   Add volume/launcher background icons and New Window. Preserve ordinary
   FILES.APP use and the shell's standard startup profile.
4. Run emitted two-window ownership/epoch/visibility checks and an OF816 desktop
   walkthrough: open/resize/scroll/close two folders, switch to another client,
   close all folders and use the background/menu again. Record memory, stack,
   redraw latency and remaining unsupported behavior.

The [development record](../../development/colour-gem-cg3.json) includes 68
multi-window checks, 141 pointer checks, 398 input-event checks, 102 GUI checks,
252 window/gadget checks and 60,043 layer checks. Raw and optimized native
context/layout runs each pass 1,081 checks per client. The enlarged fixture's
assembly probe now takes its bank from the linked symbol rather than assuming
bank $0C; no production ABI workaround was added.

The packaged walkthrough covers independent paths/trees, resize, full/restore,
scrolling, closing all folders while Counter survives, background/menu reuse and
clean shell exit. Background selection repaints only the previous and new icon
cells; selecting the same icon again adds no repaint. Full-screen pixel checks
also cover the selected background icons.

Reserved bank-zero deltas are **0 fixed, 0 per public Task, 0 idle**, including
guards, alignment and unused reservation. The upper-memory layer scene grows
from 6,790 to 8,496 bytes. Each open window view is 806 bytes; a caller context
is 368 bytes. A desktop folder owns a 3,861-byte model, 28,672-byte directory
snapshot and 504-byte object pool. Resources, menu, workstation and event port
are shared. The desktop model is 2,128 bytes; no per-window Task is allocated.
