# Native console device

[Reference index](README.md) · [Console example](../guides/console-example.md)

One console worker serves the default console and additional instances.
It retains cells, accepts output, routes input and updates one shared display.
The normal text backend admits 40×24 cells. The optional bitmap backend admits
80×30 on the pinned 640×240 VBXE display. An instance adds upper-RAM state,
not a Task, stack or DP. The backend is selected before startup; live conversion
is unsupported.

## Public interface

`CONSOLE.ScreenWidth()` and `ScreenHeight()` return the active display capacity
in cells when the worker is ready and accepting work, and zero while stopped,
starting, stopping or after failed startup. The text backend reports 40 and 24; the bitmap backend reports 80 and 30.
A terminal bitmap display fault also makes these queries return zero.
Instance creation and Show use these capabilities rather than the model maximum.

Open `console.device` with unit zero for the default instance or an opaque
[instance identity](console-windows.md), and flags zero. Use the standard Exec
[device I/O contract](device-io.md) and full IOStdReq record. READ, WRITE and CLEAR
are supported; io_Actual reports transferred bytes. `CONCMD_WRITE_AT=9` writes
a printable ASCII span within one row using the same FIFO as CMD_WRITE. Its
io_Offset packs the zero-based column in the low 16 bits and row in the high
16 bits. It preserves the stream cursor and marks only the edited span. Invalid
coordinates, a span crossing the row edge or control bytes fail before any edit.
Zero-length writes are harmless. Cancellation reports an accepted prefix and
retains caller storage until the exact terminal reply. Other commands fail
explicitly.

A successful open owns the instance's device binding; arbitrary multiple device
opens on it are rejected. The DOS stream adapter shares its own binding among
multiple handles. Keep requests and buffers alive until completion collection.
OpenDevice does not start another console worker; native console support must
be enabled during system startup.

READ waits for translated keyboard input, then returns an available prefix.
WRITE consumes counted source bytes in bounded work quanta. Completion means
source bytes were accepted into retained state; physical redraw may follow.
A nonempty write of at most 64 bytes that finishes directly in the text-feed
step gets one bounded presentation pass before its reply wakes the caller.
It does not wait for all damage to clear or for a pending asynchronous scroll.
Hidden views still complete. Normal preemption remains enabled, and cancellation
during the pass is honored. A quiesced drawing failure before reply reports
`IOERR_SELFTEST` with the accepted-byte count; unquiesced DMA retains the request
for reset.
CLEAR discards buffered input and its loss latch; it neither clears the screen
nor cancels a pending Read. It ignores Data/Length and returns zero actual bytes.
Cooked editing, EOF and foreground cancellation belong to the
[DOS stream layer](streams.md), [cooked input](cooked-console.md) and
[BREAK scopes](foreground-break.md).

## Display, scrolling and input

At startup the default text instance adopts the current GRAPHICS 0 screen and
cursor position. Shell output continues after the boot messages; startup does
not clear them. Imported text uses the supported ROM glyphs; inverse attributes
and graphics characters are not retained. Additional instances start empty.
FF, including the shell's CLS and Ctrl-L, still explicitly clears the instance.
This uses the existing cell buffer and adds no fixed or per-Task reserved
bank-zero bytes.

Text admission checks GRAPHICS 0 geometry, the display-list layout and disjoint
OS-high screen/list extents. It ignores `ATRACT`, `COLRSH`, `DRKMSK`, `CHBAS`,
`CHACT` and `GPRIOR`. The installed font remains selected, allowing international
fonts. On display claim the text backend sets `CHACT`/`CHACTL` to 2 and
`GPRIOR`/`PRIOR` to 0; release restores the incoming shadows and hardware modes.
The existing VBI hook suppresses attract mode while the console owns the screen.

