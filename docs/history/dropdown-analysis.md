# Dropdown response analysis

[Measurements](../development/dropdown-analysis.json) ·
[Passive observer](../../tools/trace_menu_response.py) ·
[New Window analysis](window-opening-analysis.md) ·
[QT4 baseline](presenter-quiet-turn.md)

## Finding

Cached dropdown switching is a useful isolated target. A warm keyboard
File → View switch takes **200.576 ms**, with **143.414 ms of presenter CPU**.
Neither Desktop nor the filesystem executes in this interval. Files does not
repaint, and both the old background and new popup are restored from VRAM.

The main cost is **visibility and damage bookkeeping around the copies**.
Hiding and showing the popup costs 59.345 ms CPU, including two visibility
rebuilds costing 42.876 ms. Retiring the background restoration adds 6.423 ms.
Separate damage-readiness queries add 8.094 ms. These non-overlapping portions
account for about **74 of the 143 ms presenter CPU**.

The two `CONSOLEBITMAP.CopyStart` calls together cost **4.008 ms CPU**. Each
submits one whole-rectangle asynchronous copy. Increasing their transfer size
does not address this trace's dominant work.

## Scope and method

One capture uses the unchanged `build/presenter-quiet-turn/demo` archive at
production head `d1cb8b2`. No build or guest-state patch is involved. The
machine remains 800XL/PAL, 65816 x8, VBXE, 64 KiB plus 63 upper banks, accurate
generic56k timing, SIO patch/burst/random delay off. Exact archive, compiler,
ROM and emulator hashes are in the measurement record.

The existing menu observer supplies three application open/highlight/switch/
dismiss sequences and three keyboard plus three pointer heading transitions.
Added passive markers record native/C entries and returns, IRQ completion and
Task ownership. Per-action cache counters include a settling tail; CPU totals
stop at the first matching pixel sample. No forced cache invalidation is used.
The native Windows menu is outside this capture.

All eighteen actions cause **zero Files repaints**. The serial observer sees
normal traffic outside the timed actions but no command/receive/read events
inside them. Warm opening and switching have popup-cache hits; three-heading
keyboard cycling and the first pointer switch also provide natural misses.

CPU is the existing conservative Task charge, including kernel/scheduler work
and bus stalls, with native IRQ/NMI time separated. Whole-region pixel equality
is sampled once per PAL frame. These are three-sample medians, not p95 results.

## Observed response

| Interaction | Median elapsed | Median presenter CPU | Cache behavior |
| --- | ---: | ---: | --- |
| Warm application-menu opening | 160.411 ms | 113.456 ms | Background capture + popup restore |
| Highlight first enabled row | 60.123 ms | 30.971 ms | In-place inversion; no cache transfer |
| Warm File → View switch | 200.576 ms | 143.414 ms | Background restore + popup restore |
| Dismiss View | 140.454 ms | 84.444 ms | Background restore |
| Repeated pointer File/View, two cached cases | 280.656 ms each | 197.829 / 197.597 ms | Background restore + popup restore |

The pointer numbers include physical travel between headings and repeated
motion delivery. They must not be described as stationary-hover latency. In
the representative cached File → View pointer switch, thirteen `Mouse` calls
cost 39.751 ms CPU, including thirteen heading checks costing 14.743 ms.
Whole input servicing costs 55.092 ms. These are nested, not additive costs.
Some motion processing continues between the two copy operations. The keyboard
switch is therefore the cleaner scene-transition baseline.

Keyboard cycling visits File, View and Desk with only two popup cache slots.
All three transitions miss, taking 240.742, 320.821 and 381.197 ms. The first
pointer transition also misses (300.866 ms), followed by two hits. This explains
why the older ~321 ms keyboard median is not a warm two-popup switching result.
The cache-hit path remains slow independently of that capacity effect.

## A cached switch, step by step

Representative action: `application/switch/1`. File has a selected row; the
right-arrow shortcut switches to View. The destination popup is cached.
Keyboard handling runs at 9.906–11.033 ms. All times below begin at input
submission, not at the first menu mutation.

| Boundary | Time |
| --- | ---: |
| Start restoring old background | 22.068 ms |
| Submit background copy | 53.294–55.744 ms |
| Background completion IRQ | 56.905 ms |
| Successful completion-poll return | 59.336 ms |
| Retire old saved-scene operation | 67.928 ms |
| Prepare/show new popup, snapshot menu and select paint work | 67.928–130.844 ms |
| Submit cached popup copy | 130.844–133.285 ms |
| Popup completion IRQ | 133.873 ms |
| Successful completion-poll return | 137.665 ms |
| Retire popup restoration | 141.567 ms |
| Draw changed menu-bar headings | 155.030–164.891 ms |
| Whole-region pixel sample matches | 200.576 ms |

The transfers restore 8,960 background bytes and 4,104 popup bytes. Copy entry
to completion IRQ is 3.611 ms and 3.029 ms respectively, including software
submission. The IRQ marker is not an independent BUSY-falling-edge probe, so
these intervals must not be reported as pure hardware DMA duration.

