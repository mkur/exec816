# MagiC UPDATE and Exec scene-access audit

The tables below describe the recorded baseline. The
[SCRENMGR migration record](../history/screnmgr-migration.md) tracks delivered
caller drawing, independent input, registration lifetimes and UPDATE ownership;
the [current AES contract](../reference/aes.md) describes supported behavior.

[Architecture index](README.md) · [MagiC model](magic.md) ·
[Architecture mapping](magic-exec-mapping.md) ·
[Source inventory and evidence](../development/magic-update-scene-audit.json)

Source audit, 2026-11-15, against Exec revision
`deaf83830c5b57dff10c3f14766bdc0fbded80bc` and MagiC revision
`28cfdd29aa16fef692cc287bad3046b44ddcce3d`. The inspected path is ordinary
key delivery, UPDATE admission, window setters, cursor calls, drawing and END,
including the presenter's scene readers, mutations and retained effects.
This is an analysis of current source and saved development observations.
No executable migration or new latency measurement is included.

## Findings

1. **UPDATE does not currently confer scene access.** A caller can acquire the
   native semaphore and then sleep in `AESGATE.EnterTask`. The presenter claims
   that gate near the start of its turn and offers it near the end, independently
   of whether it owns UPDATE. The gate introduces another resource-admission
   protocol after native FIFO handoff.
2. **The gate currently protects real shared state.** Live window/Layer reads,
   route construction, GUI registration, journals and cache metadata depend on
   it. Removing its calls without assigning those accesses a new owner would
   break the current contract. Its present usefulness does not establish that
   a second broad gate belongs in the target architecture.
3. **Simple setters still have a different completion boundary.** MagiC changes
   a slider, draws the relevant frame component and releases UPDATE before
   returning. Exec invalidates frame damage, publishes views and returns; the
   presenter paints later. This is an AES/library migration issue, with existing
   Exec synchronization and display services available.
4. **The latest saved scrolls are not contention examples.** Both AP2 actions
   have zero visits to the failed native-acquisition signal site and zero to
   the scene-wait signal site. Their two setter calls still use about 15.2 ms
   of viewer CPU. A structural second queue is established; attributing those
   milliseconds to queue contention is not.
5. **No new platform service is demonstrated for this path.** Native recursive
   semaphores, signals, short publication guards and display grants already
   exist. Hosted C allocation cleanup covers the present application. Forced
   termination remains a separate lifecycle capability, not a prerequisite for
   this cooperative drawing path.

## MagiC source baseline

| Responsibility | Pinned source path | Observed boundary |
| --- | --- | --- |
| Ordinary key delivery | AESEVT `handle_key` / `write_key`, lines 1646–1681 | Append to the recipient's key buffer and publish readiness without obtaining UPDATE. |
| Recursive UPDATE and FIFO handoff | AESEVT `_wind_update`, `_beg_update`, `end_update`, `free_semaphore`, lines 1433–1557 | An uncontended/recursive owner continues; a contender waits; final release assigns the oldest waiter before publishing its event. |
| Screen-manager work | AESMAIN `screnmgr`, lines 4235–4280 and `scrmg_next`, lines 4453–4455 | Wait for events first, then obtain UPDATE for the screen-manager operation and release it before the next event wait. |
| Normal window setter | AESWIN `_wind_set`, lines 2298–2326 | Obtain UPDATE and dispatch the field handler in the calling context. This inspected path has no second scene-admission wait. |
| Slider mutation and painting | AESWIN `ws_slend` through `ws_endsw_ret`, lines 2768–2796 | With smart redraw enabled, skip equal values; otherwise update frame geometry and draw an open window before releasing UPDATE. |
| Window query | AESWIN `_wind_get`, lines 1957–2009 | Dispatch reads, including visible-rectangle iteration, without an internal UPDATE acquisition. A multi-call drawing operation needs its enclosing application UPDATE. |
| Mouse hide/show and form | AESMAIN `gm_hide` / `gm_show`, lines 7200–7208; `_graf_mouse`, lines 7244–7283 | Update application mouse state and call the physical mouse helpers without entering the window setter's UPDATE path. |

