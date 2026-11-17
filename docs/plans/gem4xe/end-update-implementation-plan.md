# Bring END_UPDATE and SCRENMGR completion closer to MagiC

[GEM port](README.md) · [END audit](../../history/gem-end-update-audit.md) ·
[Frozen measurements](../../development/gem-end-update-audit.json) ·
[Port guidance](../../contributing/README.md#gem-architecture-guidance) ·
[Development testing](../../contributing/testing.md)

Status: EU1–EU5 implemented, 2026-11-17, including the selected application-cache
removal and MagiC's explicit final yield;
see the [execution record](../../history/gem-end-update-implementation.md).
Commit every passing executable slice separately. MGVIEW is the sole application
acceptance target; other applications may break during the later API cutover.

## Outcome and source baseline

Drawing operations complete their physical work and cursor restoration in the
caller. SCRENMGR wakes for actual input, interaction, lifecycle or unfinished
device work. An ordinary END_UPDATE releases ownership without creating a
manager turn or a painting transaction.

Use MagiC revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d`:

- `AESEVT.S:1428–1471`: common recursive UPDATE acquisition and semaphore wait.
- `AESEVT.S:1508–1562`: decrement, final FIFO release, `appl_yield`, return.
  Final release makes the oldest waiter ready; the semaphore helper itself
  does not switch Tasks.
- `AESMAIN.S:4235–4287`: SCRENMGR waits for key/button/menu/message events and
  acquires UPDATE after an event. Ordinary painting completion is not an event
  that sends it through a generic maintenance turn.

The [source model](../../architecture/magic.md) pins the source files and the
[mouse cross-check](../../history/gem-mouse-magic-review.md) establishes shared
device visibility, application-owned forms and routing-based cursor ownership.
Retain the existing GEM4XE-derived graphics implementation; do not introduce a
second renderer or change raster algorithms in this plan.

The [audit commit](../../history/gem-end-update-audit.md), `0ee003dc`, is EU0's
completed baseline. Reuse its cached provider/APP, donor hashes, ROM/emulator
configuration and passive PC definitions. END takes 17.34/17.45 ms elapsed:

| Measured responsibility | Down/up |
| --- | ---: |
| Viewer CPU in END | 6.23 ms |
| Native semaphore release CPU, included above | 0.069 ms |
| Journal/cache CPU, included above | 3.06/2.45 ms |
| Off-Task at Permit after native release | 9.06 ms |
| SCRENMGR CPU in that interval | 6.81 ms |
| Final release Signal CPU, included in viewer CPU | 0.72 ms |

The manager performs no interaction, UPDATE acquisition or VBXE submission in
that wake. The cache scan rejects width 635; publication returns without a
rebuild. These are targets for eliminating unnecessary work, not guaranteed
latency savings. Useful viewport painting precedes END; PAL/COP observations
remain quantized and other ready Tasks may run after release.

## Boundaries and choices

Keep normal Exec Task preemption, independent input.device/backend execution,
native recursive FIFO ownership, private caller packets, physical display
grants, failure retention and IRQ/NMI protocols. Keep the user-selected committed
hit snapshot and endpoint lifetimes. Geometry/hit changes still publish a complete
snapshot before another owner can act on them.

No new Task, signal bit, queue, kernel selector or platform service is proposed.
Use public semaphores, Signal, Wait, Forbid/Permit and Yield. No public semaphore
field may be inspected: its representation is opaque. If these services prove
insufficient, report the missing general capability before implementation.

EU1–EU3 preserve the current application painting/cache contract. EU4 proposes
removing that contract from ordinary GEM windows. Its explicit choice is below;
authorization of only the earlier slices does not select that removal.
EU5 proposes MagiC's explicit final yield and must not be conflated with a
SCRENMGR notification or assumed equivalent to Permit.

## EU1 — finish cursor consequences with the drawing operation

Current `CONSOLEBITMAP.Run` and `Drawn` set `drawingChanged` after drawing,
including caller work whose `borrow_leave` already restores overlays and the
cursor. Establish which operation has actually left presentation unfinished.

- In `lib/console/consolebitmap.act`, distinguish completed synchronous caller
  output from work still requiring cursor/outline presentation. In
  `ports/gem4xe/adapter/gem-vbxe.c`, use the existing final fence, overlay restore
  and grant release as the physical completion boundary. Cover shared native
  owner paths as well as borrowed caller paths.
- Consume an old hint before the operation that satisfies it. Preserve a new
  drawing/input arrival during that operation and retain/rearm work after BUSY
  or failed admission. Do not clear a shared flag unconditionally after return.
- Use existing `drawingChanged`, pointer `dirty` and mouse revision/completed
  state first. A newer position/form/visibility target remains pending even
  when the previous operation restored its own cursor pixels.
- Preserve explicit hide/show nesting, application forms, raw VDI visibility,
  active outlines and asynchronous copy completion. No additional fence or
  per-primitive AES RPC is introduced to acknowledge completion.

Focused check: extend the optimized emitted cursor-hint fixture for successful
inline completion, late arrival, BUSY retry and failure, retaining its existing
late-draw cases. Use the cursor-completion probe only if its C boundary changes.
Repeat the MGVIEW down/up pair for actual rendering and guards.

Pass: a completed parked-pointer draw leaves no redundant presentation work;
a newer target or unfinished operation remains discoverable. The release wake
is still present in this slice, so it must not be reported as eliminated.

Commit: `gem: retire cursor work at physical drawing completion`.

## EU2 — notify SCRENMGR only for a genuine blocked continuation

- In `lib/aes/aeslocks.act`, remove final painting release's unconditional
  setting of `UPDATE_WAITING`. Preserve `SystemBlocked`'s guarded arm/recheck
  and `Notify`'s consume-and-signal protocol for actual pending continuation.
- Keep native semaphore waiting/handoff as the UPDATE ownership mechanism.
  Do not Signal a semaphore waiter, add a parallel AES waiter queue or infer
  ownership from an update hint.
- Check every producer of manager work: physical pointer capture, retained
  gestures/Escape, application outline suspension, MCTRL, cursor retry,
  registration/retirement, shutdown and device completion. Each durable pending
  condition needs its existing producer wake or an armed release wake.
- Keep the short final notification/release guard where needed for the real
  lost-wakeup race. Do not remove guards solely because the uncontended
  measurement does not exercise them. Leave yield policy for EU5.
- Update passive accounting to accept zero manager turns in the measured
  interval. The current timeline helper requires multiple SCRENMGR turns to
  discover its Task. Read Task identities once at the ready checkpoint, retain
  scheduler/IRQ markers and attribute an absent manager cycle as zero. Do not
  wake the manager for tracing or assume historical Task-pool indices.

Focused check: extend the optimized locks/interaction fixture with an idle final
release and a real blocked continuation. Place release before the waiter arms,
between its initial check and guarded recheck, and after arming. Verify nesting,
MCTRL routing restoration and FIFO handoff with two contenders. Run the changed
cases, not the complete historical application matrix.

Pass: the parked-pointer MGVIEW END produces no synthetic SCRENMGR wake or
release Signal. A blocked continuation resumes once it can proceed; nested END
does not announce final availability. Input/device progress remains independent.
Other ready Tasks may still execute before the application returns.

Commit: `gem: wake blocked manager work on final UPDATE release`.

## EU3 — service input and cursor work at their actual change boundaries

- In `lib/aes/aeshost.act`, remove unconditional input-snapshot refresh from
  every `Service` call. Use existing publication changes and `mouseDirty` to
  identify routing/eligibility updates. Keep endpoint retirement, caller
  continuation settlement and application-outline suspension when pending.
- Keep physical sample publication in input.device's existing callback path.
  Refresh recipients/eligibility on registration, focus, geometry/stack, MCTRL,
  gesture ownership, loss and release transitions even with no pointer motion.
  Paint-only UPDATE does not change input ownership.
- In `lib/desktop/deskinput.act`, avoid repeated recipient selection and a
  second unconditional `Present` when nothing changed in between. Retain a
  post-interaction presentation when interaction changed the target or pixels.
- In `lib/aes/screnmgr.act`, dispatch the relevant durable pending work before
  Wait. Wake bits remain hints; an arrival after acknowledgment or during
  physical work must remain pending. Reuse existing state rather than creating
  another scheduler, work queue or generic polling framework.
- Make ordinary paint-only release skip routing publication once all actual
  routing mutation paths publish at their own boundaries. Preserve END_MCTRL's
  routing transition and the complete committed hit snapshot.

Focused check: stationary-pointer focus/MCTRL changes and one late pointer
arrival during cursor completion. Check a lifecycle wake with a closing
endpoint. Reuse passing EU2 ownership cases unless their paths change again.

Pass: unrelated wakes do not scan every input recipient or call the unchanged
mouse adapter. Input, routing changes and completion wakes still reach their
consumers, with no periodic retry loop. No mouse disappearance or stale form
after a blocked interaction, redraw or hide/show transition.

Commit: `gem: service mouse and input state on actual changes`.

## EU4 — replace the ordinary painting journal with standard GEM flow

### Policy proposed for selection before this slice

For external GEM application windows, remove optional backing-image preservation
and the requirement to acknowledge painted pixels through Exec-specific reports.
Use MagiC's visible-screen copy/exposed-region redraw flow under UPDATE.
Window/menu operations retain responsibility for their own physical effects.
This accepts losing optional application backing-cache restores in the MGVIEW-first
port. Other applications using the extensions may need source changes.

This is the recommended concrete choice. An alternative is to retain the
application backing cache and its explicit invalidation/completion contract,
designed separately; that alternative leaves EU4 pending and does not authorize
moving the same journal work into every VDI primitive. Record the selected
policy before changing the current public contract.

### Coordinated cutover after that selection

- Inventory the live users of paint epochs, `pixelsReady`, change flags,
  invalidation/paint journals and cache candidates across `AESWINDOWSTATE`,
  `AESLOCAL`, `DESKCACHEWORK`, Layers, C drawing bindings and MGVIEW's native
  patch. Distinguish scene/endpoint identity epochs from pixel-completion proof.
- Remove ordinary BEGIN/END's window touch, journal consumption and application
  cache capture/patch scan. Remove the corresponding per-draw journal writes.
  Keep real geometry/exposure bookkeeping and normal redraw message delivery;
  do not pretend a pending obligation was painted by setting readiness to one.
- Remove backing-cache candidates/restores for external application windows
  together, so an old cached image cannot survive the loss of its invalidation
  protocol. Keep system menu/background storage only where its owning operation
  establishes validity and retires the physical copy. Document that boundary.
- Make standard UPDATE and visible-rectangle enumeration sufficient for drawing.
  Replace MGVIEW's `ExecAESBeginUpdate(window)` with ordinary
  `wind_update(BEG_UPDATE)`, and remove its `pixelsReady`/`ExecAESPainted` repair
  protocol. Preserve UPDATE across enumeration, scroll copy and exposed redraw.
  Verify normal window queries select the correct view without the old helper.
- Follow the pinned MagiC window movement/exposure path when replacing a cache
  fallback; retain the current geometry model and GEM4XE/VBXE copy implementation.
  Correct source pixels are the caller's drawing responsibility. A display
  failure must not be converted into successful painting or a valid cache image.
- Remove obsolete helpers/fields/imports through the machine-readable ABI
  definitions and generators; update all linked library consumers and affected
  fixtures. Keep one implementation and ABI, with no successful legacy stubs.
  Rebuild MGVIEW and the matching provider together if the ABI changes. Record
  unbuilt application migration requirements without rebuilding the catalog.

Focused check: the same loaded MGVIEW scroll pair, then one exposure/move case
that proves exposed content still gets `WM_REDRAW` and reconstructs correctly.
If shared records/imports change, add only the small raw/optimized layout and
bridge probe required for that ABI boundary. Update the current
[AES contract](../../reference/aes.md#optional-repaint-completion) in this commit.

Pass: MGVIEW uses ordinary UPDATE and VDI drawing with no pixel-completion
reports. END performs no application journal/cache work; window exposure and
visible screen copies remain correct. No extra per-glyph/per-row RPC or grant
is introduced. Any remaining END work has an identified ownership/lifecycle role.

Commit: `gem: use standard GEM painting completion for application windows`.

## EU5 — match MagiC's final scheduling boundary and record the result

MagiC explicitly calls `appl_yield` after final semaphore release. The proposed
mapping is public `EXEC.Yield()` after the final matching AES ownership scope
has released its native resource and exited the short Forbid guard. Nested
releases do not yield merely because a binding helper returned. This is a
separate scheduling change, with its own measured cost, not part of EU2's wake
removal. Record the choice before implementation; retaining Permit alone is
an explicit departure requiring a reason and user selection.

- Check public UPDATE/MCTRL, temporary handler scopes and SCRENMGR release
  nesting together. Use AES's balanced scope ownership, not private native
  semaphore depth/queue fields or a new kernel operation. If existing scope
  bookkeeping cannot identify the correct boundary, present that concrete
  scope-accounting change and its upper-RAM cost in the slice; follow the
  governing review rule if it would depart from the selected ownership model.
- Yield with no physical grant held, and retain normal preemption throughout
  drawing. Native FIFO handoff determines the next resource owner; scheduler
  priority still determines which ready Task runs.
- Extend the focused emitted ownership case to show a peer's progress after
  final release, no premature resource access and no final-release behavior
  at an inner nesting level. Reuse kernel semaphore tests; do not change kernel
  policy to make the GUI measurement smaller.

Repeat the matched MGVIEW pair and retain a new immutable record. Report viewer
END CPU, pre/post-release intervals, real release notifications, manager phases,
cursor calls, grant/submission counts, viewport/window pixels and lifetime/guard
results. Separate test-controller CPU and native interrupts. Explicit yield may
retain off-Task time; success is eliminating invented GUI work while matching
the chosen scheduling semantics.

Commit: `gem: align final UPDATE release scheduling with MagiC`.

## Build, validation and resource budget

Use [pinned compiler inputs](../../../toolchain/actionc.json). Ordinary checks
are optimized emitted-code development runs and host checks. Raw runs are only
for a changed ABI/compiler boundary or a suspected compiler defect. No QED,
Counter, catalog, demo, packaging or release qualification is part of this plan.

Use `test_cursor_hint.py`, `test_cursor_completion.py`, the selected `locks`
cases in `test_aes_server.py` and the interaction fixture behind
`test_aes_migration.py` as starting points. Add case selection where necessary
to avoid running unrelated scenarios. `test_screnmgr.py` supplies the MGVIEW-only
loader/build reuse path; do not run its complete wrapper after every small edit.
Recompile only changed C objects, relink/rebuild the native policy as needed,
and reuse the verified APP until its source/ABI changes in EU4.

The audit's `--end-detail` analyzer assumes a journal stage exists. Update its
definition and attribution for EU4/EU5 so a removed stage is reported as absent
and a newly linked program is resolved from emitted PCs. Preserve old captures
and hashes. Compare the full final window as well as the viewport; do not use
fewer trace markers to claim a reduction in work.

Plan for **zero additional reserved bank-zero bytes**: fixed, root, kernel,
idle and per-public-Task, including guards, alignment and spare capacity. Reuse
existing upper-RAM state first and report any changed upper-RAM/static/heap or
stack cost. Do not enlarge Task pools to accommodate tracing. Report the actual
reservation delta after every executable slice, including zero.

Each commit must leave its focused emitted fixture executable and its changed
contract documented. Preserve stack/domain guards, complete native context,
endpoint/Task lifetimes, bounded completion and independent input/device progress.
The final report distinguishes measured CPU reductions from latency observations
and development acceptance from hosted-system qualification.
