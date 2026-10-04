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

## DT6 Shutdown, failures and two-client load

The controller now closes admission before draining clients. Bindings cannot
initialize after that boundary; queued Register/Open requests are rejected while
existing clients can collect events, cancel, close and unregister. Partial shell
admission unwinds the window, registration and port. Startup adapter failure
releases the stopped service before reporting failure.

[DT6 evidence](../development/desktop-dt6.json) covers raw/optimized capacity
failure followed by successful re-admission, a queued Open crossing the shutdown
boundary, exact cleanup and OS return. Selected raw/optimized blitter faults use
an actual desktop scroll and pending read/write: quiesced hardware permits
cleanup; unquiesced hardware retains the Layers token, registration and borrowed
request under the reset-required contract. DT4/DT5 retain the independent-client
close/cancel, held-button, route retirement and complete-pixel records.

The corrected IRQ path was measured with the second Task computing and repainting
31 times, alongside 100 paced motions and thirty clicks for each load. An
unobserved replay uses the same image and stimuli. The focused FASTEST125 disk
case also checks shared-timer accounting and physical SIO after the IRQ change.

| Two-client load | Pointer median / p95 / max | Button consumption max | Sample gap max |
| --- | ---: | ---: | ---: |
| Idle | 44.39 / 81.27 / 86.83 ms | 23.13 ms | 0.167 ms |
| Console output | 64.09 / 106.03 / 146.82 ms | 87.02 ms | 0.170 ms |
| Physical disk | 46.28 / 105.13 / 165.75 ms | 164.52 ms | 0.271 ms |

Capture counts, the strictly below 1 ms sample-gap gate and serial service pass.
**Pointer p95/max and the loaded disk-button target remain open**, alongside
DT4 outline/repair limits. The single-client DT3 record remains the comparison:
adding application computation/repaint worsens the presentation tail. The
longest observed input-service interval rises to 204.78 ms under disk load;
call elapsed maxima are 9.05/23.34/33.36 ms for idle/scroll/disk. Native IRQ entry
through routing accounts for 31.1/31.1/36.1% of observed elapsed time, excluding
scheduler/RTI. Those observations distinguish capture from Task/presentation
backlog; they are not exclusive CPU or DMA utilization measurements. This slice
does not alter sampling frequency or claim the desktop meets its speed target.

Host checks pass: 338 tests, four historical audit skips; affected generated
layouts are current. No runtime globals, VRAM or Tasks are added by shutdown
handling. Reserved bank-zero growth remains **0 fixed, 0 root/kernel, 0 per
existing public Task and 0 idle bytes**, including guards, alignment and slack.

## DT7 Local desktop preview

`tools/build_demo.py --desktop` selects the framed 64×20 shell plus the
independent graphical application, with no primes. The default build retains
its standard shell/prime workload and five-second OF816 autoboot. The optional
ZIP contains only the OF816 XEX, matching system ATR, pinned AltirraOS ROM,
short ST/port 1 guide, upstream notices and checksums. Existing cartridge work
is preserved separately.

[DT7 evidence](../development/desktop-dt7.json) records cold boot of the exact
packaged media, physical app keys/clicks, title dragging, focus return to the
shell, disk commands, a two-command pipeline and clean exit. Complete scanout is
compared with independent recomposition from retained geometry/content; it does
not reuse target visibility/damage calculations. Prompt occupancy is five Tasks;
the pipeline peaks at seven of eight. Guards, DP/native return, final ownership
and checksum/member checks pass. This is a local development preview, not a
public release or whole-system/hardware qualification.

The combined shell/application exceeds the former 2 KiB upper-RAM globals arena.
The desktop package explicitly reserves 2,560 bytes there: 2,164 payload bytes,
12 alignment bytes and 384 unused bytes. Reservation growth is **512 upper-RAM
bytes**; other demo selections retain their existing profile. There is no new
VRAM or Task pool. Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 per
existing public Task and 0 idle bytes**, including guards, alignment and unused
capacity. The application uses the existing ordinary pool recorded in DT5.

The guide carries the open timing limits: pointer/outline response, disk-load
button delay and move repair. Capture and lifecycle correctness do not close
those targets. The next focused performance work is presentation scheduling,
activation damage and move repair, before adding menus, resizing or a file browser.

## Desktop pointer sensitivity

Interactive feedback identified too little travel for hand movement. The desktop
now maps one decoded ST step to two screen pixels, without acceleration. This is
presenter policy: the sampler, input ABI and native capture remain unchanged.
The input acquisition bounds controller coordinates to 320×120 inclusive; the
presenter scales and clips once before pointer drawing, hit testing, event
delivery and dragging. Overshoot is discarded before scaling, so reversal at
either screen edge responds immediately. The inclusive right/bottom endpoints
639/239 remain reachable; the first reverse step there is one pixel, then two.

[Sensitivity evidence](../development/desktop-pointer-scale.json) records seven
physical motion sequences in each raw/optimized image, including positive and
negative motion, both-axis overshoot and immediate reversal. Native cumulative
counts are checked independently of clamped screen positions. The optimized
fastest-supported input case captures all 97 steps per axis, including vertical
overshoot. Complete-scene drag checks cover idle raw execution and optimized
idle/scroll/disk execution, both screen edges, Escape, event-queue loss, declined
close, hiding and retirement while held. These are development checks, not a
new latency or hardware qualification result. Historical DT3/DT6 measurements
remain tied to their original one-pixel images.

The focused regression uses `tools/build_desktop_input.py --mode raw` or `opt`,
then `tools/test_desktop_pointer_scale.py --program DIR/program --output RESULTS`.
Desktop builds record their scale in `build.json`; physical test tools convert
screen targets into controller steps using that image's metadata. Older frozen
images without the field retain their recorded one-pixel interpretation.

No globals, Task pool, VRAM or memory reservations are added. Reserved bank-zero
growth is **0 fixed, 0 root/kernel, 0 per existing public Task and 0 idle bytes**,
including guards, alignment and unused capacity. Host checks pass: 338 tests,
four historical audit skips; generated desktop definitions are current.

The refreshed `build/desktop/preview-pointer-2x/exec816-demo.zip` includes OF816,
the matching system disk, pinned ROM, guide and notices. Cold boot of those exact
files passes seventeen independently recomposed desktop scenes, application
keys/dragging/focus, disk commands, a seven-Task pipeline and clean shutdown.
Native guards, ownership, DP and OS restoration pass. This local refresh changes
travel sensitivity; it does not close the existing presentation timing targets.
