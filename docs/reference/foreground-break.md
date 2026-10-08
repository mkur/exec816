# Foreground break contract

Status: B1–B5 implemented and qualified on the pinned PAL 8× eight-Task platform.
The W1–W3 extension to per-instance routes/focus uses development checks; its release
qualification remains pending. D4 adds bounded two-member foreground groups;
their validation is recorded with the demo development checks.
See the [console plan](../plans/console-interaction-implementation-plan.md).

Cancellation is cooperative. A foreground scope identifies one participating
Task and one console. A two-stage pipeline binds one parent scope to the console
and links two child scopes to it; each child retains its own signal and I/O state. It has a dynamically allocated signal, a nonrepeating
generation and durable pending-break state. A Task that neither polls nor enters
an interruptible DOS operation continues running. Cancellation never removes a
Task or frees storage still owned by a worker.

## Scope and lifetime

The DOS operations are BeginForeground(console), EndForeground(),
BreakPending() and ClearBreak(). Begin requires an owned CON: handle and an idle
client; each client and console may have at most one active foreground scope.
Beginning again on the same owned console atomically retires the old generation
and starts a fresh scope, retaining its allocated signal. This permits prompt
and command handoff without an intervening unbound keyboard route. Failure
leaves the previous scope intact.
Begin/End report success or an ordinary DOS error. Query and acknowledgement
preserve IoErr, so checking for break cannot hide a preceding I/O failure.

The DOS context retains the scope and prevents Task removal or context release
while it exists. Closing its console is rejected until EndForeground retires the
scope. Its lifetime identity includes that retained DOS context, its owner and
the scope generation. End removes every route's reference to the target before
freeing the signal or scope. Captured old events can then retire without touching
the old Task, including after its slot or address is reused.

ClearBreak acknowledges both durable state and the notification bit in one
serialized operation. Repeated input coalesces while the state remains pending.
A later break can create a new pending request after acknowledgement. End also
retires stale notification bits. Cleanup proceeds despite pending break.

## Captured routing

Each raw event carries a four-byte route generation captured by the IRQ. The
worker resolves that generation and performs translation and signal delivery in
Task context. It recognizes Ctrl-C/BREAK even with no pending Read or redirected
Input. A bound break produces durable cancellation without a duplicate input
byte. An unbound console retains ordinary byte $03 behavior. Binding a new
scope retires unbound break bytes still in the translated FIFO, preserving
ordinary typeahead. An unbound break still in capture when binding occurs also
retires without canceling the new scope.

Route records remain until captured events retire. Retiring a foreground scope
clears the target from its old records; it does not redirect those events to the
next scope. Route generations never wrap: exhausted generation space rejects
new publication. A bounded table also rejects admission when it cannot retain
the old routes. B1 retains 16 records, addressed by the low four tag bits and
validated by the full tag. The high 28 bits are a monotonically increasing
epoch; admission fails at $0FFFFFFF or when all records must be retained.
Windows reuse this same mechanism. A 16-bit capture mailbox keeps
one pending break per retained route when the 64-event ring is full; a separate
16-bit mailbox tracks input loss. The worker consumes break before ordinary
input. Old records can be reclaimed once the ring and both mailboxes are empty. Each admitted instance retains
its permanent unbound route and current route, including while unfocused.
End returns to that instance's unbound route without allocating another tag;
captured bound events retain their retired command identity. See the
[instance contract](console-windows.md).

Route publication must serialize Task-side state and atomically replace the
IRQ-visible generation. Forbid prevents another Task from changing the records;
the short native publication masks IRQ and restores the original P. NMI may
still enter. The existing native interrupt protocol defers switching when the
interrupted I bit is set and preserves the complete interrupted context. No IRQ
follows a Task, DOS context or route-record pointer.

Input overflow must not make a captured bound break disappear. B1 must qualify
both translated-FIFO loss and full raw-ring behavior, including stale-route
events, before publishing its delivery guarantee.

