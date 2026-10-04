# Mouse sampling and pointer batching

[History](README.md) · [Implementation plan](../plans/gem4xe/mouse-performance-implementation-plan.md)

Development-tier work on the pinned PAL 65C816 8×, 4 MiB, VBXE FX 1.26 and ST
port 1 configuration. The desktop retains two pixels per decoded step. This
record does not qualify physical hardware or the whole hosted system.

## MP1 — 4 kHz capture

Implemented 2026-10-05. Timer 1 now runs at 3,958.6 Hz except for short SIO
COMMAND and write-turnaround windows. Those use the existing 7,917.2 Hz clock
and alarm counts, while pointer capture skips alternate fine edges. SIO owns
the demand; the platform owns the divisor, shadow and divider. AUDF1 changes
do not add STIMER resets during serial frames. Timer 2 deadlines and the
blitter's sixteen-VBI watchdog retain their units.

[MP1 evidence](../development/mouse-performance-mp1.json) includes a matching
2× two-client baseline, raw/optimized emitted mouse/SIO cases, phase-shifted
physical mouse boundaries, sensitivity/edge reversal, recovery/cancellation,
blitter completion and lost-IRQ wrap, and stock-profile timeout checks.
The original COMMAND setup/hold and RX/TX deadlines remain enforced. The two
stock timeouts were observed 28.05 and 29.60 µs after their absolute deadlines,
inside the unchanged 100 µs limit.

In the matching twenty-motion idle workload, native IRQ entry through routing
fell from **31.08% to 15.88%** of observed elapsed time. This excludes final
scheduler/RTI and is not exclusive mouse or total CPU utilization. Pointer
drawing still uses four submissions in this slice; its charged CPU median is
4.07 ms versus 4.18 ms before. Loaded response targets remain open.

A raw public-admission test initially failed because it required a short SIO
alarm to remain armed throughout mouse registration. The unchanged 8 kHz
baseline fails the same assertion, after the same seven successful checks.
Public registration can outlast the alarm. The fixture now checks the joined
owner and continued exact-byte transfer; it retains the independent wire timing
oracles. The corrected raw in-flight acquisition and raw emulation cases pass.

The profile-limit runner now uses the actual pinned mouse-tooling emulator;
its older observer binary had been removed during cleanup. The evidence records
the selected ROM and emulator hashes. Host checks pass: 340 tests with four
historical skips; generated timer/SIO definitions are current.

Reserved bank-zero change is **0 fixed, 0 root/kernel, 0 per public Task and
0 idle bytes**, including guards, alignment and slack. Two timer fields consume
unused bytes inside its existing 32-byte upper-RAM reservation. Stack/DP pools
are unchanged; emitted guards and OS-return checks pass.

## MP2 — One pointer list

The shared GEM/desktop cursor renderer builds restore, save, AND and OR records
in its existing command buffer and submits them together. A visible move uses
one upload and one START; show uses three records, hide one, and an unchanged
valid pointer performs no submission. The call remains synchronous and leaves
interrupts enabled while waiting. The new save geometry is adopted only after
success. Drawing/outline invalidation still erases the pointer before changing
its saved background, and a pending scroll retains the command arena.

[MP2 evidence](../development/mouse-performance-mp2.json) records 62 cursor cases
in each raw/optimized build. Independent complete-scene pixels and record bytes
cover parity, corners, overlapping/distant moves, neighboring nibbles, unchanged
positions and rejected packets. Faults cover the one-, three- and four-record
lists, plus reset-required retention. Desktop checks cover physical 2× motion,
drag outlines, edge clamping, cancellation/retirement and both pending-scroll
watchdog outcomes. The drag oracle now includes the optional independent app
and tracks expected stacking separately from the target's layer list.

In the same twenty-motion idle cost fixture, pointer submissions/uploads fall
from **80 to 20**. Median charged cursor CPU falls from **4.071 to 3.761 ms**
after MP1, a **7.6%** reduction; the original 8 kHz/four-submit baseline is
4.182 ms. These CPU spans exclude native interrupt bodies and off-Task time,
but include validation, fences, scheduling tails and bus stalls. The blitter
still transfers the same pixels. Preparation-to-first-START is an elapsed
measurement; exact hardware BUSY edges are not measured.

The code adds no production buffer or VRAM reservation. Reserved bank-zero
growth remains **0 fixed, 0 root/kernel, 0 per public Task and 0 idle bytes**.
The instrumented renderer's large Task stack peaks at 350 bytes raw and
374 bytes optimized, inside its existing guarded pool. Host checks remain
340 passing tests with four historical skips. Combined latency acceptance is
recorded separately in MP3.
