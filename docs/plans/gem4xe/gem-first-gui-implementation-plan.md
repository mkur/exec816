# GEM-first GUI implementation plan

[Design](gem-first-gui-design.md) · [GEM plans](README.md) ·
[Current AES contract](../../reference/aes.md) ·
[Testing policy](../../contributing/testing.md)

GF0–GF7 pass at the development tier. GF8–GF15 remain open. The
[execution record](../../history/gem-first-gui.md) retains native I/O/GUI
coexistence, the current resource inventory, the shared window policy audit
and the window effect/commit checks. GF3 separates scene ownership from physical
work and waits, with independent input delivery during caller ownership.
The design is committed
as `633b45fe` on `gem-first-gui`, following the two-Counter MagiC reference at
`39e774ef`. Those references establish the direction and reference behavior;
they do not qualify the redesigned native system.

Implement in order, with a separate commit after each executable slice passes
its selected checks. A slice must leave a runnable system. Keep one shared
policy implementation while transports and clients migrate; remove obsolete
paths with their last caller. This plan does not implement a second GUI mode.

## Starting points and constraints

| Current code | Work to retain or change |
| --- | --- |
| [AES window dispatcher](../../../lib/aes/aeswindow.act) | Presenter-side create/open/close/delete/set/find; includes input routes, cache operations and copied moves that must be separated before caller execution. |
| [Window publication](../../../lib/aes/aeswindowstate.act), [locks](../../../lib/aes/aeslocks.act), [policy gate](../../../lib/aes/aesgate.act) | Existing window views, UPDATE journals and eligible-waiter rules; caller UPDATE currently uses presenter handoffs and RPC fallback. |
| [Window route resources](../../../lib/aes/aesroutes.act) | GF7 separates unpublished route preparation/rollback and hidden-window retirement from scene publication. Callers use the same open/close policy; the presenter retains input consumption and busy retirement continuations. |
| [C window binding](../../../c/calypsi/aes-windows.c), [local native entry](../../../lib/aes/aeslocal.act) | Per-Task context and caller-owned views; suitable locations for direct entry without repeated admission checks. |
| [Desktop core](../../../lib/desktop/deskcore.act), [state](../../../lib/desktop/deskstate.act) | Existing common scene, focus and geometry machinery. Consolidate policy and records into AES rather than creating another scene. |
| [Console worker](../../../lib/console/consoledriver.act), [AES hooks](../../../lib/aes/aeshost.act), [desktop hooks](../../../lib/desktop/deskhost.act) | Presently combine console/backend, GUI policy, input and presentation. Evolve the existing graphical worker into the AES system Task. |
| [Counter](../../../examples/gem-counter/counter.c), [browser/desktop](../../../examples/gem-browser/browser.c), [application supervisor](../../../examples/gem-desktop/resident.c) | Existing GEM clients and loaded Process lifetime. Counter, Files and Control Panel already use GEM; preserve their application bodies. |

Use pinned Action!/C, ROM, emulator and platform inputs. Preserve normal Task
preemption, IRQ/NMI protocols, native context, stack guards, FIFO display
admission, DMA fences and fault retention. Priorities remain inactive. Device
queue/cancellation policy stays in drivers using public Exec primitives. No
GUI-specific kernel service or compiler migration is part of these slices.

The first correctness path uses conventional GEM redraw, visible rectangles
and VDI clipping. Preserve optional cache behavior during migration, including
valid misses; UPDATE end or unchanged geometry never proves repaint completion.
Application callbacks remain within the current supported profile.

## Resource budget to establish in GF0

Use the standard [twelve-Task map](../../architecture/task-capacity.md), not an
assumed eight-Task production limit. Root and service workers count toward its
twelve public slots; private idle is separate. There are eight ordinary worker
pools with 1,312-byte stacks and three large pools with 2,560-byte stacks.
Current [C image admission](../../reference/c-program-loading.md) declares
1,312 bytes for Counter and Panel; other applications retain their measured
requirements. Preserve the internal interrupt reserve and outer guards.

AES currently admits four applications, independently of Task capacity, and
the desktop defines six window slots. Retain these limits initially. Record
actual registrations, windows, workstations, signals and stack-pool assignments,
including hidden windows and delayed retirement. Failed admission must leave
existing clients intact.

The following is a planning inventory for the eventual combined test, not
measured admission evidence:

