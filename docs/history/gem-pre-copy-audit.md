# MGVIEW work before the scroll copy

[History index](README.md) · [GEM plans](../plans/gem4xe/README.md) ·
[Measurements and pinned inputs](../development/gem-pre-copy-audit.json) ·
[Completed END_UPDATE work](gem-end-update-implementation.md)

The 2026-11-17 audit traces the frozen EU5 executable. It changes host observation
and reporting only: no application, AES, renderer, driver or kernel behavior,
target builds or drawing limits change.

**Most pre-copy time is active work, with scrollbar painting the largest single
part.** Slider arithmetic and contended UPDATE acquisition do not explain the
delay. MagiC's unchanged-value exit and selected-axis geometry are already
present, but Exec surrounds them with repeated context lookup, general menu
reconciliation, publication and exposure completion.

## Capture and boundaries

`tools/measure_mgview.py --pre-copy-detail --expect-copy-units 1` reuses
`build/gem-end-update/eu5/viewer`. It observes emitted APP arithmetic entries,
resident bindings, native AES/window/geometry routines and the selected frame
renderer. APP addresses follow the actual disk-loaded relocation. Full Task D/S
match callees and returns; ordinary APP call-site observations distinguish
mouse hiding, clipping and arithmetic without measuring a different executable.
Runtime helpers that consume inline operands or a return address are excluded
from the ordinary call-site matcher.

The measured interval starts at `set_shift` entry and ends at `vro_cpyfm` entry.
The table's caller stages are disjoint. Each interval separately accounts for
viewer CPU, viewer IRQ/NMI work and time on other Tasks. Inclusive routine costs
overlap and must not be added to their callers. CPU includes gateway/return work
and hardware bus stalls; a fence routine's CPU is not a measurement of pure
blitter execution.

| Caller stage | Down elapsed | Down CPU | Up elapsed | Up CPU |
| --- | ---: | ---: | ---: | ---: |
| Before slider helper, including BEG_UPDATE | 1.878 ms | 1.571 ms | 5.198 ms | 2.181 ms |
| Size calculation and argument preparation | 0.411 ms | 0.324 ms | 0.412 ms | 0.324 ms |
| Unchanged `WF_VSLSIZE` | 5.293 ms | 4.367 ms | 5.293 ms | 4.367 ms |
| Position calculation and argument preparation | 0.342 ms | 0.298 ms | 0.342 ms | 0.298 ms |
| Changed `WF_VSLIDE` | 25.792 ms | 20.663 ms | 25.854 ms | 20.623 ms |
| Helper return | 0.005 ms | 0.005 ms | 0.005 ms | 0.005 ms |
| After helper, before copy entry | 11.260 ms | 8.575 ms | 11.188 ms | 8.543 ms |
| **Whole pre-copy interval** | **44.981 ms** | **35.803 ms** | **48.292 ms** | **36.341 ms** |

Viewer interrupts account for another **7.764/8.008 ms**. Off-Task time is
**1.414/3.943 ms**; this is not all resource contention. All three native UPDATE
Attempts succeed in each action, with **zero Obtain calls**. The three Attempts
and two nested Releases together charge **0.329/0.341 ms CPU**. The up sample's
longer BEGIN includes scheduling during context lookup, rather than a semaphore
wait. SCRENMGR charges zero CPU in both pre-copy intervals; the record retains
test-controller and other peer Task charges separately.

## What the setters actually do

The unchanged size setter calls neither `GEMFRAME.Slide` nor `AESFRAME.Paint`.
Its 4.367 ms CPU still includes:

- context lookup: **0.708 ms**;
- two temporary scope boundaries: **1.100/1.105 ms** combined;
- general `AESLOCAL.Exposure`: **1.141 ms**, including **0.973/0.966 ms**
  in `DESKMENU.Reconcile`;
- `AESLOCAL.Publish`: **0.197 ms**.

These are inclusive subintervals within the setter, not an additional bill.
Two `AESSNAPSHOT.Publish` calls occur per setter, one through the menu path.
All four return zero in each scroll: these are repeated unchanged-publication
checks, not four full snapshot copies.

