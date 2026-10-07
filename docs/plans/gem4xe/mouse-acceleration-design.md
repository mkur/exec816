# Desktop mouse acceleration

[GEM integration](README.md) · [Implementation plan](mouse-acceleration-implementation-plan.md) ·
[Current input contract](../../reference/input.md) · [Current desktop contract](../../reference/desktop.md)

Status: MA1–MA2 implemented, 2026-10-07; mild remains opt-in until MA3.
See the [execution record](../../history/mouse-acceleration.md).
Baseline: Exec816 `7f9a25d`, including PI3 and the subsequently tested desktop
demo. The desktop is usable enough to defer further presenter optimization
until it offers a more complete desktop experience. PI4 and HY4 remain open;
this feature does not change their acceptance or historical measurements.

Add a mild speed-dependent pointer profile: precise slow movement and faster
travel across the 640×240 desktop. Preserve a fixed 2× profile as the off option.
Use captured movement timing, so delayed desktop service does not make the
pointer travel farther. Apply the profile in the existing desktop Task before
cursor updates, hit testing, dragging and application event delivery.

## Scope and ownership

The ST mouse on port 1 and VBXE remain the initial target. Keep the existing
approximately 4 kHz capture schedule and fine-timing SIO exceptions. Acceleration
adds neither a Task nor a timer request, signal, scheduler policy or kernel
operation. It does not reduce the time until a redraw appears; it improves the
relationship between hand movement and pointer travel.

The platform adapter owns physical transition capture and timing metadata.
The input library owns ordered delivery, acquisition/route lifetime and loss.
The desktop owns pointer sensitivity, screen coordinates and clipping. GEM and
native applications continue receiving absolute screen coordinates through
their current GUI interfaces; applications need no acceleration code.

