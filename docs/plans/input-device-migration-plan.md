# input.device migration plan

[Plan index](README.md) · [Design note](input-device-design.md) ·
[Current INPUT](../reference/input.md) · [Device I/O](../reference/device-io.md) ·
[SCRENMGR migration](gem4xe/screnmgr-migration-plan.md)

Prepared 2026-11-15 from the independent input.device design. **Implementation
started: IM0–IM3a are recorded; IM3b–IM8 are pending.** The selected direction reuses the resident console/system
Task for generic input and supports the standard Atari text console, future
VBXE text-mode console and GEM. The design's bounded consumer handler is the
proposed delivery interface. This plan specifies implementation slices and
identifies the remaining execution-placement decision before live cutover.

Commit each passing slice separately. Do not resume the unrelated, unfinished
frame-setter work as part of this plan. No executable change, build or system
qualification is delivered by this planning commit.

## Boundaries and ordering

Keep physical capture in INPUT. The input.device Task owns Acquire/Take/Release
and invokes a bounded consumer handler in ordinary Task context. Consumers own
translation and destination policy. Console streams/models stay in their
driver/backend; DOS retains cooked editing. AES publishes application events
through copied routing and forwards interaction to SCRENMGR. Display owners
perform rendering, cursor work and hardware retirement outside input dispatch.

The device and its minimal test image must link without AES, DESK modules,
SCRENMGR, console renderers or a DISPLAY lease. It must run with keyboard alone
and without VBXE. Handlers cannot Wait, obtain UPDATE/MCTRL/AESGATE, draw, enter
a display grant or invoke recipient application callbacks. Preserve the current
IRQ/NMI protocol, caller-owned storage contract and exact I/O completion semantics.

Implement IM1–IM3 using isolated device fixtures before production cutover.
IM4 converts the standard Atari console first; IM5 adds pointer/AES preparation;
IM6 converts GUI delivery. Existing startup selections remain the supported
text/GEM modes. Each mode has one source owner. Extract shared helpers during
staging and remove superseded acquisition paths as consumers move; add no
legacy-device option or duplicate queue/identity implementation.

The future VBXE text-mode renderer, live text/GEM switching, global handler
chains, event observers and input injection remain outside this migration.
Preserve the existing bitmap console's supported startup selection and safe
retirement; it is not the proposed VBXE text-mode implementation.

## Execution-placement proposal before cutover

The current source map has two service Tasks, not an unoccupied third context:
[CONSOLEDRIVER.Worker](../../lib/console/consoledriver.act) owns input, display
and AESSYSTEM.Run, while [CONSOLEBACKEND](../../lib/console/consolebackend.act)
owns stream/model quanta. [CONSOLEFRONT](../../lib/console/consolefront.act) is
called code, not a Task, and currently imports GUI/display policy even for
standalone rendering. DESKHOST also does not create a separate manager Task.

| Target context | Placement and responsibilities | Status |
| --- | --- | --- |
| input.device | Repurpose the existing console/system Worker and its lifecycle storage. Own source leases, control requests and bounded handler dispatch. No display or scene work. | Selected by the user. |
| Console backend | Retain the existing CONSOLEBACKEND Task for console requests, ingress queues, models and copied views. | Preserve existing separation. |
| Active display frontend | Proposed separate context: standard text/standalone frontend for text startup; SCRENMGR/GUI display owner for GEM startup. Only the selected mode is resident. | Placement proposal requiring selection before IM4/IM6. |
| Applications | Keep ordinary AES/VDI calls and their drawing in callers; Terminal remains a GEM application. | Existing migration direction. |

The separate frontend proposal consumes **one additional simultaneous Task
slot** compared with the present two-service arrangement. It keeps physical
work away from both capture and stream acceptance. With existing pools, an
ordinary frontend occupies 1,600 reserved bytes and a large frontend 2,848,
including DP and guards; pool reservation growth can remain zero. Retain the
current GUI role's large stack class until measurement establishes otherwise.
Neither the input stack nor application capacity is assumed to improve.

An alternative is to run standalone text presentation in CONSOLEBACKEND outside
its stream guard. That adds no Task for text mode, but couples stream progress
to rendering and changes the backend's current no-display responsibility. It
still does not provide a GUI manager context that can block on UPDATE while
console streams progress. No existing application Task has been identified as
an available replacement for that context. Do not count an unidentified reuse
as a saved slot.

The user's request to implement this plan selects the separate frontend
proposal. The [IM0 contract](input-device-contract.md) records ownership and the
provisional resource ledger. No enlargement of the map is authorized. Report
any missing general platform capability before
implementation; do not put specialized completion or deferred-work services
in AES or input.device to conceal an unresolved owner.

## Responsibility and source map