| Role | Public Tasks | AES registrations |
| --- | ---: | ---: |
| Root/controller | 1 | 0 |
| AES system Task, replacing the existing graphical presenter | 1 | 0 |
| Console backend and GEM terminal frontend | 2 | 1 |
| Filesystem and SIO workers | 2 | 0 |
| GEM desktop application | 1 | 1 |
| Two Counters | 2 | 2 |
| Headless I/O load | 1 | 0 |
| Planning subtotal | 10 | 4 |

Audit additional shell Processes, supervisors, guest Tasks and startup overlap
before using this subtotal. A separate Files/Panel/QED client can exhaust AES
even when Tasks remain free. Rotate test clients where appropriate; if a real
default workflow requires more slots, add a separately budgeted capacity slice
before enabling it. Do not silently increase limits or reduce a workload to
claim coexistence.

GF0–GF8 target no new Tasks. GF9 reuses the graphical presenter Task. GF10/GF11
can add a console-backend Task and terminal Process as responsibilities split;
their live-slot and stack requirements must be measured before enabling them.
All slices initially target **0 added fixed/root/kernel, 0 per-public-Task and
0 idle reserved bank-zero bytes**, including guards, alignment and unused
capacity. An occupied existing pool still consumes concurrency capacity.
Justify any reservation growth from measured depth and report the full pool
cost in its slice. Record upper RAM, code banks and VRAM separately.

## Slice order

| Slice | Executable result |
| --- | --- |
| GF0 | Frozen native two-Counter/disk baseline and measured resource inventory |
| GF1 | Shared window-policy helpers behind the existing transport |
| GF2 | Window effects separated from scene commits |
| GF3 | Scene serialization separated from drawing and waiting |
| GF4 | Caller-side hidden-window creation/deletion |
| GF5 | Caller-side title/info/slider changes |
| GF6 | Caller-side geometry, stacking and window lookup |
| GF7 | Caller-side open/close and safe route retirement |
| GF8 | Caller-side contended window/UPDATE/MCTRL waits |
| GF9 | AES system loop extracted from console presentation |
| GF10 | Independent console backend and reusable terminal-view interface |
| GF11 | GEM terminal for existing console sessions |
| GF12 | Native graphical API retired; one AES window record and policy |
| GF13 | Object preparation reused within unchanged drawing units |
| GF14 | Measured drawing-unit/batching decision |
| GF15 | Combined acceptance, current contracts and OF816 package |

### GF0 — Capture native coexistence before changing policy

Add a focused runner, provisionally `tools/test_gem_first.py`, reusing existing
build/emulator, passive GUI observation and filesystem audit helpers. Load two
copies of the production Counter through the ordinary Process/application
path. Keep its application body unchanged. Use private fresh disk images and
the standard twelve-Task configuration; select only the startup clients needed
by the workload and record them explicitly.

Run an idle control and a fixed disk cohort. Start with a deterministic 16 KiB
file and four complete read/write/Close passes through real DOS/filesystem/SIO,
using an upper-RAM buffer. Audit reread bytes and persisted media independently.
Freeze transfer sizes/counts, cache state, disk timing, pointer/button inputs
and completion deadline in the baseline before any production edit. Keep the
load active long enough to overlap multiple natural Counter timer expiries;
adjust and freeze the fixture if the proposed cohort does not achieve that.

Include cancellation during active I/O and a small separate GEM fixture that
performs a synchronous Read from its event loop. Its own loop pauses while its
peer advances. Repeat with deliberately held logical UPDATE: peers may wait to
paint, but disk/IRQ and a headless heartbeat must progress until release.
This contention case is distinct from the ordinary coexistence gate.

Record counter/model/paint progress, inactive-window pixels, pointer event and
scanout timing, caller/system CPU, off-Task time, lock waits, SIO progress and
normal retirement. Reuse the [IL3 workloads](../io-latency-implementation-plan.md)
and original limits where applicable. Preserve failed latency comparisons.
Do not use Counter increments as elapsed-time measurement or logging as load.

Acceptance: all functional/cancellation/cleanup checks pass, exact workload and
source/image/media hashes are frozen, and actual Task/AES/window/stack use is
recorded. Existing timing failures can remain open with their measurements.
Keep large artifacts under `build/gem-first-gui/gf0/`; add compact development
evidence and a history page to their indexes. Capture a passing baseline before
proceeding; repair and commit any exposed defect as its own focused slice.

Commit: `test(gem): capture native GUI and disk coexistence baseline`.