## Interruptible operations

Console Read/Write waits for either a specific console request's completion or
durable break.
If completion wins, its result is retained. Otherwise AbortIO requests
cancellation, and the caller still collects that exact terminal reply before
releasing any buffer, request, endpoint lease or busy flag.

Queued filesystem Read, Seek, Open, Lock, Examine and ExNext use a private
identity, command generation and explicit ownership state. Cancellation
notification is separate from the packet currently owned by the worker. The
worker can retire another client's queued operation while its own serial request
remains active. Dequeue and queued cancellation serialize their claim; the winning
path alone owns the packet. A reply already published wins over a late request.
Active operations check cancellation between bounded traversal, enumeration,
sector and copy steps, and before starting another transfer. There is no public
asynchronous DOS packet interface. Mount-management controls and cleanup
operations do not use foreground cancellation.

Canceled Read/Write with committed bytes returns that positive count and
ERROR_BREAK in IoErr; zero committed bytes returns failure with ERROR_BREAK.
A canceled file Read advances its cursor by exactly that committed prefix.
A canceled Seek preserves its starting position.
Displayed output is not undone. Console cancellation returns ERROR_BREAK only
after the terminal reply is collected; a stale notification cannot complete a
request. Pending break before submission leaves the request unsent.

Cooked Read cancels a valid partial line, clears queued typeahead and starts a
fresh line before returning failure with ERROR_BREAK. It omits a redundant
newline when the cursor is already at column zero, including after a canceled
scroll finishes. Echo bytes do not count as
returned input. A line invalidated by loss or overflow retains its discard-through-Return
state: break cannot make its surviving suffix executable. Cleanup ignores the
pending break, which remains set until acknowledgement or scope renewal.
An earlier device or filesystem error retains precedence. Object-producing
operations must reclaim unreturned objects before replying. Close, UnLock,
selector restoration and terminal reply collection remain cleanup operations.

## Shell command scopes

The resident shell keeps prompt editing and each built-in in separate scope
generations. TYPE and DIR poll between bounded steps; console and filesystem
waits use the interruption rules above. Input redirection does not change the
physical console that owns break or the prompt. CD releases a canceled candidate
without replacing the selected directory.

On cancellation the shell restores temporary Input/Output, closes command
resources, retires queued typeahead and renews its prompt scope. It reports
status 10 with ERROR_BREAK; the fresh prompt is the visible acknowledgement.
An earlier error retains precedence through cleanup. Scope or signal admission
failure unwinds the selected console and DOS context like other startup failures.
Late events and stale notification bits cannot cancel the next generation.

A canceled output request finishes an already committed scroll before replying.
The worker retains the existing 40-cell edit and 38-cell redraw quanta, checks
input between them and remains preemptible by VBI. It omits voluntary yields
while retiring that bounded canceled edit. A write whose final source byte is
committed and whose edit is idle replies in the same quantum; display continues
from retained cells after the caller releases its source buffer.

## Pipeline cancellation

A group keeps one captured console route and at most two linked child scopes.
The console worker marks all three scopes pending and signals their owners while
holding Forbid; this bounded fanout occurs in Task context. IRQ still captures
only a route generation and follows no Task or group pointer. Member publication,
unlinking and delivery use the same scheduling exclusion; native route publication
retains its existing IRQ/NMI protocol.

Pipe waits, console waits and filesystem operations observe each child's durable
state. Joining a pending group immediately marks the new member pending. A child
cannot acknowledge or replace its loaned scope. The parent cannot clear or end
the group while prepared, live or uncollected members retain it. The group remains
bound until both children and their exact I/O replies have retired and been
collected. Begin and End renew the route, so old captured ordinary input and BREAK
cannot leak into the next prompt. The prime worker is outside the group.

