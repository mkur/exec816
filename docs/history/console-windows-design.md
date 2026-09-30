# Console instances and windows

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/console-windows.md) and [history index](README.md).

Status: W1–W3 implemented; focused raw/optimized development checks pass,
including eight-Task fairness/SIO. Full window release qualification remains
pending. Follow the
[console plan](../plans/console-interaction-implementation-plan.md) and
[two-tier testing policy](../contributing/testing.md).

## Instance identity and lifetime

An enabled console service supports four instances: default unit zero plus up
to three application-created instances. One resident worker services all of
them. Each instance owns retained cells, dimensions, cursor, keyboard state,
input FIFO, one pending read and its own FIFO write queue. Creating an instance
allocates no Task, stack, direct page or physical screen.

`CONSOLE.Create(width,height)` returns a nonzero opaque LONGCARD unit, or zero
if geometry, capacity, identity space, route storage or memory prevents creation.
Width is 1–40 and height is 1–24. New instances start blank, at cursor (0,0),
and hidden; writes still complete into their retained cells. These functions
do not use DOS IoErr.

`CONSOLE.Destroy(unit)` returns one on success, zero on rejection. Only the
creating Task may destroy a created instance. Open device/DOS references and
foreground scopes prevent destruction. The creating Task cannot be removed
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

## Tiled presentation and focus

`CONSOLE.Show(unit,left,top)`, `Hide(unit)` and `Focus(unit)` return one on
success, zero on rejection. The creating Task controls its instances; any
application Task may control the permanent default. Calls require task context
with scheduling permitted. A presentation operation already in progress rejects
another operation; the caller can retry after yielding.

Show places the full retained dimensions within the existing 40×24 screen.
Rectangles cannot overlap or extend beyond it. An already visible instance can
only be shown again at its existing position. Hide erases its rectangle and
retains its cells and I/O; output continues while hidden. Showing it later
redraws all retained cells. Hide the full-screen default before showing tiles.
There is no additional physical screen, overlapping, resize/reflow, scrollback
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

## W3 progress limits

The following limits are frozen before the first W3 development run, on the
pinned PAL 8× machine with eight live Tasks and FASTEST125 SIO. They measure
caller-observed completion/visibility and include scheduling and polling:

| Observation | Maximum |
| --- | --- |
| Eight-byte small Write submission to exact collection | 250 ms |
| Small Write submission to observed complete redraw | 500 ms |
| Continuous 20-byte flood Write to exact collection, including scroll | 1,000 ms |
| Captured key to collection of another window's pending RAW Read | 250 ms |
| Captured key to observed RAW/CON echo | 500 ms |
| Captured BREAK to durable foreground notification | 100 ms |

The worker retains 64-source-byte, 40-edit-cell and 38-redraw-cell quanta and
rotates runnable instances. The development workload uses a continuous producer,
eight small writes, two pending readers, focus changes and a computing foreground
scope alongside complete 777-byte DOS reads on 128-byte media. It establishes
eight simultaneously live Tasks and verifies exact bytes, FIFO write order,
physical tiles, heap/ownership, route peak and unchanged SIO deadlines. Full
70,003-byte reads, additional profiles/placements and identical-input replay
remain release qualification under the testing policy.

## Memory and asynchronous entry

The four permanent registry entries and header now occupy 172 upper bytes:
a 20-byte header and four 38-byte entries. The header retains the presentation
owner with a TaskLease; each entry has its creator lease. Together with the
default instance's open lease and alignment, the console arena grows from 672
to 720 bytes in [C5b](console-refactor-implementation.md). The service's worker
lease fits its existing 160-byte slot. No per-instance worker is added.

Each additional instance uses 80 allocated bytes for its 74-byte record, 32 for
its 30-byte presentation record, 128 for its FIFO, and its cell count rounded
up to eight bytes: **240 + round8(width × height)** upper heap bytes. The extra
16 allocated bytes hold the open lease and alignment. The foreground scope
remains 48 bytes. Fixed and per-Task reserved bank-zero changes are **zero**,
including guards, alignment and unused capacity; eight-slot loading/runtime
totals remain 57,232 / 61,536 bytes including the OS.

Creation publishes an owner and CREATING state under Forbid before allocation,
then publishes LIVE after initialization. The worker marks a permanent registry
entry busy before checking LIVE and reading its instance pointer. Retirement
publishes RETIRING under Forbid, preventing new borrows, then waits for an
existing borrow before freeing outside Forbid. The worker releases its borrow
after its final pointer access and before yielding. IRQs remain enabled; the
existing native entry protocol preserves context across NMI and scheduling.

Presentation operations publish a transaction owner and pause all live worker
borrows under Forbid, then wait for an existing quantum with scheduling enabled.
They remove cursor overlays and erase the admitted rectangle with preemptible
native row fills.
The final publication resumes the entries and wakes the worker. Device I/O and
captured input remain bound while presentation is paused. The transaction owner
cannot be removed, and the service cannot stop during presentation. This also
protects the shared default screen during another Task's lifetime operations.

The historical W2 slice used existing record padding for focus, the presentation owner, and route
mailboxes, with no record or heap allocation growth. Native helpers need 108
bytes beyond the old 8,192-byte linker code subregion; it is expanded to 8,704
bytes inside the already reserved upper Task arena. The full arena reservation
and all bank-zero reservations are unchanged; the extra 512-byte subregion
includes unused capacity and adds no Task, stack or direct page.
