# Dropdown bookkeeping implementation

[Plan](../plans/gem4xe/dropdown-bookkeeping-plan.md) ·
[Starting analysis](dropdown-analysis.md)

## Paint candidate lookup

DB1 replaces the presenter's repeated damage/visibility intersections with
the existing Layers summary. Menu and focused-window lookup use
`FindDamaged`; round-robin selection reads the known slot's bit. The popup/bar
order, two-menu-transaction limit and ordinary paint transaction behavior
remain unchanged. Hidden damage still becomes runnable on later exposure.

The optimized Layers fixture passes 2,123 checks, including an independent
geometric oracle for lookup results, covered/hidden layers, background,
deletion and slot reuse. The host suite passes 490 tests with four historical
skips. Evidence is under `build/dropdown-bookkeeping/db1-layers`.
The optimized desktop presentation fixture also passes its independent raster,
window move/repair, guard and OS-return checks; evidence is under
`build/dropdown-bookkeeping/db1-presentation`. It uses the pinned compiler's
release host executable, with the same optimized target emission.

The new lookup occupies 471 native bytes with a 20-byte local stack peak.
Combined Layers/Regions code grows from 35,879 to 36,350 bytes in the focused
fixture; its largest local stack peak remains 56 bytes. There is no new
mutable storage, record-layout change or VRAM reservation. Reserved bank-zero
delta is **0 fixed bytes, 0 per public Task and 0 for idle**, including guards,
alignment and unused capacity. DP and stack reservations are unchanged.
The changed presenter routines shrink by 167 bytes, for a combined production
routine delta of **+304 bytes**. `MenuLayer` local stack grows 26 → 30 bytes;
`Pump` remains at 66 bytes. These are per-routine compiler figures, not full
call-chain bounds.

These are development checks; final menu comparisons follow both code slices.