This follows the project's Exec/GUI separation: device capture supplies facts,
and the GUI supplies pointer policy. As a conceptual reference, libinput also
distinguishes adaptive and flat profiles and derives adaptive behavior from
motion speed; this proposal uses a much smaller integer implementation suited
to the 65816. See its [pointer acceleration documentation](https://wayland.freedesktop.org/libinput/doc/latest/pointer-acceleration.html).

Initial selection is a build setting, `off` or `mild`, recorded in build
metadata. Make `mild` the desktop default only after the integration checks.
A preferences window, persistent settings, multiple devices and per-application
profiles are later work. The existing Control Panel remains a widget demo.

## Why the baseline event stream was insufficient

At the PI3 baseline, [deskinput.act](../../../lib/desktop/deskinput.act) asked INPUT for bounded
controller coordinates and multiplied them by `POINTER_PIXELS_PER_STEP = 2`.
The [input library](../../../lib/input/input.act) had already discarded motion
beyond those controller bounds. Accelerating differences between these absolute
coordinates would lose movement and give incorrect behavior at screen edges.

The [capture adapter](../../../platform/altirraos/pointer.s) stores cumulative
counts in a 32-record ring and merges compatible movement. Its VBI tick does
not preserve the timing of each merged transition. Dividing a delivered delta
by time since the previous desktop service would measure rendering and disk
load as well as mouse speed. A coarse VBI timestamp alone is also insufficient
for the intended response.

Consequently this feature needs a small capture-data change before the desktop
filter. Simply adding a multiplier in `Service` is insufficient.

## Preserve timed runs of relative movement

Keep cumulative hardware counts for existing absolute-coordinate acquisitions
and loss/baseline handling. Add a relative acquisition mode to the same current
INPUT API. In that mode, motion events carry unclipped signed transition counts
plus a timing class. The desktop alone changes to relative input.

The producer classifies the interval preceding each legal nonzero transition.
A transition is the sampled vector `(dx, dy)`, with each component −1, 0 or +1.
Capture supplies a quantized duration, not a desktop gain. Use a small generated
age-to-class table; an initial set of upper bounds in clock quanta is
`1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 255`, plus an explicit
reset/unknown class. A zero or invalid interval uses the reset class, not the
fastest class. Freeze the encoding and boundary convention in the ABI generator
before implementing consumers.

A raw movement record may merge transitions only when acquisition, route,
epoch, button state, exact vector and timing class match. Cap a run at 64
transitions. Keep the producer's previous-motion clock and direction history
independent of whether a ring record was consumed or the ring became empty.
Otherwise faster Task service would itself change the next gain.

An available run is readable immediately. There is no waiting for a bucket to
expire, a run to fill, or a future sample. Splitting a run because the consumer
read it early must produce the same total displacement as reading it together.
The exact-vector rule also makes clipping an aggregated run equivalent to
clipping its monotonic component transitions.

Button changes remain ordered barriers. A sample containing movement and a
button change retains the existing motion-before-button ordering. Its movement
is delivered once; the retained button event has zero relative delta. A pure
button change does not change the speed estimate. Acquisition/route changes,
discard, loss, invalid timing and a direction reversal reset velocity history;
the first following movement uses the slow gain. Keep the existing durable
loss and gesture cancellation behavior.

## Platform interval clock

Use a saturating age measured from ANTIC `VCOUNT` at existing pointer captures
for the first PAL implementation. A quantum spans two scanlines; PAL has 156
quanta per frame. While motion history is active, accumulate modular differences
between successive samples and saturate at 255 quanta, approximately 33 ms.
After saturation the idle fast path need not keep updating that age; the next
motion restarts history at the slow gain. No periodic Task wakeup is needed.

This is a short platform-local motion interval, valid under the existing
sub-millisecond capture-gap requirement. It is not a new public monotonic clock.
Frame wrap, first-sample initialization and the saturated state need explicit
tests. Detected capture/timing discontinuities invalidate history and must never
be interpreted as a high speed. A modulo beam phase alone cannot detect an
entire missed frame; this design retains the capture-gap requirement rather
than claiming recovery from arbitrary interrupt suspension.

Do not use physical timer IRQ counts as elapsed time: normal and fine modes
have different periods and SIO can reset the timer phase. Do not concatenate
`E816_VBI_COUNT` with `VCOUNT` without proving their phase relationship and NMI
read protocol. The existing public event tick retains its current meaning.

MA1 must prove the chosen interval clock under beam wrap, normal/fine timer
transitions, SIO restarts and native/emulation interrupt entry. Measure the
extra active-idle capture cost as well as the movement path. If the clock or
cost fails these checks, revise the capture implementation before integrating
the profile; do not substitute presenter drain timing. NTSC acceleration needs
its own generated clock constants and equivalent evidence before a support
claim. The initial demo claim remains the pinned PAL configuration.

## INPUT representation and migration

The proposed public layout keeps `InputConfig` at 32 bytes and `InputEvent` at
24 bytes. Allocate a configuration flag for relative pointer delivery, an event
flag identifying relative coordinates, and replace the event's reserved word
with `motionInfo` for the interval class, vector shape and reset indication.
Keyboard and absolute-pointer events keep that word zero. In relative mode the
initial-coordinate and maximum fields are unused; screen bounds belong to the
desktop. Document their required configuration values at admission.

Relative pointer/button events use `x` and `y` as signed deltas. Loss events
continue to carry their established loss information and are not motion.
Metadata must describe the delivered run, including the zero-delta retained
button case. The generated layout must make these rules unambiguous.

Bump INPUT's version from 2 to 3, regenerate Action!, assembly and C bindings,
and migrate all callers and fixtures together. This is one API with two useful
coordinate modes, not two implementations or a version-2 compatibility layer.
Audit C consumers that currently require the reserved event word to be zero.
Establish mode/configuration validity once at acquisition. Trust generated
records thereafter while retaining queue bounds, lifetime and loss handling.

The native sample grows from 24 to 28 bytes: retain existing fields
and add the interval class, vector encoding and bounded run length. The initial 32-slot proposal
would cost 128 additional live bytes. Up to 24 bytes of extra producer
history could fit alongside it within the existing 1,536-byte upper-memory
reservation: the current 1,280-byte structure and two 16-byte guards leave
224 bytes spare. Pin actual offsets and guard placement through
[input-native.json](../../../abi/input-native.json) and its generator.

MA1's capacity check requires 64 slots: 60 alternating axis transitions can
arrive within about 31 ms at the supported per-axis rate. The 32-slot diagnostic
fails this delayed-drain case. The final 2,304-byte structure occupies a
2,560-byte reservation, including two 16-byte guards and 224 spare bytes.
Capture stays at `$4810`; blitter code moves to `$5200`, native source state to
`$5A00`, and timer state to `$5B00`, all in the same upper Task bank. Native code
stays at `$6000–$7FFF` and now also holds the pointer routines and timing table.
Relative to PI3, capture reservation grows by 1,024 bytes while the following
native-work suballocation loses 512 bytes of padding, a net 512 reserved upper
bytes with no additional bank. Loaded physical checks remain necessary: never
hide overflow by merging different timing classes or vectors. Arbitrary consumer
stalls retain ordinary bounded-queue loss semantics.

## Desktop transform and initial curve

Put the transform in a small desktop module with screen position, fractional
remainders and the selected profile. Use signed fixed-point arithmetic with
quarter-pixel units. Read one gain for a timed run and apply the same gain to
both axes. A shape column in the gain table may account for the greater length
of simultaneous two-axis transitions, using a documented integer approximation;
axis-aligned and diagonal travel need explicit comparison during tuning.

The following are tuning anchors, not measured user-preference claims:

| Captured movement | Mild profile | Off profile |
| --- | --- | --- |
| First movement after reset or a pause | 1 pixel per transition per active axis | 2 pixels |
| Slow deliberate motion, about 80 transitions/s or less on one axis | 1 pixel | 2 pixels |
| Ordinary movement, roughly 160–320 transitions/s on one axis | About 2 pixels | 2 pixels |
| Fast travel, roughly 500 transitions/s or more on one axis | Up to 4 pixels | 2 pixels |

Use intermediate gains such as 1.5× and 3× and a monotonic table between these
anchors. Keep the first profile conservative and cap it at 4×. Both modes use
the same relative-coordinate path; `off` selects a constant gain. Generate the
table from recorded parameters. Use shifts/adds for its limited fixed-point
gains, with no general multiply, divide, remainder or floating-point helper in
the transform. A larger lookup table is unnecessary for the initial curve.

Preserve fractional motion across compatible runs so draining one run as
several events cannot change distance. Clear fractional remainders on a capture
history reset, including reversal or an elapsed pause. Clear desktop motion
history and remainders on loss or a new acquisition/route, retaining the last
screen position and selected profile.
Use capture reset metadata for elapsed pauses, never desktop wall time. There
is no smoothing window, deferred flush or synthetic movement after the mouse
stops. The stepped curve and single-transition speed estimate are deliberately
basic; measured boundary jitter is a tuning issue to check before enabling it.

Clamp in pixel space to `0..639` and `0..239`. Discard outward excess, including
the clipped axis's fractional remainder, so reversing at an edge responds
immediately. Never retain an overshoot debt. The off profile preserves 2×
sensitivity but need not reproduce the old controller-grid edge artifact:
from pixel 639, one negative transition now reaches 637, rather than 638 after
the old controller-coordinate clamp.

Transform each newly taken INPUT event exactly once in `DESKINPUT.Service`,
before publishing cursor position or calling `Consume`/`AESINPUT.Push`.
The AES deferred-input queue stores final absolute screen coordinates, as it
does now. Replaying that queue must not run the acceleration filter again.
Cursor drawing, window hit testing, button feedback, client events and drag
geometry all use the transformed coordinates. Keep the same profile while a
button is down; a click or drag must not introduce a sensitivity jump.

## Cost and acceptance

Reserved bank-zero growth is **0 bytes fixed, 0 bytes per public Task and
0 bytes for idle**, including guards, alignment and unused capacity. Existing
stacks, direct pages, Tasks, signals and VRAM reservations remain unchanged.
Producer history and raw records use upper memory; the desktop gains a small
upper-memory state block and constant tables. Report actual live bytes,
reserved bytes and any linked bank-boundary growth separately in each slice.

The implementation is ready for a demo when:

- The same captured transitions/timing yield identical final coordinates and
  button positions under different ring-drain schedules, without loss. Cursor
  presentation can still skip intermediate positions when service is delayed.
- Slow/fast travel, fractional motion, pauses, reversals, all four edges,
  diagonals, clicks, dragging and deferred AES input follow the rules above.
- Selected idle, scrolling and disk traces preserve capture and SIO timing,
  queue capacity, context restoration, guards, shutdown and loss cancellation.
- The feature adds no deliberate input delay. Record capture and Task CPU cost
  against PI3 and investigate new latency or loss regressions; broader PI4/HY4
  completion remains deferred.
- The refreshed OF816 desktop archive passes checks on its extracted contents.

Development checks cover this feature and its interrupt/transport dependencies.
They do not qualify other hardware, unsupported video modes or the full hosted
system. The [implementation plan](mouse-acceleration-implementation-plan.md)
orders the capture, transform, loaded checks and demo slices.