Completion IRQ to successful poll return is 2.431 / 3.792 ms. The much larger
gap is **62.916 ms from retiring the old save to starting the next copy**.
`Advance` spends 43.505 ms CPU in this gap, predominantly showing the new layer,
rebuilding visibility and publishing menu damage. Additional presenter work
precedes the next copy. There is no peer Task running inside these routines.

After popup restoration, the menu bar still needs its selected headings
repaired. `DESKAPPMENU.Paint` costs 8.069 ms CPU; painter continuation and input
boundaries add work around it. The final pixel sample also includes scanout
and sampling delay. The last routine return is not the same endpoint as a
complete displayed image.

The complete 200.576 ms comprises 143.414 ms presenter CPU, 35.518 ms native
interrupt time and 21.644 ms charged to the idle Task. This does not support
raising presenter priority or suppressing preemption to solve this case.

## Where the CPU goes

### Full visibility rebuilds

[BeginRestore](../../lib/display/layers-save.inc) calls ordinary
[Show(...,0)](../../lib/display/layers.act). That marks exposure across the
scene and rebuilds all visibility lists. After restoring the old pixels,
`Open` changes the hidden popup bounds, then `Show(...,1)` marks damage and
rebuilds visibility again. Bounds already avoids rebuilding a hidden layer;
the two observed rebuilds come from hide and show.

The hidden-state rebuild costs **14.458 ms CPU** and the new shown-state
rebuild **28.418 ms**. Twenty-five `REGIONS.Subtract` calls inside them cost
**31.884 ms**, included in the 42.876 ms rebuild total.
[Subtract](../../lib/display/regions.act) makes a count pass followed by an
emission pass, repeating rectangle
intersections. Its public contract preserves the destination on capacity
failure. Any optimization must retain that behavior; a bounded fast path when
maximum possible output fits can avoid the first pass without weakening it.
Empty and nonintersecting cases also deserve attention.

### Damage generated and then retired

The two `DamageAll` calls cost **16.051 ms CPU**, included in `Show` above.
On a successful background restore, `FinishSave` subtracts the restored area
from damage and updates readiness, costing **6.423 ms CPU**. Ordinary exposure
machinery is being used for pixels that have just been repaired from a known
saved image. A saved-overlay transition can potentially avoid generating part
of that temporary damage in the first place.

### Readiness recomputed despite an existing summary

There are 64 `Layers.Damaged` calls costing 18.102 ms CPU. Thirty-five are
inside `UpdateDamage`, maintaining the summary. The other **29 calls cost
8.094 ms** and recompute a result already represented by `scene.visibleDamage`.
Several rejected candidates each cost about 1.84 ms scanning dirty rectangles
that have no visible intersection.

QT3 converted the global no-damage query to the bitset, but
[paint candidate selection](../../lib/desktop/deskpaint.act)
still calls the intersection predicate. Using the existing per-slot
bits there is a small, direct extension of that work, with no new storage.
Keep the intersection calculation in the mutation paths that maintain the bits.

This also affects highlighting: the inversion itself costs 4.153 ms CPU inside
a 30.971 ms presenter turn sequence. Twenty readiness queries outside summary
maintenance cost 5.329 ms. A cheap pixel operation is still surrounded by
substantial general presenter work.

## Recommended direction

1. **Finish adopting the existing visible-damage bitset in paint selection.**
   This is the smallest change, with measured opportunities in switching,
   dismissal and row highlighting. No new cache or scheduling policy is needed.
2. **Optimize the existing region operations used by visibility rebuilds.**
   Start with bounded single-pass subtraction and cheap empty/nonintersecting
   cases. Preserve aliasing/capacity semantics and measure the emitted code.
   The 31.9 ms subtraction total is an opportunity, not a promised saving.
3. **Make a valid saved-popup replacement one scene transition.** Retain the
   scene token through old-pixel restoration and publish the new popup geometry
   once, avoiding an intermediate hidden-scene rebuild where safe. Limit
   exposure damage to pixels actually needing repair. Keep ordinary hide/show
   and repaint behavior for missing/stale saves, failures and conventional
   application exposure obligations. This needs an explicit, bounded Layers
   operation rather than a general transaction framework.
4. **Then reduce redundant pointer-menu routing.** Repeated motion within the
   same current/pending heading should not repeat all menu lookup work. Preserve
   latest pointer position, heading crossings, button order and drag semantics.

Further title caching is secondary in this trace: cached switching spends much
more CPU manipulating the scene than painting its headings. The next refactor
should target Layers geometry/damage and its presenter callers. The native
copy path already handles each cached rectangle in one operation.

## Validation

Development analysis only. One unchanged optimized OF816 package, eighteen
timed actions, zero Files repaints, expected per-action cache hits/misses,
settled reference pixels and normal EXIT through the existing runner. The host
suite passes **490 tests, four historical skips**; no full qualification matrix,
raw rebuild or hardware qualification was run.

Only host observers and documentation change. Reserved bank-zero delta: fixed
**0 bytes**, per public Task **0 bytes**, idle Task **0 bytes**, including
guards, alignment and unused capacity. Guest code, RAM/VRAM reservations and
stack/DP sizes are unchanged. Raw capture stays in `build/dropdown-analysis`;
the shared record contains measurements and hashes, not bridge logs.
