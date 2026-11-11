# Copied console views

[Reference index](README.md) · [Console instances](console-windows.md)

The console service provides copied, bounded snapshots and input delivery above
ordinary Exec stream I/O. It adds no kernel selector. Exact records and constants
come from [console-view.json](../../abi/console-view.json); C declarations are in
[console-view.h](../../c/include/exec816/console-view.h). Rebuild C applications
for the current APP ABI and console-view version 3.

Subscribe with a live unit and a signal mask allocated by the calling Task.
The opaque handle retains that Task until explicit unsubscribe. Up to eight
subscriptions coexist, including temporary renderer subscriptions. Failure to
allocate storage, retain the Task or admit a subscription returns zero.
Keep handles live until unsubscribe; ownership and valid pointers are caller
responsibilities. Shared signal bits are allowed. A signal is a change hint;
Pending reports retained state independently of that bit.

Snapshot copies at most 64 logical cells starting at `first`, together with unit,
revision, geometry, cursor, mode and foreground route tag. BUSY means a retained
model edit is not settled. Match the revision of every chunk when assembling a
frame. Acknowledge only the revision actually presented. STALE rearms the hint;
a later generation can never be acknowledged accidentally. Revisions never wrap
within one subscription; exhaustion reports OVERFLOW. Source retirement reports
CLOSED with no cells and preserves the handle until unsubscribe. External live
or closed subscriptions prevent service shutdown.

Input copies up to 64 bytes, or a raw Atari key/tick, loss or cancellation record.
Echo the route from the relevant snapshot. STALE rejects a changed foreground
route; never retarget an old BREAK to a new job. Eight byte/raw packets provide
bounded backpressure through RESOURCE. Separate coalesced loss/cancel slots
remain available when those packets are full. The backend owns translation,
input overflow, request cancellation and stream completion. Normal output and
input progress independently of UPDATE and delayed repaint.

Snapshot and one backend quantum serialize through short Task guards; IRQ/NMI
entry remains governed by the platform stack/domain protocol. No mutable cell,
request or scope pointer appears in a public view packet. Unsubscribe before
freeing the signal or exiting. Snapshots already copied into consumer storage
remain ordinary consumer-owned bytes after retirement.

A subscriber can bind its view as the input source of an ordinary owned AES
window through `ExecConsoleViewBindWindow`. This associates capture focus with
the backend's current foreground route. It neither attaches cells nor changes
the window's painting policy. Focus changes publish that source route or the
next window's normal AES route; captured old tags retain their original scope.
`ExecConsoleViewUnbindWindow` restores ordinary AES keyboard delivery. Unbind
before unsubscribing or deleting the window. Unsupported hosting and ownership
failures are normal admission errors. The [input-binding slice](../development/gem-first-gf11-input.json)
records its emitted development checks; terminal migration follows separately.
