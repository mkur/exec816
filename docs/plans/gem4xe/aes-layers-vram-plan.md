# AES and Layers VRAM caching implementation plan

[Design note](aes-layers-vram-design.md) · [GEM plans](README.md) ·
[Testing policy](../../contributing/testing.md)

Status: implementing, 2026-10-13. AV1 functional checks pass; its overhead gate
remains open. See the [execution record](../../history/aes-layers-vram.md).
Implement AV1–AV6 in order. Keep each slice
executable, validate its changed behavior and commit it separately. AV2/AV3 functional implementation is complete; AV4–AV6 remain to be completed. The existing GEM API, caller-local drawing,
presenter Task and display completion path remain the foundation.

The result is shared AES/Layers repaint bookkeeping, fast menu background
restoration, two rendered-popup slots and two larger client-image slots usable
by eligible AES windows. The console remains a retained-cell renderer; no
general VRAM allocator, always-backed compositor or new kernel service is added.

## Fixed decisions

- Layers owns cache identity, validity and repaint state. The presenter chooses
  when to capture/restore, and the display backend performs transfers.
- Keep exposure, content changes and completed painting separate. Handing off
  `WM_REDRAW` does not certify application pixels; a cache restore does not
  acknowledge application repaint.
- Preserve exposure `WM_REDRAW` for external windows, even after restoration.
  Ordinary GEM apps need no new mandatory call. The shipped apps use a small
  optional completion helper in their redraw paths to become capture sources.
- Use existing outermost UPDATE exchanges to publish bounded reports. No RPC
  per glyph, object or blit; no repeated pointer/tree/geometry validation.
- Retain one scene transaction and the driver's one active transfer. No wait
  for an application holds a scene token. Slots remain pinned until DMA retires
  or the driver establishes quiescence.
- Initial transfers require even X/width. Unsupported alignment, insufficient
  space, incomplete painting or a cache miss takes the existing redraw path.

Public declarations/layouts change through their ABI inputs and generators.
Rebuild affected clients together and remove replaced cache policy. Function
names below describe internal operations; AV1 fixes declarations once their
generated sizes and focused call probes have been checked.

## Evidence and performance gates

Reuse the [menu latency record](../../history/menu-latency.md) and its
[machine-readable evidence](../../development/menu-latency.json). Preserve the
matching packaged executable and hashes before implementation. There is no
separate baseline-only slice. Extend the measurement tool as a dependency of
the first slice needing a new cohort, and run that cohort on unchanged code
before changing its behavior.

The existing idle cohort has 20 samples per interaction and approximately
20.1 ms PAL-frame sampling. Its post-ML4 medians/p95 are:

| Interaction | Median ms | p95 ms |
| --- | ---: | ---: |
| File open | 401.2 | 401.2 |
| Application highlight | 80.3 | 80.3 |
| File to View | 782.1 | 782.3 |
| View close | 401.2 | 401.2 |
| Windows open | 180.6 | 180.6 |
| Native highlight | 80.3 | 100.3 |
| Native next row | 100.3 | 100.3 |
| Windows close | 501.4 | 501.4 |

Keep compiler/Calypsi, ROM, emulator, video, mouse profile, media and geometry
identical in each comparison. The existing warmed-reference measurement is not
a cold-cache result. Add explicitly cold and warm cohorts, actual cache-hit
observations, and two completion timestamps: first correct visible repair and
final application repaint. A screenshot matching cached old content is not
evidence of the latter; correlate final completion with the known app model
and its repaint acknowledgement. Keep raw samples and polling resolution.

Freeze these acceptance targets before tuning; they are targets, not claims:

| Behavior | Acceptance target |
| --- | --- |
| AV1 bookkeeping only | Existing interaction median/p95 no more than one PAL frame above the matched baseline. |
| Valid menu-background restore | Complete visible dismissal repair p95 at most five PAL frames (about 100 ms), and median/p95 at most half the matched uncached dismissal. |
| Warm popup open | Median/p95 at most half the matched uncached opening for File and Windows. |
| Warm File-to-View switch | Median/p95 at most 75% of the matched original switch. |
| Cold opening, highlight and invalid-cache fallback | Median/p95 no more than one PAL frame above their matched uncached cohorts. |
| Final app repaint after restoration | No more than one PAL frame worse than matched original final repaint; never substitute first restored pixels. |
| Loaded pointer/button feedback | p95 no more than one PAL frame worse than the same load without the new caches. |

