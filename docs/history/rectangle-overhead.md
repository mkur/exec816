# Rectangle overhead

[Plan](../plans/gem4xe/rectangle-overhead-plan.md) ·
[Measurements](../development/rectangle-overhead.json) ·
[Display contract](../reference/display.md)

## RP1: reserve actual drawing units

The presenter no longer reserves physical display access for an entire service
turn. Existing `GemDrawing*` entries protect pointer/caret/outline operations,
text and frame batches, widget callbacks, cache copies and completion retirement.
Each callback and its command list remain protected through the fence. Widget
continuations flush and clear strip redirection before releasing; borrowers do
not use their retained private VRAM strip. Native BUSY retains pending work;
the existing owner queue/wake retries it. Async launch retains the DMA pin and
Poll can retire it while a borrower waits. No kernel, scheduling or IRQ change.

The matching current parent uses the icon-cache package from `3ff76d7`, rather
than the older pre-merge measurement. Its untraced rectangle batch median is
24.4 ms. Passive captures measure 24.080 → 21.358 ms elapsed per rectangle;
presenter CPU falls 9.692 → 7.800 ms. The candidate capture observes no owner
entry/drop during these idle rectangle intervals: CPU-only service no longer
reserves the renderer. These are three batch averages, not latency percentiles.
Loaded results and final untraced comparison follow in RP5.

Development checks: 66 optimized arbitration assertions including nesting,
FIFO/BUSY retry, DMA pin and fault revocation; two renderer borrowers beside
native output/pointer work, 48 completed borrows, one asynchronous copy, zero
overlap and 2,788 checked pixels; quiescent and unquiesced fault cleanup. The
fixture now observes both async scroll and CopyStart (the current console uses
the latter). Its first run failed the obsolete scroll-only copy counter, with
pixels and ownership intact. Six passive-trace host tests pass. The packaged
rectangle run cancels later rows with Escape, closes normally, runs HELLO and
returns through EXIT with guards intact. No full qualification claim.

Reserved bank-zero delta: **0 fixed, 0 for each of eight public Tasks, 0 idle**,
including guards/alignment/spare capacity. Upper static data and VRAM reservations
are unchanged; linked executable bytes fall by 275. No stack capacity changes;
observed headroom above the interrupt reserve is at least 313 bytes for active
application Tasks, 1,427 for the presenter and 194 for idle in this capture.