| Existing seam | Migration work |
| --- | --- |
| [INPUT](../../lib/input/input.act), [input.json](../../abi/input.json) | Reuse native queues, source generations, sixteen route slots per source and loss/cancellation. Keep the existing low-level API current. |
| [Device dispatch ABI](../../abi/io.json), [resident boundary](../reference/resident-drivers.md) | Add the statically routed input resident using ordinary request callbacks and public Exec synchronization. |
| [CONSOLECAPTURE](../../lib/console/consolecapture.act), [console input](../../lib/console/consoleinput.act), [foreground policy](../../lib/console/consoleforeground.act) | Move physical ownership to the device; retain console translation, route/session meaning and cancellation policy in the console consumer. |
| [Console lifecycle](../../lib/console/console-lifetime.inc), [driver](../../lib/console/consoledriver.act) | Separate input service lifetime from console display/model startup. Repurpose the Worker without recreating the combined loop inside the device. |
| [CONSOLEFRONT](../../lib/console/consolefront.act), [CONSOLEDISPLAY](../../lib/console/consoledisplay.act) | Remove GUI dependencies from the standard text frontend and place display Claim/Release, view subscription, painting and OS restoration in its selected context. |
| [DESKINPUT](../../lib/desktop/deskinput.act), [AESKEYS](../../lib/aes/aeskeys.act), [AES snapshot](../../lib/aes/aessnapshot.act) | Extract copied-state input delivery from live menu/drag/scene mutation and physical cursor work. Preserve captured routes and endpoint holds. |
| [AESSYSTEM](../../lib/aes/aessystem.act), [DESKHOST](../../lib/desktop/deskhost.act) | Relocate remaining manager/display responsibilities under the SCRENMGR plan; retire obsolete input-pump/console callback bindings when their users have moved. |

## IM0 — freeze ownership, interface and cutover ledger

Status: recorded in the [implementation contract](input-device-contract.md).

Record the placement selection above, startup/stop ownership and peak
simultaneous Tasks for text and GUI modes. Name who retires every retained
physical operation, including cursor work, queued display access, DMA and cache
continuations. A manager may block on UPDATE only after its own outstanding
physical work and access reservations have retired; a blocked Task cannot be
the required completion executor.

Specify the public operations from the design: open/query, attach/detach,
route creation/publication/retirement and cancellation/collection. Define the
typed handler/context/event convention, commit points, capability reporting,
limits and normal errors. Callbacks run on the input Task's stack and DP,
not the registering application's. Specify the C/Action! bridge and its legal
Task-safe calls before exposing C callbacks; report a bridge gap if necessary.

**Check/exit:** source and contract review, complete owner/resource tables and
an explicit placement selection before IM4/IM6. No new kernel selector,
scheduler hook, IRQ callback or bank-zero reservation is presumed. Independent
ABI/fixture work can continue while the placement decision is pending.

**Commit:** `Record input.device ownership and interface contracts`.

## IM1 — generate the public ABI and resident boundary

Status: implemented open/query/close and unsupported-control results. The
[current contract](../reference/input-device.md) and
[development record](../development/input-device-im1.json) report the bounded
raw/optimized native and C layout checks. No capture or input Task is active yet.

Add a machine-readable input-device ABI definition, separate from low-level
input.json, and generate shared Action!/C declarations. Extend static device
routing through the existing I/O definitions/generator. Specify native versus
C pointer representation, alignment, request sizes, handler calls and supported
options; do not hand-copy offsets or change the Task API.

Implement open/query/close admission and ordinary unsupported-command errors
in a minimal resident fixture. Establish binding/storage validity once. Keep
hardware inactive and advertise only capabilities actually implemented.

**Check/exit:** generator consistency plus a small raw/optimized emitted ABI
and language-bridge fixture. Cover request layout, typed callback argument/context
passing, Task DP/register restoration, open failure and quick/non-quick replies.
No application catalog rebuild is needed; rebuild each affected caller when
its ABI is introduced.

**Commit:** `Add generated input.device ABI and resident dispatch`.

## IM2 — implement the generic service and handler lifetime

Status: implemented and checked through the isolated capture adapter. The
[development record](../development/input-device-im2.json) reports 33 optimized
emitted checks and the host suite; production source ownership is unchanged.

Implement the reusable Task loop, control request queue, attach/detach state
machine, owner retention and exact completion. Use the selected Worker lifecycle
storage for production admission; isolated fixtures instantiate that same
service without also starting the console Worker. Do not start an additional
production input Task alongside the existing source owner.

Dispatch a borrowed event to the typed handler with no device guard held.
Serialize detach after any active callback. Define request cancellation before
and after each commit point; a completed attach requires detach. The consumer
retains code/context until acknowledgment and separately drains its own copied
messages/endpoint holds before freeing their storage. Service-owned reference
retirement does not collect a consumer's queues for it.