The changed position setter performs exactly one selected-axis update,
**0.946/0.930 ms CPU**, and one selected frame paint, **14.362/14.326 ms CPU**
(18.176/18.198 ms elapsed). There is no full `SetSize`, `SetKind`, `Calc` or
window-view layout rebuild. The renderer traverses objects **9 and 10** once,
through one callback and one scratch publication, using three command lists
of **19, 12 and 5 records**. Geometry is not being recalculated once per strip.
The remaining **6.300/6.296 ms CPU** in this setter includes mutation, scope,
context, dispatch, publication and exposure work. The record retains the
exclusive renderer construction/upload/fence breakdown rather than attributing
the whole paint to the blitter.

The slider helper's two multiplies and two divisions total only
**0.559/0.546 ms CPU** through their APP call sites. The complete size/position
preparation stages total **0.622 ms CPU**. Replacing viewer arithmetic or merging
its standard setters is not supported by these measurements.

After the helper, `graf_mouse(M_OFF)` costs **5.923/5.891 ms CPU**
(8.037/7.963 ms elapsed at the binding boundary), the first visible-rectangle
query costs **1.020 ms CPU**, and `vs_clip` costs **1.316/1.310 ms CPU** through
its APP call site. These are separate from slider calculation. Across the
whole pre-copy interval there are **seven `ExecAESContext` lookups**, charging
**4.979/5.594 ms CPU** in total. They are already included in the preceding
stages, including the renderer and mouse call.

## Comparison with pinned MagiC

The donor is MagiC revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d`,
as recorded in the [standalone model](../architecture/magic.md). Line references
are to normalized `AESWIN.S` in `build/magic-architecture/text`.

- `ws_normal` (2298–2310) resolves the window and enters UPDATE. Exec's nested
  setter scope follows this ownership boundary; removing semaphore protection
  is not the conclusion of the audit.
- `ws_slide` / `ws_slend` (2733–2794) clamp the value and, with Smart Redraw
  enabled, return through `update_0` when it is unchanged. Exec already exits
  its native frame mutation here, but then returns through general input
  publication and `AESLOCAL.Exposure`, including menu reconciliation. Those
  extra operations have no counterpart on this donor slider path.
- For a changed value, MagiC calls `_wbm_sslid` (922–965), then `wind_draw` on
  `O_VSCROLL` / `O_HSCROLL`. Exec's `GEMFRAME.Slide` and selected `AESFRAME.Paint`
  follow that structure. MagiC's `wind_draw` (354–391) clips and traverses the
  selected tree through `objc_wdraw`, then the setter releases UPDATE. It does
  not run a general menu/exposure pass afterward.
- The 65816 bindings, copied nonblocking reads, normal Task preemption,
  physical display admission and VBXE command construction are platform
  adaptations. Their measured cost must remain separate from MagiC's geometry
  or ownership algorithm. This audit proposes no new platform service or
  unapproved architectural departure.

The next bounded implementation candidate is the **unchanged slider return**:
retain normal lookup, UPDATE and resource release, but avoid unrelated general
publication/exposure work after establishing that no slider state changed.
The observed `Publish` plus `Exposure` interval is about **1.34 ms CPU** per
unchanged call; that is an opportunity estimate, not a delivered saving.
Changed-slider completion, context lookup, mouse hiding and renderer costs
remain separate follow-ups. No implementation is included in this audit.

## Development checks and limits

The native image, C provider and MGVIEW APP match EU5 byte for byte. Both actions
pass exact viewport pixels, one physical viewport copy, one exposed-row draw,
no redraw fallback, unchanged pointer position, three clean Process lifetimes,
ownership/heap restoration and stack/domain guards. The settled full scanout
matches EU5. Observed complete-viewport latency is **120.50/140.23 ms**, still
PAL observation bounds from two actions, not a latency distribution or a new
performance improvement. Host checks run **738 tests, four skipped**, including
IRQ/peer accounting, nested exclusive attribution and relocated source returns.

Added reserved bank-zero bytes: **0 fixed, root, kernel, idle and per public
Task**, including guards, alignment and unused capacity. Runtime upper storage
also changes by **0 bytes**. No new Task, buffer, ABI or platform operation is
introduced. No QED, Counter, geometry build, demo refresh or release matrix ran;
this development audit does not qualify the hosted system.
