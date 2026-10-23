# Console instances and windows

[Reference index](README.md) · [Console device](console.md)

## Instance identity and lifetime

An enabled console service supports four instances: default unit zero plus up
to three application-created instances. One resident worker services all of
them. Each instance owns retained cells, dimensions, cursor, keyboard state,
input FIFO, one pending read and its own FIFO write queue. Creating an instance
allocates no Task, stack, direct page or physical screen.

`CONSOLE.Create(width,height)` returns a nonzero opaque LONGCARD unit, or zero
if geometry, capacity, identity space, route storage or memory prevents creation.
Width and height must fit the active display: 1–40 by 1–24 for text, or
1–80 by 1–30 for standalone bitmap, or 1–64 by 1–20 for desktop.
New instances start blank, at cursor (0,0),
and hidden; writes still complete into their retained cells. These functions
do not use DOS IoErr. The Shell selects its full-size instances through
[BIND_CONSOLE](desktop.md#operations). Other GEM applications use the owned
window binding below. Standalone tiled presentation calls remain unsupported
in desktop mode.

`CONSOLE.Destroy(unit)` returns one on success, zero on rejection. Only the
creating Task may destroy a created instance. Open device/DOS references and
foreground scopes, key subscriptions and a published desktop binding prevent
destruction. The creating Task cannot be removed
while it owns an instance, including during creation or retirement. Closing a
handle does not destroy its instance. Default unit zero cannot be destroyed.

Units combine a monotonically increasing 30-bit epoch with a two-bit slot.
Epoch exhaustion rejects creation; identities never wrap or get reused during
the service's enclosing Exec lifetime. A stale unit cannot bind a replacement
instance even if its slot or storage address is reused. Allocation failure
releases partial storage and the slot but does not reuse the attempted identity.

An existing instance may be opened by another Task. Device opens remain
exclusive per instance; separate I/O requests can borrow that open binding.
The DOS adapter shares a single endpoint among that instance's RAW/CON handles,
with reference counts and an input lease independent of other instances.

## Device and DOS binding

`OpenDevice("console.device",unit,request,0)` resolves the opaque unit and binds
the resulting instance through `io_Unit`. The public I/O request ABI and
READ/WRITE/CLEAR commands are unchanged. Pending operations on one instance
do not prevent another idle instance from closing. Destruction cannot free
buffers still borrowed by the worker, including a final redraw after a write
reply; retirement waits for that bounded worker quantum to finish.

Bare `CON:` and `RAW:` select unit zero. `CON:XXXXXXXX` and `RAW:XXXXXXXX`
select an eight-digit hexadecimal unit; hexadecimal letters are case-insensitive.
The suffix is a scalar identity, never a pointer. Other suffix lengths or
characters fail with ERROR_INVALID_COMPONENT_NAME. A stale/nonexistent unit
fails to open. `CONSOLE:` and geometry/name suffixes remain unsupported.
Cooked input needs at least three columns for its tail marker, a character and
an unused final column. A positive-length CON: Read on a narrower instance
returns ERROR_OBJECT_WRONG_TYPE; RAW input, output and zero-length reads remain
available. After moving to a new row, the editor recomputes its available width
from that instance's dimensions.

Each foreground scope retains its instance identity. Every instance has a
permanent unbound input route and a current route; scope renewal creates a new
bound generation, and End returns to the permanent unbound route without needing
another route allocation. Retired bound generations cannot cancel a new scope.
All live instance routes participate in route-retention accounting.

## Application-owned GEM console

The public C header [exec816/console.h](../../c/include/exec816/console.h)
provides `ExecConsoleCreate(width,height)`, `ExecConsoleDestroy(unit)`,
`ExecConsoleMode(console,mode)` and `ExecConsoleGetMode(console)`. Create and Destroy have the native lifetime,
return and IoErr rules above. Mode uses an owned CON handle and returns one on
success; select `EXEC_CONSOLE_ATASCII` before starting a FastBasic reader.
Keep active readers retired while changing modes.
GetMode returns the applied mode flags, or -1 with IoErr; it consumes no input
and claims no reader. FastBasic saves these flags before selecting ATASCII and
restores them after execution, including cancellation. An owner which selected
ATASCII keeps its completed glyphs; the ordinary Shell returns to its native mode.

`ExecAESConsole(window,unit)` binds a caller-owned 64×20 instance to a closed,
fixed-size GEM window belonging to that application's AES context. Its work
area must be 512×160 pixels and aligned to eight pixels in both axes. For
example, `NAME|CLOSER|MOVER` with outer `(56,21,528,173)` has work area
`(64,32,512,160)`. Bind before `wind_open`; other geometry is rejected. Moving
must preserve that alignment and dimensions. The function returns one after
publication, or zero with the AES diagnostic on failure. Rebuild the provider
and applications for C import ABI 27 and AES wire ABI 18.

The console worker owns retained cells, caret and drawing. GEM owns the frame,
focus, visibility and ordinary `WM_TOPPED`, `WM_MOVED` and `WM_CLOSED` delivery.
The application handles those messages; it does not paint the console client
on `WM_REDRAW`. Hiding or covering it preserves output and pending input.
The Shell keeps its own tabs and backing bitmap. Other console windows use the
same worker's bounded, clipped retained-cell path; no painter Task or bitmap
reservation is added.

The window retains the unit through `wind_close`; `wind_delete` releases the
binding after drawing retires. Destruction still refuses live streams or a
child's scope. Close/delete the window, collect the child and close owned
CON/RAW handles before destroying the instance. A scope can remain live while
the window is hidden. Supply its CON handle in `ExecProgramStart.console` to
route input and BREAK independently of the source window and Shell. Menu Stop
uses `ExecBreakProgram` regardless of output focus. The selected presentation
identity uses four upper-RAM bytes; the C bridge table uses fifteen and the
current import table grows by fifteen. Console and stream buffers use ordinary
upper heap. Added reserved bank-zero storage is **zero**, including each Task's
stack/direct page.

## Owner-requested foreground cancellation

`CARD CONSOLE.RequestBreak(LONGCARD unit)` requests cooperative cancellation
of the console's currently bound foreground interaction. The creator controls
a created unit; any application Task may control permanent unit zero. Focus,
visibility and the caller's selected DOS handles are irrelevant. No input byte
is enqueued and DOS IoErr is preserved.

Native controls use the generated `CONSOLETYPES.CONTROL_*` result namespace,
separate from DOS errors and the older boolean presentation operations:

| Result | Value | Meaning |
| --- | --- | --- |
| `CONTROL_OK` | 0 | The operation was accepted. Repeated cancellation coalesces. |
| `CONTROL_BUSY` | 1 | A presentation operation or existing subscription prevents admission. |
| `CONTROL_BAD_UNIT` | 2 | No live instance has that complete identity. |
| `CONTROL_NOT_OWNER` | 3 | The caller does not control this created instance. |
| `CONTROL_UNSUPPORTED` | 4 | The display mode or requested physical-key shape is unsupported. |
| `CONTROL_BAD_LAYOUT` | 5 | The requested presentation is incompatible. |
| `CONTROL_UNBOUND` | 6 | No bound foreground interaction or key subscription exists. |
| `CONTROL_FAILED` | 7 | The admitted control could not complete. |

RequestBreak returns only OK, BAD_UNIT, NOT_OWNER or UNBOUND. It does not wait
for the command or its I/O to finish. Cancellation reaches the bound owner and
any admitted foreground-group followers through the existing
[foreground contract](foreground-break.md#owner-requested-cancellation).
A caller implementing session close must retain its own close intent across
an UNBOUND result or a later prompt; this operation targets only the interaction
bound when it is called.

## Full-screen activation and key notices

`CARD CONSOLE.Activate(previous,next)` replaces one owned selected full-screen
view with another in text or standalone bitmap mode. Unit zero may have its
admitted lower pane; both views hide/show together. Input, pending reads,
paused ConsoleEdit state and foreground scopes retain their identities.
A same-unit call succeeds only if that unit is already selected. Unrelated
visible tiles, incompatible dimensions and desktop mode fail before publication.
BUSY permits retry after yielding. Both views remain retained until admitted
worker drawing/DMA settles; one commit publishes visibility and the new captured
route. OK means committed selection, while final redraw continues from retained
cells. A pre-commit failure preserves the logical selection and invalidates its
paint for repair. Existing unquiesced-device fault retention still applies.

`WatchKey(unit,code,qualifiers,signalMask,watch)` registers one exact physical
key per instance using a zero-initialized, caller-owned `CONSOLETYPES.KeyWatch`.
The presentation owner supplies an allocated signal mask and stable upper-RAM
storage. Code is the base Atari scan (0–63), qualifiers use INPUT.SHIFT and
INPUT.CONTROL. The shell chord is code 33 with both qualifiers. Desktop input
arbitration runs first; only an unclaimed event for the registered captured
console route can notify the watch. No byte is inserted into ordinary input.

`TakeKey(watch,notice)` copies and clears one pending `KeyNotice` and returns
one, or zero when empty. The notice records unit, route and capture tick.
Repeated events coalesce while pending. `UnwatchKey(watch)` first withdraws the
producer, drops pending state and releases the owner Task lease. Destroy and
service shutdown reject live subscriptions. The caller must unwatch before
reusing/freeing its record, signal or Task. Take and Unwatch leave wake bits
alone because multiple watches may share one signal; consume notices after
Wait and clear/free the bit only after all producers have withdrawn.

KeyWatch occupies 36 bytes and KeyNotice 10 bytes. Four watch pointers enlarge
the resident registry by 16 upper bytes. No additional worker, bank-zero storage,
per-event allocation or worker callback is introduced.

## Tiled presentation and focus

`CONSOLE.Show(unit,left,top)`, `Hide(unit)` and `Focus(unit)` return one on
success, zero on rejection. The creating Task controls its instances; any
application Task may control the permanent default. Calls require task context
with scheduling permitted. A presentation operation already in progress rejects
another operation; the caller can retry after yielding.
An outer `Forbid` or a call from the console worker is rejected before admission.

Show places the full retained dimensions within the existing 40×24 screen.
Use `ScreenWidth()` and `ScreenHeight()` to query those current limits. The
shared retained model supports 80×30, but that alone does not admit a larger
window on the text backend.
Rectangles cannot overlap or extend beyond it. An already visible instance can
only be shown again at its existing position. Hide erases its rectangle and
retains its cells and I/O; output continues while hidden. Showing it later
redraws all retained cells. Hide the full-screen default before showing tiles.
There is no additional physical screen, overlapping, width reflow, scrollback
or escape-sequence emulation.

Focus accepts a visible instance. Only its cursor is overlaid, and subsequent
keyboard capture uses its published route. Showing the first visible instance
focuses it. Hiding or destroying the focused instance selects the visible
instance with the lowest slot, or leaves no focus if none remain. Closing a
device/DOS binding keeps its instance and presentation; destroying the closed
instance erases its tile and applies that same fallback.

Keys captured before a focus change retain their original instance. BREAK also
retains the command generation, so a retired command cannot cancel its successor.
The IRQ marks one bit in each of two 16-bit route mailboxes for BREAK and loss;
it never scans windows or follows their pointers. Independent pending BREAKs
survive even if the shared ring fills. The worker resolves the retained full
route tags in task context before delivering input or foreground signals.

Ring overflow and detected hardware overrun latch loss for the route current at
capture. Other instances keep their queued events. Read's loss acknowledgement,
CMD_CLEAR and device open/close retire only that instance's input: a native task
helper acknowledges its loss bits, snapshots the producer head, then tombstones
matching events in the bounded ring. It leaves other routes and bound BREAK
mailboxes intact. IRQs remain enabled during both scans; only each bitmap
read/clear excludes IRQ, with NMI scheduling deferred by the existing entry
protocol. Loss acknowledgement precedes the head snapshot so a new overflow is
never silently cleared. Retained route slots cannot be reused during this scan.

## Height changes and owned panes

`CONSOLE.ResizeHeight(unit,height)` returns one on success, zero on rejection.
The owner may change height at fixed width within the original cell capacity.
It preserves the unit, endpoints, input route, focus and cooked draft. Shrinking
keeps the cursor row and discards older rows above it when necessary; growing
appends blank rows. The circular retained buffer is normalized using one shared
80-byte upper-RAM row. Width changes and scrollback are unsupported.

The existing presentation transaction settles borrowed drawing and pending DMA
before changing cells or geometry. Scheduling and IRQ capture remain enabled.
An active positioned write prevents resizing until its admitted span completes;
queued writes validate against the new geometry when claimed. Ordinary streams
and pending reads retain their ownership.

`COMMAND.OpenPane(rows)` prepares one full-width output instance below the
permanent default console. The caller's selected Output must be a RAW/CON handle for unit zero; another
console, NIL or a disk stream reports ERROR_OBJECT_WRONG_TYPE. The parent must
have full-screen dimensions before docking; desktop mode rejects this operation.
One association is supported.
A second pane or conflicting Show, Hide, Focus or resize returns busy. Unit-zero
focus remains available. Allocation and admission failures preserve the layout.

The returned DOS handle owns retirement, unlike ordinary RAW/CON handles.
Close restores the parent's full height before releasing the child's instance
lease. Process return also closes it through ordinary DOS ownership cleanup,
even while the parent is waiting in a cooked Read. Its draft and captured route
survive. When the parent is hidden, closure restores its retained height without
erasing the selected console or changing focus. The pane is output-only and cannot be inherited as a selected stream.
Additional RAW bindings must close, and any key subscription must be withdrawn,
before the owning pane can retire. A busy close retains its handle.

The capacity field fits the instance's former alignment padding. The console
registry now reserves 896 upper bytes, including per-instance key-watch pointers;
the pane association needs no additional storage. Bank-zero reservation changes
by zero bytes. The implementation and development checks
are recorded in the [pane record](../history/background-pane-primes.md).

## Memory and asynchronous entry

Each additional instance owns upper-RAM cells, input and presentation state.
It shares the service worker and physical screen. Instance creation does not
add a bank-zero stack or DP reservation. Exact layouts come from
[console.json](../../abi/console.json); generated build maps account for the
resident arena, including alignment and unused capacity.

Creation retains the owner before allocating and publishes LIVE only after
initialization. Worker borrows and presentation transactions retain storage
through their last access. Retirement prevents new borrows, waits for an existing
quantum with scheduling enabled, then frees outside Forbid. IRQs remain enabled;
the platform entry protocol protects NMI and context switching.

Presentation transactions pause live worker borrows. An eight-byte preallocated
private control record passes cursor removal and erasure to the console worker,
which services it before ordinary borrows even while presentation is locked.
Only that worker mutates the physical screen. The caller publishes PENDING,
the worker sets RUNNING then DONE after the physical operation, and the caller
acknowledges it by clearing the record to IDLE before unlocking. The existing
presenter Task lease and registry states retain caller and instance storage
through acknowledgement. A caller yields with scheduling enabled while waiting;
the worker uses direct internal operations rather than waiting on itself.

The transaction uses the worker's existing wake signal and allocates no memory
or signal bit. A second control is rejected while the lock is held, and Stop
refuses a live transaction. Device bindings and captured input remain attached;
input pumping continues during normal control handling. After acknowledgement,
unlock resumes borrows and wakes the worker. The record increases the rounded
upper metadata reservation by sixteen bytes, including eight bytes of new
payload and reserved slack. Fixed, root/kernel, per-Task and idle bank-zero
reservations change by zero bytes.

Historical fairness limits, byte budgets and W1–W3 development results are in the
[window design record](../history/console-windows-design.md). The later
[console refactor](../history/console-refactor-implementation.md) records changes
to those internals. Follow the [testing policy](../contributing/testing.md) for
release qualification.
