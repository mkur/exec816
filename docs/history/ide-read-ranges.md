# Bounded IDE read ranges development record

[History](README.md) · [Design](../plans/ide-read-ranges-design.md) ·
[Implementation plan](../plans/ide-read-ranges-implementation-plan.md)

The RR1–RR4 slices implement bounded regular-file reads using the existing
filesystem worker and IDE Plus driver. Development evidence uses the compiler
pin in [actionc.json](../../toolchain/actionc.json) and the ROM, BIOS and emulator
inputs in [altirra-ideplus.json](../../toolchain/altirra-ideplus.json). Large native
builds and disposable media remain under build/ide-read-ranges. Compact results
are in [ide-read-ranges.json](../development/ide-read-ranges.json).

## RR1 Device command

Device ABI revision 4 adds READ_SECTORS=14 and a four-sector maximum without
changing request layouts. Native PIO fills each destination sector, then checks
terminal status. Failed/aborted reads publish zero actual bytes; issued range
ATA errors require cold reset. Discovery and single-sector operations keep
their existing behavior.

The small raw/optimized fixture passes 1/2/3/4-sector APT reads, raw-unit reads,
exact partition ends, invalid lengths/offsets, queued repeated abort, bank carry,
neighbour guards, unchanged media, one reply and ownership cleanup. Optimized
fault injection after three PIO spans and after the final span confirms zero
valid bytes, the expected modified destination prefix and offline retirement.
Optimized lifetime cases pass mixed SIO traffic, active abort/draining, timeout
and NMI boundaries 4/7. Host checks: 447 passed; generator check passes.

The emitted IDE worker bound is 758 bytes including the 256-byte interrupt
reserve and 16-byte dispatch margin, within its unchanged 1024-byte stack.
Fixed, per-Task and idle reserved bank-zero deltas are all zero, including
guards, alignment and unused capacity. No controller/request/buffer or pool
grew in this slice. Development checks do not qualify hardware or a release.