The shell loads both Images in its ordinary command scope before group preparation;
BREAK during either load uses existing loader cancellation and unloads an already
loaded first Image. See the [Process group lifetime](process.md#two-member-foreground-groups).

## Active filesystem retirement

The filesystem worker owns the adapter and request through exact serial reply
collection. Before submission, cancellation leaves the request unsent. While a
request is queued or preparing, a protected conditional call uses the existing
AbortIO engine. Once a frame is on the wire, healthy cancellation waits for that
finite transfer to retire, then stops before another copy or sector starts. This
preserves bus ownership and next-request usability. Public AbortIO retains its
existing on-wire abort and unsafe-bus behavior; the private conditional operation
does not change that API.

A completed copy quantum commits all its copied bytes. If that quantum finishes
the operation, normal completion wins. Otherwise the next checkpoint reports
the committed prefix with ERROR_BREAK and invalidates cached cursor traversal.
Seek cancellation retains the old position. Unreturned Open/Lock allocations are
freed before reply; publication and its immediate reply form a completion-wins
region. Directory-result publication is similarly indivisible with respect to
cancellation checkpoints, preserving the previous enumeration cookie until its
replacement can be published.

An error already produced by the in-flight transport or parser follows its
existing error and recovery path, preserving checksum, timeout or protocol cause.
A pending break cannot turn unsafe bus state into safe shutdown. Close, UnLock
and terminal collection finish despite repeated break. The scope remains pending
until acknowledged or renewed.

## Acceptance limits

On the pinned PAL 8× eight-Task machine, B5 requires at most 100 ms from capture
to durable break, 250 ms from queued cancellation publication to terminal reply,
and 500 ms from capture to a usable prompt on a healthy path. The
[B5 qualification](../history/console-interaction-implementation.md#b5-shell-cancellation-and-prompt-recovery)
passes 25 physical-input observation/replay cases, with maxima of 42.479 ms,
41.751 ms and 402.343 ms respectively. Queued timing uses exact caller collection
as an upper bound on reply publication; prompt timing uses the later of physical
RAM completion and caller readiness after collecting the prompt Write. Delivery,
cancellation and visibility remain separate measurements. These results cover
the recorded workloads and pins, not arbitrary uncooperative Tasks.

The transport's maximum active timeout is 1,000,000 µs for FASTEST125 and
2,000,000 µs for STOCK810 and GENERIC57600. Error retirement retains its existing
three-tick quiet interval (60 ms on PAL). Thus active error paths have that
finite transport allowance in addition to scheduling and DOS cleanup; they are
outside B5's healthy-path 500 ms prompt gate. B4 records fault/cancellation
retirement separately. Uncertain bus state remains offline,
and unsafe service shutdown retains the existing fail-stop behavior. There is
no retry, baud fallback or reset implied by break.

Scope payload is budgeted at no more than 64 upper bytes plus one signal per
participating Task. Capture tags add 256 active upper bytes across 64 slots;
the new header adds 16 more. The current scope uses 56 bytes, including instance
identity, private operation state, cancellation linkage and eight bytes for
bounded group membership. This adds eight upper-heap bytes to the 48-byte
allocation used by B3–B5. The console retains a 264-byte
route table reserved as 272 bytes, and 560 capture bytes within the existing
4,096-byte Task arena. ClientContext now uses a 98-byte allocation (104 rounded upper bytes),
including assign-path scratch pointers and a cached timer request pointer. The
38-byte clock/alarm request is acquired lazily; it rounds to 40 bytes. Background
children have private scopes without a console route; see [Process](process.md). Reserved bank-zero change is zero fixed bytes and zero per Task,
including guards, alignment and unused capacity. The filesystem registry uses
96 bytes inside its existing 96-byte reservation and its worker allocates one
additional control signal. See the
[B1 record](../history/console-interaction-implementation.md#b1-foreground-identity-and-delivery) and
[B3 record](../history/console-interaction-implementation.md#b3-queued-filesystem-cancellation).
