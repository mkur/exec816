# Mouse acceleration development

[History index](README.md) · [Design](../plans/gem4xe/mouse-acceleration-design.md) ·
[Implementation plan](../plans/gem4xe/mouse-acceleration-implementation-plan.md) ·
[Current input contract](../reference/input.md)

## MA1 — Timed relative capture

Implemented on 2026-10-07. INPUT version 3 adds relative acquisitions while
preserving absolute users and the 24-byte public event. Native capture records
bounded runs with a common vector and interval class. Producer timing survives
partial drains; button transitions retain movement-before-button order without
duplicating the delta. The desktop still uses fixed 2× absolute input in MA1.

The initial 32-slot ring failed the delayed-drain diagnostic. At the supported
per-axis transition rate, alternating axes can produce 60 records in about
31 ms, comparable to the PI3 loaded service gap. The final 64-slot ring passes
that case with high-water 60. Arbitrary longer stalls can still report loss.

The capture structure grows from 1,280 to 2,304 bytes; its guarded reservation
grows from 1,536 to 2,560. Moving adjacent blitter/source/timer extents reuses
512 bytes of alignment capacity, for **512 additional reserved upper bytes**
inside the existing Task bank. Pointer code and its 256-byte timing table move
into spare native-work code space in that same bank. Bank-zero deltas, including
guards/padding/spare capacity, are **0 fixed, 0 per public Task and 0 idle**.
No additional CPU bank, Task, DP, stack, signal, timer or VRAM is reserved.

[Development evidence](../development/mouse-acceleration-ma1.json) records:

- 886 emitted assertions in each raw/optimized relative fixture: beam wrap and
  saturation, every interval value, partial-drain invariance, run limits,
  timing barriers, buttons, reversal, loss and the 60-record delayed drain.
- Physical absolute and relative ST capture, including independent timing-class
  expectations for the paced slow trace; emitted decoder failures and NMI entry;
  raw/optimized C/Action! layout and context checks.
- Real SIO transfers with pointer capture in native and emulation entry, no
  capture loss, preserved normal/fine cadence and passing wire-timing gates.
  A timer.device queue test covers the relocated state.
- The physical desktop boundary case preserves all 97 transitions on each axis.
  Its largest measured sample gap is 312.386 µs against the 1 ms limit; mean
  sampler cost is 9.139 µs. That workload also contains an intentionally
  unsupported burst; these are workload observations, not a universal cost bound.
- 30 focused host checks and generated-definition/whitespace checks.

The compiler source remains the clean pinned revision. Its host executable was
built with `CARGO_PROFILE_DEV_OPT_LEVEL=2` to shorten iteration; emitted raw and
optimized modes remain explicitly selected in each test. Binary hashes and
machine pins are in the evidence. These development checks do not qualify the
whole hosted system, NTSC acceleration or physical hardware. PI4/HY4 remain open.

## MA2 — Desktop profiles

Implemented on 2026-10-07, with `off` as the intermediate default. The desktop
acquires relative input, applies the generated curve once, then publishes
absolute pixels to cursor, gestures, native clients and deferred AES input.
A replayed AES event is already transformed. Both profiles clamp in pixel space;
`off` retains 2× motion, with the intentional odd-edge reversal change.

The mild table supplies 1×, 1.5×, 2×, 3× and 4× gains with a common diagonal
speed estimate, signed quarter-pixel remainders and reset on pause/reversal/loss.
The Action! transform uses shifts/adds and a 64-byte table; emitted inspection
finds no external arithmetic helper or gateway call. The new module occupies
1,726 code bytes and 76 live data bytes (77-byte extent with internal alignment).
It fits existing code/data reservations: **0 reserved upper-byte growth and no
additional linked bank** against the equivalent MA1 two-application fixture
(16 populated image banks in both). Bank zero remains **0 fixed + 0 per Task +
0 idle bytes**. No Task, timer, signal, DP, stack or VRAM reservation is added.

[MA2 evidence](../development/mouse-acceleration-ma2.json) records 2,870 optimized
transform assertions against an independent rational oracle, including split
runs and fractional tails, all classes, signs, resets and corners. Apply's
measured elapsed mean is 159.8 µs; the maximum is 809.3 µs including preemption.
The small AES queue fixture passes 35 assertions in each raw/optimized build,
including fractional motion followed by deferred button delivery. Physical
`off` and `mild` edge/reversal checks and the fastest supported diagonal capture
trace pass. Idle physical drags pass full-scene pixels, both screen edges,
Escape, event-queue loss, refused close, hide and retirement while held. Real
update/mouse locks pass retained click and drag replay (101 C assertions), disk
progress and frozen-pixel checks. Host checks pass: 399 tests, four historical-source skips.

Physical integration helpers now observe coarse physical travel and finish with
isolated slow phases. They never write guest cursor coordinates. Altirra paces
electrical phases according to movement backlog, so a host packet cannot be
assumed to have constant fast gain. The independent curve and captured-stream
fixtures remain the displacement oracles.

The expanded two-application drag run exposes a stale eight-pixel shell caret
at `(8..15,87)` after Control Panel closure. The frozen PI3 image reproduces
exactly those pixels; this is a retained rendering defect, not a change in
pointer coordinates or geometry. A loaded scroll/move also left an old caret
at `(48..55,207)` despite correct geometry. These exact-pixel failures are
retained as limitations; no renderer assertion or acceptance limit is relaxed.
PI4/HY4 and broader renderer work remain deferred.

## MA3 — Loaded checks and mild default

The default is now `mild`; `--mouse-profile off` remains available. The generated
default module exactly matches the explicit mild module used in MA2/MA3 images.
No curve tuning was needed. Bank-zero deltas remain **0 fixed, 0 per Task and
0 idle**, with no additional upper reservation or linked bank in this slice.

[MA3 evidence](../development/mouse-acceleration-ma3.json) records nine physical
traces across idle, scrolling and disk work: alternating axes, interval bands,
pauses and reversal. Every delivered run matches an independent rational
transform; hardware counts, epochs, cleanup and guards pass with no selected
trace loss. The observed queue high-water is three records; MA1's delayed-drain
high-water 60 remains the stronger capacity test. Sampled classes can differ
near a boundary under different loads, but captured-fact replay remains exact.

A matched 10-motion/10-button cohort per load and profile shows:

| Load | Button consumption median, off → mild | p95, off → mild |
| --- | --- | --- |
| Idle | 2.62 → 2.61 ms | 7.95 → 2.62 ms |
| Scrolling | 6.44 → 6.41 ms | 11.76 → 11.68 ms |
| Disk | 7.43 → 7.99 ms | 8.76 → 11.35 ms |

Cursor scanout p95 remains about 46.6 ms for both profiles, with frame-granular
observation. The largest capture gap is 319.2 µs for mild, below 1 ms. These
small cohorts show no broad timing regression; their tails are observations,
not a statistical bound or widget-feedback result. No HY4 claim is made.
The measurement tool now keeps each load's source samples when computing its
breakdown, and separates partial desktop cadence traces from full SIO lifecycle
analysis. Existing MA1 wire-timing gates remain the transport evidence.

Physical positioning helpers use coarse observed travel and a slow exact tail;
this keeps real lock/replay gestures inside the fixture's six-second lock.
The previously recorded exact-pixel caret failures remain open. No presenter,
renderer, Task schedule or sampling budget was changed to enable mild motion.
