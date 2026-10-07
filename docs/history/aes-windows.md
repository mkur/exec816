# AES window application development

[History](README.md) · [Design](../plans/gem4xe/aes-window-app-design.md) ·
[Implementation plan](../plans/gem4xe/aes-window-app-implementation-plan.md) ·
[Current AES contract](../reference/aes.md)

## WA1 — Durable GUI delivery

Implemented on 2026-10-07. Each registration reserves one 36-byte GUI record
beside its unchanged sixteen 32-byte application records. The presenter retains
pending redraw/top/move/close facts independently of the queued record. Redraw
bounds union, moves coalesce and first-pending order between kinds is retained.
Recycling wakes the existing service signal when more GUI delivery needs it.
The caller filters retired GUI epochs without interpreting ordinary application
messages. Exit closes admission and drains both record classes before freeing
storage. The private wire version is 4; no new public GEM call is exposed yet.

[Development evidence](../development/aes-windows-wa1.json) records 101 emitted
GUI assertions: a full sixteen-message ordinary queue, additional GUI delivery,
immutable queued redraws, pending union/order/coalescing, close/reopen filtering,
an ordinary message resembling a retired GUI notification, simultaneous
message/timer readiness and exit with queued GUI work. Existing optimized
registration, two-client messaging and combined-event regressions pass, as do
the focused raw/optimized C/native layout and context probes. Guards and OS
return checks pass. The host suite passes 399 tests with four historical skips.

Reserved bank zero changes by **0 fixed + 0 per public Task + 0 idle bytes**.
The service grows from 698 to 910 live upper bytes, or 704 to 912 after heap
alignment. Each registration's delivery allocation grows from 512 to 548 live
bytes, reserving 552. At four registrations this is **356 extra live bytes and
368 extra heap-reserved bytes**. Fixed upper arenas, Task/DP/stack pools and
VRAM are unchanged. The new native GUI producer occupies 3,217 code bytes in
the optimized transport fixture; its populated image-bank count is recorded in
the evidence. The integrated counter demo and its bank delta follow in WA6.

These are development checks. Window lifecycle, direct VDI, integrated pixels
and desktop latency remain later gates; PI4/HY4 are unchanged and open.
