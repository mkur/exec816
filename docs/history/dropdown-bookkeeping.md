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

## Bounded subtraction

DB2 starts directly with emission for at most 24 source rectangles, using the
existing four-piece bound and 96-entry destination. Larger inputs retain the
counting pass. The cut is still saved before any destination write, and FULL
still preserves every destination byte.

Optimized emitted checks pass: 2,133 native assertions, the existing independent
geometry/scene/damage-stream oracles and ten new multi-rectangle cases.
Those cover both sides of the threshold (48 and 50 output pieces), aliased
cut storage on both paths, an exact 96-piece result, overflow with unchanged
destination, empty input/cut and complete removal. All source bytes and guards
remain intact; normal OS return passes. The host suite passes 491 tests with
four historical skips. Evidence: `build/dropdown-bookkeeping/db2-layers`.

`Subtract` grows 1,269 → 1,310 native bytes (**+41**); its local stack peak stays
56 bytes. Mutable storage, layouts and VRAM reservations are unchanged.
Reserved bank-zero delta is **0 fixed bytes, 0 per public Task and 0 for idle**,
including guards, alignment and unused capacity. No DP/stack reservation grows.

These are development checks; final menu comparisons follow both code slices.
