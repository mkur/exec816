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
