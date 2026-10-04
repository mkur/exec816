# Desktop development

[Plan](../plans/gem4xe/desktop-implementation-plan.md) · [Roadmap](../roadmap.md)

## DT0 Inputs and budgets

The [baseline record](../development/desktop-dt0.json) freezes the existing
bitmap shell, companion disk, OF816 image, compiler, ROM and actual mouse-capable
emulator. A fresh unchanged-package smoke passed five-second autoboot, TASKS,
system volume navigation, disk HELLO, shared-cache reads, CAT/WC pipeline and
EXIT with ownership/OS restoration checks.

The current shell runs in the root Task. Console, filesystem and SIO bring
prompt occupancy to four; a two-command pipeline peaks at six. The proposed
second application raises these to five/seven of eight public slots. The
presenter will reuse the existing 2,560-byte worker pool, admitted before other
clients. Root owns the shell window/controller; the second Task registers itself.

The Layers scene occupies 4,782 upper-RAM bytes. Client queues, window records
and retained command storage will be heap allocations, not additions to the
2 KiB resident globals arena. The existing aperture and command arena remain.
Combined stack use and final UI storage are later slice measurements, not
established by the separate Layers fixture.

Existing CAT and ST capture evidence is retained rather than rerun. The saved
short-echo trace ends at drawing return, not visible scanout. DT3 must run its
new visibility observer against the frozen unchanged image as well as the
desktop; no visible-latency baseline is inferred from that older trace.

Reserved bank-zero change is **0 bytes fixed, root/kernel, per public Task and
idle**, including guards, alignment and unused capacity. DT0 adds no runtime
state. This is development evidence and does not qualify the desktop.

## DT1 Client and event service

[Native service](../reference/desktop.md) now implements four registered
clients/windows, retained fill/text batches, bounded event queues, durable
loss/focus/close bookkeeping and separate control/content/event/cancel lanes.
The service retains each owner through final reply publication. It uses ordinary
Exec messages and a recording Layers backend; hardware integration is DT2.

[Raw and optimized evidence](../development/desktop-dt1.json) each passed 143
assertions with two independent client Tasks and a presenter. The fixture covers
a waiting peer, cancellation while a paint defers controls, completion winning
a late cancellation, queue overflow/motion coalescing, invalid batches, stale
IDs, capacity exhaustion and final cleanup. A separate held-removal case reaches
the expected Exec launch fault. Stack/domain guards, native context restoration
and successful-run allocation ownership checks passed. The host suite passed
337 tests with four historical skips. These are development checks.

Service payload is 10,372 upper-RAM bytes. The fixture adds a 32-byte guard and
a separate 710-byte source batch. Three public Task slots are occupied during
the test; the production desktop has not yet been attached to the console.
Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 per public Task and
0 idle bytes**, including guards/alignment and unused pool capacity.

## DT2 Framed console and retained painting

The existing console worker now presents a 64×20 shell through Layers, with
pixel clipping for partial glyphs and odd packed-pixel edges. It paints bounded
sixteen-scanline stripes or four retained commands per turn and keeps one Layers
token through a repaint continuation or asynchronous scroll. Fully covered
damage stays retained without keeping the worker runnable. The console’s
short-write pass and fully visible scroll path remain available.

[DT2 development evidence](../development/desktop-dt2.json) contains six exact
framebuffer/scanout comparisons and 40 assertions in each raw/optimized image:
typing, circular-row scrolling, translated placement, an odd-edged overlapping
panel, clear/hidden content and close/exposure. Both runs return cleanly with
stack/domain/context and allocation ownership checks. Selected optimized
full-screen bitmap, standard text window lifetime/isolation, and the 143-check
native desktop service regressions passed. The host suite passed 337 tests
with four historical skips.

The packaged framed shell also passed the OF816 five-second cold boot, TASKS,
MOUNT, disk HELLO, physical cached reads, CAT/WC pipeline and EXIT walkthrough.
It peaks at six Tasks; the second independent graphical application is DT5.
This is a local shell-only development artifact, not the completed DT7 preview.
Pointer routing, gestures, loaded failure/timing checks and final preview
packaging remain later slices.

