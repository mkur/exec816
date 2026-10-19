# Multiple shell sessions implementation

[History](README.md) · [Design](../plans/shell-sessions-design.md) ·
[Implementation plan](../plans/shell-sessions-implementation-plan.md) ·
[Development record](../development/shell-sessions.json)

Implementation proceeds through SS1–SS8. This record distinguishes the
completed text, standalone bitmap and desktop console binding from the tab
controls and final measurements still planned. Separate desktop windows remain outside this plan.

## SS1 — explicit shell contexts

All mutable shell state now belongs to a caller-owned `ShellContext`. Shared
resident routines take that context explicitly: parsing, aliases, PATH,
completion, foreground dispatch, scripts, redirection, reporting and background
jobs use the same implementation for every caller. Existing entry programs
each supply one context; there is no shared current-shell pointer or callback
lookup. DOS selectors, errors and owned objects continue to belong to the
calling Task. Formatting scratch is local or borrowed from its shell context;
immutable names and service-owned worker state remain shared.

The private application schema and generator were introduced in SS1 so host
observers can use generated context offsets immediately. Small native probes
check the compiler's layout and nested pointer access in raw and optimized
builds. This changes neither the DOS/COMMAND ABI nor the Exec gateway.

The two-Task fixture uses distinct console instances. While the first Task is
blocked in the real console editor, the second changes its aliases, PATH,
directory and output; then their roles reverse. It checks retained status and
scratch, separate selected streams, exact cleanup and complete heap recovery.
Input injection is confined to this fixture's translated-key boundary; the
ordinary shell read and command routines remain in use.

Development checks include 498 host tests, 13 layout/access checks in each
mode, 39 optimized concurrent checks, 48 completion-matching checks, 182
filesystem-completion checks across RAM/MyDOS/SpartaDOS, and the physical
shell smoke test with exact echo, retained/physical screen and OS restoration.
The updated EXECUTE, append and alias instrumentation also passes native
interface analysis; that is a source check, not runtime coverage of those
complete scenarios. The optimized background-job fixture also passes, including loaded commands,
foreground execution, pipeline admission, cancellation, collection and cleanup.

The context occupies 24 upper-RAM bytes, replacing the same 24 bytes of
separate mutable globals. The shell's 2,612-byte payload, alias allocation,
cooked state and optional history allocations are unchanged. SS1 adds **0
fixed, 0 per-public-Task and 0 idle reserved bank-zero bytes**, including guards,
alignment and unused capacity. Task/stack/DP pools remain unchanged.

Against the retained completion baseline at `cad12ab3`, the matching and
filesystem fixtures each touch eight additional root-stack bytes. The new
concurrent fixture touches 384 bytes on root and 370 bytes on ordinary slot 3,
leaving 896 and 686 bytes above their 256-byte interrupt reserves. Both exceed
the plan's 128-byte headroom gate. These are observations of the exercised
paths, not worst-case stack proofs. All observed native guards pass.

The background-job fixture's old 4 KiB data arena overlaps resident code with
the current shared boot/fault text. Its test-only upper-RAM arena is now 8 KiB,
also accommodating its command strings and capacity Tasks. Production memory
reservations are unchanged. No compiler override is used.

SS1 preserves the existing single-shell product entry. User-facing creation,
selection, cooperative close and desktop tabs arrive in subsequent slices.
These development checks do not qualify the hosted system for release or
physical hardware.

## SS2 — owner-requested foreground cancellation

`CONSOLE.RequestBreak(unit)` resolves a console's current foreground scope
independently of focus and selected streams. Created consoles require their
creator; unit zero keeps its existing application-control rule. The native
CONTROL result constants are generated from the console schema, and the call
preserves DOS IoErr. It sends no input byte, allocates no storage and queues no
scope pointer. Bound-generation validation and the existing three-scope fanout
remain in one short Forbid region. Physical BREAK uses the same validation.

