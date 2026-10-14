# Window preservation implementation plan

[GEM plans](README.md) · [Roadmap](../../roadmap.md) ·
[Existing cache design](aes-layers-vram-design.md) ·
[Desktop](../../reference/desktop.md) · [AES](../../reference/aes.md)

Status: WP1–WP4 implemented and development-checked, 2026-10-14.
See the [execution record](../../history/window-preservation.md) for measured
client/frame completion, cache counts and remaining latency.
The proposed [frame and exposure follow-up](window-frame-exposure-plan.md)
covers initial frame construction, saved decorations and desktop repair on close.

Make switching between unchanged windows a title/menu update and a few large
VRAM copies. Participating applications explicitly opt in to preserving their
client pixels and report content changes through the existing AES update
boundary. Other GEM applications retain conventional exposure `WM_REDRAW`.

Foreground visual completion takes priority over background repaint throughput.
Keep the existing presenter, two client snapshot slots, dedicated Shell backing,
menu saves and asynchronous display transfers. Full offscreen VDI rendering,
kernel Task priorities and a new cache allocator are outside this plan.

## Starting point

The focused run of the current `cbfc26f-dirty` RAM Desktop demo alternated
title clicks between overlapping Shell and SYS: windows, twice in each
direction, with no application activity. It observed:

| Action | Current work |
| --- | --- |
| Raise Shell | Eleven backing-copy submissions; unchanged console model |
| Raise SYS: | Twelve client-cache restores totalling 38,106 bytes, one Files repaint, then a 38,106-byte cache patch |
| Click the already active SYS: title | No redraw or cache transfers |

The local observations are in
`build/ram-desktop/demo/focus-trace-results.json`. These are diagnostic counts,
not a latency distribution or a hardware qualification result. Reuse this
baseline; no separate baseline implementation slice is needed.

Three existing paths explain the work:

- `LAYERS.Order` damages the raised window's complete bounds.
- `DESKPAINT` normally cuts damage into sixteen-row strips. Shell's larger-copy
  shortcut only admits rectangles wholly inside its client, so frame-inclusive
  damage loses that shortcut. AES client snapshots also restore by strip.
- `AESWINDOWSTATE.Damage` records an application repaint before the cache lookup.
  Successful restoration therefore still leads to `WM_REDRAW` and cache repair.

The last behavior follows the existing cache design's hidden-model rule. This
plan changes that rule only for explicitly participating windows. General
stacking-order damage reduction can follow separately; it is not needed to
establish large restores and eliminate the duplicate application repaint.

## Application contract

Add one Exec-specific `wind_set` selector,
`AES_WF_EXEC_PRESERVE`, with zero meaning conventional redraw and one meaning
preserve completed pixels. Applications set it after `wind_create` and before
`wind_open`. The default is zero. Keep the setting for that window lifetime,
including close/reopen and iconification; deletion clears it. Live policy
switching is outside this first implementation.

Use the existing request and window ownership path. Keep one small policy field
in the AES window record, rather than creating a new window class or public
cache object. Allocate the selector in `abi/aes-server.json` and regenerate
shared definitions. Existing GEM entry points and message layouts stay intact.

For an opted-in window:

1. Publish changes to drawable content inside
   `ExecAESBeginUpdate(window)` / `wind_update(END_UPDATE)`, even when covered or
   iconified. Private preparation may happen earlier; the update boundary
   commits the change that the screen and saved image must represent.
2. Draw through the current VDI/object paths. Continue to report completed
   visible pixels with `ExecAESPainted` before the outer END. Visibility clipping
   still applies; this contract does not provide hidden drawing storage.
3. A model-only change uses the same update pair without a paint-completion
   claim. The current BeginUpdate invalidation and conservative EndUpdate
   behavior already make the old image unusable, including when fully hidden.
4. A valid, completed restore satisfies exposure without `WM_REDRAW`. A missing,
   evicted, stale or unusable image uses the normal redraw path. The application
   must still handle those messages.