The scene/service payload is 10,378 bytes, rounded to 10,384 by AllocMem. Runtime
and root-controller globals add 138 payload bytes in upper image RAM, with
compiler alignment; no resident arena or bank-zero region grows. The worker
used at most 678 stack bytes in these raw/optimized fixtures, leaving 1,626
bytes above the reserved interrupt floor in its existing 2,560-byte pool.
The root peak is 372 bytes; kernel peak is 266 bytes. These observations are
workload-specific lower bounds, not a new universal stack qualification.

Reserved bank-zero delta against **DT0** is **0 fixed, 0 root/kernel, 0 per
public Task, 0 idle bytes**, including guards/alignment and unused capacity.
Older shared harness `bank_zero_delta` fields compare against pre-large-stack
compaction and therefore include the already-existing 3,072-byte enlargement;
`reserved_bank_zero_delta` explicitly compares the desktop slices with DT0.


## DT3 ST input, focus and pointer checkpoint

The existing presenter now owns the ST/port 1 pointer source, route and wake
signal. Keyboard focus publishes a graphical window route or the console's
current foreground route; KEY and BREAK keep their capture-time destination.
Pointer capture and Timer 1 policy are unchanged. Input draining is bounded and
idle checks remain cheap. A new release observation is required after source
loss. Shutdown restores the pointer and releases input before display storage.

The shared drawing backend removes intersecting overlays before drawing and
retains both odd/even masks in VRAM. The initial measured move call took about
28 ms with a mask upload; the retained-mask version takes about 6.2 ms. Showing
new motion before another output quantum also reduces loaded response. These
changes stay in the drawing/presenter layers, above Exec and the sampler.

[DT3 development evidence](../development/desktop-dt3.json) separates functional
checks from timing acceptance. Raw/optimized exact scene checks, graphical
KEY/BREAK routing, captured electrical counts, ordered buttons, source/port
cleanup and native guards pass. The supported-rate case decodes 97 diagonal
transitions at 1.029 ms spacing. The independent negative control emits 256
transitions per axis at intervals down to 64.282 µs; the consumer misses
movement, so this rate remains unsupported even without a LOSS notice.
The focused FASTEST125 and ordinary 57.6k physical SIO cases pass the shared
sampler/timer checks. An unobserved replay preserves functional results.

Each optimized idle/scroll/disk latency case has 100 paced motion observations
and thirty clicks (sixty separately observed edges). The observer compares
actual completed scanout and reports an upper bound, not drawing completion.
The final early-presentation run records these capture-to-visible values:

| Load | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Idle | 43.63 ms | 46.41 ms | 46.66 ms |
| Sustained console output | 45.02 ms | 65.61 ms | 80.01 ms |
| Physical disk reads | 43.87 ms | 62.15 ms | 85.94 ms |

All maximum-latency and button-consumption targets pass in that run. **The p95
pointer targets remain open**: 40 ms idle and 60 ms loaded. DT4 can proceed with
this explicit limitation; DT6 must retain it in the two-client record and final
preview unless a measured follow-up closes it. Idle input-service intervals
include intentional waiting; they are not equivalent to queued-event delay.
The trace records IRQ elapsed share and drawing-call elapsed time separately;
neither is a whole-system CPU-utilization qualification.

The new scanout observer also runs on the frozen DT0 shell image. Twelve short
key echoes measure identical full-screen baseline/current p95 and maximum,
35.63 ms, meeting the regression target. The framed shell is recorded separately
at 55.87 ms p95/maximum. These are completed-scanout observations with PAL frame
resolution, not sub-frame hardware-display measurements.

Service payload is 10,532 upper-RAM bytes, rounded to 10,536 heap bytes. Desktop
runtime/controller globals have 280 payload bytes plus compiler alignment.
Pointer storage grows from 1,024 to 1,280 reserved VRAM bytes: one save plane
and both AND/OR mask pairs. This consumes former slack and 256 additional
reserved bytes; no extra aperture is introduced. No Task is added.
Reserved bank-zero growth against DT0 remains **0 fixed, 0 root/kernel,
0 per existing public Task and 0 idle bytes**, including guards and slack.

