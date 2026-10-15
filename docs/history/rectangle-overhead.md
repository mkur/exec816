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

## RP2: changed-only mouse snapshots

One presenter-owned `AESSTATE.mouseDirty` byte replaces unconditional all-client
publication. The state module holds it so inbox/window publication can invalidate
it without introducing cyclic module dependencies. Pointer/button samples,
release after capture, loss/recovery, registration, inbox open/close, focus,
scene visibility and outer UPDATE/MCTRL transitions invalidate it. Menu state
only invalidates on a changed value. Nested lock counts retain the existing
publication boundaries without recopying unchanged snapshots.

The ordinary idle trace improves 21.358 → 20.054 ms per rectangle. Refresh is
still called at synchronization boundaries, but its CPU drops 1.902 → 0.532 ms
per rectangle; actual per-client Snapshot calls drop 3.953 → 1.000. Presenter
CPU falls 7.800 → 6.818 ms. The remaining two-client publications correspond to
the existing outer Begin/End lock transitions, not idle service passes.

Development: 145 optimized pointer assertions pass, including new stationary
focus checks, nested UPDATE/MCTRL, queued handoff, capture/release, loss recovery
and window reopening. The normal packaged rectangle run, cancellation, HELLO,
guards and EXIT pass. The independent lock-queue fixture times out after 118
checks with no assertion failures on both RP2 and the RP1 parent; original-parent
comparison remains pending before final acceptance. This is not a passing lock
qualification. The repaired Counter baseline completes at 27.8 ms/rectangle,
with visible progress, normal app closure and EXIT.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including all
reserved capacity. Static upper RAM grows by **1 byte**; linked executable bytes
increase by 818. VRAM and all stack reservations are unchanged.