The optimized owner fixture passes 49 checks: hidden pending Read, rejection
even when the caller owns the DOS reader but not the console, repeated requests,
unaffected unit-zero output/scope, exact terminal request collection, renewal,
unbound/retired units, same-slot reuse, inherited interactive input and pending
cancellation carried into a foreground child. Cleanup recovers the original
heap and restores the OS display. The physical Ctrl-C/BREAK fixture passes 121
checks with the shared validation path.

The loaded pipeline fixture passes 68 checks. It requests cancellation through
the public API with full/empty pipes and active file I/O, and forces a barrier
before the second launch to exercise late group joining. It also covers pending
cancellation before group setup, both partial-launch failures, failed joining,
stale captured routes and continued progress by an unrelated Task. Both child
results and exact owned-memory recovery are checked.

The old pipeline expectation treated an intentionally successful early consumer
as an aggregate error; it now follows the existing documented success rule while
still checking the producer's retained ERROR_BROKEN_PIPE result. The affected
legacy fixture arenas were too small for the current shared runtime: these
tests now reserve 8 KiB of upper static data and place embedded command fixtures
in bank $3E, clear of resident code. These are test settings, not production
memory changes.

All 498 host checks and the console/context generator checks pass. SS2 adds
**0 fixed, 0 per-public-Task and 0 idle reserved bank-zero bytes**, including
guards, alignment and unused capacity. It adds no worker, console metadata or
per-request allocation. The native compiler, ROM and paced emulator pins remain
unchanged; this is development coverage, not a new release qualification.

## SS3 — grouped views and owned key notices

`CONSOLE.Activate(previous,next)` admits two owned full-screen views through
one existing presentation transaction. Worker controls erase the outgoing
view, settle physical borrows, and then publish visibility/focus and capture
routing together. Unit zero and its optional lower pane switch as a group.
Hidden output retains its own cells. A hidden pane can open, finish or close
without erasing another console or stealing focus; closure restores the
parent's retained full height.

`WatchKey`, `TakeKey` and `UnwatchKey` provide one bounded subscription per
console. The worker applies desktop arbitration first, resolves the captured
route, then copies a notice and signals the retained owner. It executes no
caller callback and inserts no ordinary input byte. Pending events coalesce;
withdrawal drops the notice and removes the producer before releasing its Task
lease. Both ordinary destruction and pane closure reject live watches. Shared
wake bits are left to the caller so withdrawing one watch cannot lose another
watch's notification.

OpenPane now requires selected Output to name unit zero, independent of display
focus. The standard demo therefore launches `RUN PRIMES >CON:`. Background
console output is allowed explicitly; background interactive input is still
rejected. This is a general stream policy change, with no PRIMES special case
or additional Process ABI. The shell jobs fixture covers the new output case,
and the pane fixture runs its child through StartBackground with inherited
unit-zero output and normal Process cleanup.

The text and standalone bitmap fixtures each pass 72 checks with physical
Ctrl+Shift+Space. They preserve a blocked read, mid-line draft/caret, paused TAB
continuation, modifier release and hidden output. Exact text cells and bitmap
pixels/caret are checked at seven stable selections, including hidden pane
closure and creation. Ownership, no-op/busy/bad-layout/stale-unit rejection,
pending-notice coalescing, unsubscribe and exact heap recovery are exercised.
The raw/optimized native record probes each pass 12 checks. A separate nine-check
lifetime case verifies withdrawal without a late wake and the guarded rejection
of owner removal while a watch retains unit zero. Existing console allocation
rollback/lifetime, pane, background-job and physical BREAK checks also pass.
The actual selected cases and pinned inputs are in the development record.

The console registry grows by 16 reserved upper bytes, from 880 to 896, for
four watch pointers including alignment. A caller supplies each 36-byte watch
and 10-byte notice; the API allocates no per-event memory and adds no worker.
SS3 adds **0 fixed, 0 per-public-Task and 0 idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. Console fixture arenas reserve
8 KiB of upper static data to fit the current shared runtime. Production Task,
stack and DP reservations remain unchanged. Physical scanout observations wait
for settled model/caret state and two complete bitmap frames; they are exact
pixel checks, not switching-latency measurements.