## DT4 Captured, nonblocking window movement

The presenter now captures title-bar drags, displays an XOR outline and commits
clamped/grid-aligned geometry after active work retires. Escape, input/event-queue
loss, hiding or closing cancel the gesture; observing release rearms it. A
close gadget sends a durable cooperative request, while the shell uses EXIT.
The four outline edge records reuse the existing command arena and are ordered
below the pointer. Neither input capture nor request intake waits for release.

[DT4 development evidence](../development/desktop-dt4.json) passes raw/optimized
exact scene checks, repeated repair, reversal, both screen edges, queue overflow
while held, Escape, hide, close refusal and retirement while held. The optimized
run measures thirty drags and 120 outline positions per load. Loaded outline
checks exclude changing console client pixels; release compares the full scene.

| Load | Outline median / p95 / max | Release-to-visible repair median / p95 / max |
| --- | ---: | ---: |
| Idle | 70.92 / 70.92 / 712.56 ms | 660.65 / 660.65 / 660.65 ms |
| Console output | 339.83 / 580.44 / 580.57 ms | 760.94 / 901.39 / 901.39 ms |
| Physical disk reads | 74.50 / 108.74 / 111.06 ms | 700.69 / 740.83 / 1422.80 ms |

**Outline and 250 ms repair targets remain open.** These are complete scanout
upper bounds. The first raise can invalidate the shell; repaint continuations
and loaded model/paint ordering dominate the long tail. The release observer
also stops/drains the producer before its full-scene comparison, so a disk read
can extend that bound. Functional dragging does not establish a snappy desktop.
A focused follow-up should separate frame-only activation damage, outline
priority and move repair/copy cost before adding richer window chrome.

Development checks: 337 host tests (four unavailable historical audits skipped),
generated definitions, raw/optimized scene tests and physical gesture fixtures.
Added storage is 36 bytes of Action globals and 12 bytes of C globals in upper
RAM, plus compiler alignment within existing image reservations. VRAM growth is
zero. Reserved bank-zero growth remains **0 fixed, 0 root/kernel, 0 per existing
public Task and 0 idle bytes**, including guards and unused capacity.

## DT5 Independent overlapping application

The optional `DESKAPP` client runs on an ordinary Task, with its own reply port,
registration, retained fill/text batch and pending event request. Clicking it or
sending a key performs a finite compute loop without GUI calls and replaces its
content. Its close gadget retires that client cooperatively. Shell output behind
the panel remains retained and is reconstructed on exposure. Either client can
retire first; stopping the demo cancels and collects the app's event request
before releasing its registration, port and storage.

[DT5 evidence](../development/desktop-dt5.json) records thirteen complete scene
comparisons in each of raw and optimized execution, physical keys/clicks, both
retirement orders, guards, ownership and OS return. Earlier DT1/DT4 records cover
invalid batches, bounded slow consumers, capacity, queue loss and captured drag
retirement. Two-client load timing and packaged pipeline occupancy follow in
DT6/DT7.

Raw reverse retirement exposed a platform IRQ race: a keyboard edge arriving
after its bounded capture check was classified as unowned and chained into ROM,
which re-entered startup in this observed sequence. The final pending check now
excludes keyboard/BREAK only while the native keyboard lease is live, as it
already excludes owned Timer 1. It leaves a late edge latched for the next native
entry. A frozen-image A/B reproduces the failure with the old mask and completes
with the corrected mask. Standalone raw/optimized keyboard tests also cover the
path without a mouse sampler. Sampling frequency and decoding are unchanged;
loaded physical SIO checks are in DT6.

Application globals add 289 upper-RAM payload bytes plus alignment; its retained
content allocates 710 bytes, rounded to 712. It occupies one existing ordinary
Task pool: 1,024-byte stack, 256-byte DP, 1,312 reserved bytes including guards.
VRAM growth is zero. Reserved bank-zero growth is **0 fixed, 0 root/kernel,
0 per existing public Task and 0 idle bytes**, including alignment and unused
capacity. Host checks: 338 tests, four historical audit skips; development tier.
