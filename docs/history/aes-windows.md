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

## WA3 — Delegated renderer access

Implemented on 2026-10-07. DISPLAY retains one physical lifetime owner and
admits up to eight 32-byte borrowing grants. A FIFO and existing Exec signals
serialize bounded drawing units. The presenter tries admission without waiting,
reserves one bounded native service turn, and keeps asynchronous DMA pinned
until its owner retires completion. Every shared native rendering entry uses
the same arbiter. Borrowers fence and restore overlays before release.

Revocation wakes queued Tasks and refuses an active unit. Grant collection
releases retained Tasks before lifetime teardown. Quiescent recovery closes
borrower admission while allowing the presenter to regain access for cleanup;
unquiesced recovery preserves the active grant and parks for reset. Ordinary
owner entry/exit avoids queue guards when no grant exists, since only that owner
can admit one. See the [current contract](../reference/display.md#delegated-renderer-access).

[Development evidence](../development/aes-windows-wa3.json) records 48 borrowed
fills alongside native scrolling and accelerated pointer work, zero overlapping
owners and 1,088 exact fill pixels after the pointer moved away. Two first units
deliberately yield while holding access. The instrumented fill units cost
2.89 ms median / 3.85 ms maximum charged CPU; elapsed time and admission waits
are reported separately. Borrower stack peaks remain within existing 1 KiB
pools; future VDI depth is not yet qualified. Raw/optimized arbitration checks
pass 63 assertions each, layout/context bridges pass, presenter intake passes
182 checks, and native panel pixels, owner faults, borrower faults and disk/GUI
coexistence pass. The host suite passes 399 tests with four historical skips.

The integration fixture exposed an old C `IOStdReq` padding error: `io_Offset`
must start at byte 38 and the record occupies 42 bytes. The generator now emits
that padding and every C image checks the emitted I/O layouts. The older GUI
integration fixture also omitted its new GUI delivery allocation from expected
heap returns; its assertion now counts the aligned allocation.

Native begin/end bookkeeping has a cost. The observed clipped console write
window increased from 1,584 ms in the WA2 control to 2,309 ms in this cohort.
Physical gesture setup already consumed over four seconds of the fixture's
six-second mouse hold. Its bounded hold is now eight seconds, and still requires
console and disk progress before unlock. This is a functional test adjustment,
not a relaxation or completion of PI4/HY4 latency acceptance.

Reserved bank-zero delta is **0 fixed + 0 per public Task + 0 idle bytes**.
The arbiter adds 49 live native upper-data bytes and 30 C bridge-table bytes
inside existing arenas. Grants are caller-owned 32-byte records, at most 256
payload bytes; WA3 itself allocates no production grants. The matched integrated
image gains 11,032 payload bytes and retains the same seventeen populated CPU
banks. Fixed arenas, stack/DP pools and VRAM reservations are unchanged.
These are development checks. Private VDI, counter applications and the optional
packaged demo remain WA4–WA6 work.

## WA4 — Private application VDI

Implemented on 2026-10-07. Each application owns one virtual workstation with
private parameters, pens and clipping. Open uses one cold delegation exchange;
attributes and drawing execute locally without presenter RPC. The shared
backend selects that state only while admitted to DISPLAY, restores native
state, and releases access between 16-row strips or 32-glyph chunks. Opening
leaves physical pixels unchanged. Exit also closes an omitted workstation.

[Development evidence](../development/aes-windows-wa4.json) records 158 C
assertions, exact complete desktop pixels with two distinct callers, forced
preemption inside the selected backend, long text crossing multiple chunks,
odd clipped glyphs, full/partial occlusion, exposure, cursor restoration,
failed-open unwind and complete cleanup. Raw/optimized context/layout probes
and 399 host checks (four historical skips) pass. The binding uses explicit
full initializers for automatic control arrays: Calypsi 5.18 emitted only the
first store for the initial partial-zero initializer.

The assertion-heavy clients touch 738 and 751 bytes in their existing 1,024-byte
pools, leaving 30 and 17 bytes above the 256-byte interrupt reserve. This is a
narrow measured fit; the counter's actual event/redraw stack still needs its own
measurement. No pool enlargement is included.

Reserved bank-zero delta remains **0 fixed + 0 per public Task + 0 idle bytes**.
A workstation uses 282 live / 288 heap-reserved upper bytes; the enlarged AES
context uses 267 / 272, an eight-byte increase. Shared native-workstation scratch
adds 92 live bytes inside the existing C data bank. Four workstations/contexts
therefore add 1,252 live upper bytes, including scratch, and 1,184 heap-reserved
bytes. Fixed arenas, staging, VRAM, stack/DP pools and Task capacity are unchanged.
WA5–WA6 follow; PI4/HY4 remain open and this is not hosted qualification.

## WA5 — Ordinary GEM counter

Implemented on 2026-10-07. The [counter body](../../examples/gem-counter/counter.c)
uses GEM window, VDI and combined message/timer calls. One redraw helper handles
both exposure and model changes under `BEG_UPDATE`; it enumerates visible work
rectangles and clips each bar/text call. Covered counters continue updating their
models. Top, move and close requests go through ordinary GEM acknowledgments.
The separate resident wrapper owns attachment, two Task entries and cooperative
shutdown through copied GEM close messages.

[Development evidence](../development/aes-windows-wa5.json) records ten exact
full-screen comparisons: timers, deferred/accepted top, physical drag, full cover,
latest-model exposure, simultaneous timer/message readiness, repeated redraws,
physical close and two complete restarts. Five test Tasks leave only one spare
slot: the first counter starts, the second creation fails, and cleanup returns
the heap before a normal two-instance launch. Final service shutdown, ownership,
OS restoration and guards pass. Host checks pass 399 tests with four historical
skips. These are development checks, not qualification.

The timed clients touch 514 and 500 bytes of their existing 1,024-byte pools,
leaving 254 and 268 bytes above the interrupt reserve. Across 192 physical units,
charged CPU is 1.82 ms median / 6.85 ms maximum. The 60 complete redraw calls take
76.88 ms median / 194.25 ms p95 elapsed, including update arbitration and
scheduling. The caller-observed logical hold is 60.18 ms median / 114.23 ms maximum;
physical units are independently released between chunks. This functional
fixture deliberately delays consumers and polls its controller, so these are
diagnostics rather than production GUI response limits. PI4/HY4 remain open.

Reserved bank-zero delta is **0 fixed + 0 per public Task + 0 idle bytes**.
Two application models add 392 live upper bytes; wrapper mutable data adds 29,
configuration adds 32 read-only bytes, and the native call pointer adds three.
A fully initialized counter uses 2,052 live / 2,088 heap-reserved bytes for its
binding, delivery, view, workstation and timer. The controller uses 869 / 888.
Their combined heap allocation is 4,973 / 5,064; service storage is separate.
Existing fixed arenas, stack/DP pools and VRAM reservations are unchanged.
The focused scenario uses four public Tasks, three registrations and three
layers. Native disk/pipeline integration and the optional packaged demo remain WA6.

## WA6 — Coexistence and the OF816 demo

The optional `tools/build_demo.py --aes-counters` selection packages the same
resident application body and wrapper with the production shell. It replaces
the native panel, retains the five-second OF816 boot, matching system/work disks,
pinned ROM, notices and checksums, and distributes only `exec816-demo.zip`.
The default shell/prime selection is unchanged. The donor checkout is unchanged.

The four-layer coexistence fixture exposed a continuation deadlock: a console
text segment retained its scene token while a newly queued AES update lock made
that console appear unrunnable. Both counter clients then waited indefinitely
for the scene to become idle. `CONSOLEWINDOWS` now selects the already frozen
unit-zero text source before other views and lets that existing segment finish
before granting the update lock. It still blocks fresh writes. No new kernel
operation, ownership bypass or persistent storage is involved.

The same fixture also exposed stale console text after scroll plus a partial
exposure: the scene painter marked every model row clean after painting only
the exposed rectangle. It now acknowledges all rows only after a successful
full-window repaint; partial exposure leaves remaining model damage pending.
The original failing comparison differed in 2,496 pixels at x=40–238/y=120–190,
so this was distinct from the previously recorded caret artifacts. The exact
framebuffer oracle is unchanged.

Resource admission uses existing pools:

| Scenario | Public Tasks | Layers | AES registrations |
| --- | ---: | ---: | ---: |
| Packaged counter desktop at prompt | 6: shell, presenter, SIO, filesystem, two counters | 3 | 3, including controller |
| Same desktop with CAT/WC pipeline | 8: above plus two Processes | 3 | 3 |
| Panel proof before disk access | 5: root, presenter, panel, two counters | 4 | 3 |
| Panel proof with root-driven disk reads | 7: above plus SIO/filesystem | 4 | 3 |
| Matched native control, no counters | 3 before disk / 5 after disk | 2 | 0 |

Requested stack sizes remain 1,536 bytes for the root, 2,560 for the presenter,
and 1,024 for the SIO/filesystem/panel/counter Tasks. Loaded commands reuse the
remaining suitable existing pools; the second pipeline Process can occupy the
spare 2,560-byte pool. Every pool retains its existing 256-byte interrupt floor
and guards. No extra Task, direct page or stack class is introduced.

Reserved bank-zero growth against the pre-WA profile is **0 fixed + 0 per public
Task + 0 idle bytes**, counting alignment, guards and spare capacity. The common
stack helper also reports a historical +3,072-byte delta against the older
bank-zero-compaction record: the two enlarged presenter-capable pools predate
WA1 and are not a change made here. Demo global arena reservation stays 4 KiB;
the instrumented coexistence fixture uses an explicit 8 KiB upper arena.
Per-counter, controller, workstation and display scratch costs are recorded in
WA4/WA5; WA6 adds no production persistent data. The [full development record](../development/aes-windows-wa6.json)
reports linked banks and measured stacks separately.

PI4/HY4 remain open. The two earlier caret artifacts (x=8–15, y=87 after panel
close; x=48–55, y=207 after scroll/move) remain recorded in the
[mouse history](mouse-acceleration.md). Passing new scene checkpoints does not
close those historical cases or qualify the hosted system.

The production bundle uses 3,196 bytes of native global payload (3,209 including
internal alignment) within the existing 4,096-byte arena. Against the pre-WA
native panel demo, populated image banks rise from 17 to 19 and emitted segment
payload from 901,998 to 949,845 bytes. These are image measurements, separate
from heap-reserved runtime objects. Upper banks `$0E` and `$1C` are newly
populated; the pinned machine already supplies all 63 high banks.

The final extracted ZIP walkthrough checks every archive checksum and its
counter-specific guide, then boots for 249 PAL frames before handoff. It checks
both counter timers, pixel-position drag, top/overlap repair, physical close,
accelerated pointer motion, native shell commands, the eight-Task pipeline,
BREAK during output, writable WORK media and orderly EXIT. All complete scene
comparisons are exact. Guard checks, Task retirement, media audit and OS return
pass. The packaged counter stack peaks are 500 and 498 bytes in the two 1 KiB
pools (268/270 bytes above the 256-byte interrupt floor); presenter peak is
738/2,560, filesystem 577/1,024, and root 589/1,536. These are observed peaks,
not a guarantee for larger application bodies.

An untraced four-layer replay also passes. While one counter is paused outside
all ownership, its peer advances four timer events, the root completes 32 disk
reads and the native panel accepts three updates. The retained reference image
matches again after the delayed client resumes. Service shutdown follows client
retirement and releases all checked ownership.

Matched diagnostics use one instrumented image, enabling either zero or two
counters while running the same native panel toggles/title drags and offered
idle/scroll/disk root workload. Scene geometry and achieved throughput differ
when the two applications are present. Each panel cohort has eight releases,
so its p95 equals its maximum; these are development observations, not acceptance
statistics. Release-to-label ends at the first exact completed scanout and has
up to one-frame observation quantization. The 782 ms native idle outlier remains
included. The counter replay reproduces these gesture timings without tracing.

| Load | Native release-to-label p50 / p95 / max (ms) | With counters (ms) |
| --- | ---: | ---: |
| idle | 180.62 / 782.10 / 782.10 | 180.62 / 280.91 / 280.91 |
| scroll | 160.41 / 160.66 / 160.66 | 180.62 / 260.70 / 260.70 |
| disk | 240.71 / 260.79 / 260.79 | 240.62 / 300.97 / 300.97 |

The counter-specific boundaries are separate. Notification runs from a producer
marker just before GUI `PutMsg` to the application's message-ready hook.
Update wait includes `BEG_UPDATE` to its return; physical wait brackets
`DISPLAY.Enter`. Drawing CPU excludes native interrupts and other Tasks.
Repaint runs from before `BEG_UPDATE` through `END_UPDATE` return, after all
pixel fences, and is distinct from scanout. Timings include both timer repairs
and redraw messages from exposure; they are not all full-window redraws.

| Boundary (ms, p50 / p95 / max) | Idle | Scroll | Disk |
| --- | ---: | ---: | ---: |
| GUI notification | 4.74 / 11.60 / 11.60 | 4.68 / 26.16 / 26.16 | 6.68 / 15.48 / 15.48 |
| Update-lock wait | 32.13 / 133.19 / 152.21 | 41.52 / 126.72 / 142.42 | 31.80 / 153.81 / 182.50 |
| Physical-access wait | 0.91 / 12.89 / 30.82 | 0.91 / 12.55 / 20.42 | 0.93 / 21.13 / 45.63 |
| Caller drawing CPU | 28.31 / 32.95 / 33.14 | 26.89 / 31.63 / 31.67 | 26.89 / 29.59 / 30.58 |
| Completed repaint | 116.17 / 199.97 / 254.69 | 110.62 / 183.56 / 236.99 | 126.69 / 210.59 / 260.78 |
| Logical update hold | 80.20 / 126.25 / 129.71 | 66.49 / 102.56 / 109.96 | 86.00 / 129.62 / 150.68 |
| Physical unit CPU | 1.72 / 7.18 / 8.20 | 1.72 / 7.10 / 7.86 | 1.72 / 6.86 / 7.80 |

The distinction matters: median notification delivery is under 7 ms in these
cohorts, while redraw CPU and update ownership account for much larger portions
of completion. Physical ownership is bounded per strip/chunk; elapsed ownership
can still include preemption. This milestone adds working application windows,
not a claim that whole-response latency is solved.

The instrumented counter stack peaks are 547 and 533 bytes, leaving 221 and 235
bytes above the interrupt floor. The host suite passes 399 tests with four
historical skips; the nine packaging checks also pass. Local documentation links,
Python syntax and whitespace checks pass. These development checks do not
qualify physical hardware or broaden the advertised GEM profile.
