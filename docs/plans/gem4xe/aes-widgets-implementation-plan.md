# AES widget library implementation plan

[GEM plans](README.md) · [Desktop contract](../../reference/desktop.md) ·
[Layers](../../reference/layers.md) · [Roadmap](../../roadmap.md)

Status: planned, 2026-10-05. Port a bounded selection of GEM4XE AES object
and form code into a widget library hosted by the existing Exec816 desktop
presenter. Deliver a control-panel application beside the shell, with labels,
buttons, toggles, radio groups and keyboard navigation. Preserve the source
provenance of the port and the desktop's independent application lifetimes.
Implement AW0–AW6 in order and commit each executable slice separately.

The current desktop and MP1–MP4 mouse work are the starting point, at Exec816
revision `d2c9f1a`. This plan includes the architectural decisions needed for
implementation; it does not require a separate design-note milestone. Current
reference contracts remain authoritative until each corresponding slice lands.

## Scope and visible result

The existing VDI port supplies selected GEM graphics code. The window service,
Layers, focus and desktop gestures are Exec-native. This milestone adds actual
AES-derived widget implementation, with a native service interface. It does
not advertise complete AES source or binary compatibility.

| Initial feature | Supported behavior |
| --- | --- |
| Object trees | Bounded hierarchy, relative coordinates, drawing order and hit testing. |
| Boxes and labels | `G_BOX`, `G_IBOX` and `G_STRING`, using the existing GEM 8×8 font and palette. |
| Buttons | `G_BUTTON`, normal/selected/disabled states, default action and press/release feedback. |
| Toggles and radio groups | Selectable buttons retain selection; `RBUTTON` selects one sibling in its group. Use GEM selected-state visuals initially, without promising a new checkmark or round-radio artwork set. |
| Keyboard interaction | Tab/Shift-Tab focus traversal, Space activation, Return default action and Escape cancellation. |
| Retained updates | Bounded state/label patches and redraw of their affected region. Exposure reconstructs the current widget tree. |

The control panel is an ordinary demonstration application, not a service for
changing system configuration. Its actions update its own visible state and
report selected object IDs. It replaces the existing demonstration app in the
optional desktop build, preserving the shell-plus-one-application Task budget.

A task bar is a follow-on consumer of the button library. Listing windows,
reserving a desktop work area, switching focus, minimizing/restoring and
launching programs are separate desktop policy work. Widgets must not assume
they are full-screen or modal, so that reuse remains possible.

Defer editable `TEDINFO` fields, `.RSC` loading, icons/bitmaps, arbitrary fonts,
menus, sliders, resizing, `G_USERDEF` callbacks, indirect object specifications,
full `appl_*`/`evnt_*`/`form_do` compatibility, GEMDOS and G4A loading. Reject
unsupported types, flags and style combinations explicitly at admission.

## Port boundary and provenance

Start from GEM4XE 0.9.4, revision
`e413c39d2f8e1bec8fe16596f610b923de4a0ae9`, already selected by
[inputs.json](../../../ports/gem4xe/inputs.json). AW0 adds exact hashes for the
additional source dependencies. Keep a separate AES selection and patch series
under `ports/gem4xe/`, using the existing reproducible extraction approach.
Record which routines are extracted unchanged, adapted or replaced.

| Donor source | Reuse and required adaptation |
| --- | --- |
| `src/aes/objc.c` | Reuse object traversal, offset/hit calculations, supported branches of `ob_sst`/`just_draw`, and state handling. Admit trees before traversal; widen coordinate arithmetic and provide bounded paint continuations. |
| `src/aes/graf.c` | Reuse box geometry, colour decoding and text placement. Replace workstation startup, global-screen assumptions and graphics calls with the hosted drawing adapter. |
| `src/aes/form.c` | Reuse selection/group/default-action decisions. Replace `gr_watchbox`, `ev_button`, `fm_do` waits and global input ownership with explicit state advanced by desktop events. |
| `src/aes/aes.h` | Extract the required object, rectangle, flag and state definitions. Verify emitted layouts; do not include the whole AES environment. |
| `tools/aesref.py` and its dependencies | Pin and reuse the supported object pixel reference as one oracle, alongside independent integration and state-machine assertions. |