Verbose kernel startup prints worker readiness before display claim. After the
shell opens its stream, console and shell readiness go through retained output.
The [platform boot contract](platform.md#boot-service-settings) defines these
milestones and the independent fatal-startup screen path.

The retained model and presentation are separate. Hidden instances still accept
output; showing them redraws retained cells. The worker rotates runnable instances
and bounds output/redraw work so pending input and other Tasks can progress.
[Window presentation](console-windows.md) defines tiling and focus limits.
Damage is retained separately for each changed row, so distant edits do not
force the rows between them to redraw. A bounded presentation cannot discard a
newer edit when it acknowledges completed work.

Bitmap presentation starts a segment of at most 32 glyphs from one dirty row.
Desktop clipping resumes one visible fragment per pass, with at most 16 glyphs
when the fragment cuts through the glyph height. The scene token freezes the
model and geometry until all fragments of that segment retire; no borrowed
view or source pointer survives a worker return. The dirty endpoint advances
only after that segment completes; a batch keeps
its paint phase and withholds the caret until all of its damage is repaired.
Visible pending damage drains before further writes or scrolling can restart
the repair. Cancellation and clear can abandon that repair. Ready segments
resume on fresh worker turns, with input, control admission and instance
rotation between them, without a voluntary Task handoff per segment. A short
WRITE's presentation pass completes its active fragment sequence before reply.
Cancellation preserves the accepted prefix; a quiesced drawing failure retires
the token without acknowledging partially drawn damage. A queued AES update lock
still permits the existing unit-zero text continuation to finish and release
its scene token. Other views cannot replace its frozen source. A scene exposure
acknowledges all dirty console rows only if it repainted the full window;
partial exposure preserves model damage outside the painted rectangle.

The text backend uses the installed OS font with the standard Atari screen-code
mapping, with `?` for unsupported terminal bytes.
Bitmap output uses the shared GEM 8×8 font, black ink and an opaque white
background. A synchronized visible instance scrolls with one asynchronous opaque
rectangle copy followed by the exposed-strip fill in the same hardware list.
A height-one tile submits only the fill. Hidden or invalidated presentation
redraws retained damage; clear retains bounded fills.

Long bitmap writes (more than 64 bytes) can accumulate several bottom-row
scrolls before presentation. Admission requires a fully visible, synchronized
view taller than one row. Each turn accepts at most 64 source bytes and recycles
at most one character row. One shared 44-byte upper-RAM context tracks at most
four scroll rows, 256 source bytes and four turns. A changed VBI tick, control
byte, request end, cancellation or waiting short write also ends gathering.
There is no extra source buffer and no wait for a subsequent WRITE.

The resulting list copies the surviving rectangle and clears all exposed rows
once. Completion preserves the accepted text's damage; bounded presentation
then paints its final positions, including text above the exposed strip. Input
and READ service continue between quanta and during DMA. Other model writes
wait until this continuation settles. Hide or other presentation changes may
discard the optimization and redraw the accepted model after DMA is quiescent.
An aborted WRITE reports its accepted prefix exactly once; no continuation
retains the request or source after reply.
See the [batching measurements](../history/console-output-batching.md): cached
CAT improves by 1.66× on the pinned demo; broader latency targets remain open.

The worker owns console drawing and the physical display lifetime, with one
list in flight. [Delegated VDI drawing](display.md#delegated-renderer-access)
shares its renderer through the common physical arbiter. A retained VBXE
completion signal wakes it; an independent sixteen-VBI-tick watchdog wakes it
if that interrupt is lost. It queries completion on a notification, continues
bounded input and READ service, and waits when no actionable work remains.
Queued output or controls blocked by DMA do not keep it yielding. Further model writes and all
hardware drawing, including caret and presentation controls, wait for completion.
The logical scroll commits once, and cancellation preserves accepted bytes.
The upper-RAM association holds only unit and view/model generations, never a
borrowed instance pointer across a turn. Completion borrows only a matching live
entry. A presenting entry defers adoption until publication; a retired entry
cannot adopt it. The durable completion flag prevents an unrelated focus change
from forcing an unchanged output tile to redraw. Invalidated views redraw
from their retained cells. Hide, destruction and Stop settle DMA before releasing
its storage or display ownership. Unquiesced recovery retains both.

A steady focused underline caret restores its cell before copying and redraws
after presentation settles. Completion makes that redraw runnable even if no
WRITE remains. Clean cells and an unchanged caret cause no drawing submissions.
An opaque bitmap text span also erases an old caret inside the cells it actually
draws, avoiding a separate glyph restore. A caret outside that span still needs
restoring, including cursor-only moves and cells deferred by clipping or the
presentation budget.
When the last dirty span completes full-screen bitmap presentation, the renderer can
append the new caret to that text operation. This requires a focused, settled
view and an old caret already absent or covered by the span. Text and caret
then share one owner check and the final blitter list and fence. Cursor-only
moves and incomplete presentations retain separate operations.
Desktop presentation finishes every clipped text fragment before its separate
caret operation.
The native/C packet is version 6, 78 bytes, including the trailing fill and clipping geometry
and driver-owned completion mask returned at open. Rebuild both sides together.
The worker reserves its request/input/stop bits before display initialization
allocates that signal.
Output control bytes have these effects:

| Byte | Effect |
| --- | --- |
| BS | Move left, clamped at column zero; do not erase. |
| HT | Next eight-column tab stop, or the next line at the right edge. |
| LF | Column zero of the next row, scrolling at the bottom. |
| FF | Clear this instance and move its cursor to the top left. |
| CR | Column zero of the current row. |
| Other C0 controls and DEL | Consume without effect; BEL does not use POKEY. |
| High-bit bytes | Render `?`; no implicit ATASCII or UTF-8 interpretation. |

Printable output wraps at the instance bounds. `$9B` is not a newline; an ATASCII
viewer must translate it. The cursor overlay does not change retained cells.

Retained characters use a circular row origin within their original allocation.
Scrolling clears the recycled physical row and advances the origin; it does not
copy the other character rows. Cursor positions, damage and presentation indexes
remain logical. Readers map a row or printable run once, preserving far-address
carry across CPU banks. Full redraw visits the current logical row order.

FF resets the origin when the clear edit commits, after cursor removal; parsing
FF alone does not change it. CMD_CLEAR only clears captured input. Every scroll
still dirties all logical rows for hidden, clipped or invalidated views. The
physical text-screen move and VBXE rectangle copy/fill remain necessary. Pending
DMA gates later model edits, and completion never rotates the origin again.
This is a current-screen buffer, with no scrollback. See the
[circular-buffer record](../history/console-circular-buffer.md) for measurements.

Keyboard capture uses the shared [input lease and route API](input.md). The
console maps captured generic route tags to retained instance/foreground state.
Focus changes do not redirect already captured keys. Input loss is explicit;
BREAK delivery has retained route state independent of the ordinary key FIFO.
IRQs do not scan instance records or follow arbitrary application pointers.
Each worker turn atomically collects input/stop/display notifications with `SetSignal`,
merging the previous `Wait` result. A worker-local flag retains possible input
until a bounded drain observes EMPTY; full batches keep it runnable. Output with
no input notification or retained work does not call `INPUT.Pending` or `Take`.
The worker never clears notifications after a drain or before sleeping, so an
arrival after EMPTY still wakes it. Unexpected resident-lease errors terminate
through the invariant-failure path. Public input validation remains unchanged.
Stopping the console releases input ownership before its signal/storage and display retire;
hiding a window does not release either ownership domain.
[Idle-input development evidence](../development/console-idle-input-q3.json)
records 9.7–10.0 ms for input checking across a full-screen bitmap scroll, down
from 52 ms on that historical image. Subsequent validation and asynchronous
scroll results are recorded in the
[drawing implementation plan](../plans/drawing-validation-implementation-plan.md).
Aligned bitmap text now uses the shared library's checked run generator, with
up to 32 glyphs and one background fill per hardware list. The operation remains
synchronous and retains the existing worker and ownership boundaries. See the
[drawing adapter](../../ports/gem4xe/adapter/README.md) for its limits and the
[responsiveness measurements](../history/console-responsiveness.md) for measured
CPU and loaded input costs.
The subsequent [blitter IRQ measurements](../history/blitter-completion-irqs.md)
record less completion-checking CPU work, about 32.5 ms isolated scrolling and
98–139 ms sampled loaded visible input on that image. Subsequent
[circular-buffer measurements](../history/console-circular-buffer.md) reduce
retained-edit CPU by 52–56% per call and isolated scrolling to about 30.5 ms.
Loaded visible input remains 101–148 ms with mixed changes across phases; the
broader latency targets remain open.

## Lifetime and limits

The worker and console registry are resident system services. Instance owners,
open bindings and active presentation/worker borrows prevent premature removal
or destruction. IRQs remain enabled during ordinary processing; asynchronous
entry follows the [platform protocol](platform.md).

The optional bitmap build defers automatic startup, binds its checked ordinary
C call and display callbacks, then starts the existing worker in an available
2,560-byte pool. It adds no bank-zero storage. The shared drawing image reserves
upper banks `$0C/$0D`; the loader validates these alongside native reservations.
The optional [bitmap shell preview](../guides/bitmap-console.md) uses queried
80×24 shell and 80×6 prime tiles; the standard demo uses 40×18 and 40×6.
The [implementation plan](../plans/gem4xe/bitmap-console-implementation-plan.md)
tracks the open responsiveness gate. Functional development checks do not promise
40 ms input, 20 ms scrolling or 500 ms repaint. A single framebuffer permits
intermediate updates between fences and scanout.

A quiesced bitmap hardware fault restores the OS display and latches terminal
backend failure. Waiting READ/WRITE requests receive `IOERR_SELFTEST` once;
WRITE retains its accepted-byte count. New opens and requests are rejected.
Existing bindings can close, controls can retire, and Stop retains its usual
live-instance/open-binding checks. Restart after a completed Stop retries
acquisition. Unquiesced DMA retains ownership and requests in reset-required
park. An unrelated fatal kernel exit while bitmap ownership remains active also
parks; emergency exit never copies bitmap pointers as text screen addresses.

There is no overlapping-window compositor, width reflow, scrollback or terminal
escape-sequence emulator. The [instance contract](console-windows.md) owns those
limits and creation/presentation semantics. The
[historical console design](../history/console-io-design.md) retains the initial
hardware gates, resource measurements and implementation sequence.
