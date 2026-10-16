# Popup replacement implementation

[Design](../plans/gem4xe/popup-transition-design.md) ·
[Plan](../plans/gem4xe/popup-transition-plan.md) ·
[Measurements](../development/popup-transition.json) ·
[Layers contract](../reference/layers.md)

## PT1 Layers transaction

`BeginSavedReplace` claims before publication and retains the old geometry,
visibility and saved-image pin. `FinishSavedReplace` commits clean or dirty
replacement geometry with one rebuild, or retains old geometry and damages
both touched rectangles on failure. Generic `Finish` rejects this token kind.
Successful retirement subtracts only the old restored footprint; application
pending repaint and bounded-overflow damage remain intact.

Development checks pass: 491 host tests (four historical skips), generated
Layers definitions, and 2,250 optimized emitted Layers assertions, including
117 additional checks for replacement/damage/ownership and the existing scene,
region, bank-crossing, guard and OS-return cases. Artifacts are in
`build/popup-transition/pt1-layers`. No raw or qualification matrix was run.

The fixture's first build exceeded its incidental no-argument Task-entry
capacity; passing the strip count to the new regression keeps that helper out
of the Task entry table without enlarging production reservations.

Layers/Regions native code grows 36,391 → 38,646 bytes (+2,255).
Begin/finish replacement occupy 803/1,426 bytes with 34/32-byte local stack
peaks; the library maximum remains 56. These are local compiler figures, not
whole-call-chain bounds. Scene storage remains 9,186 bytes with no mutable
Layers globals. Reserved bank-zero delta is **0 fixed bytes, 0 per public Task
and 0 idle**, including guards, alignment and unused capacity. DP, stack and
VRAM reservations are unchanged.

## PT2 Cache continuation

The cache adapter now retains one Layers token and the image pins through
background restore and optional popup copy. It freezes the existing popup key,
uses staged bounds for the second copy, and reports CLEAN, DIRTY or REPAIR for
the menu owner to adopt. A dirty commit records the cache miss once; ordinary
painting skips the redundant lookup. Production menu admission is unchanged
in this slice.

The optimized presenter fixture passes eight cases and 163 emitted assertions:
hit with a differently sized popup, miss, rejected background submission,
failed background completion, rejected popup submission, failed popup completion,
invalidated background and stale menu revision. It checks independent VRAM
pixels across both popup footprints, one final rebuild, retained pins while
unquiesced, damage/save validity, and stale completion rejection during a later
transaction. The fixture suspends unrelated console painting while supplying
its own synthetic scene; the console caret lies outside the compared rectangle.
Fault controls exist only in generated fixture modules.

Artifacts: `build/popup-transition/pt2-cache`. Host checks pass (491 tests,
four historical skips). Stack/domain guards, ownership cleanup and normal OS
return pass. Observed presenter stack peak is 690 of 2,560 bytes, with 1,614
bytes above its floor remaining; kernel peak is 283 of 1,536 bytes. These are
observations in this fixture, not worst-case bounds or qualification.

New fixed upper-memory fields total **21 bytes**: an 18-byte frozen key and
three scalar bytes. Final production code/alignment accounting follows in PT4;
the fault-instrumented fixture is not a production code-size comparison.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. Scene, DP, stack and VRAM reservations
are unchanged.

## PT3 Menu integration

Eligible GEM heading switches now enter the combined transaction before the
ordinary restore path. Completion adopts the new heading under the policy gate
and damages only the old/new title segments. Odd or unusable saved geometry,
first open, dismissal and native menus retain the existing paths.

Keyboard dequeue and pointer gesture delivery defer from the first pending
heading through adoption, using the existing queues. The worker retains its
input hint while excluding blocked input from runnable work. Shared menu-turn
accounting lets ready ordinary painting run after two preferred transactions;
without such work it does not delay menus. Normal Task preemption is unchanged.

The final optimized menu fixture passes **315 AES checks**, four native checks,
all seven exact-pixel phases and eight injected input cases (rapid heading keys
and Escape, Return, outside press/release, and pointer loss during each copy).
It retains physical pointer/keyboard, owner replacement, native menu, long/odd
clipped menu, selection inversion and exact command-delivery coverage. The
ordinary-paint fairness case passes. A fixture-only counter observes 58 worker
waits with deferred keys and a replacement in progress, confirming that the
pending hint does not force spinning. This is not a worst-case scheduling bound.

Artifacts: `build/popup-transition/pt3-final`. Host checks pass (491 tests,
four historical skips). Stack/domain guards, zero live Tasks at cleanup and
normal OS return pass. Observed presenter stack peak is 836 of 2,560 bytes,
leaving 1,468 above its floor; kernel peak is 299 of 1,536 bytes. Testing uses
the development tier, with no raw, filesystem or full qualification matrix.

The phase byte and existing menu-turn counter move into shared desktop state;
no duplicate fields, queues, signals or timers are added. The combined fixed
upper-memory field increase remains 21 bytes before final alignment accounting.
PT3 reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. Scene, DP, stack and VRAM
reservations are unchanged.

## PT4 Matched measurements and demo

Production commits are `50e542d` (Layers), `772391b` (cache continuation) and
`95fee02` (menu/input integration). The clean `95fee02` OF816 package is compared
with the preserved clean DB3 `5264ac1` package and its original 18-action trace.
Compiler `05c01f39ff3beef97af0e65b0a16666f5a1bd805`, compiler binary, ROM,
emulator, PAL/65816x8/VBXE/63-bank configuration and accurate generic-56K disk
settings match. No local compiler override or target instrumentation is used.

