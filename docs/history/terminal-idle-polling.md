# Terminal directory notifications and idle polling

[History](README.md) · [Plan](../plans/gem4xe/terminal-idle-polling-plan.md) ·
[Previous measurements](terminal-wake.md)

## TP1 Independent directory watches

Console-view version 5 adds WatchDirectory, TakeDirectoryChange and
UnwatchDirectory through the existing three-ULONG bridge. APP ABI 38 fences the
new capability: older providers reject these APPs before an unsupported operation
could be interpreted as a handle. All 130 import ordinals and the existing
92/76/42-byte public packets remain unchanged.

Four optional directory watches have their own bounded list, independent of the
eight cell subscriptions. Each retains its recipient Task, starts pending with an
initial signal, and coalesces later publications until Take. Take clears only the
pending flag, before metadata reads; it leaves the shared signal untouched.
Unwatch withdraws publisher access before releasing the lease and storage.
External watches prevent service Stop; source destruction does not depend on them.

[TP1 evidence](../development/terminal-idle-tp1.json) records raw and optimized
emitted C/Action bridge checks, including bit 31, two independent Tasks,
allocation/lease failure rollback, capacity, preserved cell slots, pure reads,
coalescing and changes around Take/read/Wait. Both runs check exact heap return,
stack/domain guards, ownership and EXIT. Failure injection replaces only the
watch allocator/Retain calls in a fixture copy. The standalone renderer occupies
one cell slot, leaving seven for the probe. The real public bridge is retained.

A record emits as 22 upper-memory bytes; four allocations cost 96 bytes after
rounding. The emitted list head/count occupy four upper-memory data bytes (a three-byte
pointer and one-byte count). TP1’s JSON bookkeeping estimate said five; the
emitted globals correct that estimate, without changing its heap or reservation
measurements. Complete
`bank_zero_budget`, `task_pools` and `runtime_reservations` match the earlier
eight-Task signal probe: reserved bank-zero growth is **0 fixed, 0 root, 0 kernel,
0 idle and 0 per public Task bytes**, including guards, alignment and unused
capacity. No production reservation grows. The fixture uses an 8 KiB upper data
arena because linking the actual console facade also retains AES globals; the
production GEM profile already reserves 12 KiB. This fixture adjustment does not
reserve guest bank-zero space in production.

Generated definitions and 711 host tests pass, with four existing skips.
These are development checks. Metadata publishers and Terminal admission follow
in TP2; this slice leaves Terminal's polling behavior unchanged.

## TP2 Metadata publishers and Terminal admission

Console LIVE/removal, supported geometry changes and accepted frontend activation
now publish directory invalidations after their state commits. Shell creation,
READY/failure, closing, collection, selection/fallback and controller port
withdrawal do likewise. Queries, painting, ordinary cell output and unchanged
controller turns remain silent. The lower notification core keeps text and
standalone producers independent of the AES facade.

Terminal registers its watch before querying metadata and withdraws it alongside
cell subscriptions before releasing the shared notification bit. Watch-admission
failure follows normal supervised startup rollback. The private record grows by
four bytes to 5,851; the handle is appended at offset 5,847. This slice retains
the 100 ms timer and unconditional metadata refresh.

The raw and optimized startup/teardown probes pass 38 checks each, including
watch admission failure and resource recovery. The shell allocation-failure
fixture passes 145 checks over 19 allocation points; 12 failed creations that
advanced the public identity retain a directory hint. Exact heap return,
Task leases, guards and EXIT pass. Its upper data fixture arena grows from 8 to
12 KiB to hold the linked watch support and test state; production reservations
do not change.

Complete eight-Task probe bank-zero budgets, Task pools and runtime reservation
maps still match the frozen signal probe: **0 fixed, 0 root, 0 kernel, 0 idle and
0 per public Task bytes added**, including guards, alignment and unused capacity.
No production Task, signal bit, upper-memory reservation or VRAM arena is added.

[TP2 evidence](../development/terminal-idle-tp2.json) also records the real GEM
keyboard/session/modal-close scenario. Two native observer Tasks block on their
own directory signals without timers. Creation/retirement and a replacement unit
epoch, plus frontend activation, wake both while the publisher owns UPDATE.
Their counts stay 8/8 during a quiet interval and ordinary ECHO output, then
advance for NEWSHELL/READY, selection and closing/fallback. These are observed
coalesced hints, not a promised event count. Both observers unwatch after port
withdrawal before root finishes. Three exact pixel checkpoints, keyboard editing,
cancelled/confirmed close, ownership, guards and EXIT pass. The focus test now
uses an actual peer layer's bounds, covering both legacy panel/counter and Files
desktops. The host suite passes 711 tests with four existing skips.
