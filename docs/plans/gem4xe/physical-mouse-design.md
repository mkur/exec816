# Physical mouse support for hosted GEM

[Implementation plan](physical-mouse-implementation-plan.md) · [GEM work](README.md) ·
[Current input contract](../../reference/input.md) ·
[Platform contract](../../reference/platform.md) · [Roadmap](../../roadmap.md)

Status: implemented through M0–M6 development checks, 2026-10-02. This follows the completed
[I0–I7 input milestone](input-and-events-implementation-plan.md). The selected
emulator device is **ST mouse on joystick port 1**, matching the user's confirmed
Altirra configuration. See the [execution record](../../history/gem-mouse.md)
and [current input contract](../../reference/input.md). The design discussion
below preserves its pre-implementation rationale; it is not a qualification claim.

The result should be a mouse that moves the existing cursor and operates the
field, Count and Exit controls while keyboard input and physical SDFS reads
continue. Use Altirra's existing mouse model and configuration. The work belongs
in Exec's input backend and shared hardware ownership; it does not require a
new mouse device model or a ROM paddle-scan adaptation.

## Supported target and evidence

Altirra's existing input map is named `Mouse -> ST Mouse (port 1)`. It maps host
horizontal/vertical movement and mouse buttons to the ST controller. The map is
defined in
[inputmanager.cpp](https://github.com/ilmenit/AltirraSDL/blob/52c18c89e354290199d6f1bbd98eb5048849b15c/src/Altirra/source/inputmanager.cpp);
the quadrature and trigger outputs are implemented by `ATMouseController` in
[inputcontroller.cpp](https://github.com/ilmenit/AltirraSDL/blob/52c18c89e354290199d6f1bbd98eb5048849b15c/src/Altirra/source/inputcontroller.cpp).

The first Exec backend supports motion and the left button on this configured
port. Record the enabled map, sensitivity, host capture settings and conflicting
port mappings alongside the existing
[ROM/emulator/machine pin](../../../toolchain/altirra-gem-vdi.json).
Configuration establishes the emulated device; emitted-code tests must establish
that Exec consumes it correctly. A real ST mouse on physical hardware remains
a separate validation claim.

The pinned GEM4XE
[pointer implementation](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/pointer.c)
provides useful decode tables. Its standalone timer installation owns registers
also used by Exec SIO, so reuse the decoder findings through an Exec backend.
The [input manifest](../../../ports/gem4xe/inputs.json) currently excludes the
donor pointer runtime.

The [Altirra Hardware Reference Manual](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf),
2026-01-02 edition, section 7.3, describes quadrature on joystick direction
lines and the left button on the trigger input. Motion requires frequent samples.
A once-per-frame sample can miss entire quadrature cycles without observing an
invalid transition.

## Port and decoding

| Resource | First backend |
| --- | --- |
| PORTA, `$D300`, bits 0–3 | Read port 1's ST quadrature lines. Preserve port 2 and PIA configuration. |
| TRIG0, `$D010`, bit 0 | Read left button: zero means pressed. Check that the selected GTIA configuration does not latch a stale press. |
| POT inputs / POTGO | Not needed for motion and the left button. |
| POKEY timer 1 | Proposed shared sample clock and existing SIO fine-alarm clock; see ownership below. |
| VBXE and cursor backing store | Existing renderer remains the sole graphics owner. |

Select ST/port 1 explicitly. Do not auto-detect a mouse from an idle nibble:
an absent device or another controller can present the same levels. Reject
unsupported backend/port configurations before changing ownership.

Use one PORTA read for both axes. For nibble bits `b0..b3`, the donor's
emulator-tested pairing is X = `(b0 << 1) | b1`,
Y = `(b2 << 1) | b3`. Decode through a four-state Gray-code transition table,
with unchanged state yielding zero and opposite-state jumps yielding loss rather
than an invented direction. Verify both signs against actual controller output;
seed the previous state from the first sample without moving the cursor.

Accumulate decoded motion with checked counters. Task context converts it to
absolute `0..639` / `0..239` coordinates, initially one transition per pixel
without acceleration. Continue consuming motion at screen edges. Keep sampled
button transitions ordered with the motion position observed at each transition.

## Shared timing with SIO

The proposed clock is the timer-1 base already configured by
[native SIO](../../../platform/altirraos/sio.s). SIO currently uses it for fine
phase alarms, enables it only while an alarm is armed, and disables owned timer
bits at terminal completion. Its initialization also rejects existing timer
owners. These paths require an explicit shared-ownership migration.

Move timer-1 configuration, interrupt acknowledgement and enable decisions into
one platform timing component used by the SIO adapter and pointer backend.
Use the existing fine-alarm divisor as the initial experiment, measuring its
actual period and worst sampling gap on the pinned PAL/65C816 configuration.
Preserve SIO's logical alarm units; choosing a different base period requires
explicit conversion and timing regressions.

The component has two fixed users: SIO's fine alarm and pointer sampling. Keep
timer 1 enabled while either requires it. A physical tick is acknowledged once;
it advances an armed SIO alarm once and performs at most one pointer sample.
Disarming an SIO alarm must not disable pointer capture. Releasing the mouse must
not disturb an armed SIO alarm. Idle, command, payload, terminal, recovery and
shutdown states all need the same ownership rule.

This is platform coordination, not a GEM-private kernel service. Existing public
producer admission protects Task and signal lifetimes. The driver retains SIO
queue, phase, cancellation and recovery policy. If implementation needs an
additional kernel operation, specify a reusable public ABI rather than extending
a private SIO-to-mouse protocol.

| Shared concern | Required behavior |
| --- | --- |
| IRQ dispatch | Service time-critical serial work first, then bounded timer/mouse work, with the serial rechecks needed to meet measured deadlines. |
| IRQEN / POKMSK | Compose enabled sources from live owners; retiring SIO must preserve an active pointer source and vice versa. |
| AUDF/AUDC / AUDCTL | One writer maintains the shared timing baseline. Mouse admission cannot overwrite the serial divisor or unrelated channel configuration. |
| STIMER | SIO transaction setup resets hardware timer phases. Account for that sampling gap and preserve logical alarm behavior; never restart timers merely to acquire the mouse during a transfer. |
| SKCTL and keyboard | Retain existing serial/keyboard ownership. The mouse does not reset keyboard scanning or use fast paddle mode. |
| Native and emulation IRQ entry | Both must dispatch the same timer users, including when no SIO transaction is active. |
| Initialization / shutdown | Admit SIO-first and pointer-first orders. Save state once at first ownership and restore affected state only after its last owner and pending activation retire. |

Measure timer overrun and maximum time between actual PORTA reads, including
VBI/OS work, DMA, IRQ masking and timer restarts. A nominal interrupt frequency
is not a guarantee of mouse accuracy. Enabling a pending timer bit must not
consume a stale tick as a newly armed SIO alarm.

If the shared clock cannot meet both serial deadlines and the selected mouse
motion envelope, revise the timing design with measurements. Do not hide the
failure by stopping mouse capture during transfers. DLI remains disabled and
the current ROM remains the baseline.

## Capture, ownership and events

Follow the existing Amiga-inspired division: platform code captures hardware,
the input library owns its bounded stream, and the application owns gestures.
Keep the existing application and renderer Tasks; no extra input Task or third
large stack is proposed.

Extend INPUT to admit one keyboard lease and one pointer lease concurrently,
with independent source state, routes and generations. Add a fixed POINTER
producer using the public
[admission and retirement contract](../../reference/signals.md), available to
ordinary Tasks. Generate identifiers/configuration and language bridges from
ABI definitions, updating callers together. The implementation plan must define
exact layouts and status behavior before code changes.

The IRQ sampler decodes transitions into counters and records changes, not an
event for every unchanged timer tick. Use a bounded upper-RAM ring, preserving
button edges and their counter snapshots. Adjacent motion may coalesce only
within the same acquisition, route, button state and validity interval.
Counter overflow, impossible transitions or ring exhaustion latch durable loss
outside the ordinary queue. Never silently overwrite a button release.

Records retain capture identities, tick and ordered motion/button state.
Publication finishes the record before advancing the head. Coalescing and
Task-side consumption must use the same bounded native guard so a consumer
cannot copy a record while IRQ rewrites it. Use the existing deferred-wake
mechanism; do not invoke ordinary Signal, client callbacks or graphics in IRQ.
Notify on pending work without flooding the wake queue on unchanged samples.

Preserve complete native/emulation context and each Task's DP ownership.
IRQ masking protects against this producer, but does not mask NMI: retain
SWITCHING and the platform's saved-frame protocol during activation, multi-byte
state changes, stack transitions and retirement. Measure interrupt stack use
and keep storage resident until deactivation and producer drain complete.

Task-side delivery uses the existing 24-byte InputEvent shape:

- POINTER carries absolute coordinates, resulting button state and code zero.
  BUTTON carries the changed LEFT mask and resulting state at the sampled
  position. For simultaneous movement and a button edge, deliver POINTER at
  that position with the previous button state, then BUTTON with the new state.
- Captured events carry TICK_VALID and have INJECTED clear. Durable loss does
  not invent a timestamp. Initial pointer qualifiers are zero.
- A hardware discontinuity or overflow is a gesture barrier. Loss must be
  acknowledged separately from ordinary queue consumption.

The GUI retains both leases. Associate the pointer acquisition/route explicitly
with the current GUI session before forwarding events into the private queue,
which currently validates the keyboard lease. Validate both identities before
translating tags. Route changes and close invalidate the association, stop
addressed capture, purge stale records and disarm the gesture.

Drain keyboard and pointer work with separate bounded budgets. Keep the
application runnable while either has pending work; otherwise wait on retained
signals. A mouse event must wake an idle application. Retain one outstanding
graphics packet and the existing cursor/redraw fairness.

## Gestures and limits

Require a fresh released-button observation before arming, including after
acquisition or loss. Press arms one enabled control; matching release over it
activates once. Release elsewhere, loss, Escape or BREAK cancels the gesture.
Recovery seeds the current quadrature state and never invents a click.

Two opposite quadrature states expose missed or invalid transitions, but three
missed transitions can resemble reverse movement and four can resemble no motion.
Compare decoded motion with a known stimulus; a zero invalid-transition count
does not prove zero loss. Define the supported motion envelope from the maximum
sampling gap and minimum per-axis transition spacing in that stimulus, not from
average timer frequency. Exercise the normal host mouse mapping as well.

Buttons are sampled levels. A complete down/up pulse between samples is
unobservable; publish the measured minimum supported duration. Physical
connection and disconnection are not reliably detectable from the idle lines.
Keyboard navigation remains available if the mouse is absent or capture fails.

On exit, close GUI admission, deactivate and drain pointer capture, discard
queued records and associations, then release its signals and leases. Preserve
SIO if it is still active. Follow existing keyboard, graphics and disk shutdown
ordering afterward. Reacquisition must not inherit old phases, clicks or wakes.

## Memory and validation

This documentation change reserves **zero bytes**. The implementation target is
also zero additional reserved bank-zero bytes: fixed adapter storage 0,
root/kernel stacks 0, each public Task stack/DP 0 and private idle 0, including
guards, alignment and unused reserved capacity. The two large Tasks remain the
application and renderer. Check the
[bank-zero budget](../../reference/platform.md#bank-zero-memory-budget) before
allocating any interrupt stub or expanding an existing segment.

A provisional upper-RAM capture allowance is 1,536 bytes: 32 records × 24 bytes,
128 bytes of control/counters, 16 loss slots × 24 bytes, 32 guard bytes and
224 bytes of alignment/slack. This is a design budget, not an ABI layout.
Account separately for shared-timing state, code and bridge growth, and identify
any reused reservation. No additional cursor VRAM is proposed.

The [implementation plan](physical-mouse-implementation-plan.md) expands these
stages into M0–M6, with generated ABI choices and checks before each commit:

1. **Configured-device observation and timing.** Record ST/port 1 settings and
   prove PORTA/TRIG0 changes through the existing controller. Migrate timer
   ownership and measure sampling during idle, OS calls and physical SIO.
2. **Reusable capture.** Add generated configuration, concurrent keyboard/mouse
   leases, decoding, bounded queues, loss, wake and release/drain/reuse.
3. **GUI integration.** Connect the admitted stream to the existing cursor and
   controls. Demonstrate keyboard and mouse use throughout cold disk reads,
   media errors and cancellation.
4. **Evidence and optional artifact.** Exercise a production build, publish
   measured limits and update contracts/guide for demonstrated behavior.

Automated tests may need a small bridge command to drive the existing mouse
controller at scheduled emulated times. That is test access to an existing model,
not a prerequisite for enabling the mouse in Altirra. Record the actual stimulus
commands and hashes if tooling changes. Injection directly into InputEvent or
the GUI queue remains useful separately, but cannot establish device capture.

Use the development tier with focused raw/optimized emitted-code checks:
all quadrature transitions and signs, slow motion, reversal, fast-motion loss,
counter/tick boundaries, clipping, motion plus button edges, held button on
entry, queue saturation, stale routes and late IRQs during shutdown. Validate
native and emulation paths, complete register restoration, stack/domain guards
and bounded completion. Cover both source-admission orders, either owner's
release, SIO terminal/offline/recovery paths and shared-timer stale interrupts.

Compare generated motion, captured counters and final framebuffer pixels.
Measure keyboard and mouse response during exact-content SDFS reads, failures
and cancellation. Use 12 PAL ticks as the initial maximum visible-response
acceptance ceiling for the existing bounded scene, consistent with the scale of
the [keyboard baseline](../../history/gem-input.md); separately record sampling
gaps, serial errors and interrupt cost. Repeat the final scene without observer
hooks. These checks do not qualify physical hardware or the entire hosted system.

When packaging, use [build_demo.py](../../../tools/build_demo.py), retain the
matching pinned ROM/disk, OF816 and five-second standard-shell/prime autoboot,
and keep the ZIP limited to boot files, guide, notices and checksums. Release
qualification remains governed by the
[two-tier testing policy](../../contributing/testing.md).

Right/middle buttons, wheel, other ports/protocols, XEM1 adapters, NTSC,
double-click/drag, AES, menus and desktop integration remain separate work.