The extraction must build selected donor routines, rather than silently
substituting a new widget implementation behind familiar names. Preserve donor
copyright/licence notices and update the source/licence map for new files.
Public native binding declarations follow the repository's existing licence
split. Normalize host text line endings before source-range extraction; preserve
font and binary fixture bytes.

Retire donor `ZWIN`/near-storage assumptions in the extracted build. Use the
existing large-code/huge-data Calypsi bridge, ordinary Exec stack/DP context and
upper-RAM storage. Do not import donor allocation, cooperative contexts, COP
dispatch, device startup, IRQ capture or application callbacks. A compiler
defect belongs in its owning toolchain with a focused regression.

## Ownership and execution

The application owns its request buffers and receives semantic widget events.
The presenter owns copied widget trees, mutable control state, interaction
state and all physical drawing. No widget code runs in an IRQ. No application
callback runs inside the presenter. The application performs its own work and
DOS I/O after collecting events.

This follows the existing Amiga-inspired division between Exec mechanisms,
Layers geometry and desktop interaction. Serializing the AES-derived code in
the presenter is the explicit 65816 adaptation: it shares renderer scratch and
the existing large stack. It introduces no widget Task, Task per control,
second display owner, private kernel service or kernel ABI operation.

Keep one retained widget context per widget window. Durable focus/selection,
pressed object and paint progress must be per context; remaining C drawing
scratch is presenter-private and valid only during one bounded call. Rebind or
reset graphics attribute caches at each entry because console and other-window
drawing can run between widget turns. Never retain a pointer into a returned C
activation. Widgets occupy their window's existing layer; tree size does not
consume additional Layers slots.

Add a `CONTENT_WIDGETS` window kind alongside console and retained-command
windows. Keep the window kind fixed for its lifetime. A new Action! module
under `lib/desktop/` manages the native protocol and calls an internal C bridge
under `ports/gem4xe/`. Rendering uses the shared ordinary drawing boundary, not
the separate exclusive-display GEM demo service.

## Native widget contract

AW0 freezes a proposed `abi/widgets.json`; extend `abi/desktop.json` for the
content kind, operations and events. Generate Action! and C declarations and
emitted layout probes together. Rebuild all callers after a desktop record
change; maintain one current ABI. Exact numbers are assigned by the generators.

Proposed initial limits are 32 objects including the root, eight hierarchy
levels, 1,024 string bytes including terminators, and 63 glyphs per label.
Limit a tree packet to 2,048 bytes and an update to eight changed objects.
AW0 must prove that the generated layout fits these limits before they become
the public contract. Increasing a limit requires a recorded memory/work bound,
not truncation of accepted data.

Use a self-contained tree packet with bounded object indices and string offsets.
Convert offsets into service-owned far pointers only after admission. Do not
accept application code pointers or retain client tree/string pointers after
reply. The admitted payload occupies one live upper-RAM allocation contained
in one CPU bank; reject overflow, wrapping and unsupported placement. Internal
service allocation uses the same proven bank-containment rules.

| Proposed operation | Semantics |
| --- | --- |
| `SetTree` | On an owned widget window, validate and copy the complete tree. At a safe boundary, atomically install it, cancel old interaction, assign a fresh tree epoch and damage the client area. Failure preserves the previous tree. |
| `UpdateWidgets` | Match window, tree epoch and expected model revision. Validate a bounded batch of absolute state/label assignments, then commit all changes and their damage together. No application-side toggle operation. |
| `ReadWidgetState` | Return the current epoch/revision, focused object and selected/disabled states through caller-owned reply storage. Used for initialization and recovery after event loss or a stale revision. |
| `NEXT_EVENT` | Continue using the existing event lane. Add widget-action/cancel events identifying window, tree epoch, object and resulting model revision/state. |

Set/update/read use the existing content lane; they do not allocate another
reply port or signal. Mutations wait for the current paint/DMA token to retire.
Read replies describe a consistent committed model. Control replies acknowledge
logical state, not visible scanout. The application keeps request and payload
storage stable until exact reply collection, following the desktop lifetime
contract.

