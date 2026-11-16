# Replace the combined presenter with SCRENMGR

[GEM plans](README.md) · [MagiC model](../../architecture/magic.md) ·
[UPDATE/scene audit](../../architecture/magic-update-scene-audit.md) ·
[Governing guidance](../../contributing/README.md#gem-architecture-guidance)

Direction adopted by the user on 2026-11-15: replace the combined presenter
with MagiC's `SCRENMGR` structure and flow. MagiC spells the name `SCRENMGR`;
this plan uses that spelling. SM0 records the decision and current responsibility
map. SM1a implements scene-independent caller cursor policy; SM1b paints changed
vertical slider positions in the caller; SM1c adds vertical slider sizes and
SM1d adds horizontal position/size. SM1e completes caller-side title/info painting.
SM3a implements the selected nonblocking raw hit query. SM3b/c implement
registration lifetimes and operation ownership; SM3d removes the scene gate.
SM4 is in progress; the blocking manager loop is not installed yet. Independent
input delivery is implemented through input.device. The
[execution record](../../history/screnmgr-migration.md) tracks delivered slices.
Current reference contracts continue to describe supported behavior until each
replacement slice lands.

## Target responsibilities

SCRENMGR is the AES screen-manager execution role: wait for interaction events,
obtain UPDATE for the resulting manager operation, process menu/window-frame
interaction, publish the appropriate messages and return to the main event
wait after releasing UPDATE. Interactive helpers retain the particular
MagiC-defined capture/MCTRL and nested wait semantics they require; the main
loop shape is not a blanket prohibition on waiting inside such helpers.

Ordinary AES/VDI work executes in its caller. A window setter owns UPDATE across
the relevant scene change and frame drawing. Applications repaint their work
areas in response to `WM_REDRAW`. The renderer and display driver supply shared
device execution below both callers and SCRENMGR. They do not require a general
presenter queue between a synchronous setter and its frame painting.

Ordinary input delivery must proceed independently of SCRENMGR waiting for
UPDATE. Console streams and models remain driver/backend responsibilities;
Terminal paints through ordinary application AES/VDI calls. Cache and device
continuations belong to their owning operations and resources. None of these
roles is implicitly assigned to SCRENMGR because the old presenter performed it.

The [pinned source model](../../architecture/magic.md#resident-screen-manager)
and [source audit](../../architecture/magic-update-scene-audit.md#magic-source-baseline)
establish the baseline: AESMAIN `screnmgr` / `scrmg_next`, AESEVT ordinary key
delivery and recursive UPDATE, AESWIN caller-context setters and frame drawing.
Exec retains its native Tasks, scheduler, IRQ/NMI protocol and device services.
GEM4XE remains the primary graphics implementation donor.

## Current responsibilities to relocate

| Current implementation | Target responsibility | Dependency to settle |
| --- | --- | --- |
| AESSYSTEM.Run, DESKMENU and DESKDRAG | SCRENMGR menu/frame interaction | Separate interaction events from ordinary recipient delivery; retain source-defined capture and MCTRL lifetimes. |
| AESLOCAL / AESWINDOW plus deferred DESKPAINT | Caller-context window operation and synchronous frame draw | Adapt frame renderer state and use existing delegated display access. The shared console packet cannot simply be called by another Task. |
| Retired AESGATE and turn-wide scene ownership | UPDATE for shared UI operations; short guards for copied publication | SM3a–c assign readers, mutation and lifetime owners; SM3d removes the gate and stack waiter queue together. |
| input.device, DESKINPUT and CONSOLEINPUT | Independent capture and copied application delivery | Implemented by IM0–IM8. Keep capture out of the manager. SM3d removes the obsolete AESDEFER scene-wait pump. |
| CONSOLEBACKEND and CONSOLEDRIVER.BackendTurn | Existing console stream/model backend | This Task already exists and has no scene or display lease. Preserve that separation; do not move console model work into SCRENMGR. |
| CONSOLEFRONT / loaded Terminal | Standalone console painting where applicable; normal GEM Terminal application in GUI mode | CONSOLEFRONT already declines GUI-mode painting. Preserve text/standalone startup and shutdown while removing graphical-loop coupling. |
| CONSOLEBITMAP / DISPLAY / VBXE completions | Physical operations, grants and completion owned by their resource users | Retire or independently service hardware work before a manager wait can block its owner. Preserve fault retention and device shutdown. |
| DESKCACHE, DESKMENUCACHE and DESKMOVE | Cache/copy lifetime inside the corresponding AES operation | Finish client-owned continuations without acquiring the client's semaphore from a different Task; preserve existing pixel/cached-move behavior until explicitly migrated. |

Current source seams: [system loop](../../../lib/aes/aessystem.act),
[console resident](../../../lib/console/consoledriver.act),
[console backend](../../../lib/console/consolebackend.act),
[keyboard consumer](../../../lib/console/consoleinput.act),
[pointer consumer](../../../lib/desktop/deskinput.act),
[UPDATE scopes](../../../lib/aes/aeslocks.act),
[frame renderer](../../../lib/desktop/desktop-frame.c) and
[drawing interfaces](../../../ports/gem4xe/adapter/gem-drawing.h).

## Execution-context decision before the blocking loop

The selected frontend still calls AESSYSTEM.Run, but it no longer owns physical
input. The [input.device migration](../input-device-migration-plan.md) moves
Acquire/Take/Release into the generic device Task. Bounded AES handlers resolve
held snapshots and publish application inboxes without UPDATE, scene access or
physical drawing. Copied manager interactions wait for the frontend's ownership;
their window identities/epochs and endpoint holds survive that wait.
CONSOLEBACKEND remains a separate stream/model Task.

The implementation uses three service contexts: input, backend and the selected
text/GEM frontend. It occupies one more ordinary Task pool than the previous
combined two-service arrangement, within the existing eight-pool map. The GUI
frontend keeps its large stack. This delivers SM2's input-service portion; it
does not install the final blocking SCRENMGR loop or complete SM3/SM4's scene
reader, caller drawing and physical-retirement dependencies. The chosen Task
placement is an explicit Exec adaptation of MagiC's scheduler-side input role.

The [execution-placement comparison](screnmgr-execution-map.md) records this
selection and retains the earlier alternatives. Bring actual departures or
newly required platform services to the user with source, costs and alternatives.
Do not add a private GUI deferred-work service or change the scheduler to
conceal a dependency. Current measured resources are recorded in the
[input migration record](../../history/input-device-migration.md).

## Migration slices

Commit each executable slice separately. This plan assigns dependencies rather
than authorizing a second implementation or compatibility profile.

### SM0 — adopted target and responsibility map

Record the replacement direction in contributor guidance, the architecture
mapping, design/index and roadmap. Preserve the completed audit and measurement
records. Distinguish the existing combined loop from the selected target.

Status: documented by this slice. Validation is source/content/link checking;
no executable behavior is changed.

### SM1 — caller operations stop depending on presenter painting

Deliver small executable sub-slices. Start with the audit's logical cursor path:
use its existing bounded cursor/publication guards consistently and retain its
caller-side device completion, removing only its unnecessary broad scene entry.

SM1a implements this cursor sub-slice. Client identity/binding/endpoint publication
now uses one existing registration guard, and cursor depth is read inside its
transition guard. Cursor calls no longer enter/release AESGATE or publish route
geometry merely to update mouse state. Physical completion and fault handling
retain their existing caller/device flow. See the
[development record](../../history/screnmgr-migration.md#sm1a-cursor-policy-without-scene-admission).

SM1b implements `WF_VSLIDE` with a caller-owned packet, grant-protected renderer
state and synchronous visible-rail painting. Manager completion preserves client
repaint obligations; cold AES-only access reuses public display delegation. See
the [development record](../../history/screnmgr-migration.md#sm1b-synchronous-vertical-slider-position).

SM1c extends the same path to `WF_VSLSIZE`, following MagiC's shared vertical
position/size handler and frame draw. Cold admission, equal-value return and
manager completion use the existing SM1b services without another renderer or
resource. See the [development record](../../history/screnmgr-migration.md#sm1c-synchronous-vertical-slider-size).

SM1d adds `WF_HSLIDE` and `WF_HSLSIZE` to the same caller operation, using the
existing short-strip renderer under the delegated grant. Text setters remain
for the next sub-slice. See the
[development record](../../history/screnmgr-migration.md#sm1d-synchronous-horizontal-sliders).

#### SM1e — synchronous title and info setters

Implemented: see the [SM1e execution record](../../history/screnmgr-migration.md#sm1e-synchronous-title-and-info).
The slice resumes the existing frame changes through their common path. The pinned AESWIN `ws_name` / `ws_info` / `ws_naminf` (2417–2461) checks the
matching NAME/INFO bit, updates stored text/frame state, draws an open linked
frame object and returns through `ws_endsw` / `update_0`. This confirms failure
for a missing component. An iconified title remains drawable; unlinked info
changes retain metadata for later restoration. Keep Exec's existing bounded
owned text buffers and equal-value/cold-admission conventions.

Use the existing caller packet, delegated grant and shared GEM4XE frame raster.
A changed visible component completes before UPDATE release; hidden/unlinked
components require no physical admission. Preserve menu-title publication,
cache/journal obligations, clipped completion and display-failure retention.
Remove the corresponding deferred frame dependency once that boundary passes.

Check the focused optimized frame fixture: ordinary/PB calls, equal values,
missing components, hidden/iconified state, held UPDATE, clipping, cold/warm
admission and teardown. Keep the caller parked while checking pixels so manager
painting cannot satisfy completion. Run host checks, record stack/resource
costs and commit before starting the next ownership family. No QED/catalog/demo
or release matrix.

Continue with the remaining frame fields in small sub-slices. Preserve explicit
call state and the existing display grant: equal-value return; changed-value
mutation, visible clipping and frame painting before handler UPDATE release and
return. Reuse the graphics implementations and donor provenance; keep
journal/cache and failure behavior coherent and remove superseded deferred routes.

The scene gate may remain as the current serialization mechanism during these
intermediate slices. That is a staged dependency, not the target ownership model.
Do not remove it selectively from a scene mutator while live readers still
depend on it. Use the smallest cursor or slider/Counter pixel and lifetime case.

### SM2 — establish independent input and device progress

Follow the [input.device migration plan](../input-device-migration-plan.md):
IM1–IM3 establish the public service/capture, IM4 converts standard Atari text,
and IM5–IM6 extract AES delivery and switch GUI source ownership. Resolve the
selected frontend placement described above. Preserve captured route
identities, endpoint holds and durable wake rules. Application input delivery
does not acquire UPDATE. Screen-manager interaction receives its own event
readiness. Console model/stream processing stays in CONSOLEBACKEND.

Input-service cutover alone does not complete SM3/SM4. Retain the current
manager loop only until their scene-reader and caller-drawing dependencies
permit its replacement; no scene work, drawing or UPDATE wait belongs inside
the generic input Task.

Verify one application holding UPDATE while keys/buttons reach application
inboxes, console I/O completes and physical completions retire as required.
Measure actual stack use and pool occupancy. Any additional platform service
must first be reported and discussed under the governing guidance.

### SM3 — shared UI state follows UPDATE ownership

Start only after the SM1 frame operation boundary is complete; independent
capture is already supplied by IM0–IM8. Keep the old scene gate until the final
cutover, rather than removing it from selected callers while readers still rely
on it. Use the audit as an inventory, updating entries for the installed input
service. Commit executable prerequisites separately.

1. **SM3a: queries and publication contract.** Inspect MagiC `_wind_get` and
   `_wind_find` alongside current `wind_get`, `wind_find`, routing and window-view
   publishers. Specify coherent nonblocking reads and serialization of snapshot
   construction. Pointer routing cannot stand in for `wind_find`: it applies
   focus/menu/MCTRL policy. Bring any changed query semantics or architectural
   departure to the user before implementation; no automatic UPDATE Obtain. The
   [design note](gem-first-gui-design.md#sm3a-selected-read-boundary)
   records the user's 2026-11-16 selection of committed raw hit snapshots, plus
   the live-commit alternative and costs. Implement that selected query boundary
   as the first executable SM3 prerequisite, retaining the scene gate elsewhere.
   Status: implemented; see the [SM3a record](../../history/screnmgr-migration.md#sm3a-nonblocking-committed-window-hits).
2. **SM3b: registration and retirement.** Give client-table publication, event
   settlement, input-window association and endpoint close a complete owner and
   lifetime boundary. Preserve input callback/queued-manager holds. Use short
   publication guards for copied state; never draw or wait under Forbid.
   Status: implemented; see the [SM3b record](../../history/screnmgr-migration.md#sm3b-registration-publication-and-retirement-lifetimes).
3. **SM3c: UPDATE-owned mutation and completion.** Assign every live window,
   menu, Layers, paint-journal and cache operation to UPDATE, including readiness
   scans and END. A retained caller effect must complete under that operation's
   authority or in its caller; the manager cannot Obtain a foreign owner's
   semaphore to reply to it. Resolve this before adding blocking manager waits.
   Status: implemented; see the [SM3c record](../../history/screnmgr-migration.md#sm3c-update-owned-scene-work-and-caller-continuations).
4. **SM3d: whole-inventory cutover.** Remove the scene waiter queue and turn-wide
   scene claim together only after all entry/read/continuation families above
   have owners. Retain the one current implementation and update private-layout
   fixtures/references. Check competing setter/query, one retained effect,
   independent input, normal preemption and clean shutdown.
   Status: implemented; see the [SM3d record](../../history/screnmgr-migration.md#sm3d-single-update-ownership-cutover).

No replacement scene semaphore, long Forbid, GUI-specific deferred-work service
or scheduler change is implied. Report a missing general Exec service at its
actual dependency rather than bypassing it.

### SM4 — install the SCRENMGR event loop and retire the combined loop

Run the screen-manager role in the selected GUI frontend context; retain its
existing large pool and the separate input/backend Tasks. Its main loop
waits for interaction events, acquires UPDATE for actual manager work, invokes
the shared AES window/menu helpers, releases at the source-defined boundary
and waits again. Application drawing and synchronous setter completion do not
require a manager turn. Input/device progress uses the SM2 arrangement.

First account for every remaining paint/cache/console/fence responsibility:
caller-owned work stays with its operation, manager interaction stays with
SCRENMGR, and physical completion stays with its resource owner. No active DMA
or grant borrow may need an unavailable manager turn to retire.

Remove AESSYSTEM's combined paint/cache/console scheduling loop and its obsolete
callback interface once remaining responsibilities have their intended owners.
Update module/task names with this responsibility change. Preserve cooperative
startup, failure retention and shutdown, plus the separate standalone console
path. Do not retain an alternate presenter implementation.

#### SM4 ownership audit and executable order

MagiC AESMAIN `screnmgr` / `scrmg_mainloop` (4235–4282) waits in `_evnt_multi`
and then calls `update_1`; `scrmg_next` (4453–4455) releases with `update_0`.
Ordinary application AES and workstation admission do not require SCRENMGR to
service a request. Exec cannot install the blocking Obtain while retaining its
current owner-side service dependencies.

| Remaining responsibility | Current execution dependency | Required owner/boundary |
| --- | --- | --- |
| Background window capture/patch and popup capture | DESKHOST.Cache starts DMA and leaves its token/pin for a later Controls turn. | SM4a: retire the started copy and token inside that cache operation's UPDATE scope, using the existing device completion/watchdog signal. |
| Ordinary frame/background exposure and cache restore | DESKPAINT owns a shared packet and retained paint token across frontend turns. | Finish under the originating caller/manager operation; send client `WM_REDRAW` for application work. Adapt the shared GEM4XE renderer to caller packets before removing its executor. |
| Menu save/restore/replacement | DESKMENUCACHE and DESKMENU keep physical and interaction state. | Keep the source-defined manager operation and finish its hardware work before blocking on a different resource. |
| Console painting | CONSOLEFRONT already declines GEM mode; loaded Terminal paints normally. | Preserve the standalone loop. Remove GEM's no-op console render budget after native presentation controls have their owner. |
| Native console presentation controls | CONSOLECONTROL.Submit waits for the display-owner Task. | Account for existing erase/cursor controls before the frontend can block; retain driver lifecycle policy. |
| AES registration/init/final detach/profile RPC | AESCORE.Dispatch is still executed by the frontend. | Move ordinary library operations to their caller, with existing registration/publication guards. Retire the transport dependency coherently with its callers and fixtures. |
| Cold display grants | AES_OP_DISPLAY RPC calls DISPLAY.Delegate in the lifetime owner. | Resolve general display-service admission below. A caller can already own UPDATE when it opens VDI or needs its first frame grant. |
| Copied application input and endpoint wakes | input.device and guarded copied publication. | Preserve independent delivery; no AES request server or drawing is added to input.device. |

**SM4a** is an executable prerequisite, not the completed manager-loop migration.
It changes only cache-operation completion. Background snapshot pixels and pins
must be terminal before Cache returns, normal preemption remains enabled, and
unsafe hardware keeps the existing reset-required retention. Check optimized
cache pixels/pins and normal cleanup; no public record or bank-zero reservation
change is needed.

#### SM4 display-admission decision

`DISPLAY.Valid` requires the lifetime owner's current Task; Delegate uses it.
Both `c/calypsi/aes-windows.c:display_ensure` and `c/calypsi/vdi.c:open_virtual`
therefore submit AES_OP_DISPLAY to that Task. A queued manager interaction can
make it wait on UPDATE while an existing UPDATE owner issues one of these calls:
the caller waits for its RPC, and the manager waits for that caller. Draining the
port before Obtain cannot close the race with later admission. Existing native
semaphores and signals cannot change the display API's caller contract.

Selected on 2026-11-16: general driver grant admission callable by the requesting
borrower while the retained display lifetime owner is asleep. Admission uses the
existing active generation, eight-slot table, Task retention and short driver
guard. It opens no hardware access; Enter/Leave retain their FIFO and fence rules.
Session shutdown still requires all grants to retire. The existing caller-owned
32-byte grant and signal are reused; no new Task, bank-zero reservation, GUI
queue or kernel operation is proposed. The public driver contract and its
machine-readable bindings must describe the selected admission rule.

The user selected direct borrower-side admission, then reaffirmed MagiC's
structure and flow as the default. This follows the inspected VDI DISP
`vdi_entry` / `vdi_disp` (40–54) and CONTROL `v_opnvwk` (785–806): dispatch,
allocate/init the workstation, increment the driver use count, return in the
application's call. SCRENMGR is absent from that call path. Exec retains its own
display generation, Task lease and physical FIFO/fence implementation below it.
No additional display-service Task or nonblocking substitute manager loop is
selected. Routine mechanics within this selected model need no new decision.

Continue in executable commits:

1. **SM4a — terminal background cache operation.** Finish and check the current
   cache prerequisite above, then commit its production code and focused evidence.
   Status: implemented; see the [SM4a record](../../history/screnmgr-migration.md#sm4a-background-cache-operation-completion).
2. **SM4b — direct general display admission.** Generalize the one public
   Delegate operation to ordinary Task callers; retain live target Tasks, existing
   grants, capacity and generation rules. Guard admission and closing-state
   publication together. Call it directly from cold AES frame/VDI setup, remove
   AES_OP_DISPLAY and its request-server path, and update current generated
   bindings/contracts and affected fixtures. Check admission while the lifetime
   owner sleeps, shutdown exclusion, capacity, physical FIFO and normal cleanup.
   Status: implemented; see the [SM4b record](../../history/screnmgr-migration.md#sm4b-direct-borrower-side-display-admission).
3. **SM4c — caller registration and ordinary AES service.** Move initialization,
   final registration retirement and profile calls out of manager RPC. Preserve
   endpoint/client publication and queued input holds; retire obsolete transport
   dispatch and update bindings/callers together. Check a caller operation while
   the manager waits on its UPDATE, independent events and cooperative exit.
   Status: implemented; see the [SM4c record](../../history/screnmgr-migration.md#sm4c-caller-registration-and-final-detach).
4. **SM4d — operation-owned exposure and cache work.** Adapt shared GEM4XE
   painting to caller-owned packets and grants; finish frame/background exposure
   and cache restoration under the originating AES/manager operation. Application
   work receives WM_REDRAW. Move cache maintenance to its operation boundary;
   preserve current pixels, pins, cached moves and failure retention.
5. **SM4e — manager interaction and lifecycle cutover.** Account for menu
   save/restore, native console controls, cursor/device completion and shutdown;
   remove GEM's no-op console-render callbacks while preserving the standalone
   console loop. Install and name the selected frontend SCRENMGR: event wait,
   blocking UPDATE for actual interaction, shared helpers, release and wait.
   Remove the combined scheduling loop and obsolete helpers, with no alternate
   presenter implementation, Task addition or new scheduler service.

Use minimal optimized emitted checks for each changed boundary and the small
ABI probes when a layout/bridge changes. Commit passing slices separately. The
SM5 combined check remains a separate acceptance step; no broad application or
release matrix is implied.

### SM5 — minimal combined development check

Use Counter and a tiny widget/window case for interaction, caller painting,
UPDATE contention, independent input and close/retirement. Add one existing
MGVIEW/Counter scroll observation when the changed caller path is integrated;
reuse matching APPs when ABI and imports permit. Separate CPU, off-Task time,
ownership waits and physical completion; two actions do not establish a latency
distribution. No performance gain is assumed from renaming or repartitioning.

Use optimized emitted code for affected behavior and a deeper focused boundary
case when ownership/interrupt changes require it. No routine QED, application
catalog, demo refresh or release matrix is part of these slices. A later
explicit demo refresh still follows the repository's OF816 packaging rules.

## Resources and open costs

SM0 changes **0 fixed, 0 root, 0 kernel, 0 idle and 0 per-public-Task reserved
bank-zero bytes**, including guards, alignment and unused reserved capacity.
Target code, upper-memory records, public ABIs and VRAM are unchanged.

Future Task placement is not costed as free: an existing reserved pool can have
zero reservation growth while consuming simultaneous execution capacity. The
[Task capacity contract](../../architecture/task-capacity.md) records ordinary
1,312-byte and large 2,560-byte stacks, each with a 256-byte DP and two 16-byte
outer guards. Those occupy 1,600 or 2,848 reserved bytes per pool; selected stack
headroom, startup needs and measured peaks must determine the actual placement.
No pool enlargement, additional Task, new service or stack saving is claimed
by this documentation slice.
