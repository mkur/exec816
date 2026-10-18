# Multiple shell sessions

Status: implementation in progress, 2026-10-19. SS1 isolates the shell state and
SS2 adds owner-requested cancellation. SS3 adds grouped console activation and
owned key notices. Controller integration and desktop presentation remain. The
[SS1–SS8 implementation plan](shell-sessions-implementation-plan.md) defines
the remaining interfaces and gates; [slice evidence](../history/shell-sessions.md)
records actual checks without a hosted-system qualification claim.

[Plans](README.md) · [Implementation plan](shell-sessions-implementation-plan.md) ·
[Roadmap](../roadmap.md#commands-and-cli) ·
[Shell guide](../guides/shell.md) ·
[Console instances](../reference/console-windows.md) ·
[Task capacity](../architecture/task-capacity.md)

## Intended behavior

Support two independent interactive shells initially. Each has its own command
state, current directory, PATH, aliases, history, edited draft, completion state
and jobs. A command running in one session must leave the other usable, subject
to ordinary Task and memory admission. Hidden sessions keep running and retain
output within their existing console cell capacity.

Deliver switched sessions on the text display first, then tabs in one desktop
Shell window. Separate desktop shell windows use the same session model but
are a later presentation extension. Opening another view of the same session,
detaching tabs into windows, width reflow, scrollback, persistent sessions and
more than two shells are outside the initial scope.

This follows the Amiga Exec model of independent Tasks, owned messages, shared
devices and cooperative cancellation. A tab is presentation policy above those
services; it does not change scheduling or suspend a hidden Task. The bounded
session controller and fixed initial capacity are Exec816 application policy
chosen for its bank-zero stack/DP budget. No new kernel operation, scheduler
policy, compiler ABI or per-console worker is required by this design.

## Baseline foundation and gaps before SS1

| Area | Current behavior | Required change |
| --- | --- | --- |
| Console instances | Four slots: permanent unit zero and three created instances; independent cells, input, cursor and command routes. | Bind one instance to each shell; count the prime pane against the same capacity. |
| DOS contexts | Task-local streams, current directory, owned objects and IoErr. | Keep each shell in its own Task and use its own context. |
| Cooked input | Per-open session storage, shared through inheritance; one input lease per console endpoint. | Give each shell a fresh CON handle on its own instance; preserve child inheritance within that session. |
| Shell implementation | `shell`, `aliases`, `aliasCount`, `script` and `job` are resident module globals. | Move mutable state into a session context and make shared routines reentrant. |
| Boot lifetime | Root runs the shell; returning from it initiates application/service shutdown. | Root supervises shells and remains alive when any individual shell exits. |
| Text presentation | Owner-controlled Show/Hide/Focus; one docked pane blocks arbitrary layout changes. | Add an owned view-switch transaction that understands the existing pane association. |
| Desktop presentation | One `consoleWindow`, unit-zero route and fixed Shell backing bitmap. | Bind the tabbed window to a selected console; later support a binding per window. |

The relevant sources are [shell state and lifecycle](../../examples/shell/shell-session.inc),
[boot startup](../../examples/shell/shell-boot.inc),
[Process](../../lib/dos/process.act),
[console presentation](../../lib/console/consoletiling.act),
[desktop admission/focus](../../lib/desktop/deskcore.act) and
[desktop binding](../../lib/desktop/deskhost.act).
The current [ConsoleEdit contract](../reference/dos.md#resumable-console-editing)
already permits filesystem completion while a draft retains input ownership.
Switching presentation must not cancel or restart that continuation.

## Ownership and execution

The existing root Task becomes the session controller. It owns the bounded
session registry, creates additional console instances, owns presentation
requests and starts/collects shell Processes. It waits for requests and child
completion through ordinary Exec ports/signals. It performs no interactive
console Read and runs no shell command loop. The console worker continues to
own drawing and input delivery; filesystem and transport workers stay shared.

Each shell runs a registered resident entry through ordinary `PROCESS.Start`.
It opens its assigned `CON:XXXXXXXX`, selects its streams and establishes its
own foreground scope. Do not start it with `StartForeground`: that would loan
the controller's console and suspend its DOS context. Do not use
`StartBackground` as a substitute for an independent interactive session: its
unbound cancellation scope has different semantics. The controller's selected
streams must be empty before spawning, so no unrelated console is inherited.

Use a scalar session identity in Process argument text. The identity selects
a controller-owned startup record, retained until the child has consumed it and
ultimately retired. DOS handles and locks are never passed between Tasks.
The shell opens resources in its own context. Only the controller collects
shell Processes; each shell remains responsible for its own command children.

Move all mutable shell globals into one upper-RAM context, including job,
script and alias ownership and completion scratch. Pass that context explicitly
through shell helpers. Shared literals and code remain resident. Any callback
with a fixed signature must use an established Task-to-session binding; it
must not swap a global current-shell pointer around a call that can block or
be preempted. Audit included helpers, startup scratch and caller-side library
globals, distinguishing immutable data and worker-owned scratch from state
used concurrently by shell Tasks. Keep one implementation for both the first
and subsequent shells.

The registry separates controller-owned lifetime/presentation fields from
shell-owned command state. Publish requests and replies through bounded Exec
messages; retain each message and borrowed buffer until its exact reply. Session
identities must reject stale messages after a slot is reused. A durable close
flag may be shared under the existing Task-side synchronization rules; the
controller does not edit another shell's parser, DOS context or job record.

## Starting sessions and booting once

Boot configuration, hardware startup, initial mounts and the standard C:/S:
assignments remain one-time system work. Separate those operations from opening
an interactive shell. The first shell runs the existing S:STARTUP and S:USER
scripts once, then the optional prime demo. Opening another session does not
rerun those scripts or republish global assignments. Keep new-session admission
closed until initial startup has settled. A future per-session startup hook
would be a separate feature.

Proposed user commands are `NEWSHELL`, `SESSIONS` and `SESSION number`: create
and select a shell, list sessions, and select an existing session. These are
shell builtins backed by controller messages. Desktop New Shell and tab clicks
use the same controller operations. The implementation plan fixes their names
and error behavior; they are not current commands.

NEWSHELL snapshots the invoking shell's canonical directory name into the
request. The child resolves that path into its own lock; disappearance or
unavailability is a startup failure, not a silent switch to SYS:. This copies
a path value, not the identity of a live directory lock. Desktop creation with
no invoking shell starts in SYS:. PATH and aliases start with the existing
defaults; history, draft, status and jobs start empty. Copying arbitrary PATH
and alias settings is outside the initial scope.

Creation proceeds as a reversible admission: reserve a session record, create
the hidden console when needed, start the child, and wait for its ready report.
Publish the selectable tab only after console/DOS/foreground setup succeeds.
On failure collect any started child before destroying its console and freeing
the record. Keep the old session selected and report the normal resource or
startup error. Do not wait for an occupied Task slot to become free while
holding partial creation indefinitely.

Track creating, ready, closing and retiring states in the controller. Waiting
for readiness or retirement is part of its event loop, so another session's
switch/close request can still progress. Coalesce repeated close requests and
reject selection of a retiring session. Publish terminal creation failure only
after its owned resources have been reclaimed or explicitly retained on fault.

First startup uses unit zero, preserving the existing boot display. Later
sessions use created units. After a unit-zero shell exits, retain the permanent
instance without a shell binding; reuse it only after all old references and
routes settle and its retained input/output have been reset. A visible session
number is not a console unit or reusable Task-slot identity.

## Session state and shared system state

Current directory, selected streams, PATH, aliases, history, draft, return
status and the existing single background-job slot belong to the shell.
Foreground commands and pipelines inherit from that shell through the current
[Process ownership rules](../reference/process.md). Closing or redirecting one
session's handles cannot change another's selections.

Files, mounted volumes, RAM: and [ASSIGN mappings](../reference/assigns.md)
remain system-wide. A MOUNT, UNMOUNT or ASSIGN performed in one shell affects
new resolutions in all shells, subject to existing resource retention. Directory
completion continues to observe live namespace changes and ordinary enumeration
errors. There is no private filesystem namespace or independent copy of media.

Shared filesystem/transport workers still serialize their work. Independent
shells provide concurrency and input access, not parallel disk bandwidth or
process memory protection. Existing corruption and caller-ownership assumptions
are unchanged.

## Focus, switching and presentation

The switch action belongs to the input/presentation layer and must work while
the selected shell is blocked in Read, a filesystem call or a child wait.
Recognize the shortcut before cooked editing, then send a selection request to
the controller. Plain TAB remains completion. Desktop Ctrl+Tab and
Ctrl+Shift+Tab retain their existing window-cycling meaning. The plan selects
Ctrl+Shift+Space from the Atari key mapping, with physical modifier checks
required during implementation. GUI tabs and the SESSION command remain
explicit selection paths.

Publish selection at a settled presentation boundary. Retain both source and
destination instances while removing the old caret, changing visibility and
publishing the new focus route. Draw the destination from its retained model.
Failures before commitment preserve the old selection; admitted asynchronous
drawing retains storage through retirement. Do not expose a sequence of
uncoordinated Hide/Show calls as the session switch.

The console library needs an owner-authorized activation operation for this
bounded view transition. It must be reusable by ordinary console owners and
implemented with existing console presentation transactions and public Exec
primitives. Specify its exact signature and failure boundary in the plan;
do not add a shell-specific kernel service or let the controller bypass driver
ownership by mutating instance records.

Each instance keeps its current foreground route while hidden. Only keyboard
capture selection changes. Keys and BREAK captured before publication retain
their original route/generation; queued input is never reassigned to the new
session. Switching preserves pending Read, ConsoleEdit ownership, history
browsing, draft and logical cursor. Input loss stays attached to its captured
route. IRQ code continues to capture scalar route identities, with delivery in
Task context and the existing IRQ/NMI publication protocol.

### Text and standalone bitmap sessions

Use the existing console dimensions and switch the visible view. No extra
physical screen or width reflow is needed. The first text milestone can use
keyboard selection and session numbers without reserving a tab row. A desktop
tab strip is a later front end, not a requirement for independent shells.

The standard prime pane must be handled in the same milestone. Initially retain
one output-only pane associated with unit zero. Switching away hides that pane
with its parent; switching back restores both at their retained dimensions.
The prime Task continues while hidden. Pane close while hidden still restores
the parent's full height, preserving its draft and later view geometry. It
must not activate that parent or disturb the currently selected shell.

This requires migrating the current global pane exclusion to explicit handling
of the admitted parent/pane association. The controller may switch the parent's
view as a group; the prime Process keeps ownership of pane I/O and retirement.
That association authorizes the grouped presentation change, not arbitrary
control of another Task's console. RUN PRIMES in another session cannot claim
the existing unit-zero pane; report unsupported/busy before changing layout.
Do not silently retarget it. Additional panes remain outside the first slice.

### Desktop tabs

Use one native Shell window and bind it to the selected session identity and
console unit. Replace the fixed unit-zero route pointer with the selected
instance's established route. Window focus and tab selection are separate:
selecting a tab chooses the content; keyboard routing follows it when the
Shell window has focus. A tab click activates the window through normal desktop
policy. Hidden sessions must never draw into the selected session's bitmap.

Reuse the existing 40,960-byte Shell backing surface. Tag it with console
identity, geometry and content validity. On selection change, invalidate it and
rebuild from the destination's retained cells before presenting those pixels.
Damage from hidden output must remain attributable to its console until that
console is rendered. Retain the backing owner through DMA; neither an old
completion nor exposure repair may mark the new session's pixels current.
The tab strip belongs in window chrome outside the console's fixed 64 by 20
cell area. Its geometry and hit testing must agree with painting.

### Separate desktop windows

Later, bind each native console window to its own session/unit and let the
existing desktop choose the focused window. Generalize console admission,
focus, caret, exposure and lifetime bookkeeping per window. Use existing Layers
and presenter scheduling rather than adding a presenter Task per shell.

Start with fixed console geometry. The six desktop window slots are shared
with Files, other applications and the desktop itself. Multiple windows also
need an explicit backing policy: dedicated bounded surfaces or regeneration
from retained cells with cache ownership. The single fixed Shell surface cannot
be reused as though it holds every window simultaneously. Freeze the VRAM map
and measure exposure costs before selecting that policy in a later design.

## Closing, cancellation and shutdown

EXIT closes only its shell, including cooperative stop/collection of its job
and normal DOS cleanup. A close control sets a durable request on that session,
then interrupts its current foreground interaction so that it can reach cleanup.
The shell checks the close flag before dispatching another command or acquiring
a new prompt; acknowledging ordinary BREAK must not clear the close request.

There is an API gap to resolve explicitly: `PROCESS.RequestStop` does not stop
a plain resident Start with an independently created foreground scope. A signal
alone also does not create durable DOS cancellation. Add a reusable native
console operation for the console owner to request BREAK on that instance's
currently bound route. It captures and retains the route generation, then uses
the existing scope/group cancellation delivery in Task context. It never
targets whichever session happens to have focus later. Define no-bound-route
and retirement results; the durable close flag handles startup and scope gaps.
No synthetic input byte, private scope-pointer write or new kernel gateway is
an acceptable substitute. A close of a pipeline must reach its current group.

Check the close flag both before scope creation and after publishing a new
scope, before entering a blocking operation. Once that scope is published,
owner-requested BREAK supplies the durable wakeup. This ordering must cover a
close arriving between the initial check and route publication; an unbound
BREAK result alone must not leave the shell asleep in its next prompt.

The controller posts close before requesting cancellation. The shell settles
the current exact I/O reply and foreground children, cancels a paused editor
continuation if necessary, stops its background job, ends its scope and closes
owned DOS resources. It then returns through Process finalization. The
controller collects it, retires its view, destroys a created console after all
references and presenter borrows are gone, and releases session storage.
Storage with outstanding ownership is retained on failure.

Cooperative close can remain pending on a noncooperative command. Show that
state and keep other sessions usable; do not force-remove the Task or free its
stack, buffers or console. A close of an inactive session must leave the active
one focused. Closing the selected session selects another ready session.
Closing the last shell enters the existing ordered demo/desktop shutdown and
OS restoration path; session creation stays closed once shutdown begins.

## Capacity and memory

Two shells are the initial application limit, not a promise that every workload
fits. The console service's four-instance ceiling includes unit zero and the
prime pane. Two shells plus that pane use three instances. Desktop window
capacity and route capacity remain independent admission limits.

The controller uses the existing root Task, but moving the first shell out of
root costs one additional live Task even with only one session. Each shell
retains a Task slot while waiting. Count this change explicitly; do not budget
only the second shell.

The standard SIO profile has three shared workers: console, filesystem and SIO.
The following are design arithmetic for the proposed controller, based on the
current [demo composition](../guides/demo.md), not execution measurements:

| Workload | Public Tasks |
| --- | --- |
| Controller + workers + one shell | 5 |
| Above + prime + two-command pipeline | 8 |
| Controller + workers + two shells | 6 |
| Above + prime + one external command | 8 |
| Two shells, no prime, two external command Tasks | 8 |
| Two shells + prime + two-command pipeline | 9: rejected by the eight-slot build |

IDE workers, desktop application Processes and other jobs must be counted for
their selected profile. Finished but uncollected children still occupy their
reserved slots. Existing Process/pipeline admission must fail cleanly and
release partial preparation. Do not stop other jobs or quietly increase Task
capacity to make NEWSHELL or a command succeed. Recheck startup script workloads
and emitted shell stack margins in the non-root slots before shipping this
lifetime change. Keeping the first shell in root would save one slot, but would
couple controller progress to its blocking DOS waits and complicate independent
closure; this design accepts the explicit supervisor cost.

The [completion record](../history/shell-completion.md#resource-costs) provides
the current starting costs: 2,616 rounded shell bytes, 1,152 alias bytes,
416 cooked bytes and 2,824 optional history bytes, totaling 7,008 bytes before
allocator bookkeeping, DOS objects and console storage. New context fields,
messages, startup records and controller metadata need emitted accounting.
Text cells at 40 by 24 need 960 bytes; desktop cells at 64 by 20 need 1,280,
with input, dirty-state and presentation metadata additional. These are upper
RAM costs. There is no executable copy per resident shell.

The initial target is **0 fixed, 0 per-public-Task and 0 idle additional reserved
bank-zero bytes**, using existing pools and including guards, alignment and
unused capacity. This documentation change itself adds zero. Reusing slots
consumes capacity even when reserved bytes do not grow. Any required stack
enlargement or new capacity profile must be reported and justified separately
under the [platform budget](../reference/platform.md#bank-zero-memory-budget).
Desktop tabs target zero additional backing VRAM; separate windows have no
approved VRAM budget yet.

## Implementation boundaries and evidence

The subsequent plan should establish reentrant shell execution and controller
lifetime, then two physical switched sessions including the prime pane, then
desktop tabs. Separate windows follow after selecting their backing policy.
Use small executable slices; keep the single-session path on the same code.

Development checks must exercise optimized emitted code and include:

- Independent directory, PATH, aliases, history, draft, completion and status;
  shared files/ASSIGN changes; inherited foreground CON and ordinary TAB input.
- Switches during prompt editing, paused completion, file I/O, command output,
  pipeline waits and hidden output; exact retained cells, caret and pixels.
- Capture immediately before/after focus publication, routed BREAK and input
  loss, stale session messages, route reuse and session recreation.
- Startup/allocation/admission rollback; first shell closing while the second
  stays alive; active/inactive close; close while a command/group owns input;
  final collection, heap recovery, guards and OS restoration.
- Pane output/close while its parent is hidden; no focus theft or draft loss;
  clean rejection of a second unsupported pane.
- Eight-slot boundary cases and non-root shell stack observations, including
  completion, scripts, pipelines and cleanup. Record actual Task populations.
- Desktop backing replacement with delayed DMA, old paint completion and
  covered output; tab clicks, existing window shortcuts and background repaint.

Measure switch request to correct destination text/caret, redraw work and input
latency under continuous hidden output on frozen compiler/ROM/emulator/media
inputs. Include cold backing rebuilds and contended I/O; report sample counts
and remaining limits before selecting performance targets. Extend focused raw
and optimized ABI probes only where new generated layouts or bindings require
them, following the [testing policy](../contributing/testing.md).

Any demo refresh uses tools/build_demo.py with OF816, the five-second autoboot
and standard initial shell/prime behavior. Test the extracted distribution,
with one session initially and a second created interactively. Record the
actual supported command concurrency instead of implying that eight Tasks
permit two arbitrary simultaneous workloads. Full release and physical Atari
qualification remain separate.

The [implementation plan](shell-sessions-implementation-plan.md) fixes the
message schema, native control interfaces, Ctrl+Shift+Space chord, desktop tab
geometry and stack-headroom gate. Each selected build still needs its emitted
layout and measured Task/stack census. The ownership, two-session limit, root
controller, per-shell Task and staged presentation choices above are the
proposed design baseline.