Use a test-only capture seam for this slice; introduce no public injection
command. Process bounded capture/control batches and sleep on durable work plus
arrival hints. Do not allocate per event or poll an idle session directory.

**Check/exit:** optimized emitted service fixture covering handler execution
context, early/coalesced wakes, empty-to-Wait, preemption during dispatch,
attach/detach, abort commit races, exactly one reply and safe owner retirement.
The linked device image has no AES/DESK/display/console-renderer dependency.

**Commit:** `Implement input.device dispatch and consumer retirement`.

## IM3 — connect physical capture and capture-time routes

IM3a status: keyboard capture and route operations pass 25 optimized emitted
assertions with six physical key actions, native handler context, filter/raw
route transitions, detach/reacquire and exact keyboard hardware restoration.
See the [development record](../development/input-device-im3a.json). IM3b pointer
capture remains pending.

Deliver keyboard support first as IM3a; add relative ST/port-2 pointer capture
as IM3b, each with its own check and commit. Acquire/Take/Release execute in the
input Task. Preserve native capture transactions and normal Task preemption.
Keyboard-only operation must not acquire a mouse or probe the display.

INPUT copies filters at Acquire. Define source activation at attach using the
consumer's generic filter configuration; retire/reacquire a source in the input
Task when a new configuration requires it. Keep the resident service alive
through detach. Do not add a console Ctrl-C or GEM Escape constant to the device,
or mutate an active low-level configuration as a shortcut. A source-set attach
unwinds its acquired prefix before failure and publishes no partial ownership.

Wire generic route operations through retained device bindings. Keep publication
bounded/nonwaiting and coordinate it with the consumer's copied routing guard
using the existing native publication transaction. Give route retirement an
explicit BUSY/drain/discard protocol. Preserve durable cancellation across
overflow and route handover; never retarget old captures after focus changes.

**Check/exit:** focused optimized physical capture fixtures for keyboard, then
pointer motion/buttons. Cover route zero, old/new tags, loss, filtered/unfiltered
input, physical BREAK, acquisition rollback and release/reacquire. Record stack
peaks and memory deltas, including the handler path. Do not repeat ABI raw cases
unless the interface changes.

**Commits:** `Connect keyboard capture to input.device`; then
`Connect relative pointer capture to input.device`.

## IM4 — migrate the standard Atari text console

Depends on the placement selection in IM0 and keyboard delivery in IM3a.
Extract the console consumer: copy captured events to the existing console
ingress, wake CONSOLEBACKEND, and retain console key translation, foreground
route/session policy and raw reads. DOS continues cooked line editing and echo.

Move TEXT display Claim/Release, 40×24 snapshots, view subscriptions, bounded
painting and OS screen/cursor restoration to the selected text frontend context.
Remove AESLOCKS/DESKHOST/DESKSTATE dependencies from that standalone path; simply
skipping GUI routines at runtime does not establish independence. Keep backend
request/model mutation guards short and rendering outside them.

Repurpose the existing Worker for the input service in text startup, remove its
old console-specific capture acquisition and untie console close from input
service termination. Keep display/model readiness separate from device readiness.
Ordinary console clients retain their stream API.

**Check/exit:** one optimized standard Atari text-console image without AES,
SCRENMGR or VBXE. Exercise typing, a raw read, one cooked line, Ctrl-C/BREAK,
output/scroll, instance focus and safe close/stop with OS restoration. Use small
fixtures; do not launch QED or rebuild the shell/application catalog solely for
this check. Record the actual Task occupancy and text frontend stack peak.

**Commit:** `Migrate Atari text console to independent input.device`.

## IM5 — extract the AES consumer and manager event boundary

Use the copied-state portions of DESKINPUT/AESKEYS and AESSNAPSHOT rather than
calling DESKINPUT.Service/Present wholesale. The handler translates GEM input,
resolves retained snapshot routes and publishes application inbox readiness.
Build/update snapshots under their existing scene owner; the handler never
walks live scene pointers or acquires UPDATE/AESGATE.

Move menu/drag interpretation that changes shared UI state into manager event
consumption. Queue copied interactions with capture identity, retained endpoint
references and explicit overflow/cancellation. Move pointer positioning policy
above relative capture and physical cursor rendering outside the handler.
Do not create another AES routing Task or a private kernel delivery operation.

**Check/exit:** a tiny AES consumer fixture: while one Task holds UPDATE and the
manager is blocked, another application receives key and pointer events.
Check focus/MCTRL route publication and recipient close without stale delivery.
Verify no waits/drawing/live scene mutation in the handler, and measure its
callback/stack cost. Split keyboard and pointer/manager commits if necessary.

**Commit:** `Separate AES input delivery from manager interaction`.

## IM6 — switch GUI startup to the shared input service