Use 20 samples for each comparable idle/cold cohort. Add at least 30 loaded
interactions with Counter and sustained shell output, at several offsets within
the update cycle; check progress and final content, not just counts. Loaded
timing needs new matched baseline samples: the old Counter coexistence test
proves progress only. Numeric misses remain open in the record; do not change
the gate or remove failing samples after seeing results. Separate functional
completion from performance acceptance, and keep an unproven optional fast
path disabled rather than introducing a second production implementation.

## AV1 Track application repaint through AES and Layers

Change `abi/layers.json`, `abi/aes-server.json`, their generators,
`layers.act`/`layers-update.inc`, `aeswindowstate.act`, `aeslocks.act` and the
caller bindings. Keep ordinary rendering unchanged in this slice.

1. Add bounded pending external repaint and a repaint generation to layer
   state. Track work-area obligations separately from frame damage. Preserve
   those obligations after `FinishHandoff`, without a runnable spin or repeated
   delivery of the same pending event.
2. Introduce internal content-change and completed-region operations. Exposure
   preserves otherwise reusable saved content; a content change invalidates
   it even when invisible. A completion matches the layer lifetime, generation
   and actual painted region, and cannot retire newer damage.
3. Publish generation/snapshot state at outermost `BEG_UPDATE`. Initially
   invalidate saved images of all the owner's windows and intersecting saves
   conservatively. Hold this invalidation through nested updates.
4. Add a caller-local bounded journal and sticky drawing-failure flag. VDI and
   object entry points report modified bounds before visibility clipping,
   once per public call. A completion helper reports only regions the caller
   actually reconstructed. Publish at outermost END, before releasing update
   ownership; failure/owner exit never turns partial work into valid pixels.
5. Allow at most eight completed-region entries in the journal. Changed bounds
   may merge conservatively; completed regions may merge only without adding
   unpainted area. Overflow drops excess completion claims, retaining pending
   repair. Final generated storage must fit the budgets below.
6. Integrate the helper into Counter and the common Files/desktop redraw path,
   so AV2 can use the real SYS folder as a completed capture source. Keep an
   ordinary GEM fixture without the helper as the fallback proof. Do not infer
   completion from `END_UPDATE` or exhausting the visible-rectangle iterator.

Validation: extend the existing Layers external checks and AES window/VDI
fixtures. Cover partial/disjoint completion, frame/work separation, generation
changes, nested updates, sticky failure, journal overflow, multiple owned
windows, hidden updates and delayed consumers. Check both Action!/C layout
directions and record access with small raw/optimized probes. Broader cases run
optimized. Repeat the existing idle menu cohort for the AV1 overhead gate.

Exit: a completed visible client is distinguishable from a delivered-but-undrawn
redraw; arbitrary GEM callers still redraw correctly. No VRAM change. Record
actual fixed/client upper-RAM growth and zero bank-zero reservation delta.

## AV2 Restore menu backgrounds with Layers transactions

Add a small `lib/display/layercache.act` companion for generic slot validity,
pinning and identity. Move the existing native snapshot metadata/policy into it
in this slice; keep display packet construction in the presenter adapter. Update
the desktop ABI/generator and migrate existing native cache users together.
The current 64 KiB client slot sizes stay unchanged until AV4.

Reserve the design's 76,800-byte menu background at `$14000–$26BFF` in
`vbxe-vram.json`, generating shared constants from that map. Add bounded
scene-rectangle read and coordinated popup hide/restore transactions to Layers.
Use existing transaction completion, not a second lock or transfer queue.

Integrate the state machine into `deskmenu.act`, `deskappmenu.act`, the painter
and presenter pump:

- Before showing the popup, capture the complete footprint only if all visible
  contributing pixels are known complete. Strip overlays and pin storage.
  Pending source paint causes an immediate fallback, not an application wait.
- Invalidate a save on any intersecting underlying content change or relevant
  geometry/lifetime change. Include console writes/scrolls and native widget
  changes. The popup's own show/highlight/hide is excluded. Use per-rectangle
  intersection; unrelated activity elsewhere must not invalidate every save.
- Hide and restore with stable post-hide visibility; retire restored manager
  damage only after copy completion. Preserve external exposure messages and
  avoid a redundant presenter clear/repaint of successfully restored pixels.
