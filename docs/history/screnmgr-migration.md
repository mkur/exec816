# SCRENMGR migration

[History](README.md) · [Migration plan](../plans/gem4xe/screnmgr-migration-plan.md) ·
[Current AES contract](../reference/aes.md) ·
[Cursor evidence](../development/screnmgr-sm1-cursor.json) ·
[Vertical slider evidence](../development/screnmgr-sm1-vslide.json)

## SM1a: cursor policy without scene admission

The caller cursor handler no longer acquires or releases AESGATE. It uses
published input routing and bounded Task guards for recipient selection,
application hide/form state and the shared device target. Device depth is read
inside that guard. Registration now publishes client identity, binding and
endpoint within its existing guard so cursor readers cannot observe a partially
published client after losing the scene gate's exclusion.

The existing physical-completion bridge runs in the caller after the transition
guard is released. Display arbitration, fallback continuation, revision wakeups
and fault handling retain their existing responsibilities. A physical operation
can still wait; this slice removes scene admission from cursor policy, not
device arbitration. No viewer/application source or public ABI changes.

This follows MagiC's mouse path, which does not enter the window setter's UPDATE
path. See the pinned [source audit](../architecture/magic-update-scene-audit.md#magic-source-baseline)
and [mouse cross-check](gem-mouse-magic-review.md). The combined presenter and
other scene users still exist. Frame setters and independent manager/input
execution remain later migration work.

### Development scope

The small emitted scene-owner probe runs the production local cursor dispatcher
while a competing native Task owns the scene and computes without yielding.
Normal preemption returns control to the caller. It checks nested hide/show,
form/save state, raw device hide/show, unsupported selectors, preserved outer
Forbid nesting, unchanged scene ownership and an empty scene-waiter list.
Only physical completion is substituted; the probe also requires that callback
to execute in the calling Task. A separate existing mouse/Counter integration
checks actual device pixels, recipient/history behavior and retirement.

Development checks pass: 65 scene-owner assertions and 431 mouse/Counter
assertions, including 147 exact pixel comparisons. Both use the clean pinned
compiler in its optimized mode and the pinned PAL 8x/4 MiB ROM/emulator profile.
The real-device fixture returns status zero with normal ownership restoration
and intact guards. Its root, presenter and kernel stack peaks are 845, 730 and
287 bytes respectively, inside their existing reservations. Host checks pass
718 tests, with five historical skips. Documentation links are checked separately.
The evidence retains image/compiler hashes, runtime context and per-Task stack
measurements. No raw matrix,
QED, application catalog, demo refresh or release qualification is included.
These checks make no scrolling-latency or hosted-system qualification claim.

Fixture preparation initially omitted generated console declarations, then a
test routine's name collided with its local mouse pointer. Those attempts
stopped at compilation and are excluded from executable evidence. The final
scene probe explicitly yields to its computing peer before checking progress.

### Resource impact

Production gains no Task, signal, record field or global storage. Public wire,
request, client and service layouts are unchanged. Reserved bank-zero deltas are
**0 fixed, 0 root, 0 kernel, 0 idle and 0 per public Task**, including guards,
alignment and unused reserved capacity. No stack/DP reservation, upper-memory
record or VRAM reservation changes. Measured stack use belongs to the selected
fixtures and is retained in the evidence.

## SM1b: synchronous vertical slider position

A changed `WF_VSLIDE` now completes visible vertical-rail painting in the caller
before returning, including inside an outer application UPDATE. Equal values
return without physical access. Hidden/iconified changes retain metadata/damage
for later exposure. Other frame fields remain deferred for subsequent small
slices. The current scene gate remains in use; this is not the final SCRENMGR
loop or input execution map.

This follows the pinned MagiC AESWIN `ws_slend`: compare the previous value,
change frame state, draw the open window's scroll object and finally release
UPDATE (lines 2768–2794). Exec's existing UPDATE pins the native window, title and
frame-visible region while the scene gate is released around device access.
Frame clipping uses the layer's native visible region, rather than the C view's
work-only rectangles. No application changes are required.

The existing console-format packet is local to the admitted native call.
Renderer callbacks receive that packet explicitly; they bind shared packet and
glyph scratch only after obtaining physical access and end the borrow before
release. Both presenter and caller use the same frame raster and widget strip.
The delegated caller uses the existing compact side renderer, retaining its
16-pixel width and 240-row limits. Successful visible clips retire only manager
damage through `LAYERS.Repaired`; client repaint epochs and outstanding work
remain intact. A failed physical draw leaves its damage outstanding. Subtraction
capacity overflow conservatively retains existing damage.

If a public VDI workstation is open, drawing reuses its grant. Otherwise a
visible changed setter establishes one 32-byte upper-heap grant through the
existing display-delegation request. The native handler checks authoritative
visibility under UPDATE before mutation; missing access returns to the library
for cold admission outside the handler scope and a fresh attempt. This avoids a
restore racing a C-side visibility check. It uses the application's existing
reply signal. This cold resource setup is one
RPC; warm setters have none. Public workstation opening closes the standalone
grant before establishing its own. Application exit closes either form, retaining
storage/identity if close fails. No new Exec service, Task, signal, wire field or
VRAM allocation is introduced.

The new native frame packet occupies 82 bytes within the caller's existing stack
reservation. One upper-memory renderer binding holds its three-byte entry
address. A context without a public workstation can retain the 32-byte grant
payload, plus the allocator's normal overhead, until workstation opening or
application exit. Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel,
0 idle and 0 per public Task**, including guards, alignment and unused reserved
capacity. Stack/DP reservations are unchanged.

### Development scope

The optimized frame fixture passes 198 application assertions and five native
assertions across 34 pixel checkpoints. Six vertical-position checkpoints verify
completed frame pixels while the caller remains parked, including ordinary/PB,
equal-value, held-UPDATE, occluded and peer cases. The cold visible changes each
use one delegation RPC and two handler attempts; warm changes and equal values
use no RPC. Extra checks cover a cold equal setter, a supported hidden setter,
public-workstation reuse, close/recreation and complete heap reclamation on exit.

The image is sampled after two PAL scanout frames, following the existing frame
atlas fixture. Held cases retain application UPDATE throughout that settling
interval, so presenter painting cannot supply their expected pixels. This delay
belongs to the observer, not the setter. The initial immediate scanout comparison
sampled an old frame; it is excluded from the passing evidence. The initial new
layer assertion also incorrectly assumed aborting an external handoff would not
restore manager damage; the corrected check requires that coverage again.

The optimized Layers run passes 8,948 checks, including manager completion,
client-obligation preservation, active-token rejection and abort recovery. Host
checks pass 718 tests with five historical skips. Frame guards and ownership
restoration pass; root, peer, presenter and kernel stack peaks are 1,063, 800,
736 and 283 bytes within existing reservations. The native frame routine's
local stack peak is 144 bytes, including its packet and temporary state.

The [evidence](../development/screnmgr-sm1-vslide.json) retains exact source,
compiler/image, ROM/emulator, scanout and stack records. The clean pinned Action!
compiler and Calypsi 5.18 run optimized on the pinned PAL profile. This is a
focused development check; no raw matrix, QED/catalog/demo build, release
qualification or scrolling-speed claim is included. Next SM1 work migrates
remaining frame fields using the same renderer and resource boundary.


## SM1c: synchronous vertical slider size

Changed `WF_VSLSIZE` now uses the same native vertical-frame operation as
`WF_VSLIDE`, completing visible rail painting before returning or releasing the
handler UPDATE. MagiC routes both fields through `ws_sl_verti` and `ws_slend`
(AESWIN lines 2750–2794): change the selected value, update the frame, draw the
open vertical scroll object, then release UPDATE. This slice extends that shared
path without changing the renderer, scene admission, physical grant lifetime,
client paint journal or cache policy.

The existing vertical/horizontal selection now controls cold admission for both
vertical fields. Missing access is detected under UPDATE before mutation;
the C binding delegates through the existing service outside the handler scope
and retries. Equal, hidden and unsupported size setters do not establish access.
Open workstations supply their existing grant. Successful painted clips retire
only manager damage; failed or incomplete coverage remains outstanding. The
remaining horizontal slider and text setters still use deferred painting.

The focused fixture starts the root application's visible drawing with a size
change and the peer's with a position change. It covers ordinary/PB calls,
unchanged values, invalid and unsupported size requests, zero-size thumb geometry,
occlusion, held/unheld UPDATE, workstation reuse, grant recreation after close
and complete heap reclamation. Scanout settles for two PAL frames while the
caller remains parked, retaining any outer UPDATE. This uses the existing
observer and adds no delay inside the setter.

Production adds no storage, Task, signal, public ABI field or VRAM reservation.
Reserved bank-zero changes are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per public
Task**, including guards, alignment and unused reserved capacity. The prior
packet, renderer scratch and optional grant storage are reused unchanged.

The optimized [development run](../development/screnmgr-sm1-vslsize.json) passes
202 application assertions and five native assertions, 34 frame pixel checkpoints
and 12 synchronous vertical-slider checkpoints, split equally between position
and size. Size-first and position-first cold admission each use one RPC and two
handler attempts; warm and equal calls use no RPC. Host checks pass 718 tests
with five historical skips. Guards and ownership restoration pass. Root, peer,
presenter and kernel stack peaks are 1,074, 824, 736 and 285 bytes, within the
existing reservations. The complete reserved bank-zero budget matches SM1b.

Only the focused frame fixture and host checks ran. Unchanged renderer and layer
completion sources were checked against the SM1b evidence; its separate Layers
suite was not repeated. No raw matrix, QED/catalog/demo build, release
qualification or scrolling-speed claim is included. Next SM1 work is the
horizontal slider fields, retaining MagiC's shared position/size flow.


## SM1d: synchronous horizontal sliders

`WF_HSLIDE` and `WF_HSLSIZE` now mutate and paint their visible bottom rail in
the caller before handler UPDATE release. Both reuse the common MagiC
`ws_sl_hori` / `ws_slend` flow, the existing native packet and manager-damage
completion. The same cold-admission check covers all four slider fields.
Equal, hidden and unsupported operations retain their existing boundaries.

Delegated frame drawing now selects the existing compact tall-side or short
widget-strip path from clip geometry. The trusted frame renderer completes
short-strip continuations before releasing its grant; no scratch or packet
borrow escapes physical ownership. Pixel/row and glyph-chunk limits are
unchanged. This also supplies the existing renderer seam needed for text
setters, without another raster or Task.

The fixture exercises both horizontal fields in a window with both rails,
arrows and a sizer, plus the existing peer vertical window. Its independent
raster uses both cached thumb geometries and kind-derived work borders. The
observer obtains field IDs from the shared AES ABI. An initial observer edit
used incorrect numeric horizontal IDs and was corrected before accepting the
run; the C image is reused only after its source/header hashes are verified.

Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per
public Task**, including guards, alignment and unused capacity. No data-record,
Task, signal, heap payload, VRAM allocation or public ABI layout is added.


The optimized [development record](../development/screnmgr-sm1-horizontal.json)
passes 202 application assertions, five native assertions, 34 frame pixel
checkpoints and 12 synchronous slider checkpoints. Host checks pass 718 tests
with five historical skips. Guards and stack floors pass; bank-zero reservations
match SM1c. Only the focused frame fixture and host checks ran. No QED, demo,
raw matrix or release/performance qualification is included.


## SM1e: synchronous title and info

Changed `WF_NAME` and `WF_INFO` now paint their visible component in the calling
Task before returning or releasing handler UPDATE. This follows AESWIN
`ws_name` / `ws_info` / `ws_naminf` (2417–2461): require the matching component,
change text/frame state, draw the open linked object, then release UPDATE.
An icon's title remains drawable; its unlinked info text is stored for restoration
without scheduling physical painting. Hidden and equal strings need no drawing
admission. Bounded copied text remains the installed Exec binding convention.

This reuses the slider operation's packet, delegated grant, clipped renderer and
manager-damage completion. Cold visible text establishes access before mutation;
normal/PB calls and warm workstations use the existing boundary. No new renderer,
Task, signal, public ABI record, VRAM reservation or persistent heap payload is
added. Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per
public Task**, including guards, alignment and unused capacity.

The optimized [development record](../development/screnmgr-sm1-text.json) passes
220 application and five native assertions, 36 complete frame/menu pixel
checkpoints and synchronous changed-component checks. The two icon checkpoints
use real native iconification through a test-only hook: the title calls the
caller renderer and info makes zero caller draw calls. Component-less fields,
hidden/equal text, copied caller scratch, bad strings, occlusion, held/unheld
UPDATE, cold/warm access, readiness retry and complete cleanup are covered.

The synchronous oracle checks the called window's changed component while the
caller stays parked with any outer UPDATE held. An earlier observer incorrectly
required a peer's pending exposure to be complete at the same instant; that
condition was removed. The full scene frame/menu oracle still runs after release.
Host checks pass 718 tests with five historical skips. Guards, ownership and
stack floors pass. This is development coverage only: no QED/catalog/demo build,
raw matrix, release or latency qualification.


## SM3a: nonblocking committed window hits

The user selected this read contract on 2026-11-16. `wind_find` now reads copied
AESSNAPSHOT bounds/order/handles under one short Forbid, without UPDATE, scene
admission, waiter publication, drawing or RPC. Overlapping mutations may leave
the prior complete stack visible; operation completion must publish before
return. All other live scene families retain AESGATE pending SM3b–d.

MagiC AESWIN `wind_find` (2812–2838) scans the current window stack without
UPDATE or input-recipient filtering. Exec's normal Task preemption requires
the selected coherent publication boundary. The existing rows supply it without
another buffer. Native/chrome/desktop occlusion is retained; icons now return
their AES handle, following MagiC. Background/outside hits retain Exec's existing
zero result. Focus, menu, MCTRL and closing input admission do not filter raw
window identity. Endpoint close still withdraws input recipients and holds.

The optimized [development record](../development/screnmgr-sm3a-find.json) passes
110 emitted assertions. It covers overlapping and inactive windows, exact rectangle
edges, desktop/native occlusion, menu/MCTRL independence, icon hits, old geometry
before publication and new geometry after it, endpoint close and complete heap
cleanup. A real peer Task obtains the native UPDATE semaphore and claims the
scene gate; the query returns while that peer remains asleep owning both. No
scene waiter or policy-waiting flag is added. Task/nesting restoration, stack
headroom, domain/stack guards and bank ownership checks pass. The run includes
native NMI entries and Task switches. The fixture uses a raw
native caller entry; public C/PB layout and binding code are unchanged.

An initial fixture cleanup left a removed peer as the service's wake target;
restoring the live root owner fixes that test lifetime error. The final source
also distinguishes copied raw handles from input admission: closing an endpoint
cannot erase the handle of a window still in the published stack.

No persistent data, public record, Task, signal, heap payload or VRAM allocation
is added. Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and
0 per public Task**, including guards, alignment and unused capacity. Host
checks pass 718 tests with five historical skips. Only this focused optimized
fixture and host checks ran for SM3a; no QED, demo refresh, raw matrix or release
qualification. SM3b next assigns registration/retirement and copied-publication
lifetimes before the remaining gate cutover.


## SM3b: registration, publication and retirement lifetimes

Snapshot construction now copies and pins each accepted registration under a
short Task guard before it follows endpoint storage. The existing prepared
rows own those holds until publication transfers them or rejects a closing
endpoint. An invalidation during construction survives the final copy, so a
concurrent close cannot disappear behind a clean-cache flag. Raw window handles
remain separate from input admission. Registry identity, binding, endpoint and
client count commit together; final detach withdraws them in one guarded
transition. GUI event publication rejects a closing endpoint inside its existing
queue guard. The GUI queue remains copied, guarded event state rather than a
live geometry reader.

The console input-window facade now obtains the ordinary UPDATE semaphore
before changing a window's route association. Its scope opens no application
paint journal and uses the existing final-release notification. Scene admission
remains in place until SM3d. No drawing or device wait occurs under Forbid.

This follows MagiC's caller application/window cleanup and common UPDATE flow;
MagiC's supervisor exclusion is adapted using Exec's short publication guards
and existing endpoint/Task leases. AESMAIN `appl_init` (5164–5187) reads the
registered APPL identity; AESEVT `appl_exit` / `_appl_exit` (118–138) drains its
message path and observes UPDATE. Exec's current cooperative exit still retains
its context and UPDATE while callback/delivery holds drain.

The existing snapshot dirty declaration bound absolute address `$000001`.
It is now an ordinary image global, with explicit clean/building/dirty states.
This adds one upper-image byte and no bank-zero reservation. No public layout,
Task, signal, persistent heap payload or VRAM reservation changes. Reserved
bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per public Task**,
including guards, alignment and unused capacity.

The [development record](../development/screnmgr-sm3b.json) covers the optimized
snapshot fixture, including 110 raw-hit assertions and ten construction/close
assertions with a real preempting peer, plus the small C registration fixture.
The latter's peer binding needed aliases for the newer display/frame helpers.
Its old blocking UPDATE probe deadlocked correctly behind an exiting owner's
retained UPDATE; it now checks a failed native TRY and progress of a real
registration RPC while the endpoint hold remains live. No ownership assertion
was relaxed. Host checks and local documentation links are included. These are
development checks, with no QED/catalog/demo build or release qualification.


## SM3c: UPDATE-owned scene work and caller continuations

Ordinary window/menu mutations and completion stay in the calling Task under
UPDATE. `DESKMOVE` now keeps a local packet and Layers token through the existing
GEM4XE delegated copy/fence instead of retaining global manager request state.
Even horizontal coordinates/widths require no edge staging. Cold geometry copy
access reuses the standalone frame grant path before mutation. Success publishes
the moved geometry; a quiescent failure retires the token with old geometry.
Copy refusal keeps the redraw fallback. Four old continuation globals are removed.

`AESLOCAL` retries pending close/menu/readiness work in its caller. The former
SYSTEM/SYSTEM_WORK wait states and manager request execution are removed.
Pending-descriptor publication and settlement scans use short Task guards;
`AESCORE.Settle` signals waiting callers without inspecting or mutating their
window requests. Registration and copied GUI-event publication remain independent
of UPDATE. END keeps the painting marker live until journal/cache completion,
then publishes owner/count transitions under a short guard before native release.

Manager live-scene, readiness, cache-candidate, paint and menu probes acquire
UPDATE with nonblocking Try before inspecting state. A miss arms the existing
release hint and leaves input/RPC/lifetime progress available. RPC queue readiness
remains visible even when drawing belongs to another Task. Snapshot construction
runs under its operation's UPDATE or exclusive startup/teardown; the old gate
Offer no longer constructs scene state without that authority. Ordinary native
captures and open menus retain manager UPDATE through the interaction. Their
logical hold is separate from physical readiness, so menu completion can progress.
The controller's console-idle probe borrows/releases UPDATE directly, without
entering the manager's retained scope state; a miss reports busy. Idle console
gathering is discarded under manager UPDATE before a waiter takes over; actual DMA retains its existing owner through retirement.

The existing application MCTRL outline uses retained copied capture authority,
not a manager acquisition of the application's semaphore. Admission/tracking
values use short guards, drawing freezes coordinates and a concurrent cancel or
replacement remains dirty after the physical call. A painting BEGIN waits for
erasure through that retained visual path; END does not expose an intermediate
painting-marker transition. No ordinary drawing or device wait is inside Forbid.

This follows MagiC AESWIN `_wind_set` / `ws_curr` (2298–2326, 2520–2542) and
`set_windxywh`: the caller changes geometry and finishes its graphics before
`ws_endsw` releases UPDATE. Exec's existing semaphore, Task guards, input.device,
display grants and typed blitter borrow supply the platform mechanisms. No new
platform service or GUI-specific substitute is introduced. The scene gate and
combined loop remain staged dependencies for SM3d and SM4; this slice does not
claim their second wait has disappeared or establish a scrolling-speed gain.

The cache fixture uncovered an input migration gap: Ctrl-Esc with an AES window
focused went straight to the application inbox. Capture now reserves global
shortcuts and keys for a published active menu into the copied manager queue.
The callback classifies copied state only; the manager interprets the key under
UPDATE. Menu-open/restore pixels now pass with the focused AES window. An early
scope edit also retained menus by adding them to physical readiness; separating
logical retention from physical readiness corrected that self-blocking condition.

The [development record](../development/screnmgr-sm3c.json) includes the focused
optimized native ownership/publication probe, cache/pixel fixture and lock fixture.
The native probe checks 128 assertions plus ten publication-close assertions:
foreign UPDATE excludes live scene/cache probes, pending requests receive only
wake hints, idle batch handoff completes, caller-side shutdown probes release their borrow,
and the native hold count is balanced.
The cache fixture checks 224 application assertions, 32 checkpoints, copied-move
pixels, repair/exposure policy, menu background restore and cleanup. The lock
fixture checks 237 application assertions including FIFO handoff and restoration.
The copied-move boundary fixture covers normal, quiescent-failure and unsafe
hardware cases, with independent counter/query progress and retained operation
storage. Its pause hooks and fault injection now follow the caller's synchronous
copy/fence. A route-retirement pause leaves scene re-entry to its enclosing
operation. Cleanup allows bounded retries of a busy console stop and skips
unpaintable damage after a terminal drawing fault. Stack/domain guards, bank
ownership and bounded completion pass. Host checks
pass 718 tests with five historical skips. C images are reused only after source,
header and generated-layout hash verification. No QED/catalog/demo refresh,
full raw matrix, release or performance qualification is included.

Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per public
Task**, including guards, alignment and unused capacity. Public records, Task
pools, signals, persistent heap and VRAM reservations are unchanged. The new
manager-capture flag is one upper-image byte; removing copied-move continuation
state releases twelve upper-image bytes. The 82-byte typed packet is stack-owned
by the corresponding frame/move operation. Actual stack peaks are retained in
the evidence, within the existing reservations.


## SM3d: single UPDATE ownership cutover

SM3d removes AESGATE, its stack-allocated scene waiter queue and the combined
frontend's turn-wide Claim/Offer together. UPDATE now supplies the live window,
menu, Layers, journal and cache authority installed by SM3a–c. Committed hit and
window views remain nonblocking copied reads; registration, endpoint, event and
retained capture transitions keep their short Task guards. Input.device keeps
its independent copied application delivery.

Caller frame/copy operations retain UPDATE, their own packet and any Layers
token through physical admission, completion and geometry commit. Open/close
route work retains the same caller UPDATE while input.device drains its capture
references. Physical calls no longer suspend/reclaim UI ownership; the obsolete
AESDEFER reentrant pump and console suspend/resume hooks disappear with the gate.
The driver already provides nonblocking display delegation and independent
completion, so no new platform service, semaphore, scheduler rule or Task is
needed. Pending effects use the existing registered caller descriptor and reply
signal. Snapshot publication and manager notification remain explicit before
resource release or retained-effect waits. Rejected outline calls can arrive
without UPDATE, so their copied capture notification does not build a snapshot.

Private layout/ownership fixtures now inspect the native UPDATE object and
actual executing Task. The gate-only probe and former combined scene/deferred
pump probe are retired; their historical evidence remains pinned in Git. Current
contention, input and effect tests exercise the installed boundaries. Trace tools
observe UPDATE scopes, caller publication and the real frontend loop head; they
no longer classify a wait as scene admission. The combined frontend loop remains
in place for SM4; this slice does not install its final SCRENMGR blocking loop.

Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per public
Task**, counting guards, alignment and unused reserved capacity. The private
upper-heap AES service shrinks from 2520 to 2510 bytes (nine removed payload
bytes plus one alignment byte); Client remains 374 bytes, public Request 418,
and the native semaphore 12. The console's private hook record loses two
three-byte entries. Task pools, signals, public ABI, scratch and VRAM reservations
are unchanged.

Development checks pass on the pinned compiler revision
`05c01f39ff3beef97af0e65b0a16666f5a1bd805` and dedicated AltirraOS PAL/VBXE
configuration. [Machine settings, hashes and results](../development/screnmgr-sm3d.json)
record the actual execution scope:

- Small raw and optimized pending-descriptor/layout probe: 19 checks each.
- Optimized committed-query/foreign-UPDATE probe: 126 main plus 10 publication
  lifetime checks; manager scene/readiness attempts decline under a foreign owner.
- Optimized Counter/input fixture: 68 checks, competing setter, copied keyboard
  and pointer callbacks, input-window binding and cooperative nested cleanup.
- Optimized cursor/CPU-owner fixture: 64 checks; the competing UPDATE owner never
  yields and still permits caller progress through normal Task preemption.
- Optimized copied-move effect: success, quiescent failure and unsafe park, with
  30/25/18 C checks. The first two restore ownership; unsafe hardware deliberately
  parks reset-required while retaining the operation's storage.
- Optimized locks: 237 C plus 4 native checks, FIFO/resource waits, console input
  under UPDATE and clean shutdown. The fixture no longer forces old gate bytes.
- Host suite: 718 tests, five existing skips. Changed documentation links and
  current emitted trace-marker construction pass.

No QED, full catalog, demo refresh, raw system matrix, release qualification or
scroll-performance claim is included.
