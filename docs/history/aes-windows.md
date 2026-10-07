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

## WA2 — GEM windows and redraw ownership

Implemented on 2026-10-07. Named and AESPB bindings expose fixed-size windows,
copied 64-character titles, pixel-position moves, top/work/current queries and
caller-local rectangle conversion/enumeration. The presenter publishes visible
work snapshots under update ownership. Close preserves the hidden handle;
delete and cooperative exit release it. Physical title/drag/closer input sends
requests and leaves committed state unchanged until the app accepts them.

Application windows use an explicit external-paint Layers transaction. The
presenter finishes the frame and durably hands work damage to `WM_REDRAW` before
retiring its token. These layers remain excluded from pixel-copy, copied-move
and cache paths. No scene transaction waits for an application redraw reply.
The outline renderer now preserves adjacent packed pixels at odd X coordinates.

[Development evidence](../development/aes-windows-wa2.json) records 176 C window
assertions, an independent visible-pixel region oracle, physical top/move/close,
exact outline restoration, copied-title inspection and full desktop-slot
exhaustion beside the native shell. Full/partial occlusion, nested locks,
deferred peer moves, stale iterators, queue-full close/reopen and remaining-window
exit pass. Layers passes 53,345 assertions, the native desktop 317, and GUI and
lock regressions pass. Raw/optimized layout/context bridges and 399 host tests
(four historical skips) pass. These are development checks, not qualification.

Reserved bank zero changes by **0 fixed + 0 per public Task + 0 idle bytes**.
AES service storage is 988 live/992 heap-reserved upper bytes; desktop service
is 12,480 bytes, including the enlarged 5,084-byte scene and all four title
buffers. An attached C context is 259 live/264 reserved bytes. Each allocated
window view uses 798 live/800 reserved bytes. At four attachments with four
views, the WA2 delta is **3,536 live / 3,544 heap-reserved upper bytes**. Fixed
arenas, Task slots, stack/DP pools and VRAM are unchanged. The fixture's maximum
observed presenter stack use is 658 bytes; this does not qualify future caller
VDI stack use. Direct drawing, counter applications and the packaged demo remain
WA3–WA6 work.