Use no new per-change RPC operation, tree hashing, model-memory inspection
or validation at every drawing layer. Most apps reuse their existing drawing
update pair. Text publishes one model-only pair per newly queued damage batch
because its drawing continues across event waits; otherwise idle maintenance
could certify a partially updated document. Existing identity, content
revision, paint completion, synchronization and transfer lifetime checks remain
the authority. A missed application update boundary is a caller bug that can
leave stale pixels; the flag is a promise, not a request for AES to discover
unreported changes.

## WP1 Restore complete visible client rectangles

Change `lib/desktop/deskpaint.act`, reusing `deskcache.act` and the console's
existing backing-copy descriptor:

- Separate the client intersection from frame fragments before applying the
  software paint-strip limit. A frame-inclusive damage rectangle must not split
  an otherwise reusable client image into sixteen-row copies.
- Submit the whole aligned visible client intersection as one asynchronous
  copy. For an unobscured Shell this is 512×160 pixels; for the current SYS:
  client it is 438×174. Use the same rule for other cacheable window sizes.
- Keep current visibility clipping. Separate visible rectangles remain separate
  transfers; do not copy over another window or widen an odd edge. Retain the
  existing renderer fallback for unsupported alignment and cache misses.
- Keep frame composition within its actual scratch capacity. The native frame
  batch currently accepts at most sixteen rows; increasing a global strip
  constant would overrun that contract. Paint title feedback, restore the client,
  and finish the remaining frame fragments without repainting restored content.
- At transaction boundaries, prefer pending work for the focused window after
  existing menu precedence. Finish its useful restore before unrelated
  background repairs. Keep round-robin selection for other windows and cache
  maintenance at idle. Add no kernel scheduling priority or interrupt masking.
- Preserve the scene token, source pin and display completion path through the
  entire transfer. Pointer/input capture and IRQ/NMI continue; scene edits wait
  for completion as they do now. No busy-wait loop or allocation is needed.

Completion: each aligned visible client rectangle uses one copy submission,
subject only to existing display-driver limits. The matched full Shell and SYS:
restores fall from eleven/twelve submissions to one each. AES still sends its
conventional redraw in this slice, making the copy change independently usable.

Focused check: exact pixels after one Shell/SYS: switching cycle, a partially
covered restore and an odd-edge fallback; check the existing transfer-failure
case still retains ownership until quiescence. Reuse the existing native/AES
cache harnesses rather than building a new renderer test framework.

## WP2 Make preservation satisfy exposure

Implement the opt-in selector and cache-hit completion in `aeswindow.act`,
`aeswindowstate.act`, `deskpaint.act` and the existing Layers transaction path.

- For conventional windows, keep exposure notification after restoration.
- For opted-in windows, try a matching cache restore before creating a new
  application repaint obligation. Successful hardware completion retires only
  the exposure actually restored. Do not clear an earlier content change,
  unrelated pending damage or an already delivered application message.
- On a miss or failed restore, retain/recreate the required damage and deliver
  normal `WM_REDRAW` once the display is usable. Preserve existing reset-required
  device-fault behavior. Completion after a superseded revision must never make
  stale pixels current.
- Keep initial painting, resizing, failed/partial painting and cache eviction on
  the ordinary fallback. Preserve the existing position-only cache reuse and
  lifetime checks. A policy flag alone never makes an image complete or valid.
- Apply the same policy to successful menu-background restoration in
  `deskmenucache.act`. Its saved rectangle may cover several window owners:
  conventional owners still receive exposure, participating owners need no
  redraw for successfully restored current pixels. A window snapshot is not
  required when the composite menu save itself proves those pixels reusable.
- Preserve invalidation of the menu save on content changes, including hidden
  changes. Failed or uncovered portions use ordinary repainting. Do not use the
  existing bounding union of exposure notifications as proof that every pixel
  inside that union was restored. Keep actual restore coverage and fallback
  damage separate using the existing transaction/region machinery.

Completion: a fixture with a valid opted-in image receives no exposure redraw
after raise or menu dismissal, while an otherwise identical conventional window
still receives it. No repaint-driven full-window cache patch follows an unchanged
preserved restore.

