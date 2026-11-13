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
rounding. The list head/count add five upper-memory data bytes. Complete
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
