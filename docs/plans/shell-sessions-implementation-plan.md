# Multiple shell sessions implementation plan

[Design](shell-sessions-design.md) · [Plans](README.md#programs-and-shell) ·
[Roadmap](../roadmap.md#commands-and-cli) ·
[Testing policy](../contributing/testing.md)

Status: implemented through SS8, 2026-10-19. Each executable slice was committed
with its validation record. See the [slice evidence](../history/shell-sessions.md)
for measured behavior, final OF816 packages and development scope. Release and
physical-hardware qualification remain separate.

The outcome is two independent resident shell Processes supervised by the
existing root Task: switched text/standalone bitmap sessions first, then two
tabs in one desktop Shell window. Each shell has its own console, directory,
PATH, aliases, history, draft, completion state, results and job. Shared services
and system-wide files/mounts/ASSIGNs retain their current ownership rules.
Separate shell windows require the follow-on backing/VRAM design described in
the design note; they are not an incomplete part of this plan.

## Decisions fixed for implementation

### User interaction

| Action | Behavior |
| --- | --- |
| `NEWSHELL` | Create and select a session in the caller's canonical directory, with default PATH/aliases and empty history/jobs. |
| `SESSIONS` | List at most two live session numbers, selected marker and creating/ready/closing state. |
| `SESSION number` | Select a ready session; reject malformed, stale or closing identities. |
| Ctrl+Shift+Space | Select the next ready shell, wrapping in creation order. With one ready shell, consume the chord without changing the draft. |
| `EXIT` / a tab's close control | Cooperatively close that session; select another ready session or perform ordered shutdown after the last one retires. |
| Desktop New Shell | Create in SYS: with the same defaults. |

Session numbers are monotonically increasing nonzero 32-bit identities, printed
in decimal. Do not reuse them during a boot or wrap on exhaustion. Two registry
slots do not imply that the visible numbers are always 1 and 2.

The Atari keymap in [console.json](../../abi/console.json) assigns Space scan
code 33; both modifier bits are already represented by INPUT. Recognize that
physical chord before console byte translation. Plain TAB remains completion;
desktop Ctrl+Tab/Ctrl+Shift+Tab and Ctrl+Escape retain their current meanings.
Only a captured route belonging to a registered shell console can consume the
session chord. Menus, dialogs and active mouse/title gestures retain their
existing input priority; unrelated AES clients do not lose the chord. Include
a physical modifier-release check before treating this binding as supported.

NEWSHELL waits for startup completion, but the controller's event loop remains
responsive while that request is pending. A failed create preserves the old
selection and reports the actual startup error. Parse errors use the existing
shell status/error convention; a missing session reports ERROR_OBJECT_NOT_FOUND,
a closing selection ERROR_OBJECT_IN_USE, and capacity exhaustion
ERROR_NO_FREE_STORE. SESSIONS writes to selected Output; diagnostics use the
invoking shell's retained console. Add all three names to the existing shared
command classifier/completion source. Keep them interactive-only: reject them
inside EXECUTE/startup scripts, RUN or pipelines before sending a request.

### Controller protocol and state

Add an application-owned shell controller module and one private shared type
include alongside the shell sources. Describe its message records in a new
`abi/shell-sessions.json` and generate the include and host layout constants
through a small generator. This is a resident application protocol, not a new
kernel, DOS or loaded COMMAND/C ABI.

The request envelope contains an Exec Message, BYTE operation, BYTE flags,
LONGCARD session, LONGCARD value, BYTE POINTER payload, CARD capacity,
LONGINT primary and LONGINT secondary. Use generated native offsets and size,
including the existing Exec Message definition; never duplicate host offsets.
Define operations CREATE, SELECT, QUERY, CLOSE and READY. A fixed two-entry
query buffer contains identity, console unit, Process identity, BYTE state,
BYTE selected and the two LONGINT result fields for each entry. CREATE borrows
a NUL-terminated canonical directory buffer of 256 bytes; READY identifies the
child and its setup outcome. SELECT/CLOSE carry the full session identity.

The sender owns each request and payload through exact reply collection.
The controller copies CREATE data into its owned startup record before spawning;
it never retains shell scratch after replying. Startup records contain the
identity, console unit, initial-directory text and first-boot/prime flags and
remain live through child retirement. Process argument text carries only the
eight-digit hexadecimal identity. Shell code resolves its own admitted startup
record; no raw DOS handle or lock crosses the boundary.

Use FREE → CREATING → READY → CLOSING → RETIRING → FREE. Initial failures enter
RETIRING without publishing READY. Keep Process completion and presentation
retirement distinct. Only root collects shell children, and a shell collects
its commands. A CLOSE reply acknowledges durable acceptance, not completed
retirement. Repeated CLOSE coalesces. Do not reuse a record while any request,
Process, key subscription, view or console reference can still reach it.

Use one controller request port and existing Process completion signals.
Retain at most one ordinary outstanding request per producer, plus the child's
independent READY message. Keep signal bits/ports and copied startup data in
upper RAM. The controller waits for the union of request, shortcut and child
completion events; it must not block its loop in PROCESS.Wait for one child.
Selection busy retries yield or wait for progress and continue collecting
other events. Do not add a polling Task or fixed-delay retry loop.

### Native console operations

Add these native console-library interfaces and their constants/records to
[console.json](../../abi/console.json) and its generator. They operate above
existing public Exec primitives and add no COP selector or loaded import.

| Interface | Required semantics |
| --- | --- |
| `CARD Activate(LONGCARD previous, next)` | Atomically replace one owned visible full-screen view with another, including its admitted pane association; preserve console I/O and foreground scopes. Text and standalone bitmap only. |
| `CARD RequestBreak(LONGCARD unit)` | Request durable cancellation of this owned console's currently bound foreground route/group, independently of display focus. |
| `CARD WatchKey(LONGCARD unit, CARD code, qualifiers, LONGCARD signalMask, KeyWatch POINTER watch)` | Register one exact physical-key subscription per instance, owned by its presentation owner, using a caller-allocated signal and stable upper-RAM record. |
| `BYTE TakeKey(KeyWatch POINTER watch, KeyNotice POINTER notice)` | Atomically consume one pending notice; return zero when empty. |
| `CARD UnwatchKey(KeyWatch POINTER watch)` | Withdraw the producer, clear pending notice state and release its Task/instance retention before returning. |

Use a distinct generated CONTROL result namespace: OK=0, BUSY=1, BAD_UNIT=2,
NOT_OWNER=3, UNSUPPORTED=4, BAD_LAYOUT=5, UNBOUND=6 and FAILED=7. These are
console results, not DOS IoErr. Validate owner/lifetime at admission; do not
walk handles or repeat checks inside drawing or cancellation loops. Unit zero
retains its current application-control rule; created units require their
creator. Callers must be ordinary Tasks with scheduling permitted where the
operation can wait for presentation.

Activate requires the previous view to be selected and the next view to fit
the full display, except unit zero may have its existing lower pane. Reject
unrelated visible tiles, incompatible dimensions and desktop mode before any
layout change. Same-unit activation is a successful no-op only when already
selected. A presentation conflict returns BUSY. Once admitted, retain both
views through the existing worker control/transaction path, settle borrowed
painting/DMA and publish visibility/focus together. Retained cells become the
source of redraw; OK means layout/focus committed, not final pixels displayed.
On pre-commit failure keep old logical selection and repair touched pixels;
unquiesced device failure retains storage under existing fault semantics.

RequestBreak resolves the unit and current route, validates its bound scope
and calls the existing bounded Notify fanout in one short Forbid region. There
is no wait or queued pointer to a scope, so scope retirement cannot race
delivery. Return UNBOUND if no live bound interaction exists; stale units and
foreign ownership fail without changing another scope. Repeated requests
coalesce. Pending cancellation must carry through an admitted foreground child
handoff/group join under the existing DOS rules. Never send byte 03 or borrow
whatever route happens to be focused later.

KeyWatch stores the established unit, code/modifiers, owner Task lease, wake
mask, bound/pending state and copied KeyNotice (unit, route and tick). The
worker latches a matching event and signals the owner in Task context; multiple
events while pending coalesce. TakeKey and producer publication serialize
without losing a wake. A watch retains its console until UnwatchKey, which is
required before destruction or reuse. Do not expose an arbitrary callback
executed from the console worker or make it wait for the controller. No event
is synthesized into the ordinary input FIFO. Register only the shell chord;
this bounded mechanism is reusable by another console owner.

### Desktop geometry and backing

Keep 64 by 20 console cells and the existing 512 by 160 backing surface. Add a
16-pixel native Shell tab strip between title and cells. The strip starts at
outer left + 8, outer top + 11 and is 512 pixels wide: two 240-pixel tab slots
and one 32-pixel New button. Reserve the rightmost 16 pixels of each occupied
tab for its close control. Clip labels to the remaining area and show the full
session number through SESSIONS. Empty slots have no select/close action.

The resulting fixed outer size is 528 by 189. Cells start at outer top + 27;
the existing eight-pixel console move alignment is preserved by the 16-pixel
addition. Put constants in desktop.json and make frame bounds, hit testing,
damage and rendering use them. Other native/AES work-area calculations retain
their current geometry. The existing Shell frame closer stays absent; the
explicit tab close names the session being closed.

The single backing image is tagged by console identity, geometry and content
generation. A switch retires its previous borrow, invalidates ownership and
rebuilds from the new console before exposing new pixels. Hidden consoles
update retained cells without rendering into another session's surface or
losing their own dirty state. Do not add a second backing bitmap or a VRAM
allocator for tabs.

## Resource and acceptance gates

Use the compiler in [actionc.json](../../toolchain/actionc.json), with recorded
ROM/emulator/configuration pins. Do not introduce a compiler override for shell
reentrancy; compiler defects belong in actionc with focused regressions.

The fixed budget is eight public Tasks, two shells and four console instances.
Root becomes a controller, so even the first shell now needs a separate Task.
For the standard SIO service set the base count is `4 + shell_count` (root,
console, filesystem, SIO and shells). Add prime, commands, desktop applications
and any extra transport workers explicitly:

| Selected workload | Required slots | Expected outcome |
| --- | ---: | --- |
| One shell, prime, two-command pipeline | 8 | Runs |
| Two shells, prime, one external command | 8 | Runs |
| Two shells, no prime, two external command Tasks | 8 | Runs |
| Two shells, prime, two-command pipeline | 9 | Clean admission failure |

The last successful row covers either one pipeline or one external command in
each shell. A ninth Task never starts. Publish a census for every shipped demo
variant; several current desktop/IDE peak workloads will need to report
capacity failure after the controller change. Keep applications/prime running;
do not silently disable them, preserve old peak claims, or expand Task pools.

For the same workload, add one Task to a current one-shell build's recorded
peak, or two when adding the second shell as well. Thus a current peak of 6
becomes 7/8; 7 becomes 8/9; and 8 becomes 9/10. Values above eight describe
rejected workloads, not new build capacities. SS4 must publish the selected
text, bitmap, desktop and IDE variant table before migrating their assertions.

Target **+0 fixed, +0 per-public-Task and +0 idle reserved bank-zero bytes**
through every slice, including guards, alignment and unused reserved capacity.
Report all upper-RAM allocations, resident code/static capacity and subscriptions
from emitted layouts; the design's 7,008-byte shell/editor/history sum is only
a starting subtotal. Tabs add zero backing VRAM. If a stack or reservation
must grow, record the actual delta and revise the checked platform budget
before advancing; zero is a target, not permission to omit needed storage.

Require at least **128 measured bytes above the protected stack floor**, in
addition to the existing 256-byte interrupt reserve, for each shell and the
controller in the selected deep scenarios. Exercise a shell in an ordinary
1,312-byte slot as well as a larger slot; do not make correctness depend on
obtaining slots 6–7. Combine lifetime-attributed watermarks with emitted frame
inspection because fill-pattern scans can miss unwritten frames. Preserve all
stack/domain guards and direct-page ownership.

## SS1 — make shell execution reentrant

Freeze the current source/pins and retain a standard completion/editing demo
baseline before changing execution. Reuse existing artifacts only where source
hashes match. Capture baseline stack observations and Task census with the
first affected fixture; no separate baseline-only commit is needed.

Move shell, aliases/count, script, job and mutable startup/helper scratch into
one ShellContext. Pass it explicitly through every include and completion,
redirection, parser and job helper. Replace implicit address assumptions in
fixture generators/observers with emitted layout data. Audit caller-side DOS
and formatting scratch for concurrent use; immutable constants and worker-owned
state stay shared. Introduce Task-to-context lookup only for a callback whose
signature cannot carry the established context, with bind/unbind lifetime rules.

Keep the existing single-shell entry using that same implementation. Add a
small two-Task fixture running the same resident code against distinct consoles
and overlapping reads/commands; two sequential calls do not prove reentrancy.
Cover separate aliases/PATH/status and temporary buffer contents across a wait.
Run affected shell/core/jobs/completion checks and generated-layout probes in
raw/optimized mode where layouts cross a host/language boundary. Record context
and stack deltas. Completion gate: both Tasks retain correct state after
preemption and cleanup, with no mutable global current-shell pointer.

## SS2 — add owner-requested foreground cancellation

Implement RequestBreak in CONSOLE/CONSOLEFOREGROUND, reusing the existing
Notify/Deliver semantics and generated CONTROL results. Keep physical BREAK
delivery on the same scope/group rules. Audit close races at prompt renewal,
foreground child adoption and pipeline publication; do not change Process
RequestStop to guess at unrelated console scopes.

Extend console/foreground fixtures for bound and unbound units, hidden target,
repeated requests, other-owner rejection, stale unit reuse, pending Read/file
I/O, inherited interactive input and two-member groups. Force retirement or
handoff immediately before/after admission. Cancellation may reach the same
admitted interaction through its child handoff, but cannot cancel a later
unrelated generation. Verify terminal I/O replies, cleanup and other-console
progress with VBI enabled. Update the console and foreground reference pages.
Completion gate: ordinary Tasks can cancel their owned console interaction
without UI focus, private DOS writes or a new kernel operation.

## SS3 — switch console views and migrate the prime pane

Implement Activate using one presentation transaction and existing worker
controls. Do not have the controller mutate driver records. Implement the
key subscription API and physical chord at the shared capture-consumption
boundary; preserve desktop input arbitration and unclaimed key translation.

Replace the global pane prohibition only for the admitted grouped activation.
Hide/show the unit-zero pane with its parent, preserving the parent's reduced
height. Hidden pane retirement restores its parent without erasing the active
view or stealing focus. Keep ordinary pane I/O/destruction with its Process.
At the DOS OpenPane boundary, reject a caller whose selected output does not
belong to the permitted unit-zero parent; do not let a second shell's PRIMES
claim unit zero merely because it is visible. Keep other layout conflicts busy
and retain one pane association. Update callers and the single implementation.

Use two console fixtures before controller integration: exact text cells,
retained drafts/caret, pending Read and paused ConsoleEdit, output during hide,
no-op/busy activation, captured-key/BREAK/loss boundaries and allocation/retire
failures. Exercise visible and hidden prime completion/close, plus a separate
bitmap pixel check. A watch must unregister cleanly with a pending notice and
cannot outlive its owner or wake a reused Task. Completion gate: the physical
chord notifies an owner while the reader is blocked, and grouped switching
preserves all I/O ownership. Record upper metadata, no additional worker, and
actual bank-zero reservation deltas.

## SS4 — run the first shell under the root controller

Implement the generated application protocol, controller loop and registered
shell Process entry, initially admitting one shell. Split one-time system
startup from shell session opening. Root performs boot configuration/service
setup and assignments; the first shell alone runs S:STARTUP/S:USER and the
optional prime launch. Retain existing recoverable first-boot disk errors and
fatal console-setup behavior. Before spawning, detach root's selected streams;
pass startup options by the immutable record, not inherited console handles.

Migrate demo, standalone shell and desktop entry callers to the new lifecycle;
DESKBOOT/DesktopStart/Stop remain controller-owned. Root names itself distinctly
from the shell Process. Publish READY only after setup/initial scripts settle;
startup EXIT can retire without a ready prompt. End the shell through ordinary
Process finalization, collect it and shut down in the existing service order.

Wire durable CLOSE and RequestBreak now. Check close before and after scope
publication, before blocking or dispatching, and at command/pipeline completion.
Do not let ClearBreak or a fresh prompt discard close. Cover the interval between
a close check and foreground handoff, including a group with partially admitted
children. Cancellation returning UNBOUND must not strand the next Read.

Run boot scripts, first-shell editing/completion, background prime, pipeline,
EXIT and setup-failure checks through this entry. Verify the eight-slot standard
pipeline, controller responsiveness during waits, non-root shell stack gate,
exact child collection and OS restoration. Completion gate: the normal initial
shell/prime experience and shutdown work under a supervising root, using one
current implementation and no compatibility entry path.

## SS5 — expose two independent text sessions

Enable the two-entry registry and NEWSHELL/SESSIONS/SESSION builtins. Register
the session chord for each unit and resolve notices against the established
session/unit binding; retired subscriptions cannot select a replacement.
Copy directory text, resolve in the child, publish the ready session and call
Activate before acknowledging successful create/select. If child setup succeeds
but presentation fails, unwind the newly created session and report failure;
do not leave an undiscoverable child. QUERY can observe CREATING/CLOSING without
borrowing another shell's mutable context.

Implement close/recreate, selected-session fallback and unit-zero reuse. Remove
input subscriptions before freeing or reusing units; settle presentation borrows
after Process collection. Before reusing unit zero, retire its old endpoints
and foreground scope and reset captured/translated input through the console's
normal reset path; clearing just the pending shortcut notice is insufficient.
Last-session retirement closes admission and enters
ordered shutdown. A closing noncooperative command retains its resources and
visible closing state while the other session/controller continue working.

Add `tools/test_shell_sessions.py` with independently selectable ownership,
startup, close, capacity, physical-text and standalone-bitmap cases and small
native fixtures. Verify separate current directories, PATH, aliases, history,
drafts, TAB, status and jobs; shared ASSIGN/file mutations; input redirection and
ordinary inherited CON. Switch while the first shell is blocked in each major
wait. Test all Task rows above, second-pipeline partial preparation rollback,
late close replies, failure at each creation allocation, and repeated reuse
with exact heap/Task/console recovery. Include the hidden prime pane and rejection
of PRIMES pane creation from the other session.

Completion gate: one shell can run a command while the other edits and completes
input; closing the first leaves the second usable; exhausted admission changes
neither. Build an OF816 text demo through tools/build_demo.py and exercise these
behaviors from its extracted ZIP, including five-second autoboot and final EXIT.

## SS6 — bind the desktop Shell view to a selected console

Keep one desktop Shell window. Replace unit-zero assumptions in DESKHOST,
DESKCORE, DESKPAINT, DESKMOVE, DESKSTATE and console desktop drawing with a
retained selected-console binding. Introduce a native desktop BIND_CONSOLE
control request carrying the existing window and target unit; only the window's
registered controller/console owner may submit it. Use the existing pending
request/reply path and BUSY/admission rules; do not call standalone Activate
from the console worker, which would wait on itself.

At the existing settled Layers/UPDATE/DMA boundary, remove the outgoing caret,
bind the destination view and retire backing ownership. Publish focus routing
with selection only when Shell is focused; changing its tab while another
application is focused must not take that application's keyboard. Carry console
identity through paint continuations, scroll work and backing completion checks.
Hidden output updates its own retained model and dirty generation. Rebuild the
selected backing before copying; old completion cannot clean the new owner.

Use the keyboard and SESSION command to switch content in the existing frame
before adding tab controls. Preserve 64 by 20 cells and the 40 KiB backing.
Test exact pixels/caret for covered windows, iconification, hidden output,
scrolling, delayed/failed DMA, close during a pending bind and an old completion
after a new selection. Existing AES focus, menus, UPDATE and window moves must
remain functional. Completion gate: one desktop console view safely presents
either independent shell with zero additional backing VRAM.

## SS7 — add desktop tab controls

Add the fixed tab geometry above and generate all shared frame constants.
Use existing presenter hit testing, release/loss cancellation, damage and message
delivery. A press captures the full session identity; release cannot act on a
replacement in the same tab slot. Pointer selection tops the Shell window through
normal desktop policy; closing an inactive tab leaves selected content focused.
The New button disables at two live/creating sessions, and busy/closing tabs show
their state without reading private shell fields.

Send CREATE/SELECT/CLOSE from controller-owned control messages; the presenter
never executes a shell command or waits for session cleanup. Coalesce duplicate
close gestures and bound pending UI work. Selection is acknowledged after bind
commit, with redraw still measured separately. Closing the last tab uses the
same controller shutdown path as EXIT, including other desktop app retirement.

Extend desktop presentation/input fixtures for geometry, blank/occupied slots,
click-release outside, focus changes, double/repeated gestures, stale identity,
loss, BUSY retry and closing while commands run. Check text cells, frame pixels,
tab hit bounds and caret placement independently. Run existing window cycling,
menu/drag/iconification cases plus a physical two-tab session walkthrough.
Completion gate: tabs and keyboard commands select and close the same session
objects without new window slots, Tasks or VRAM surfaces.

## SS8 — measure, document and package the final behavior

Freeze final source, compiler, ROM, emulator, video, media, workload and observer
inputs. Extend the focused runner to record exact Task/console/heap inventories,
per-lifetime stack headroom, emitted layouts and all reservation deltas. Compare
one-shell prompt/completion and command throughput to SS1's matched baseline;
separate the supervisor cost from output/backing work.

For text and desktop, measure 20 switches per direction at idle and 20 while
the hidden shell produces continuous output. Include a draft with a mid-line
caret, a long horizontal viewport, a covered/iconified Shell, cold backing
rebuild and switching during real disk I/O. Measure request-to-focus-commit and
request-to-correct-pixels/caret separately. Report median/p95, sampling resolution,
paint/copy work and samples of both sessions making progress. Record cooperative
close through prompt, active disk I/O and pipeline retirement separately; an
uncooperative fixture must remain retained without stopping its peer.

Functional gates are exact final model/pixels, no cross-session input or state,
bounded existing I/O/cancellation completion, no lost ownership, slot admission
and the 128-byte stack target. No numerical switching-latency promise is made
before these measurements. Publish observed limits and regressions; a missed
resource or correctness gate blocks completion rather than becoming an ignored
benchmark result. Full hardware/release qualification remains separate.

Refresh the standard OF816 shell/prime demo and the optional desktop package
with tools/build_demo.py. Keep one shell initially, five-second autoboot,
matching disks/ROM and notices. Verify extracted ZIPs and checksums; distribute
only boot files, guide, notices and checksums. Keep manifests, traces and build
intermediates outside the ZIP. Demonstrate two sessions, completion and close;
include the documented capacity failure followed by successful reuse after a
job stops. Recheck optional desktop/IDE Task census and update their advertised
concurrency rather than retaining old assumptions.

Update shell, console, foreground-break and desktop references/guides as their
slices land. Add final `docs/history/shell-sessions.md` and
`docs/development/shell-sessions.json` with hashes, actual selections, timings,
resources and remaining limits, and update their indexes and this plan's status.
Do not mark separate desktop windows implemented or claim hosted qualification.

## Validation discipline

Use the development tier after each executable slice: host suite, affected
generators with `--check`, focused optimized native cases and content/link checks.
Reuse and extend test_shell_core.py, test_shell_completion.py,
test_shell_jobs.py, test_shell_startup_scripts.py, test_console_windows.py,
test_foreground_break.py and test_desktop_presentation.py where they already
cover the affected boundary. The new session runner selects the missing cases;
do not duplicate the complete shell or desktop suite in it.

Use small raw/optimized probes for new message/console records and calling
conventions. Routine timing, integration and failure cases use optimized code;
raw builds diagnose a suspected compiler defect. Keep stack/domain guards,
IRQ/NMI coexistence and exact reply collection enabled. Record the actual
execution scope; passing compiler/host checks alone is never a session-system
qualification. This documentation-only plan requires content/link checks and
adds zero bank-zero bytes.
