# Native console device

[Reference index](README.md) · [Console example](../guides/console-example.md)

One console worker serves the default text console and additional instances.
It retains cells, accepts output, routes input and updates the shared 40×24
physical screen. An instance adds upper-RAM state, not a Task, stack or DP.

## Public interface

Open `console.device` with unit zero for the default instance or an opaque
[instance identity](console-windows.md), and flags zero. Use the standard Exec
[device I/O contract](device-io.md) and full IOStdReq record. READ, WRITE and CLEAR
are supported; io_Actual reports transferred bytes. Other commands fail explicitly.

A successful open owns the instance's device binding; arbitrary multiple device
opens on it are rejected. The DOS stream adapter shares its own binding among
multiple handles. Keep requests and buffers alive until completion collection.
OpenDevice does not start another console worker; native console support must
be enabled during system startup.

READ waits for translated keyboard input, then returns an available prefix.
WRITE consumes counted source bytes in bounded work quanta. Completion means
source bytes were accepted into retained state; physical redraw may follow.
CLEAR discards buffered input and its loss latch; it neither clears the screen
nor cancels a pending Read. It ignores Data/Length and returns zero actual bytes.
Cooked editing, EOF and foreground cancellation belong to the
[DOS stream layer](streams.md), [cooked input](cooked-console.md) and
[BREAK scopes](foreground-break.md).

## Display, scrolling and input

The retained model and presentation are separate. Hidden instances still accept
output; showing them redraws retained cells. The worker rotates runnable instances
and bounds output/redraw work so pending input and other Tasks can progress.
[Window presentation](console-windows.md) defines tiling and focus limits.

Printable ASCII uses the available ROM glyphs, with `?` for unavailable glyphs.
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

Scrolling uses native row copy/fill helpers for retained cells, with a physical
screen fast path when presentation state permits. General redraw handles dirty,
hidden or clipped state. The [console refactor record](../history/console-refactor-implementation.md)
contains the changes and measured development results; an old benchmark is not
a promise of current timing.

Keyboard capture retains the instance and route generation at capture time.
Focus changes do not redirect already captured keys. Input loss is explicit;
BREAK delivery has retained route state independent of the ordinary key FIFO.
IRQs do not scan instance records or follow arbitrary application pointers.

## Lifetime and limits

The worker and console registry are resident system services. Instance owners,
open bindings and active presentation/worker borrows prevent premature removal
or destruction. IRQs remain enabled during ordinary processing; asynchronous
entry follows the [platform protocol](platform.md).

There is no overlapping-window compositor, resizing, scrollback or terminal
escape-sequence emulator. The [instance contract](console-windows.md) owns those
limits and creation/presentation semantics. The
[historical console design](../history/console-io-design.md) retains the initial
hardware gates, resource measurements and implementation sequence.