Tree epoch and model revision are nonzero 32-bit identities. Never wrap them
into reusable values; report exhaustion while preserving close/unregister.
Replacement retires the old epoch. Queued old-tree notifications are purged or
rejected by their epoch, never applied to a reused object index. No-op updates
cause no revision increment and no damage. A stale update rejects without model
or pixel mutation; the client reads current state before retrying.

Validate structure once on SetTree: supported types/flags, root and sibling
terminators, index ranges, single parentage, reachability, depth, absence of
cycles, labels, radio groups, colours and complete visual extents. Treat GEM's
parent-return links as structural terminators, not ordinary children. Bound
validation itself, including malformed sibling chains. Use wide arithmetic for
ancestor sums, borders and text extents; admit content-local geometry within
the client area, including outward button borders.

Topology and geometry stay immutable until SetTree. Updates can change labels,
selection, disabled state and subtree visibility; hiding/disabling an active
control cancels its gesture and moves keyboard focus to an eligible control.
Validate the complete resulting batch, including radio exclusivity and string
capacity, before commit. Cache parent/order/geometry data after admission.
Ordinary input and paint turns do not rescan writable-memory tables, revalidate
the whole tree or cross a message gateway per object.

## Drawing and damage

The donor requires more than the current solid replace-only public VDI subset:
transparent text, selected-state XOR and the fixed disabled-state stipple occur
even in basic buttons. AW1 implements and tests these exact requirements through
the hosted drawing boundary. Keep the fixed 8×8 face; allow only the selected
solid/hollow box styles and the disabled pattern. Do not broaden the advertised
public VDI opcode set merely because internal widget rendering gains helpers.

Define a complete state/style allowlist in AW0, including supported button
border thicknesses. Exclude `OUTLINED`, `SHADOWED`, `CROSSED`, `CHECKED` and other
decorations until their extent and drawing rules are deliberately implemented.
Draw keyboard focus with a documented small internal decoration whose full
extent participates in damage. The checkbox behavior in this milestone is a
selected toggle button, not an implementation of every GEM object-state bit.

Use an explicit effective clip: window client area intersected with the Layers
paint region and the current rendering slice. Translate content coordinates
once. Donor empty-clip conventions must never disable this outer clip. Preserve
odd pixel edges, partial glyphs and neighboring packed nibbles. Anchor stipple
phase consistently so moving/repainting or splitting a clip does not change
the intended object appearance.

State updates compute the union of old/new visual bounds of changed objects,
including an old/new focus decoration and both radio selections. Label changes
clear the full object area so shorter text leaves no residue. Hiding a subtree
damages its previous coverage. Call `LAYERS.Invalidate` for these extents;
do not route a widget patch through the current whole-window `REPLACE` path.
Layers may conservatively merge damage into a bounding rectangle; this plan
does not require a new region implementation.

Repaint the damaged background and all intersecting objects in their original
paint order, including overlapping siblings and transparent containers. Drawing
only the changed object's foreground is insufficient. Exposure, repeated paint
and incremental updates must produce identical pixels. In particular, adapt
`ob_change` into model mutation plus invalidation: do not rely on its direct
screen XOR fast path surviving occlusion or later reconstruction. A selected
object may use XOR during reconstruction after its base pixels are painted.

Store traversal/order and continuation state in upper RAM. Keep at most four
objects and sixteen scanlines of widget painting per worker turn initially;
bound backend work/list size as well, since a single object can be large.
Return to input/completion/control service between turns. Hold the Layers token
until the entire damage snapshot completes; do not acknowledge damage early
or restart completed objects on each continuation.

The presenter removes/restores intersecting pointer and drag overlays at its
existing boundaries. Adapt nested donor mouse-off/on calls to this hosted
scope, avoiding extra pointer submissions per primitive. Preserve exclusive
command-arena use during asynchronous console scrolling. Widget drawing uses
bounded synchronous lists; no second in-flight operation is introduced.

## Event handling and recovery