### GF1 — Extract one shared window-policy implementation

Split request decoding from reusable window helpers in `AESWINDOW` and its
desktop dependencies. Start with hidden create/delete, then route the existing
dispatcher through those helpers. Keep existing transport and state layouts
for this slice. Do not copy the dispatcher into a caller-only implementation.

Inventory each remaining operation's scene reads/writes, publication, input
route, allocation, cache/copy, rendering, wait and retirement effects. Identify
every user of the scene and shared compiler scratch. This inventory determines
where later calls leave/reenter serialization; a direct call instruction alone
does not establish reentrancy.

Acceptance: optimized `windows`/`multiwindow` behavior, identities, geometry,
events, cleanup and selected cache pixels match the parent. Run host checks.
Record the operation/effect inventory with the slice's evidence.

Commit: `refactor(aes): share window policy outside request decoding`.

### GF2 — Separate window effects from scene commits

Refactor move/resize/top and copied-move paths into prepare, physical effect
where justified, and coherent commit/retirement. Establish the required logical
operation ownership across those phases. Keep old committed geometry visible
until the defined commit point; retire or invalidate dependent visible-rectangle
walks and caches on mutation. The existing presenter transport still executes
the operation in this preparatory slice.

Separate route setup/retirement and console attachment effects from scene
publication too, using the GF1 inventory. Retain operation identities/storage
across deferred effects, failure rollback and retirement. This prepares the
window paths for GF3's rule that the scene gate cannot span physical work or
external waits, before any of them becomes a new caller entry.
Update native callers of the same geometry/input helpers together.

Do not enter the current `DESKMOVE.Application` path blindly from a direct scene
helper. If a copy cannot retain valid identities, source pixels and completion
storage across the phases, use conventional damage/redraw for that case and
measure the cost. Preserve quiescent failure cleanup and reset-required storage
retention; neither fallback nor failure may publish speculative geometry.

Acceptance: optimized move/resize/top, overlap, iconify/restore, copy/refusal and
open/close cases have correct geometry, redraw events and settled pixels. Force
preemption and selected effect failures between phases. Existing application
behavior stays runnable through the current transport.

Commit: `refactor(aes): separate window effects from scene commits`.

### GF3 — Separate scene access from physical work and waits