Elapsed response, **minimum / median / maximum in milliseconds**, three samples
per cohort:

| Action | DB3 | PT4 |
| --- | ---: | ---: |
| Warm open | 140.203 / 140.454 / 140.454 | 140.202 / 140.454 / 140.454 |
| Highlight | 60.122 / 60.122 / 60.122 | 60.123 / 60.374 / 60.374 |
| Warm File → View | 180.368 / 180.368 / 180.619 | 120.245 / 120.245 / 120.497 |
| Dismiss | 120.245 / 120.245 / 120.245 | 120.245 / 120.497 / 120.498 |
| Keyboard heading sequence | 220.533 / 300.865 / 360.988 | 180.619 / 240.490 / 300.612 |
| Physical pointer headings | 280.656 / 280.656 / 300.864 | 280.656 / 280.656 / 280.908 |

Presenter CPU, **minimum / median / maximum in milliseconds**:

| Action | DB3 | PT4 |
| --- | ---: | ---: |
| Warm open | 96.866 / 96.884 / 96.896 | 97.551 / 97.942 / 98.328 |
| Highlight | 25.364 / 25.373 / 25.373 | 25.561 / 25.564 / 25.576 |
| Warm File → View | 121.519 / 121.522 / 121.931 | 78.915 / 78.920 / 78.920 |
| Dismiss | 75.235 / 75.360 / 75.362 | 73.021 / 73.054 / 73.691 |
| Keyboard heading sequence | 177.107 / 242.023 / 291.961 | 143.060 / 191.926 / 243.020 |
| Physical pointer headings | 181.627 / 187.146 / 241.189 | 149.554 / 158.898 / 224.579 |

Warm switch latency drops **33%**, and its presenter CPU drops **35%**.
The three-heading keyboard sequence still misses all three popup images in the
two-slot cache. Physical pointer movement still dominates its sampled response;
one miss and two hits remain, with lower presenter CPU but no median elapsed
gain. All 18 per-action transfer counter records match DB3 exactly. No Files
paint or serial event occurs during any measured action.

Open/highlight/dismiss remain within the same sampled-frame response, with
sub-millisecond elapsed differences. Open CPU increases by 1.1 ms (about 1%);
inspection finds the same five controls turns, nine menu advances, one rebuild
and two copies, with slightly higher input/policy overhead. Highlight CPU rises
0.2 ms and dismiss CPU falls 2.3 ms. No additional cache miss, scene transition
or application repaint appears in these controls.

### Replacement structure and remaining work

All three warm switches have **one** visibility rebuild, two whole-image
copies and no intermediate `Show`, `Bounds` or `TopChrome` call. In the
representative `application/switch/1` trace:

- Background completion observation → next copy submission: **56.945 →
  0.959 ms**. Across the new warm samples this gap is 0.958–0.959 ms.
- The historical retirement → submission gap was 48.170 ms. It has no direct
  new equivalent: the replacement has one final commit after both copies.
- Two `Show` calls costing 46.012 ms disappear. Rebuild count falls 2 → 1,
  with inclusive rebuild CPU 29.579 → 18.612 ms. Subtraction calls fall 25 → 15.
- New begin costs 0.375 ms, final finish 23.247 ms (including its rebuild),
  and menu snapshot adoption 1.692 ms. Both copy submissions together still
  cost about 4.0 ms CPU.

The background copy starts at 20.323 ms, the popup copy at 27.364 ms, and final
scene commit ends at 63.559 ms. Title updates and the rest of the presenter turn
still precede the 120.245 ms final pixel sample. The transaction removes most
of the inter-copy bookkeeping; it does not make the complete menu response a
single blitter-duration operation. Inclusive routine costs overlap and must
not be added together.

### Resources, validation and delivery

Native routine bytes grow **1,086,159 → 1,095,128** (+8,969). Native data entries
grow **13,523 → 13,544** (+21). The mutable arena's occupied end advances 22
bytes including alignment, within the existing 7,424-byte reservation and the
32-byte design target. Scene storage remains 9,186 bytes. The entire memory
reservation manifest matches DB3: **0 fixed bank-zero bytes, 0 per public Task,
0 idle**, including guards, alignment and unused capacity; DP, stack and VRAM
reservations are unchanged. PT4 itself adds no target state.

The exact packaged desktop passes the menu capture, five-second OF816 autoboot
(249 PAL frames), stack/domain guards, normal OS return and zero-live-Task
cleanup. Presenter peak is 829 of 2,560 bytes (1,475 above its floor remaining),
kernel peak 289 of 1,536, and idle peak 59 of 512. These are observations, not
whole-program bounds. PT1–PT3 focused results remain as recorded above; no
additional full qualification matrix was run.

Artifacts:

- `build/popup-transition/demo/exec816-demo.zip`
- `build/popup-transition/demo/launch-altirra.command`
- `build/popup-transition/menus` (development trace outside the ZIP)

The ZIP contains only boot/media files, the pinned ROM, user guide, licenses
and checksums. All 22 checksums verify; OF816 wraps the matching native image
and system disk. Archive SHA-256:
`c2aaf830af4eb30565995dfbb4dccd56bca6d5cd7c8cea69794ab0355b017b38`.

This is development evidence, not hardware qualification. Three samples do
not establish p95 or worst-case latency. The pixel endpoint includes scanout
and once-per-PAL-frame sampling; copy entry/IRQ/observation timings include
software and interrupt latency rather than measuring pure hardware DMA.