The presenter advances a finite interaction state from captured input. A press
inside an enabled button arms it and shows pressed feedback. Motion outside
cancels that feedback; returning inside restores it. Release inside commits
one action, release outside cancels. Momentary buttons return to their normal
state; toggles keep their new selection; radio selection updates the group
atomically. These release-time semantics intentionally adapt the donor's
blocking form behavior and must be covered by independent transition tests.
Keep temporary pressed appearance separate from committed selection. Model
revisions cover committed tree/state/label changes; press tracking and focus
decoration still invalidate their pixels and remain frozen during a paint token.
An application patch that changes the armed control cancels that gesture before
installing its new state.

Window hit testing and title/close gestures run before client widget hit testing.
A widget gesture captures motion/release outside its object, without transferring
the click to another window. First-click focus and widget arming occur in order
at a safe scene boundary. Escape, focus loss, hiding, tree replacement, close,
input/event loss or shutdown cancel the gesture. Require a new released-button
observation after ambiguous input; held buttons cannot rearm it.

Translate the required Atari raw scans and qualifiers at the widget boundary.
Console key translation remains unchanged. Tab/Shift-Tab visit enabled visible
interactive objects in tree order; Space activates the focused control; Return
chooses the one enabled default action. Escape emits a dialog-cancel event and
does not close the window automatically. BREAK retains cancellation semantics.
Keyboard navigation of buttons is a documented hosted extension beyond the
donor's editable-field traversal. Unhandled keys keep the existing graphical
event path. Consumed widget input is not also delivered as an actionable raw
click/key. Preserve capture routes and tick-valid flags across focus changes.

Input intake must continue while a Layers token or scroll gates model edits.
Use a bounded presenter-owned deferred widget-input queue, initially sixteen
records carrying destination/epoch, route, capture metadata and transitions.
Coalesce only adjacent motion with identical destination and button state;
preserve press/release ordering. Drain at a safe boundary with a bounded quota.
Overflow or stale destination cancels affected interaction and records LOSS;
never replay an old click against a replacement tree. Reserve queue capacity in
the shared upper-RAM budget. No timer poll or wait-for-release loop is added.

Semantic events use the existing bounded client queue and LOSS behavior. State
changes are authoritative in the presenter; clients resynchronize toggles and
radio state through ReadWidgetState after LOSS. Activation notifications are
not guaranteed to survive overflow and must not be replayed or synthesized;
an application must not execute a command merely because a button is selected.
Preserve durable close/focus notices. A stalled client cannot block another
client, allocate unbounded storage or retain an active mouse gesture forever.

Client patches and user actions serialize at presenter commit boundaries.
Expected revisions prevent a delayed application update from overwriting a
newer user selection. Sequence/epoch checks are local lifetime checks, not
per-event address-range audits. No arbitrary application lock is acquired.

Widget-event queue exhaustion must also cancel its presenter's interaction
state, not just post a client-side LOSS notice. If a paint token is live,
disarm capture immediately and defer the corresponding visible/model repair
until it retires. The old immutable paint snapshot remains valid meanwhile.

## Memory and retirement

Target zero reserved bank-zero growth: fixed, root/kernel, each public Task and
idle, including guards, alignment and unused capacity. Reuse the presenter's
2,560-byte stack and the application's existing ordinary Task pool. Measure
raw/optimized C stack high-water marks with interrupt headroom before accepting
the integration; a donor stack estimate is not proof that it fits.

Set initial upper-RAM budget ceilings of 4 KiB per admitted widget window and
4 KiB shared staging/interaction/render scratch, excluding linked code. Count
rounded allocations, object/string capacity, cached geometry, deferred input,
new event-record fields across all queues and unused slots. This is a proposed
ceiling to prove in AW0, not an allocation already made. Use allocation on widget
admission rather than a new bank-zero reservation. Confirm code/data bank fit;
if more upper code/data banks are needed, record their whole reserved size and
update image placement explicitly. Do not silently enlarge a linker arena.

Target zero additional VRAM reservation by reusing current command/glyph/stencil
storage after its owner retires. Any indispensable new pattern storage requires
an explicit extent and accounting before use. Keep the four-window/layer and
eight-public-Task limits. Widgets do not consume extra window slots.

