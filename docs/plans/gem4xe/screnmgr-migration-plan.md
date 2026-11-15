# Replace the combined presenter with SCRENMGR

[GEM plans](README.md) · [MagiC model](../../architecture/magic.md) ·
[UPDATE/scene audit](../../architecture/magic-update-scene-audit.md) ·
[Governing guidance](../../contributing/README.md#gem-architecture-guidance)

Direction adopted by the user on 2026-11-15: replace the combined presenter
with MagiC's `SCRENMGR` structure and flow. MagiC spells the name `SCRENMGR`;
this plan uses that spelling. SM0 records the decision and current responsibility
map. Executable migration is pending. Current reference contracts continue to
describe supported behavior until each replacement slice lands.

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
| AESGATE and turn-wide scene ownership | UPDATE for shared UI operations; short guards for copied publication | Cover every reader/mutator from the audit, including queries, registration, input-window bindings and caller-owned continuations, before removing the old gate. |
| DESKINPUT, CONSOLEINPUT and AESDEFER | Input capture consumption and application event delivery, independent of blocked SCRENMGR | Resolve the consuming execution context and lease lifetime. Keeping a helper in the same blocked Task does not provide independent progress. |
| CONSOLEBACKEND and CONSOLEDRIVER.BackendTurn | Existing console stream/model backend | This Task already exists and has no scene or display lease. Preserve that separation; do not move console model work into SCRENMGR. |
| CONSOLEFRONT / loaded Terminal | Standalone console painting where applicable; normal GEM Terminal application in GUI mode | CONSOLEFRONT already declines GUI-mode painting. Preserve text/standalone startup and shutdown while removing graphical-loop coupling. |
| CONSOLEBITMAP / DISPLAY / VBXE completions | Physical operations, grants and completion owned by their resource users | Retire or independently service hardware work before a manager wait can block its owner. Preserve fault retention and device shutdown. |
| DESKCACHE, DESKMENUCACHE and DESKMOVE | Cache/copy lifetime inside the corresponding AES operation | Finish client-owned continuations without acquiring the client's semaphore from a different Task; preserve existing pixel/cached-move behavior until explicitly migrated. |

Current source seams: [system loop](../../../lib/aes/aessystem.act),
[console resident](../../../lib/console/consoledriver.act),
[console backend](../../../lib/console/consolebackend.act),
[keyboard consumer](../../../lib/console/consoleinput.act),
[pointer consumer](../../../lib/desktop/deskinput.act),
[deferred pump](../../../lib/aes/aesdefer.act),
[frame renderer](../../../lib/desktop/desktop-frame.c) and
[drawing interfaces](../../../ports/gem4xe/adapter/gem-drawing.h).

## Execution-context decision before the blocking loop

Today the console resident's Worker calls AESSYSTEM.Run. That same Task acquired
the keyboard and pointer input leases and drains their events. AESDEFER runs
on its stack while scene admission is unavailable. CONSOLEBACKEND is a separate
Task, but does not own those capture leases.

With an unconditional blocking UPDATE Obtain in that Task, the independent
input pump would stop with it. INPUT permits Take only in the acquiring Task;
an arbitrary second consumer is not an available shortcut. Likewise, moving
capture decoding or AES callbacks into IRQ/NMI is outside the current platform
contract. See [INPUT ownership](../../reference/input.md#calls-and-ownership).

Before installing the final SCRENMGR wait loop, prepare a concrete execution
map using existing public Task/input/display services. Account for who acquires,
consumes and releases each lease, who delivers application events, and who
retires physical completion while SCRENMGR is blocked. Compare reuse of existing
contexts with any additional ordinary Task, including simultaneous application
capacity, stack/DP occupancy and shutdown ordering. A combined nonblocking loop
that continues all presenter work is not accepted as SCRENMGR merely by renaming it.

The user has selected the replacement architecture. Its execution placement is
not fixed by this note. Bring actual departures or newly required platform
services to the user with source, costs and alternatives. Do not add a private
GUI deferred-work service or change the scheduler to conceal the dependency.

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

Then adapt the existing frame renderer for ordinary caller use with explicit
call state and the existing display grant. Start with one simple slider setter:
equal-value return; changed-value mutation, visible clipping and frame painting
before its handler UPDATE release and return. Reuse the graphics implementations
and donor provenance; do not call the presenter-only packet from another Task.
Keep journal/cache and failure behavior coherent. Migrate the other frame fields
in further small sub-slices and remove their superseded deferred routes.

The scene gate may remain as the current serialization mechanism during these
intermediate slices. That is a staged dependency, not the target ownership model.
Do not remove it selectively from a scene mutator while live readers still
depend on it. Use the smallest cursor or slider/Counter pixel and lifetime case.

### SM2 — establish independent input and device progress

Resolve the execution-context map above before code depends on it. Implement
the agreed public-Task/lease arrangement, preserving captured route identities,
endpoint holds and durable wake rules. Application input delivery does not
acquire UPDATE. Screen-manager interaction receives its own event readiness.
Console model/stream processing stays in CONSOLEBACKEND.

Verify one application holding UPDATE while keys/buttons reach application
inboxes, console I/O completes and physical completions retire as required.
Measure actual stack use and pool occupancy. Any additional platform service
must first be reported and discussed under the governing guidance.

### SM3 — shared UI state follows UPDATE ownership

Use the audit's complete ownership inventory to move live scene operations
under UPDATE and retain short copied-publication guards. Resolve the coherent
query and registration contracts explicitly; blindly making `wind_find` block
on UPDATE changes the inspected MagiC query path. Preserve the return and
retirement of already admitted client-owned effects without a foreign Obtain.

Remove the old scene waiter queue and turn-wide scene claim only after every
affected entry has an owner. Use a focused preemption/ownership case with a
competing setter/query, one retained effect and normal shutdown. Update callers,
private-layout fixtures and current references together.

### SM4 — install the SCRENMGR event loop and retire the combined loop

Run the screen-manager role on the agreed execution context. Its main loop
waits for interaction events, acquires UPDATE for actual manager work, invokes
the shared AES window/menu helpers, releases at the source-defined boundary
and waits again. Application drawing and synchronous setter completion do not
require a manager turn. Input/device progress uses the SM2 arrangement.

Remove AESSYSTEM's combined paint/cache/console scheduling loop and its obsolete
callback interface once remaining responsibilities have their intended owners.
Update module/task names with this responsibility change. Preserve cooperative
startup, failure retention and shutdown, plus the separate standalone console
path. Do not retain an alternate presenter implementation.

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