Status: complete at the development tier. The initial nonblocking admission
step and the complete scene/physical/input partition are recorded in the
[execution history](../../history/gem-first-gui.md#gf3--scene-ownership).
The [GF3 record](../../development/gem-first-gf3.json) identifies the selected
emitted cases, source hashes, resources and qualification limits.

Evolve `AESGATE` into the single library-level scene serialization mechanism;
update presenter, existing local UPDATE and deferred paths together. Protect
owner/waiter publication with short Task-side guards. Metadata work remains
preemptible. The system side tries admission and defers, while a caller can
sleep without holding another resource needed for its wake.

Partition the presenter's turn into scene work, physical work and work using
published input/event snapshots. Audit scene/cache readiness queries too.
Release the scene gate before physical admission, fences, external waits or
callbacks. Retained Layers transactions remain explicit logical ownership and
continue excluding conflicting mutations until retirement. Preserve coherent
window/input snapshots and endpoint holds while the system handles events
without touching a caller-owned scene.

Acceptance: emitted tests force preemption with a caller holding the gate,
early/coalesced release signals, waiting presenter and pending input. Prove
continued capture/event delivery, no lost wake, no spin, and no scene access by
a nonowner. Existing UPDATE nesting, journals, cache behavior and guards pass.
Add a small raw/optimized bridge probe only if the native entry/layout changes.

Commit: `refactor(aes): isolate scene ownership from drawing and waits`.

### GF4 — Execute hidden create/delete in the caller

Status: complete at the development tier. Caller hidden creation/deletion,
ordered fallback and Task/heap checks are recorded in the
[execution history](../../history/gem-first-gui.md#gf4--caller-hidden-window-lifecycle)
and [GF4 record](../../development/gem-first-gf4.json). Console-bound deletion
retains its explicit system path.

Bind hidden `wind_create`/`wind_delete` to the GF1 helpers through the GF3 gate.
Allocate caller-owned view storage before entering scene work. Use the common
logical eligibility policy, including older waiters and owner recursion.
Release ownership before waiting or freeing retired storage. Keep nonmigrated
operations on their existing transport to the same core; a temporary transport
fallback must never leave a partially applied operation.

Acceptance: independent clients create/delete to capacity, reuse slots with
fresh identities, fail allocation/admission cleanly, and retain sibling state.
Eligible direct calls make zero window request/reply exchanges. Check mixed
direct/transport sequence numbering, ordinary and parameter-block calls,
Task context, stack headroom, heap restoration and normal exit.

Commit: `feat(aes): execute hidden window lifecycle in callers`.

### GF5 — Execute bounded frame attributes in the caller

Status: complete at the development tier. Title/info was committed as
`95ac3509`; supported slider setters now use the same caller helper. See the
[execution history](../../history/gem-first-gui.md#gf5--caller-frame-attributes),
[title/info step record](../../development/gem-first-gf5-text.json) and
[complete GF5 record](../../development/gem-first-gf5.json).

Move supported title, info and slider setters into the common direct path.
Commit values and damage under scene ownership, then wake frame work after
release. Keep string lifetime rules, value bounds, unchanged-value behavior,
menu renaming and cache invalidation. No physical repaint occurs under the gate.

Acceptance: changed/unchanged attributes, unsupported fields, covered windows,
two owners, publication and frame pixels match the parent. Confirm zero RPC on
eligible migrated fields and measure complete setter/feedback cost, including
deferred system work. Repeat only the affected GF0 observation window.

Implement in two runnable steps, committing after each passes:

1. Extract one bounded frame-attribute helper in `AESWINDOW`, used by RPC and
   the existing `AESLOCAL.Call` entry. Enable `WF_NAME` and `WF_INFO` first.
   Preserve the admission rule, copied strings, unchanged fast return,
   Windows-menu revision and damage/cache publication. Keep other setters on
   RPC before applying any mutation. Capture a GF4 parent fixture before
   enabling the direct path.
2. Enable supported `WF_VSLIDE` and `WF_VSLSIZE` through that same helper.
   Preserve range checks, missing-gadget errors, derived slider geometry and
   view/iterator publication. Compare the complete fixture with the parent,
   including covered/hidden windows, two owners and mixed ordinary/PB calls.

Use optimized `tools/test_aes_server.py --suite frame --output DIR` for focused
state, sequence, caller identity, deferred pixels and complete setter/feedback
observations. Its `--frame-local none/text/all` argument describes the expected
migration stage for parent/step comparisons; it does not select a production
implementation. Run affected optimized `windows`, `cache`, `locks` and
`lifecycle` regressions, plus `tools/test_gem_first.py --case idle --output DIR`
for the affected GF0 observation. The C/Action entry ABI is unchanged; retain
GF4's focused raw/optimized bridge evidence. Report code/data and stack changes,
and reserved bank-zero bytes including unused capacity, guards and alignment;
the target remains zero in every category.

Commit: `feat(aes): update window frame attributes in callers`.

### GF6 — Execute geometry and lookup in the caller

Status: complete at the development tier. The
[query record](../../development/gem-first-gf6-query.json) and
[complete record](../../development/gem-first-gf6.json) retain both executable
steps, starting from GF5 commit `32ef5b1a`. Eligible bounds/top and committed
lookup execute in callers; physical copy/caret/widget effects retain their
existing system continuations. Hosted-system and latency qualification remain open.

Enable supported current-rectangle/top operations and `wind_find` through the
shared helpers. Queries observe coherent committed state; they do not wait for
unrelated repaint completion. Preserve peer exclusion, owner mutations within
UPDATE, window focus, iterator invalidation and durable resulting notifications.
Keep frame drawing and interactive gestures on system work using the same core.

Acceptance: two clients, overlapping/hidden windows, stale iterator restart,
menus and held drag/release/Escape have matching state/events/pixels. Run the
queued-UPDATE drag regression and the disk-load subset from GF0. Measure direct
call completion and input-to-pixels rather than merely the number of RPCs.

Implement as two executable steps, committing after each passes:

1. Route ordinary/PB `wind_find` through one shared lookup helper. Acquire the
   scene gate, then read the committed stack without consulting repaint,
   logical-owner or older-mutation readiness. Preserve registration checks,
   foreign/border hits and native/desktop/tile occlusion; queries do not mutate
   selection or transport sequence. Test while a peer owns UPDATE and while
   mutation readiness is deliberately unavailable.
2. Share a thin `WF_CXYWH`/`WF_TOP` decoder between caller and RPC. Enable
   metadata-only bounds changes (including owner mutations within UPDATE,
   hidden/iconified geometry, no-ops and resizes) and effect-free focus/top.
   Check copy eligibility and caret/widget focus effects before mutation.
   Cases needing those effects retain their existing system continuation and
   fall back unapplied; no caller enters presenter-owned copy or widget scratch.
   Preserve copied-move completion/failure behavior and console extensions.

Use optimized `tools/test_aes_server.py --suite geometry --output DIR` for
ordinary/PB calls, two owners, coherent lookup, exclusion, stale iterators,
deferred work and call timing. Compare the parent window/cache observations;
run copied-move effects, lock/lifecycle checks, the queued-UPDATE native drag
regression and GF0's disk cohort. Build the drag package with `tools/build_demo.py`
so OF816, its five-second boot, matching disk/ROM and notices remain included.
Keep the unchanged entry ABI's focused raw/optimized bridge evidence. Target
zero added reserved bank-zero bytes in every category, including unused
capacity, alignment and guards; report code/data and observed stack depth.

Commit: `feat(aes): execute window geometry and lookup in callers`.

### GF7 — Execute open/close with safe input-route lifetime

Status: complete at the development tier. The
[route record](../../development/gem-first-gf7-routes.json),
[caller-open record](../../development/gem-first-gf7-open.json) and
[complete record](../../development/gem-first-gf7.json) retain the three slices.
Eligible ordinary/PB open/close execute in callers. Referenced input retains a
hidden-window RPC retirement continuation; close retry and exit share cleanup.
Native console attachments and physical caret/widget focus effects retain
system admission. Contended admission remains the next GF8 step.

Move ordinary open/close into the common direct path. Separate route creation,
input draining/retirement and scene publication so blocking work never holds
the scene gate. Preserve open epochs, pending redraw facts, focus restoration,
close/reopen notification withdrawal and failure rollback. Reuse the same
retirement helpers for `appl_exit`; freeing a view cannot race a publisher.
Native console attachment remains a tracked unmigrated extension until GF11.

Acceptance: repeated open/close/reopen and exit with queued GUI messages, full
application queue, active capture and a waiting peer. Obsolete notifications
retire without requiring receipt. No leaked routes, grants, contexts, windows
or Tasks; selected allocation/route failures leave the live scene coherent.

Implement as three executable steps, committing after each passes:

1. Extract route preparation/rollback and draining/retirement into `AESROUTES`.
   Keep scene publication in `AESWINDOW.CommitOpen`/`CommitClose` and preserve
   RPC behavior. Exercise failed open rollback, repeated close/reopen, queued
   notifications and peer lookup while a hidden window retains its old tag.
2. Enable caller open with route preparation outside the scene gate, safe
   re-admission, allocation rollback and fresh open epochs.
3. Enable caller close and reuse retirement for exit. Preserve capture and
   notification withdrawal, focus and pinned window/view storage across waits.

Commit: `feat(aes): execute window open and close in callers`.

### GF8 — Finish library-level contended window and lock waits

Replace RPC-based pending admission for migrated windows, UPDATE and MCTRL with
one shared eligibility/waiter policy reached by callers and system work. Keep
recursion, TRY, nesting overflow, scope, older eligible waiters and the existing
owner's upgrade exception. Publish waiter state before release can wake it;
wait and recheck through ordinary Exec signals with registration storage pinned.
Use existing private signals where their ownership permits it; record any new
signal allocation and handle exhaustion at registration.

Remove remaining RPC fallback and pending-window transport branches after all
their callers migrate. Registration, menu association and
service lifecycle can still use messages. Preserve synchronous BEGIN snapshots
and final END journals; do not introduce asynchronous pointers to reused state.

Acceptance: forced contention, mixed UPDATE/MCTRL, TRY, release/arrival races,
owner exit and simultaneous timer/message readiness. No scene/physical ownership
across sleep; system input/event work continues while mutations defer. Rerun
the GF0 ordinary and UPDATE-held cases, guards and affected cache regressions.

Commit: `feat(aes): wait for window and update ownership in callers`.

### GF9 — Extract the AES system loop

Move graphical input, menu/gesture continuation, frame/pointer work and display
lifetime control into an AES system module, provisionally `aessystem.act`.
Reuse the existing graphical presenter Task and existing driver arbiter. Keep
the console model behind an explicit interface during extraction. Text-mode
console startup/recovery remains a separate backend selection.

Acceptance: boot/stop, pending input, menu/drag continuation and deferred physical
work operate without requiring a console write or repaint to drive AES. Run
two clients plus disk, close the final graphical client and verify orderly
service/display shutdown. Task count and reserved bank-zero delta stay zero.

Commit: `refactor(aes): extract the graphical system task loop`.

### GF10 — Separate the console backend and publish a view interface

Move retained cells, cooked input, stream requests and cancellation into their
console backend worker. Add a reusable console-view interface for bounded cell
snapshots, geometry/cursor state, generation-tagged change notification and
input delivery. Define public records/constants in the appropriate machine-
readable ABI input and generate Action!/C declarations. This is console service
policy using ordinary Exec I/O/messages, with no kernel GUI selector.

Copy coherent bounded snapshots; do not expose mutable cell pointers across
Tasks. Coalesce changes without losing a wake or acknowledging a generation
not painted. Preserve stream acceptance, prefix counts and buffering/backpressure;
completion must not depend on graphical painting blocked by a producer's UPDATE.
Keep a temporary frontend adapter using this interface until GF11 replaces it.

Acceptance: emitted backend/view tests cover writes during snapshots, full
buffers, input, cancellation, unsubscribe/rebind, delayed repaint and stop with
live requests. A producer holding UPDATE can complete accepted stream output.
Measure the added worker's slot, stack, upper storage and whole-system peak;
justify any capacity change before enabling it. Check the new ABI in raw/opt.

Commit: `feat(console): separate stream backend from graphical presentation`.

### GF11 — Make the graphical terminal a GEM client

Add one terminal Process serving the existing console sessions/windows through
the view interface. Use ordinary AES windows, messages, UPDATE/visible-rectangle
iteration and private VDI state. Retained cells stay in the backend. Put backend
access and any combined native wait in the terminal's platform adapter.

Preserve shell switching, input focus, tabs/session actions, foreground BREAK,
close confirmation/retirement and pipe behavior. Draw session controls inside
GEM content or supported GEM controls; retire the native shell-frame extension
with its callers. Terminal startup/exit must not depend on synchronous painting
by the backend or cause a Task to wait for itself.

Acceptance: shell editing/output, session switching, background output, active
disk job cancellation, covered/exposed terminal, producer-held UPDATE and normal
close/EXIT. Record slot, AES/window use and measured frontend stack requirement.
Fit the GF0 inventory or justify growth; then remove native console attachment
and the temporary graphical frontend for the migrated path.

Commit: `feat(gem): present console sessions in a GEM terminal`.

### GF12 — Retire native graphical policy and duplicate window records

Finish migration of remaining native graphical clients/test previews. Reuse
the existing GEM Panel/Files/desktop implementations rather than rewriting
their application bodies. Replace the retained native preview in `deskapp.act`
with the appropriate GEM client, or retire its obsolete build profile and
update its callers/tests together.

Make AES window records authoritative for frame data, ownership, focus and
stacking. Keep Layers and published caller views as derived geometry/snapshots;
internal IDs, GEM handles and lifetime epochs retain their distinct purposes.
Remove the native `DESKTOP` packet interface, retained command/widget window
kinds and second policy path after their final callers are gone. Retain useful
geometry, frame drawing and cache helpers as implementation details. Regenerate
shared ABI definitions/imports and rebuild all affected applications together.

Acceptance: source/call-graph audit finds no native graphical clients or
obsolete dispatch path; desktop/terminal and supported GEM applications pass
launch, overlapping redraw, focus/menu switching and retirement checks. Exercise
resource exhaustion. Update current AES/console/display/Layers contracts and
move superseded contract explanations to history with corrected indexes.

Commit: `refactor(gem): retire the native graphical window interface`.

### GF13 — Prepare each object once across drawing fragments

Use the [drawing profile](../../history/aes-drawing-profile.md) to select safe
caller-local decoding/layout work in `aes-objects.c` and the GEM4XE adapter.
Reuse a prepared description across visible intersections/current strips.
Keep shared GSX writes under physical ownership and preserve all current
ownership-unit, device command/work, completion and buffer limits.

Acceptance: focused box, nested/wide/hidden tree, text/icon, selected-state and
clipping cases plus the matched AES corpus. Exact pixels and guards agree;
callback setup and total caller/system cost improve on the targeted workload
without changing object/fragment work. Reprofile before choosing GF14's change.

Commit: `perf(aes): reuse prepared objects across drawing fragments`.

### GF14 — Measure and choose drawing-unit boundaries

Change one measured ownership/batching boundary at a time. Prefer natural
object/VDI-operation boundaries where safe, splitting for scratch/work/latency
limits. Keep driver admission, FIFO fairness, fences, overlay ordering and
normal Task preemption. Hardware count/work limits stay in force; changing
their public contract would require its own design and driver validation.

Acceptance: the matched drawing corpus and GF0 disk/input load preserve exact
results and I/O integrity. Report total CPU/elapsed cost, grants/submissions,
maximum ownership interval, peer progress and input latency. Adopt a change
only with measured net benefit and no unexplained material regression against
the frozen controls. If none meets that gate, retain existing boundaries and
commit the measured decision without claiming an optimization or relaxing limits.

Commit: `perf(gem): record measured renderer batching decision`.

### GF15 — Reconcile acceptance and package the GEM-first system

Run the combined two-Counter/disk/input case on the final production build and
compare with GF0 using equal offered work and pinned settings. Exercise normal
desktop/terminal/application startup, overlap/exposure, menus, close/relaunch,
resource exhaustion, cancellation and EXIT. Include one focused QED coexistence
walkthrough for the changed window/terminal path. Preserve existing failed
latency gates unless their original protocols now pass.

Build the GUI demo with `tools/build_demo.py`, OF816, matching system disk/ROM,
five-second autoboot, notices, guide and checksums. Check the exact extracted
package's boot/application/EXIT path and the standard shell/prime boot. Keep
intermediates and traces in the development tree; distribute the normal ZIP.
Release publication and a full qualification matrix require their own scope;
if a release is prepared, include both Atarimax CAR forms and raw BIN alongside
the matching XEX as required by the distribution instructions.

Acceptance: all selected functional, guard, I/O and lifetime checks pass;
performance results and open limits are explicit; current references match the
one implementation. Record compiler/ROM/emulator/source/media hashes, actual
Task/stack use, code/data/VRAM changes and complete bank-zero reservation deltas.
Reconcile development evidence/history/indexes and provide the runnable package.

Commit: `test(gem): record GEM-first integration and refresh OF816 demo`.

## Focused checks and evidence

Select existing checks by the behavior changed; extend them for semantic cases
instead of duplicating their implementation in host assertions:

| Behavior | Existing starting checks |
| --- | --- |
| Scene gate, wake and context | [Gate fixture](../../../tools/test_aes_gate.py), [Caller bridge](../../../tools/test_aes_local_bridge.py) |
| Windows, messages, locks, events, multiple windows | [AES service runner](../../../tools/test_aes_server.py), selecting `windows`, `multiwindow`, `gui`, `locks`, `events`, `timers` or `inbox` as affected |
| Physical interaction and loaded GUI progress | [Desktop proof](../../../tools/test_aes_desktop.py), [drag checks](../../../tools/test_desktop_drag.py), GF0 combined runner |
| Shared drawing and cache behavior | [Matched AES corpus](../../../tools/measure_magic_aes.py), [drawing observer](../../../tools/measure_aes_drawing.py), [UPDATE observer](../../../tools/measure_aes_update.py) |
| Console/session and application coexistence | [Console windows](../../../tools/test_console_windows.py), [shell sessions](../../../tools/test_shell_sessions.py), [QED coexistence](../../../tools/test_qed_coexist.py) |
| Measured stack use | [Passive stack observer](../../../tools/measure_gem_stacks.py), plus the affected native/C entry probe |

Use optimized emission for functional, failure, integration and performance
checks. Restrict raw/optimized pairs to changed compiler-facing ABI/bridge
contracts or defect diagnosis. Host checks cover changed tooling and generators;
documentation-only slices need content/link checks. Do not rerun complete
system scenarios in raw mode or run full qualification after every commit.

For each slice keep compact status, selected cases, failures, input/build hashes,
resource deltas and artifact hashes in `docs/development/`, with durable findings
in `docs/history/`. Update the relevant indexes when those records are added.
Logs and build intermediates stay under the slice's `build/` directory. Preserve
the GF0 executable, media and observer inputs for matched comparisons; historical
paths must not silently resolve to rebuilt or interactively modified artifacts.

This plan changes documentation only: **0 fixed/root/kernel, 0 per-public-Task
and 0 idle reserved bank-zero bytes**, including guards, alignment and unused
capacity. No executable validation or new hosted/hardware qualification is
claimed by preparing the plan.