Depends on IM0's selected GUI placement and IM5. The input Task acquires both
configured sources, then AES attaches its consumer. Move GUI lifetime/display
ownership to the selected frontend context. Startup initializes endpoint storage
before attach and publishes GUI readiness only after required resources succeed.
Unwind each failed prefix in its owning Task.

Remove GUI keyboard/pointer Take/Acquire/Release from console and DESKINPUT
paths. Route GEM Terminal through AES/session input, with no competing standalone
console sink. Keep console backend acceptance independent of UPDATE and display
waits. Preserve the existing bitmap startup selection through its frontend.

This delivers the input-service portion of **SM2**. The existing manager loop
may remain in the frontend context until SM3/SM4 replace it; it no longer owns
capture. Do not add a second presenter implementation. Install the final blocking
SCRENMGR loop only with the SCRENMGR plan's caller-drawing, scene-reader and
physical-retirement dependencies satisfied. IM6 alone does not complete SM3/SM4.

**Check/exit:** Counter/widget with concurrent key/pointer delivery and console
I/O during UPDATE contention and a drawing grant wait. Retire owner DMA/access
before any blocking manager Obtain; verify input continues independently. Check
one GUI startup failure and clean shutdown. Record occupied slots and actual
input/manager/backend stack peaks; use deeper ownership cases only as needed.

**Commit:** `Migrate GEM input ownership to input.device`.

## IM7 — close lifecycle and consumer-handoff boundaries

Verify attach failure, detach with queued capture, abort racing normal control
completion, route exhaustion, cooperative consumer exit and last console/AES close.
Detach stops device callbacks; consumer shutdown separately drains copied
interaction/inbox references. Unloading code or freeing state waits for both.
Use existing cleanup paths; automatic recovery from an uncooperative Task exit
is not supplied by a retained reference or promised by this migration.

Keep input.device resident while the last frontend detaches. Reattach a different
test consumer without old keystrokes/buttons reaching its new route. Test this
without switching physical displays; live GEM/text conversion remains separate.
System shutdown must stop admission, retire requests/routes and release INPUT
in its acquiring Task before signal/storage reuse. Unsafe retirement retains
resources and reports failure.

Remove obsolete console capture wrappers and input-pump bindings once all users
move; retain the shared low-level INPUT API and unrelated standalone callers.
Coordinate removal of AESSYSTEM's remaining callback interface with SM4, rather
than deleting still-used display/manager completion paths prematurely.

**Check/exit:** only focused optimized lifetime/ownership cases for the boundaries
above, preserving guards, complete native context and bounded completion. Fixes
and checks belong with the slice introducing each behavior; IM7 covers remaining
cross-consumer seams, not deferred basic cancellation correctness.

**Commit:** `Complete input.device shutdown and route handoff`.

## IM8 — record minimal acceptance and publish current contracts

Run one coherent standard Atari text case and one GEM Counter/widget case after
the integrated cutover. Reuse unchanged APPs when ABI/imports permit. Record idle
wakes, capture-to-handler/inbox delay, off-Task time and handler/control cost;
separate these from UPDATE waits and physical paint latency. Do not claim a
scroll improvement from reduced coordination CPU alone.

Publish the implemented device contract in reference documentation and update
input/console/display ownership descriptions and their indexes. Retain this
plan and the design rationale as linked planning/history according to repository
conventions. Record actual checks, compiler/ROM/emulator pins, upper-memory and
bank-zero deltas, remaining limits and the SCRENMGR slices still outstanding.

**Check/exit:** development-tier emitted checks for affected behavior plus
content/link/generation checks. No QED, full catalog, demo refresh or release
matrix. No future VBXE text renderer is required for acceptance.

**Commit:** `Document input.device migration acceptance and resource costs`.

## Resource and completion rules

This planning slice changes **0 fixed, 0 root, 0 kernel, 0 idle and 0
per-public-Task reserved bank-zero bytes**, counting guards, alignment and
unused reserved capacity. No target ABI, upper-memory or VRAM allocation changes.

Every implementation commit must report that same reservation breakdown,
occupied pools and per-Task stack/DP costs separately. Reusing a reserved pool
does not make an extra Task free. Preserve the [current map](../architecture/task-capacity.md);
do not enlarge it or shrink a stack without the required evidence/decision.
Count registration records, Task metadata, ports, requests and any new upper-RAM
buffers; reuse existing capture queues and remove replaced storage.

The complete migration needs IM4 and IM6 on one current device implementation,
safe IM7 retirement and IM8 evidence. The standard Atari text frontend must have
no GUI dependencies, the device must have no display dependencies, and normal
Task preemption must remain. A missing service, unapproved placement or failed
ownership boundary is reported at its dependency gate, not bypassed with a
specialized substitute.