Shell controller integration, user-visible session commands and desktop tabs
remain for SS4–SS8. SS3 does not claim release or physical-hardware qualification.

## SS4 — first shell Process and root controller

Root now performs one-time service/mount/assignment setup, detaches its selected
streams, and starts the resident shell through ordinary `PROCESS.Start`. The
child resolves a copied startup record using its eight-digit identity argument;
no console handle or directory lock crosses that boundary. Only this first
child runs optional S:STARTUP/S:USER and launches the optional prime job. READY
follows startup completion, including script failure or EXIT. The controller
collects the shell, while the shell remains the owner and collector of its
commands. Text, prime, native desktop and GEM desktop entries use this lifecycle.
Optional desktop application startup failures still produce a console notice.

The generated private protocol adds a 40-byte message, 22-byte session query
entry, 44-byte two-entry query, eight-byte shared control and 266-byte startup
record. It changes no public kernel or loaded-command ABI. ShellContext grows
from 24 to 28 bytes for its stable control pointer. The two-entry controller
registry reserves 660 upper bytes, including two 36-byte key subscriptions;
its two shell contexts reserve 56 bytes and its temporary boot context 28.
A request and its payload remain sender-owned through exact reply collection.
The controller waits on the request port, shortcut signal and child completion
signals, also servicing root-owned desktop applications. Busy presentation
admission yields through the same loop. It adds no polling Task.

CLOSE sets a durable per-session flag before requesting cancellation of that
console's foreground scope. Shell code checks it before and after scope
publication, before dispatch and child admission, and before another blocking
read. Scope renewal cannot lose accepted close intent. Process completion and
presentation retirement remain distinct. The first-session slice admits only
one shell; interactive creation and fallback selection belong to SS5.

Development checks include 31 layout/access checks in each native mode,
50 controller checks for blocked-prompt and pre/post-bind close plus exhausted
Task admission, and 33 checks for close after foreground preflight and during
partial pipeline admission. They also cover startup
scripts and interruption, startup EXIT without prime launch, first-shell
editing and command execution, prime progress through BREAK, and desktop
input/EXIT. The controller fixture checks exact heap recovery across repeated
startup/close and failed admission. The standard packaged OF816 walkthrough
checks five-second autoboot, disk commands, pipeline completion, guards and
restoration using files extracted from the ZIP. A separate extracted run
observes eight live Tasks during a prime-plus-pipeline workload, cancels it
with physical BREAK, and verifies ownership recovery before HELLO and EXIT. The development JSON records
the exact cases, frame layouts, machine pins and runtime stack observations;
these checks do not constitute release or physical-hardware qualification.

The selected shell paths leave at least 407 measured bytes above the
protected stack floor in an ordinary 1,312-byte slot; controller paths leave
at least 828 bytes above their floor. Emitted frame metadata accompanies the
watermarks. All 498 host checks pass.

