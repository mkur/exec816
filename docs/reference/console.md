# Native console device

[Reference index](README.md) · [Console example](../guides/console-example.md)

One console worker serves the default console and additional instances.
It retains cells, accepts output, routes input and updates one shared display.
The same Task runs the AES graphical system loop; console stream/model turns
return to that loop before graphical input, event and frame work continues.
Graphical progress does not require a console write or repaint.
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

`CONCMD_MODE=10` takes one byte: RAW_KEYS=$80, ATASCII=$40, NO_CARET=$20;
other bits must be zero. It shares the write FIFO, clears pending input and
preserves the instance Caps state. Set zero to restore native mode. Callers
coordinate mode changes with their readers. `CONCMD_GET_MODE=14` snapshots the
currently applied `$E0` mode flags into one writable byte without clearing input
or claiming READ. Length and Actual are one. It observes applied state; wait for
a queued MODE operation's completion before relying on its new value.
Applications temporarily changing modes must save and restore this snapshot.
`CONCMD_WRITE_CELLS=11` uses the
same position and row bounds as WRITE_AT but accepts every byte as a cell.
ATASCII mode maps all 256 characters, including inverse and graphics glyphs,
on text and bitmap backends. `CONCMD_READ_KEYS=12` shares READ ownership and
returns scan bytes when RAW_KEYS is set: scan index in bits 0..5, Shift in bit 6,
Control in bit 7. It bypasses translation and cooked editing. BREAK retains its
separate foreground cancellation route. NO_CARET lets an application draw its
own caret. These operations use existing instance and request storage.

`CONCMD_PEEK_INPUT=13` immediately returns two bytes `{present, firstByte}`
without consuming the FIFO or claiming READ ownership. Length must be exactly
two; Actual is two even when `present=0`. The caller coordinates with other
readers; the snapshot does not reserve the byte. Bytes are translated normally,
or raw scans in RAW_KEYS mode. Stream WRITE preserves all 256 byte values in
ATASCII mode; native mode continues to replace unsupported high bytes with `?`.

`CONCMD_WRITE_CELL_SPANS=15` writes 0–30 positioned cell spans through the same
output FIFO. Offset is zero; Length and Actual count **descriptor bytes**.
Each generated `CellSpan` is ten bytes: column CARD at 0, row CARD at 2,
three-byte data pointer at 4, padding at 7, length CARD at 8. Length is a multiple
of ten, at most 300. Each nonempty span stays in one admitted row and contains
at most 80 exact cell bytes. Descriptors apply in order; later overlapping cells
win. The stream cursor and mode do not change. The worker checks the entire
vector's structure and geometry before its first model edit. Callers retain
live descriptors and nested buffers until exact terminal completion collection.

A vector consumes at most 64 source cells per worker quantum, with normal
input, control and instance-rotation opportunities between quanta. Actual advances
by ten only when a complete span is accepted. A cancelled or failed request can
have edited a prefix of the next span without counting that span in Actual.
Accepted cells are retained; there is one terminal reply and no caller pointer
survives it. Later writes and mode operations cannot pass the vector; resizing
rejects an active positioned request. Hide and retirement preserve the existing
presentation-borrow protocol. Completion is model acceptance with retired caller
storage and bounded presentation, rather than a full-scanout fence.

`DOS.ConsoleIO(file,command,offset,buffer,length)` submits these requests through
a caller-owned CON/RAW/pane FileHandle without opening another device binding.
It keeps normal request lifetime, byte-count/error and cancellation semantics.
MODE can restore the console while foreground cancellation is pending.
For vectors, a successful DOS return equals the descriptor-byte Length. BREAK
can return a nonnegative completed prefix with IoErr set; other errors return
-1 and hide Actual. Preserve IoErr even when a late error accompanies a full
count. A positioned writer can safely retry retained damage after a hidden
prefix; it must not inspect the DOS adapter's private request to recover it.

A successful open owns the instance's device binding; arbitrary multiple device
opens on it are rejected. The DOS stream adapter shares its own binding among
multiple handles. Keep requests and buffers alive until completion collection.
OpenDevice does not start another console worker; native console support must
be enabled during system startup.

READ waits for translated keyboard input, then returns an available prefix.
WRITE consumes counted source bytes in bounded work quanta. Completion means
source bytes were accepted into retained state; physical redraw may follow.
A separate backend Task owns stream work and copied input. A producer holding
AES UPDATE can wait for accepted output without waiting for painting. Cancellation
reports the accepted prefix once. The renderer later consumes bounded copied
[console views](console-views.md); it borrows no live backend cell pointer.
CLEAR discards buffered input and its loss latch; it neither clears the screen
nor cancels a pending Read. It ignores Data/Length and returns zero actual bytes.
Cooked editing, EOF and foreground cancellation belong to the
[DOS stream layer](streams.md), [cooked input](cooked-console.md) and
[BREAK scopes](foreground-break.md).

## Presentation and input

The system Task owns display and input capture. It routes captured events through
a bounded copied ingress queue to the backend Task. Eight byte/raw packets may be
queued; loss and cancellation have separate coalesced slots. A captured route
remains retained through delivery or drop. Clearing, reopening or closing input
invalidates copied bytes already withdrawn from capture. Scope handoff retires
old route tags, so delayed cancellation cannot interrupt a later job.

The loaded GEM terminal assembles bounded copied views into its own private
cells. Standalone text/bitmap consoles use a resident copied frontend. It never changes the model being edited by the backend. A multi-chunk
pass can acknowledge only one matching revision after presentation completes;
stale acknowledgements rearm the consumer hint. Drawing retains the existing
physical display lease, clipping, bounded submissions and completion fences.
UPDATE can delay drawing without delaying stream acceptance. Physical borrows
freeze the renderer's private copy until completion.

The single framebuffer can expose intermediate updates. Scrollback, width
reflow and escape-sequence emulation remain unsupported. Earlier batch and
short-write painting behavior is preserved as
[history](../history/console-presentation-before-gf10.md), rather than a current
stream completion guarantee.

## Lifetime and limits

The backend, graphical system Task and console registry are resident services. Instance owners,
open bindings and active presentation/worker borrows prevent premature removal
or destruction. IRQs remain enabled during ordinary processing; asynchronous
entry follows the [platform protocol](platform.md).

The optional bitmap build defers automatic startup, binds its checked ordinary
C call and display callbacks, then starts the system Task in an existing
2,560-byte pool and the backend in an existing 1,312-byte pool. Reserved
bank-zero storage does not grow. Each additional small Task consumes 1,600
previously reserved bytes: 1,312 stack, 256 direct page and 32 outer guards. The shared drawing image reserves
upper banks `$0C/$0D`; the loader validates these alongside native reservations.
The optional [bitmap shell preview](../guides/bitmap-console.md) uses queried
80×24 shell and 80×6 prime tiles; the standard demo uses 40×18 and 40×6.
The [implementation plan](../plans/gem4xe/bitmap-console-implementation-plan.md)
tracks the open responsiveness gate. Functional development checks do not promise
40 ms input, 20 ms scrolling or 500 ms repaint. A single framebuffer permits
intermediate updates between fences and scanout.

A quiesced bitmap hardware fault restores the OS display and latches terminal
backend failure. Waiting READ requests receive `IOERR_SELFTEST`. Admitted output still completes
model acceptance with its accepted-byte count; new opens and requests are rejected.
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