- On heading switches, restore/hide the old popup before capturing beneath the
  new one. Cancel or fall back if replacement/exit invalidates the source.
  Keep pointer/input capture and the existing completion/error paths running.

Validation: extend emitted Layers transactions, desktop cache and menu fixtures.
Verify exact source/destination pixels for backgrounds spanning several owners,
covered/uncovered Counter ticks, console output inside/outside the footprint,
replacement, close during DMA, odd edges and changed geometry. Inject failed
and unquiesced transfers; assert pins/tokens and pending damage. Retain the
ordinary GEM no-helper case and a hidden model change with no drawing call:
later exposure must still reach the app. Measure cold-open cost and both
dismissal endpoints. Add a small both-mode probe for new transaction layouts.

Exit: valid saves restore, invalid saves redraw, and no old menu can become
part of the next saved background. Production VRAM total: 320,000 bytes.
Expected bank-zero reservation delta: zero.

## AV3 Reuse rendered popup images

Reserve two 16 KiB slots at `$27000–$2AFFF` and `$2B000–$2EFFF`. Reuse the
AV2 cache companion and display adapter; do not add a parallel menu cache
lifecycle. Integrate lookup/capture with menu paint completion.

Key by stable owner/menu lifetime, content revision, heading, dimensions,
appearance and selected state. Distinguish the same heading in different apps.
Populate only from a complete visible popup after input/visible work settles.
One attempt per unchanged state prevents capture/eviction loops. Reopening an
exact match copies pixels; a miss or oversized menu uses the current renderer.

Initially require an exact selected-state match. Optional reuse of unchanged
rows must prove which cached rows match; never restore an old highlighted row
as normal. Keep existing targeted highlight drawing and disabled/checked rules.
Do not hash strings on the hot path or pre-render every selection combination.

Validation: extend the independent AES/native menu pixel oracle and lifetime
fixture, including two owners with identical geometry, menu mutations, old
selected rows, eviction, partial capture/failure, long labels and capacity
limits. Measure warm/cold opening and heading switches separately, and retain
highlight/nonmenu-progress regression gates.

Exit: real cache hits accelerate repeated openings with exact pixels and no
additional application messages. Production VRAM total: 352,768 bytes.
Expected bank-zero reservation delta: zero.

## AV4 Enable larger client snapshots for AES windows

Grow/reposition the two client slots to the design's 75 KiB ranges:
`$50000–$62BFF` and `$62C00–$757FF`. Update the generator's existing 65,536-byte
assumption and all capacity consumers; byte counts must represent 76,800 without
16-bit overflow. Reuse the migrated slot policy rather than restoring desktop-
specific validity checks.

Allow a capture when the entire client is visible and its repaint obligations
are acknowledged. Compute work bounds using the actual frame kind, including
borderless, INFO, size and scrollbar insets. Preserve client-local images on
position-only changes and title-only focus changes; resize/appearance/content
changes invalidate them. Restore under current visible clipping, while AES still
delivers the ordinary exposure redraw. Frames continue through their renderer.

Add completion-helper integration to Text and shared dialogs, and the remaining
shipped redraw paths that participate in cache capture. Ordinary callers remain
eligible for the existing redraw fallback. Preserve invalid-first/LRU selection,
one capture attempt per revision, asynchronous pins and low-priority capture.
Remove obsolete `DESKCACHE` metadata/policy and compatibility branches; retain
only the necessary desktop-to-display adapter.

Validation: extend native/AES snapshot cases for both sides of a 64 KiB VRAM
boundary, a full 640×240 buffer transfer, compact pitches, frame variants,
exposure after move/close, two competing window slots, late completion, resize,
reused slot identities and odd-X fallback. Check no-helper windows still get
redraws. Use focused app/dialog pixels and a small both-mode capacity/layout
probe; do not rerun unrelated application suites.

Exit: native and eligible AES client images share one policy; large clients fit
and external redraw obligations remain intact. Production VRAM total:
375,296 bytes. Expected bank-zero reservation delta: zero.

## AV5 Maintain small changes and prove copied moves

Refine conservative whole-slot invalidation only after AV1–AV4 work. At UPDATE
acquisition make an image temporarily unusable; retain its previous contents
as a potential base. At END use modified bounds, completed regions and failure
state to decide whether that base can be patched.