Sources: [AESEVT], [AESWIN], [AESMAIN]. The existing
[preemption comparison](magic-exec-mapping.md#preemption-and-ambient-graphics-state) explains why
Exec cannot copy MagiC's supervisor-mode execution assumptions. Exec retains
normal Task preemption; short publication guards and device ownership must
remain explicit. This does not imply a turn-wide second scene gate.

## Current caller and presenter flow

The named C APIs and parameter-block dispatch converge on the same native
handlers. `wind_get` normally reads the already published C view under a short
guard; it does not enter the native policy path. `wind_find` does enter it.
See [C window bindings](../../c/calypsi/aes-windows.c),
[UPDATE bindings](../../c/calypsi/aes.c), [AESLOCAL](../../lib/aes/aeslocal.act)
and [AESLOCKS](../../lib/aes/aeslocks.act).

```mermaid
sequenceDiagram
    participant A as Application Task
    participant U as Native UPDATE semaphore
    participant G as AESGATE
    participant P as Presenter Task
    A->>U: Acquire UPDATE
    U-->>A: Ownership established
    A->>U: wind_set acquires a recursive handler level
    A->>G: EnterTask for window metadata
    opt Presenter still owns the scene gate
        G->>P: Signal existing presenter wake
        Note over A: Sleep while retaining UPDATE
        P->>G: Offer after its current scene work
        G-->>A: Signal readiness hint
        A->>G: Retry and claim scene access
    end
    Note over A: Change frame metadata and invalidate damage
    A->>G: Publish routing and release scene
    A->>U: Release handler level
    Note over A: wind_set returns; outer UPDATE remains held
    Note over P: Frame painting waits for an eligible presenter operation
```

The second wait is reachable even after a successful uncontended UPDATE:
`AESSYSTEM.Run` calls `AESGATE.Reclaim` before key replay, input, controls,
painting, cache maintenance and scheduling decisions. It calls `Offer` only
after those decisions, dropping/reclaiming the gate around certain physical
and route operations. Presenter UPDATE scopes are narrower than this gate.
The [operation-scoped UPDATE work](../history/aes-magic-migration.md#ap1-presenter-update-scopes-follow-actual-work)
therefore did not remove this second admission boundary.

`EnterTask` publishes a stack-resident waiter under `Forbid`, signals the
presenter and waits on the caller's existing signal. `WakeCallers` detaches and
signals all waiters. Each must retry the availability flag; release does not
assign the next owner. This is distinct from native semaphore FIFO handoff.
The source inventory finds **54 external AESGATE call sites in 12 library
modules**, including eight `EnterTask` sites. These are static call sites, not
per-scroll execution counts.

For MGVIEW's ordinary copied scroll with no retained outline, its adapted
`set_shift` holds one explicit UPDATE across slider arrangement, hide,
visible-rectangle enumeration, copy, exposed-row drawing, show and END.
If both slider setters execute, the direct path contains five scene-admission
visits: two setters, hide, show and outer END. Ordinary BEGIN only starts the
journal; its `DrawingReady` check returns immediately without an outline.
Retries or retained effects can add visits. FIRST/NEXT read the C view;
VDI copying/drawing obtains physical access through the workstation grant.
The [MGVIEW adaptation](../../ports/magic/mgview/native.patch) already encloses
this operation; this audit proposes no viewer-source change.

## Shared-state ownership inventory

The table covers every current library module calling AESGATE and the main
scene/presenter dependencies reached from those callers. It does not certify
uninspected GEM extensions or arbitrary application callbacks.

| Access family and implementation | Current authority | Requirement when simplifying the flow |
| --- | --- | --- |
| Window/menu mutations in AESLOCAL → AESWINDOW / AESMENU | Native caller UPDATE level, then scene gate | Serialize live geometry, stacking, damage, frame and menu mutation through UPDATE. Route and physical continuations need explicit boundaries. |
| UPDATE/MCTRL entry and END in AESLOCKS / AESWINDOWSTATE | UPDATE; BEGIN journal reset is scene-free; MCTRL and outer painting END also enter the gate | Preserve routing overlay publication and consume journals before final native release. END does real Layers/cache work. |
| `wind_find` in AESWINDOW.Query | Gate only, without UPDATE | Supply a coherent query without automatically adding blocking UPDATE. Existing pointer-hit routing is not an equivalent query: it applies focus, menu and MCTRL policy. The read contract needs an explicit proposal. |
| C `wind_get` and visible rectangles | Published per-window view and short `Forbid`; FIRST/NEXT additionally require painting depth | Retain coherent publication and iteration lifetime. No new scene queue is needed at each FIRST/NEXT call. |
| Cursor policy in AESLOCAL / AESCURSOR | Gate, plus bounded guarded cursor/recipient updates; physical completion follows scene release | Separate copied mouse state from live scene construction. Check all reads before removing the gate: `Call` currently reads device depth before its guard. Physical completion must still use the existing display grant. |
| Ordinary key/button delivery in DESKINPUT / AESMOUSE / AESDEFER | Published route values, guarded endpoint holds and inbox publication while scene is unavailable | Preserve delivery independently of UPDATE. The normal scene-owned key path also calls native menu/gesture code and scans live windows; it cannot remain an unguarded scene reader after gate removal. |
| Route publication in AESSNAPSHOT and window views | Scene owner constructs shared `prepared` data; short guard swaps publication and endpoint holds | Serialize construction as well as the final copy. The current scratch is shared, and a reader's endpoint hold pins storage. Keep this lifetime mechanism when changing the publisher's owner. |
| Fresh native input, menus and gestures in DESKINPUT / DESKMENU / DESKDRAG | Scene gate plus operation-scoped presenter UPDATE; continuing captures/application outlines have retained authority | Scene lookups and readiness decisions also need ownership, not merely the eventual draw. Preserve the existing capture/outline cleanup paths. |
| Presenter paint and cache in DESKPAINT / DESKHOST / DESKCACHE / DESKMENUCACHE | Gate plus UPDATE; Layers tokens and DMA can retain the operation across turns | Keep transactions and physical lifetimes through completion. Metadata-only readiness/candidate scans currently also depend on the gate. A hint does not authorize scene access. |
| Copied moves and route retirement in AESCORE.Settle / DESKMOVE / AESROUTES | Caller retains UPDATE while presenter completes its admitted request under the gate | Do not make the presenter acquire the caller's semaphore. Complete the retained effect under its established operation authority, or redesign the operation to finish in its caller. |
| Registration, event settlement, endpoint close and detach in AESCORE / AESHOST | Presenter scene gate; local withdrawal first runs in the owning caller under UPDATE | Account for live client-table and publisher changes. A Task/image must remain retained through callbacks, messages and endpoint holds. These are not all drawing operations. |
| Console input-window association in CONSOLEVIEW.InputWindow | Gate only | Binding changes affect shared routing. Include this public non-AES facade in migration rather than auditing only `wind_set`. |
| Physical calls in CONSOLEBITMAP / DESKMENURENDER; input resource calls in DESKROUTES / AESWINDOW / AESROUTES | Suspend/leave the gate; retain effect identity; resume/reenter afterwards | Physical display arbitration and INPUT lifetimes are existing platform responsibilities. Eliminate gate reacquisition only after the surrounding scene continuation is assigned an owner. |

Relevant source: [presenter loop](../../lib/aes/aessystem.act),
[scene gate](../history/screnmgr-migration.md#sm3d-single-update-ownership-cutover),
[window state](../../lib/aes/aeswindowstate.act),
[input publication](../../lib/aes/aessnapshot.act),
[deferred delivery](../history/screnmgr-migration.md#sm3d-single-update-ownership-cutover),
[desktop input](../../lib/desktop/deskinput.act),
[request completion](../../lib/aes/aescore.act),
[console association](../../lib/console/consoleview.act),
[physical wrapper](../../lib/console/consolebitmap.act).

### Ownership ordering that a migration must preserve

The application path orders UPDATE before scene access. Presenter
`SystemBegin` uses a nonblocking native Attempt while already inside its scene
turn. Replacing it with a blocking Obtain in place creates a cycle: application
owns UPDATE and waits for the scene; presenter owns the scene and waits for
UPDATE. A second cycle would arise if AESCORE.Settle tried to obtain UPDATE to
finish a copied move for the caller that still owns it and awaits completion.

Physical completion can run while scene admission is unavailable:
`AESGATE.Reclaim` invokes `AESDEFER.Pump`, which services captured input and
physical fences without reading live Layers/window/cache records. Keep that
progress property. A Layers busy token preserves a drawing transaction;
it is not a substitute for Task-side serialization of all scene readers.

## Setter and renderer boundary

`AESWINDOW.Frame` returns immediately for an equal slider value. A changed
slider calls `DESKCACHE.Changed`, updates the public value, invalidates the
rail, calls `AESWINDOWSTATE.Geometry` / `Sync`, and returns. Geometry refresh
also invalidates the input-route publication. Gate release calls
`AESSNAPSHOT.Publish`, which can rebuild shared route data for changed slider
geometry. Name/info setters likewise invalidate damage for later painting.

`DESKPAINT.Pump` subsequently acquires presenter UPDATE and retains a Layers
paint token. It traverses frame fragments through CONSOLEBITMAP and
`DesktopFrame`. While an application owns an outer UPDATE, that fresh presenter
painting cannot acquire the resource. Consequently setter return is metadata
completion, rather than MagiC's completed frame draw.

Moving the existing physical call into the application would be unsafe:
CONSOLEBITMAP has a presenter-only shared packet, and `desktop-frame.c` has
shared `paint` and glyph scratch. The reusable platform already has delegated
display access and `GemDrawingBorrow`; the work is to adapt the renderer's
state and ordinary-call boundary, starting with the existing GEM4XE-derived
graphics. This audit does not justify another graphics worker, queue or
driver-specific kernel operation. Drawing limits remain unchanged.

See [frame rendering](../../lib/desktop/desktop-frame.c),
[console renderer dispatch](../../lib/console/console-bitmap.c),
[drawing interfaces](../../ports/gem4xe/adapter/gem-drawing.h),
[borrow implementation](../../ports/gem4xe/adapter/gem-vbxe.c), and the
[GEM4XE donor record](../../ports/gem4xe/inputs.json).

## Existing measurements and their limits

The saved [AP2 comparison](../history/aes-magic-migration.md#ap2-unchanged-apps-with-operation-scoped-presenter-ownership)
has matching MGVIEW/Counter APPs, PAL 8x/4 MiB configuration, pinned ROM and
emulator. The audit reads its JSON, without guest execution or rebuilding.

| Observation | Down | Up |
| --- | ---: | ---: |
| Failed UPDATE acquisition signal-site visits | 0 | 0 |
| Scene-wait signal-site visits during `set_shift` | 0 | 0 |
| Two setter calls, viewer CPU (ms) | 15.20 | 15.19 |
| Two setter calls, wall time (ms) | 24.23 | 24.38 |
| Two setter calls, off-Task time (ms) | 5.83 | 5.83 |
| Presenter CPU within already-owned UPDATE (ms) | 3.55 | 3.55 |
| Scene-release presenter posts within that interval | 1 | 1 |

These are two actions, not percentiles or a worst-case bound. Signal-site
counts establish that the selected contention branches were not reached in
those captures. The setter off-Task intervals are not therefore scene-queue
waits. The saved observer does not separately charge all nested setter helpers
or the scene gate's uncontended bookkeeping. It cannot assign the 15.2 ms to
one check, publication, renderer helper or synchronization primitive.
No speedup estimate is justified by this audit.

## Proposed next slices

The following is a proposal, not an implemented migration or approval to retain
a departure from MagiC.

1. Start with the smallest unnecessary gate dependency: the logical
   `graf_mouse` path. MagiC's mouse path has no window/UPDATE admission, and
   Exec already completes the device transition in the caller. Make its
   cursor/recipient accesses consistently use the existing bounded publication
   guard, including the depth read currently preceding it; preserve endpoint
   lifetime, completion and fault handling. Remove only this path's broad gate
   dependency. Use the small cursor/Counter case, not an application catalog.
2. Prepare the full live-scene ownership cutover from the inventory above.
   Assign ordinary UI scene accesses to UPDATE, keep independent delivery on
   copied publication, and state how query/registration and caller-owned
   continuations proceed. Bring any changed query/completion semantics to the
   user. Do not replace the broad gate with a second semaphore or a long
   Forbid, and do not remove it only from setters while other scene users remain.
3. Restore the MagiC simple-setter operation: update, clip and render the frame
   in caller context before releasing its handler UPDATE. Adapt renderer state
   and use the existing display grant; then retire the superseded deferred
   path. Keep cache/journal correctness and actual device limits explicit.

Each executable slice should use the smallest affected optimized ownership,
pixel and peer-progress check. A selected changed preemption/continuation
boundary warrants a focused deeper case; it does not warrant a release matrix.
Reuse frozen APPs for later matched scrolling only when a change affects that
path. Record actual stack and bank-zero costs when implementing.

## Validation and resource impact

Development documentation checks cover the pinned MagiC source hashes and
selected ranges, current Exec input hashes, the gate-call inventory, saved AP2
observations, and local documentation links. No application, native image,
demo, QED or release build is required for this source audit. No new emitted
behavior or hosted-system qualification is claimed.

This documentation slice changes **0 fixed, 0 root, 0 kernel, 0 idle and
0 per-public-Task reserved bank-zero bytes**, including guards, alignment and
unused capacity. Target code, upper-memory records, VRAM and public ABIs are
unchanged. Costs of proposed migration slices are not measured here.

[AESEVT]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S
[AESWIN]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESWIN.S
[AESMAIN]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S