Focused checks in the existing AES cache fixture: warm hit, forced eviction,
fully hidden model-only update, partial completion, stale/failed transfer and
mixed-policy menu exposure. Reuse existing guard/lifetime checks. If public
record layouts change, run only the small raw/optimized layout bridge probe;
otherwise routine emitted checks use optimized code.

## WP3 Adopt the contract in shipped applications

Enable preservation after auditing each application's drawable-content changes.
The window flag is set once; ordinary event handling and `WM_REDRAW` handlers
remain available for misses. Avoid repeated updates for unchanged state and use
the existing window-specific update helper so one folder does not invalidate
every window owned by Desktop.

| Application or shared path | Changes that must cross the update boundary |
| --- | --- |
| Files and Desktop folder windows | Navigation results, refresh, icon/list layout, sorting, selection, scrolling, status and file-operation results |
| Desktop background | Icon selection, labels and published status; preserve normal redraw fallback when no complete image can be captured |
| Counter | Each committed displayed count, including a tick while fully covered or iconified; scope updates to its own window |
| Control Panel and Calculator | Button/radio/focus state, displayed values and settings feedback |
| Text | Document replacement, loading results, viewport changes and displayed status |
| Shared forms, alerts and file selector | Entering, editing and dismissing borrowed-window content, including restoration of the owning application's model |

Do not let a shared dialog leave its pixels eligible as the application's normal
window image after dismissal. Reuse the existing form repair path and update
boundary; keep temporary owned dialog windows conventional unless their complete
lifecycle already satisfies the contract. Retain explicit repairs already
requested by forms.

Batch related model edits inside the update scope already needed for drawing.
Asynchronous directory/document work may prepare data privately, then publish
the changed display once. A hidden update must invalidate its old image even
when the visible rectangle list is empty.

Completion: repeated idle Shell/SYS: switches and File/View menu dismissal leave
Files' paint counter and cache-maintenance byte counters unchanged after warmup.
A covered Counter advances and displays its latest value when revealed. An
application alert closes back to the current application contents.

## WP4 Focused verification and demo delivery

Keep the development scope small. Reuse WP1/WP2 checks when their inputs are
unchanged; do not run a full application or qualification matrix.

Extend the existing passive focus observer into a reproducible focused tool:

- Warm the two overlapping windows, then alternate physical title clicks. Record
  client copy counts, restored bytes, Files paint count and maintenance bytes.
  Read counters outside timing intervals and keep guest code unmodified.
- Record input-to-correct-client-pixels and input-to-settled-window completion
  separately. Use a small matched before/after sample set and report individual
  samples/median/max rather than claiming a robust p95 from a handful of clicks.
- Compare pixels against the existing scene oracle. Include a repeated active
  title click, partial exposure, one File/View menu interaction, one hidden
  Counter update and one shared-dialog dismissal. Exercise the conventional
  no-opt-in fixture and forced cache miss in the smaller emitted test.
- Confirm background Task progress, clean EXIT and intact guards. Foreground
  restoration may delay background drawing; do not impose the old small-strip
  fairness target on the cache-copy path or launch a separate load campaign.

The principal acceptance result is structural: **one restore per aligned visible
client rectangle, zero duplicate Files redraws on warm idle exposure, and zero
maintenance copies caused solely by that exposure**. Report observed latency
without inventing a target from the earlier diagnostic counts.

Build through `tools/build_demo.py`, retaining OF816, five-second autoboot, the
pinned ROM, matching disks and notices. Exercise the exact extracted ZIP and
provide its launch command. Keep reports and traces outside the distribution.
Update the AES/desktop references and application guide only when the behavior
is implemented, then record the results in history and mark these slices done.

## Memory and delivery

WP1–WP4 target **0 additional fixed bank-zero bytes, 0 per public Task and 0
idle Task bytes**, including guards, alignment and unused reserved capacity.
They add **0 VRAM reservation bytes**. Count the actual upper-RAM policy and
painter-continuation growth during implementation; do not add per-window bitmap
allocations, new region arrays on stacks, or a second cache-validity system.

Implement in WP1 → WP2 → WP3 → WP4 order, keeping each slice executable and
reviewable. Existing uncommitted work is separate from these planned changes.
Implementation and focused
development results are recorded in [window preservation](../../history/window-preservation.md).
