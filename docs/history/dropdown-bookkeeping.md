# Dropdown bookkeeping implementation

[Plan](../plans/gem4xe/dropdown-bookkeeping-plan.md) ·
[Starting analysis](dropdown-analysis.md) ·
[Measurements](../development/dropdown-bookkeeping.json)

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
The optimized desktop presentation fixture also passes its 117 checks for independent raster,
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

## Dropdown measurements

The exact `build/dropdown-bookkeeping/demo` package at `5264ac1` repeats the
18-action baseline capture. Compiler, ROM, emulator and machine/disk settings
are unchanged: 800XL/PAL, 65816 x8, VBXE, 64 KiB plus 63 upper banks, accurate
generic56k disk timing, no SIO patch/burst/random delay. Cache hits, misses,
transfers and byte counts match for every action. No Files paint or serial
transaction occurs in the measured menu intervals.

Three samples per row, reported as medians:

| Action | Before elapsed | After elapsed | Before presenter CPU | After presenter CPU |
| --- | ---: | ---: | ---: | ---: |
| Warm open | 160.4 ms | 140.5 ms | 113.5 ms | 96.9 ms |
| Highlight | 60.1 ms | 60.1 ms | 31.0 ms | 25.4 ms |
| Warm File → View | 200.6 ms | 180.4 ms | 143.4 ms | 121.5 ms |
| Dismiss | 140.5 ms | 120.2 ms | 84.4 ms | 75.4 ms |
| Repeated keyboard headings | 320.8 ms | 300.9 ms | 258.0 ms | 242.0 ms |
| Physical pointer headings | 280.7 ms | 280.7 ms | 197.8 ms | 187.1 ms |

Warm switching saves about **15% presenter CPU** and **one PAL frame** of
visible response. Open and dismiss also save a frame. Highlight CPU falls,
but its completion remains in the same sampled frame. The record includes
minimum/median/maximum and every sample; these cohorts do not establish p95.

The repeated keyboard sequence visits three headings with two popup cache
slots, so all three switches miss that cache. The pointer sequence has one
miss then two hits and includes physical travel and repeated motion routing;
it is not stationary-hover latency. Neither its median nor maximum visible
response improves. Cached pointer CPU falls, but this is not a visible-latency
win; the last action also services 15 mouse packets rather than 13.

For representative `application/switch/1`:

| Work | Before CPU | After CPU |
| --- | ---: | ---: |
| Two `Show` transitions | 59.345 ms | 46.012 ms |
| Their two visibility rebuilds | 42.876 ms | 29.579 ms |
| Their 25 subtractions | 31.884 ms | 18.656 ms |
| Saved-background retirement | 6.423 ms | 6.464 ms |
| Independent damage queries | 8.094 ms / 29 calls | 0 ms / 0 calls |
| Two complete cache-copy submissions | 4.008 ms | 4.000 ms |

The rebuild/subtraction rows are inside `Show`; they must not be added again.
Subtraction CPU falls **41%**. Damage computation still runs where needed to
maintain the summary: 35 calls in this switch. Across all 18 actions, the 438
queries outside summary maintenance disappear. This does not claim that the
new summary lookups themselves are free.

Background retirement to the next popup copy shrinks 62.916 → 48.170 ms.
Both hide/show rebuilds and temporary damage retirement remain. They are the
next structural opportunity, requiring the separate popup-transition design
discussed in the analysis. Copy submission stays short; increasing copy sizes
would not address the remaining scene work.

Pixel completion includes scanout and one-PAL-frame sampling. Copy entry to
completion IRQ includes submission and interrupt latency, not pure DMA time.
The representative switch has no application/filesystem Task CPU; ordinary
preemption and interrupt handling remain enabled.

## Final validation and delivery

Development checks pass: 491 host tests with four historical skips, the two
optimized Layers runs and one optimized desktop presentation run above,
then the exact packaged menu replay. All menu/reference/background pixels
match, guards remain intact, EXIT succeeds and no live Tasks remain.
No raw or full qualification matrix was run.

The final memory reservation manifest matches the baseline in every field,
including all Task pools. Every slice has **0 fixed,
0 per-public-Task and 0 idle reserved bank-zero growth**, including guards,
alignment and unused capacity. VRAM and mutable storage also do not grow.
Native code increases 1,085,814 → 1,086,159 bytes (**+345**). Native data entries
total 13,535 → 13,523 bytes: only two build-version strings shrink, each losing
the six-byte `-dirty` suffix. The menu replay leaves 1,472 bytes above the
presenter's stack floor; kernel stack observation leaves 1,249 bytes untouched
from its base with zero interrupt-reserve use. These are observations, not
worst-case bounds.

All 22 distribution checksums verify. The ZIP contains OF816, five-second
autoboot, matching media, the pinned ROM and license notices; development
traces and manifests remain outside it. Launch from the repository root:

```sh
build/dropdown-bookkeeping/demo/launch-altirra.command
```

Reproduce the focused menu capture with a fresh output directory:

```sh
python3 tools/trace_menu_response.py \
  --bundle build/dropdown-bookkeeping/demo --output build/dropdown-bookkeeping/recheck
```