All existing bank-zero pools remain unchanged: **0 fixed, 0 per-public-Task
and 0 idle reserved bytes added**, including guards, alignment and unused
capacity. Each live shell consumes one of the existing public Task slots. The
standard SIO prompt therefore uses six Tasks with prime, and its two-command
pipeline uses all eight. The [variant census](../architecture/task-capacity.md#shell-controller-admission-budget)
also records rejected nine-Task desktop/IDE workloads; capacity remains eight.
Demo manifests distinguish requested peaks from admitted capacity. The shared
upper static arena grows from 7,168 to 8,192 bytes, preserving the existing
variant allowances. Desktop backing VRAM is unchanged.

## SS5 — two text and standalone bitmap sessions

The controller now admits two independent shell Processes. NEWSHELL copies the
caller’s canonical directory, establishes a hidden console, waits for the
child’s actual startup result, and selects it before replying. The new session
starts with default PATH/aliases and empty history/jobs. SESSIONS writes an
identity-sorted snapshot to selected Output; SESSION validates a full nonzero
32-bit number. These commands share the normal classifier/completion source
and are rejected in scripts, RUN and pipelines before a controller request.
Ctrl+Shift+Space uses the captured console subscription, including a closing
session whose command has not yet cooperated with cancellation.

Retirement collects the child and withdraws its subscription before selecting
a ready survivor and destroying the old created console. Failed CREATE replies
follow complete rollback, so the caller can immediately retry. Vacant unit zero
is reused only after its old endpoints and scope retire; normal open/reset plus
an explicit clear removes the old transcript. Identities increase through
FFFFFFFF and never wrap or name a replacement lifetime. A failed controller
exchange remains an operational shell error and does not close its caller.

Development checks pass 50 controller, 73 ownership, 14 closing-chord, and
109 allocation/failure assertions. The allocation fixture fails each of 16
creation allocations through READY publication and checks exact heap, Task,
console and selection recovery. A separate injected reply-port failure checks
that the invoking shell survives. The parser passes 582 assertions across 115
cases. All 498 host tests and the affected generated-definition checks pass.

The extracted standard text and standalone bitmap OF816 packages pass physical
walkthroughs for separate directory/PATH/aliases, drafts, mid-line caret,
TAB/history, shared ASSIGN/files, switching during real disk I/O, cancellation,
capacity rejection, survivor selection, repeated EXIT/recreation and unit-zero
reuse. The text run observes eight Tasks with prime plus one command, rejects
a second-shell pipeline while prime remains live, then runs that pipeline at
eight Tasks after stopping prime. The bitmap run observes seven and eight.
Additional extracted runs check redirected input and ordinary inherited CON
input while a peer remains usable, program-input exclusion from shell history,
and rejection of a prime pane on the second shell’s nonzero output console.
The bitmap guide was refreshed after the full walkthrough without changing its
native XEX; the inherited-input run exercises that refreshed ZIP. Preserved
manifests distinguish the exact artifacts used by each run.

SS5 adds four upper static controller bytes for the pending shortcut identity.
A created full-screen console allocates 1,352 upper bytes in text mode or 2,792
in standalone bitmap mode, in addition to the shell’s existing allocations.
The two-entry registry remains 660 bytes and its contexts 56 bytes. Each live
shell uses one existing Task slot; no worker or backing VRAM is added. All
bank-zero reservations remain unchanged: **0 fixed, 0 per-public-Task and
0 idle bytes**, including guards, alignment and unused capacity. Per-case
stack observations and emitted frame layouts are in the development record.
Desktop binding/tabs and timing measurements remain SS6–SS8. These development
checks make no release or physical-hardware qualification claim.

## SS6 — one desktop Shell frame, selected console binding

Native BIND_CONSOLE uses the registered controller’s existing control lane.
Root retains its pending destination record and collects the exact desktop reply
inside the ordinary shell event loop; a concurrent CLOSE cannot reuse that
record. The presenter commits a replacement only after Layers, UPDATE and DMA
allow it. It removes the old caret, retires gathered scroll reuse and backing
ownership, changes the retained console and route, then schedules a full redraw.
A bind preserves another application’s keyboard focus. Final retirement of a
created console binds permanent unit zero before releasing the created view.
Window CLOSE also resets the service binding, allowing unit zero to continue
servicing I/O after the former bound console is destroyed.

Painting, moving, focus, pending text and menu-cache invalidation now resolve
the bound console. Only that view can write the existing 512×160 backing image;
identity and presented model generation must match before copying it. Hidden
consoles retain dirty cells. The existing complete unit/view/model identity
checks protect scroll completion; binding resets view generations and rebuilds
the destination rather than adopting an outgoing image.

The raw and optimized layout probes each pass 114 checks. The presentation
fixture compares nine complete desktop rasters while switching, scrolling a
hidden console, retaining a covering window’s focus, hiding/showing and moving
the Shell. Additional physical input iconifies Shell before a bind and restores
it afterward. A replay of a retired source’s DMA completion leaves the selected
model and view unchanged. The ownership fixture passes 84 checks, including
CLOSE accepted during a held bind, subsequent retirement, repeated identity and
unit reuse, capacity failures and exact heap recovery. A close request may remain
CLOSING while a held paint prevents final console output; acceptance is distinct
from completed retirement.

The physical two-shell desktop walkthrough exercises NEWSHELL, SESSION, the
captured chord, separate drafts, repeated close/recreate, a surviving second
shell and last-created-console shutdown. It leaves at least 599 measured bytes
above the protected floor for the exercised shell lifetimes and 830 for root.
The nonzero-console watchdog cases preserve the old binding on a quiesced
failure and retain the active scroll, client and I/O on an unquiesced failure.
A backing scroll can own DMA without a Layers token; the fixture checks the
actual retained owner. Existing AES window and menu cases, the text ownership
regression, generated definitions and 498 host tests accompany these cases in
the development record. The text fixture now waits for every filler Process to
finish DOS adoption before taking its heap snapshot: an earlier snapshot could
count a later 32-byte reply-port allocation as a failed-CREATE leak.

The desktop Service record grows by four bytes to 18,722 (eight additional
allocated upper bytes after rounding). New scalar globals contain 11 payload
bytes; emitted static spans include their alignment. A full desktop console
allocates 1,672 upper bytes. No Task, window slot or backing surface is added;
the sole backing remains 40,960 VRAM bytes. Production arena capacities are
unchanged. The desktop shell fixture now reserves the production desktop’s
9 KiB upper arena instead of its old 8 KiB test-only limit. SS6 adds **0 fixed,
0 per-public-Task and 0 idle reserved bank-zero bytes**, including guards,
alignment and unused capacity. Tab controls and final measurements remain
SS7–SS8; these development checks do not qualify a release or physical hardware.

## SS7 — desktop tabs and cooperative close controls

The existing Shell frame now contains two fixed session tabs and New. The
presenter receives an 18-byte copied snapshot and sends full session identities
back to root. Root owns four bounded messages: create, select and one close per
slot. Duplicate close events coalesce independently of queued selections. A
press captures the identity, window and input-loss epoch; release outside,
Escape, loss, hiding, retirement or slot reuse cancels the action. Selection
raises and focuses Shell through ordinary desktop policy; an inactive close
preserves focus. New starts in SYS: and disables while both slots are occupied.
The last close drains event/content replies before the normal desktop shutdown.

Raw and optimized layout probes pass 124 checks each. The final physical tab
walkthrough compares four complete independent rasters and exercises empty
slots, New capacity, retained drafts, repeated inactive close, release outside,
Escape, an explicitly injected loss epoch, and release after the captured slot
has been reused. Four shell lifetimes use slots 3 and 5, whose cumulative
high-water headroom is 584 and 602 bytes above the protected floor; root retains
842 bytes. Native lifetime/bind cases pass 84 and 109 checks, including CLOSE
during a held bind, exact heap recovery, nine full rasters, physical iconification
and stale completion replay. The latter also rejects the old offscreen position
and checks a valid move with the taller frame. AES menu/window interaction and
the 73-check text ownership regression pass. The updated full presentation
fixture passes 117 checks and nineteen complete raster comparisons; 498 host
tests and generated
definitions pass. Case artifacts retain their exact source stage: the final
physical run includes the last lifecycle-publication and shutdown guards.

The Service record grows from 18,722 to 18,772 bytes (+48 allocated bytes after
rounding). A desktop-only 202-byte request block allocates 208 upper bytes and
shares the existing reply port. Keeping that block out of static storage leaves
the text ownership fixture at 8,085/8,192 bytes; the final desktop tab fixture
uses 8,641/9,216 bytes. No Task, window slot or VRAM surface is added. Reserved
bank-zero delta is **0 fixed, 0 per-public-Task and 0 idle bytes**, including
guards, alignment and unused capacity. Timing and final package measurements
remain SS8; these are development checks, without release or physical-hardware
qualification.
