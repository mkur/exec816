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