Reserve staging before publication and unwind allocation failures in reverse
order. Serialize preparation through one shared staging area. On replacement,
validate and prepare the new packet there while retaining the old context;
after paint/interaction references retire, install it into the existing fixed
context allocation. Publish the epoch/revision last. No fallible allocation or
validation remains after commit begins, and peak storage stays within the
per-window/shared ceilings. Close cancels capture/deferred input, retires semantic
notices and frees the widget context after its active token and hardware work
settle. Application disposal still requires reply collection and unregister.
Keep the existing quiescent-fault versus reset-required retention policy;
never free storage referenced by an unquiesced engine. Retiring one client must
not reset another client's widget state or rendering caches incorrectly.

## Executable slices

### AW0 Freeze the subset and execute extracted object code

Add the AES source hashes, selection, patches and notices; define generated
widget layouts and the type/flag/style/limit allowlists. Build a native C fixture
using a recording graphics adapter. Exercise admitted tree traversal, offsets,
hit testing and supported object draw records through extracted donor routines.
Freeze native operation/event layouts without enabling them in the production
desktop until their implementation slice. Measure initial code/data/stack
footprints and account for all proposed bounded storage.

Acceptance: reproducible extraction, emitted C/Action! layout agreement, raw and
optimized execution, malformed-tree termination, expected draw/hit results,
stack/DP guards and context restoration. Commit the extraction and evidence.

### AW1 Render the supported widgets through VBXE

Connect selected `graf.c` and object drawing to hosted drawing helpers. Implement
the minimum transparent-text, selected fill and disabled-pattern behavior with
explicit clips and current list/work bounds. Bind metrics to the existing
display/font without opening another workstation. Establish the immutable
tree paint order and a resumable rendering cursor.

Acceptance: raw/optimized emitted pixels against the pinned object reference
and independently calculated clipping cases. Cover every admitted type/state,
short/maximum labels, odd x, partial glyphs, borders, stipple phase, overlapping
objects, repeated paint and empty clips. Check pointer background and drawing
attributes across interleaved console/widget calls. Commit the adapter.

### AW2 Admit retained widget windows and bounded updates

Implement CONTENT_WIDGETS, SetTree, UpdateWidgets and ReadWidgetState through
the existing desktop lanes. Add service-owned context allocation, epoch/revision
checks, semantic event fields and C bridge declarations. Update window-kind
checks in title/close/focus/retirement code so widget windows behave as graphical
windows. Keep the console and command-content paths working.

Acceptance: native two-client ownership/lifetime fixtures, atomic replacement
and patch rejection, readback, stale IDs/epochs/revisions, exhaustion, maximum
capacity, no-op updates, allocation rollback and reply-buffer lifetime. Run raw
and optimized emitted bindings, including boundary placement and guard checks.
Commit the native service integration.

### AW3 Paint widget damage within desktop continuations

Extend `deskpaint.act` with the widget continuation and correct content-only
damage. Gate model edits with the existing scene token. Preserve the original
snapshot through yields, scroll completion, frame painting and overlay work.
No whole-window invalidation for an isolated control update.

Acceptance: full-scene oracle checks for a small patch, shorter label, hide/show,
disabled/selected change, radio pair, partial overlap, obscured updates and
exposure after move/raise. A fully covered widget window causes no drawing or
idle spin. Assert unchanged frame/unaffected pixels and bounded rendering turns.
Exercise pending scroll, quiescent failure and reset-required retention. Commit
damage integration after the raw/optimized presentation cases pass.

### AW4 Advance form interaction from desktop events

Port and adapt the form selection/group helpers, explicit press tracking,
keyboard focus and default/cancel decisions. Add bounded deferred intake and
semantic event delivery with the revision/loss rules above. Use current physical
ST capture and keyboard routes; do not change sampling, sensitivity or kernel
scheduling. Keep waiting clients asleep through the existing event request.

Acceptance: raw/optimized transition tests plus physical mouse/key execution.
Cover press/move-out/move-in/release, release outside, disabled/hidden controls,
radio exclusivity, Tab/Shift-Tab/Space/Return/Escape/BREAK, focus changes, title
drag precedence, replacement/close while held, scroll-gated transitions, input
loss, full event/deferred queues and a stalled client. Every admitted action has
one defined outcome; no duplicate raw/semantic action or stale-tree activation.
Commit interaction after guards and cleanup pass.