Start with one bounded repair rectangle per slot. Patch only if the whole repair
rectangle is acknowledged, currently visible and copied after successful paint.
A partial completion cannot certify its bounding rectangle. Hidden changes,
ambiguous coverage, drawing failure or a newer revision invalidate the base.
An update with no drawing/completion reports remains conservative; it cannot
silently restore eligibility after an invisible model change. Do not introduce
an application-wide promise that all hidden model changes are reported.

Coalesce repeated changes and service input/visible repair before maintenance.
Superseded work is discarded. Measure patched bytes/capture frequency: Counter
must not trigger a full-window capture for each six-digit update. If maintenance
cost exceeds its benefit, leave that image invalid instead of chasing updates.

Enable copied AES moves only for completely painted, fully visible sources
under the existing move transaction, with current frame/client pixels and
eligible destinations. Preserve application geometry publication and external
exposure notification; copying historical pixels does not waive redraw.
Otherwise use the ordinary move/redraw path. No blanket removal of the
external-layer restriction in `BeginRead`/`BeginMove` is allowed.

Validation: exercise multiple updates before patch, hidden updates, changing
content during delayed maintenance, new damage after a prepared completion,
slot eviction and failed patch. Compare copied and ordinary moves in all
directions with complete pixels, owner notifications and stack guards. Record
cache maintenance work and matched latency. Enable each optional fast path only
after its correctness and measured benefit are established; explicitly record
an unaccepted path rather than calling it complete.

Exit: small updates patch safely when useful; admitted AES moves reuse complete
pixels. No additional VRAM or bank-zero reservation is expected.

## AV6 Validate the complete desktop and publish evidence

Run the host suite and affected optimized menu/window/cache/app regressions,
reusing passing slice results when their inputs remain unchanged. Extend
`tools/measure_menu_feedback.py` to report cache hit/miss/invalidations, bytes
captured/restored/patched and the two visible-completion endpoints. Read
diagnostic counters outside timed regions; any executable instrumentation needs
an observer-disabled control.

Compare all frozen cohorts, including Counter and shell output. Confirm final
model values, absence of stale overwrite and unrelated Task progress. Report
flicker during the follow-up app redraw separately from restoration latency.
Keep failures and unmet performance gates visible in the execution record.

Build the final demo through `tools/build_demo.py` with OF816, pinned ROM,
matching system/WORK disks, notices and five-second autoboot. Exercise the exact
extracted ZIP: Files, Counter, Text/dialogs, menus, closing/raising windows and
EXIT with intact guards and released Tasks/slots. Distribute only the normal
`exec816-demo.zip` contents; provide its hash and launch command.

Update the Layers/AES/desktop reference contracts, application helper guidance,
this plan and indexes. Add `docs/history/aes-layers-vram.md` and compact
`docs/development/aes-layers-vram.json` evidence with actual source/artifact
hashes, pins, sample distributions, enabled/disabled paths and memory accounting.
Development checks do not qualify real hardware or a release matrix.

## Memory and validation accounting

| Slice | Added VRAM bytes | Production total bytes |
| --- | ---: | ---: |
| AV1 | 0 | 243,200 |
| AV2 | 76,800 | 320,000 |
| AV3 | 32,768 | 352,768 |
| AV4 | 22,528 | 375,296 |
| AV5–AV6 | 0 | 375,296 |

Check the combined production/diagnostic map in each allocation slice, including
the unchanged `$3FFF0–$4000F` diagnostic. Final added VRAM is 132,096 bytes;
148,960 bytes remain after production reservations and that diagnostic.

Each slice targets **0 fixed / 0 per public Task / 0 idle reserved bank-zero
bytes**, including stack/DP guards, alignment and unused reserved capacity.
Keep extra fixed upper-RAM metadata within 2 KiB and caller journals within
256 bytes per registered AES client. Compute generated sizes before landing
each ABI change, counting per-window published-view growth and metadata moved
out of the desktop only once. Avoid region arrays on native stacks. If measured
headroom requires stack growth, report the actual per-Task reservation and
revise the target explicitly rather than forcing a major refactor.

Use existing `tools/test_layers.py`, `tools/test_layers_probe.py`,
`tools/test_aes_server.py` window/VDI/menu/lock fixtures and
`tools/test_desktop_cache.py` as the starting harnesses. Add narrowly selected
cases where needed. Optimized emitted tests cover behavior, pixels, lifecycle,
completion faults and coexistence. Raw/optimized coverage is limited to changed
record/call/bridge boundaries or a focused compiler-defect investigation. No
compiler-wide checks or full qualification matrix are scheduled by this plan.