### AW5 Integrate the control panel and measure interaction

Replace the optional desktop demo's simple app with an Action! control-panel
client using compiled-in trees and semantic events. Keep its application work
outside the presenter. Include momentary, toggle, radio, default, disabled and
cancel cases; update a status label through bounded patches. Retain cooperative
close and shell EXIT. Use a test-only second widget context to expose accidental
global state without adding a production Task.

Run idle, console-scroll and physical-SDFS interaction with the shell alive.
Measure captured input to widget commit, application consumption and first
visible feedback separately; count damaged pixels, primitive/list work, charged
presenter CPU and maximum uninterrupted rendering quantum. Compare a small
patch with an equivalent SetTree/full-redraw operation on the same scene; do
not label a change in workload as a renderer speedup.

Use 100 representative actions per load for final distributions, including
button, toggle and radio changes, and replay the combined workload without
observers. Keep the existing desktop responsiveness targets visible: 40/60 ms
p95/max at idle, 60/100 ms under load, with 40/100 ms maximum button consumption.
Measure widget feedback separately from pointer motion. Investigate repeatable
regressions on matched existing workloads; report missed targets rather than
silently widening them. This milestone does not include a general scheduler or
window-move repair rewrite.

Acceptance: exact widget/model/scene results, continued shell and independent
application progress, bounded work and storage, clean lifecycle/fault behavior,
and recorded timing outcomes. Reuse MP3 evidence for unchanged capture behavior;
only collect missing matching controls. Commit the client and measurements.

### AW6 Document and refresh the desktop preview

Add current widget contracts under `docs/reference/`, a source-port README and
an execution record with compact evidence under `docs/history/` and
`docs/development/`. Update desktop contracts, generated-ABI documentation,
indexes and the plan status. Distinguish reused AES behavior, hosted adaptations,
unsupported compatibility and any open latency targets.

Build with `tools/build_demo.py --desktop`, including OF816, the matching system
disk, pinned ROM, upstream notices, guide and checksums. Preserve the five-second
autoboot and the standard shell/prime default. Extend `test_demo.py --boot-smoke`
to exercise the panel alongside physical disk commands, a seven-Task pipeline
and clean EXIT. Verify extracted archive members/checksums and boot the exact
packaged bytes. Keep intermediates/manifests/traces outside the ZIP.

Acceptance: package walkthrough and documentation/link checks pass; record
source/toolchain/ROM/emulator hashes, final archive hash, actual memory deltas
and timing limits. Commit documentation/evidence and provide the local ZIP.
Publishing on GitHub remains a separate action.

## Validation policy and completion

Follow the [two-tier policy](../../contributing/testing.md). Ordinary slices use
host checks, affected generators and focused emitted raw/optimized tests. Add
targeted interrupt, lifetime and transport cases when their boundary changes;
do not repeat full qualification matrices after every commit. Documentation-only
edits need content/link checks. Reuse compatible passing artifacts and collect
only evidence made stale or missing by the change.

Use [actionc.json](../../../toolchain/actionc.json), the pinned Calypsi toolchain
and [desktop machine pin](../../../toolchain/altirra-gem-vdi.json): PAL 65C816 8×,
4 MiB, VBXE FX 1.26, ST mouse on port 1 and current 2× travel. Record the actual
emulator hash from `mouse_input.tooling`, not a different observer entry. The
normal 4 kHz/fine-SIO timer policy remains unchanged. Development results do
not establish physical-hardware or whole-system qualification.

Extend the existing desktop presentation/input/fault and packaged-demo runners;
add focused extraction/layout/object/input fixtures where no existing oracle
covers the new behavior. Reference models must not derive expected visibility,
hit testing or state transitions from the target's own answers. Corrupt tree
tests must fail boundedly before rendering, rather than hanging in donor walks.

Completion means a reproducible AES source port, working retained widgets in
independent desktop windows, bounded incremental updates and event processing,
measured memory/latency, documented limitations and a tested local preview.
It does not mean a complete AES, a task bar, or a completed system preferences
application. Those can build on this library without changing Exec's Task model.
