# Remove Terminal's idle session polling

[GEM plans](README.md) · [Signal separation](terminal-wake-plan.md) ·
[Measured baseline](../../history/terminal-wake.md) ·
[Baseline evidence](../../development/terminal-wake-tw2.json) ·
[Console views](../../reference/console-views.md) ·
[Testing policy](../../contributing/testing.md)

Status: TP1–TP3 complete; TP4 measurement/delivery remains. See the [implementation record](../../history/terminal-idle-polling.md).
Starting source/tool baseline `50522ac3`, runtime `4ff5c3e6`, console-view version 4 and APP ABI 37.
Commit this plan and each passing executable slice separately.

Make an unchanged, healthy Terminal sleep until real work arrives. After startup
and pending hints drain, it must issue no periodic `SESSION_QUERY`, perform no
periodic directory scan and arm no periodic timer. Cell output, session changes,
console discovery, selection, retirement and shutdown must still progress.

## Starting evidence

Signal separation removed the reply feedback loop. The same eight repaint
actions still contain 38 completed Terminal timer waits/45 root replies in idle
and 63 timer waits/70 replies under Counter/disk load. While the viewer is ready,
Terminal/root combined CPU is 134.9 ms per idle repaint and 184.1 ms loaded,
plus 29.0/63.6 ms of IRQ execution during their selected intervals. These costs
include legitimate work; they are not a predicted saving.

The frozen package is `build/terminal-wake/demo/exec816-demo.zip`, SHA-256
`84ae2ab3e36bf831f0f99bb0ed7263f02af85506746f3721a1ab841bc22e6a01`.
Reuse its baseline captures only after checking the relevant hashes and inputs.

## Notification coverage that must be completed

[TerminalPlatformRefresh](../../../examples/gem-terminal/platform.c) currently
queries `Shell.sessions` and copies the console directory on every loop turn.
Its wait always includes a 100 ms timer. Existing cell subscriptions report
cell/cursor/mode/route changes and source closure, but cannot discover a newly
created source without an existing subscription to it.

| Change | Current publication | Required directory hint |
| --- | --- | --- |
| Created console becomes LIVE | [CONSOLE.Create](../../../lib/console/console.act) publishes the initialized registry entry | After LIVE/unit/geometry commit, including a source with no cell subscriber |
| Unit leaves the live directory | Destroy/RetirePane and [default driver lifetime](../../../lib/console/consoledriver.act) publish RETIRING | After live removal; preserve existing CLOSED cell notifications |
| Exposed geometry changes | [ResizeLocked](../../../lib/console/consoletiling.act) publishes the model | After supported geometry commits; desktop resize remains unsupported |
| Frontend activation request | [CONSOLEVIEW.Activate](../../../lib/console/consoleview.act) changes requestedUnit/activationSerial | After a successful accepted request; preserve activation serial semantics |
| Session creation, READY/failure, closing, collection, selection/fallback | [Shell controller](../../../examples/shell/shell-controller.inc) owns the returned session scalars | After actual query-visible state commits, before replies that expose the change |
| Controller port withdrawal | ShellControllerQuiesce removes the port and replies queued requests | Wake Terminal before root waits for frontend retirement |

Desktop `ShellSessionSelect` changes `selectedSession` directly; it does not call
full-screen `CONSOLE.Activate`. Console activation alone therefore cannot cover
session selection. Window focus and ordinary cell writes are not session
directory changes. Do not increment activationSerial for unrelated metadata.

## Chosen service and ownership

Add an independent directory watch through the existing three-ULONG
`ExecConsoleView` library bridge. It must work before the caller has any cell
subscription and remain live after the last cell handle is released. Admission
still requires an admitted console service; this is not a watch on a stopped
or uninitialized backend.

Proposed operations in [console-view.json](../../../abi/console-view.json):

| C helper | Operation/arguments | Result |
| --- | --- | --- |
| `ExecConsoleViewWatchDirectory(mask)` | 11, allocated caller mask, 0 | Opaque nonzero watch handle, or zero on admission failure |
| `ExecConsoleViewTakeDirectoryChange(handle)` | 12, handle, 0 | 1 if pending, consuming that flag; otherwise 0 |
| `ExecConsoleViewUnwatchDirectory(handle)` | 13, handle, 0 | Normal OK status after withdrawing the producer |

The watch covers changes to the frontend's metadata: console discovery/geometry,
activation and the session directory used by Terminal. It is an invalidation
hint, not a combined snapshot or an event count. Ordinary consumers can use the
console directory alone; Terminal also queries the separate controller port.
Copied snapshots remain authoritative. A racing update can require another
refresh; no cross-service atomic snapshot is introduced.

Implement the watch policy in [CONSOLEVIEWCORE](../../../lib/console/consoleviewcore.act)
and admission/dispatch in the console-view facade. Use a private heap record
containing next pointer, retained Task lease, mask and pending flag. Use existing
AllocMem/RetainTask/Signal/ReleaseTask/FreeMem operations. Keep a separate bounded
list of **four directory watches**, sufficient for Terminal plus three peer
observers; preserve all eight existing cell-subscription slots. Report the
emitted record size and maximum heap cost. Do not enlarge a fixed arena merely
to reserve this optional capacity.

Registration atomically installs the retained recipient and starts with
`pending=1`, posting its mask once. This closes the initial-read/subscribe race.
A Task-side metadata publisher commits its state, then sets pending under the
same short Forbid guard and signals a newly pending watch. Further changes
coalesce. Task retention keeps the recipient live; the caller keeps its signal
allocated until Unwatch completes. No interrupt handler follows these records.
Forbid coordinates Tasks; existing IRQ/NMI stack and switching protocols remain.

Take atomically reads/clears pending **before** the consumer queries metadata.
It never clears the shared signal bit. A change during or after the query sets
pending again and leaves a wake for the next wait. Query, Directory, Take,
cell Pending/Snapshot/Acknowledge, painting and unchanged controller turns must
never publish directory hints. This prevents another query/reply feedback loop.

Unwatch removes publisher access under the guard before releasing the Task lease
and freeing storage. Include directory watches in the existing Active/ActiveOutside
service-stop checks. Keep them independent of instance destruction: destroying
one unit must not require dropping the directory watch. Root withdraws its
session port, drains/replies queued requests, posts the shutdown hint, then waits
for Terminal; Terminal unwatches before freeing its notification bit.

Reuse Terminal's existing view notification mask for directory hints. The
retained pending flag identifies metadata work even when cell and directory
hints coalesce on that bit. Keep synchronous replies on their separate port bit.
Add no Task, signal bit, kernel selector, private gateway or new message protocol.

Advance console-view version to 5 and APP ABI to 38 as a capability fence;
regenerate definitions and rebuild all APPs. The existing 92/76/42-byte public
packets, operation numbers 1–10, 130 APP import ordinals and bridge signature
remain. An older provider must reject the new APP before an unknown watch
operation's status could be mistaken for a handle. Keep one supported ABI.

## TP1 Implement the retained watch and public bridge

Add the bounded watch list, admission/initial hint, Take, Unwatch and an internal
Task-side `DirectoryChanged` publisher. Add generated constants and C inline
helpers; update the current console-view/APP contracts and capability versions.
Terminal continues its existing timer/query behavior in this slice.

Extend [test_console_view.py](../../../tools/test_console_view.py) and its small
emitted probe for raw/optimized C/Action bridge coverage. Test bit 31, two
independent consumers through all three real bridge operations; layout-only or
stub-only checks do not establish this path. Also test
admission before any cell handle, initial hint, repeated
Take, coalescing, zero/unallocated mask rejection at admission, capacity and
allocation/lease rollback. Exhausting directory watches must preserve all cell
slots. Verify retained Task lifetime, shared-signal preservation, unwatch before
bit reuse, exact heap return, stack/domain guards and EXIT. Do not add per-event
ownership revalidation or protect arbitrary stale caller handles.

Force publisher changes before Take, between Take and snapshot, and between the
final read and Wait. The consumer must not sleep past an unobserved change.
Pure reads/Take must not create further hints. Regenerate/check definitions and
run host checks. Record source/artifact hashes and memory costs.

Commit: `feat(console): add retained directory change watches`.

## TP2 Wire real publishers and admit Terminal's watch

Implement every row of the producer table. Mark controller metadata dirty only
when public session fields change; coalesce notifications at a complete state
commit. Publish before an affected synchronous reply can schedule its caller,
and flush changes before root sleeps. Do not notify after every controller step
or QUERY. Audit both successful and failed creation paths; a committed rollback
or retirement must leave a final hint for an already visible intermediate state.
Use the notification core from controller/registry publishers so text and
standalone console paths do not acquire a dependency on the AES facade.

Register Terminal's directory watch in Open after allocating its existing wake
bit and before the first metadata query. A watch failure rolls back Open through
the established supervised startup failure path. Retain the current timer and
query behavior temporarily while proving publication coverage. Close unwatches
and unsubscribes all cell producers before clearing/freeing the shared bit.

Use optimized emitted integration cases with a directory consumer that blocks
without a timer. Exercise actual source/session mutations, not a test-generated
signal to the consumer: silent creation with no cell subscriber, READY/failure,
selection and fallback without output, activation without output, retirement
and slot reuse with a new unit epoch, and port withdrawal while Terminal sleeps.
Test two consumers and mutation while a consumer owns UPDATE. Directory handling
must not require a physical draw grant or hold scene ownership while querying.

Verify service Stop rejects a live external watch and succeeds after withdrawal;
view retirement and watcher teardown must not leak Task leases. A stable session
QUERY loop must leave directory pending clear. Run the existing real Terminal
keyboard/session/modal-close scenario and focused host checks. Use raw mode only
for the small changed private-layout/bridge probe, not these full scenarios.

Commit: `feat(terminal): receive console and session directory changes`.

## TP3 Gate metadata refresh and remove the healthy idle timer

Terminal consumes the directory flag before deciding whether to query. Only an
initial/forced refresh, a consumed metadata change or an explicit user action
may refresh `Shell.sessions` and the copied console directory. Reuse those owned
scalar snapshots for ordinary cell wakes, redraws and retry turns. Do not cache
mutable service pointers. Cell snapshot/revision/acknowledgement rules remain.

Force the existing metadata refresh boundaries around session actions and modal
close; a successful local action can set a caller-owned dirty flag. A cached
session identity or unit must never be silently retargeted to a replacement.
Unit zero remains live when its bitmap bit is set.

Healthy waits request AES messages/buttons and the existing notification mask,
without MU_TIMER. Keep 100 ms retries only for explicitly outstanding work:
failed cell-subscription admission or an incomplete selected-view copy/paint
that has not settled. Retry from cached metadata, processing a newly pending
directory hint first; a retry tick alone must not issue SESSION_QUERY. Clear the
retry reason on completion/closure. An inactive view's unacknowledged revision
does not by itself justify a retry timer. Watch admission failure is a startup
error, not a permanent timer fallback. Bootstrap uses the initial watch hint.
Each retry expiry permits one bounded attempt; it must not enter a tight retry
loop. Capacity may remain unavailable, so this is bounded work per retry rather
than a promise of eventual admission. No retry timer runs without an outstanding
failure reason.

Extend the focused Terminal probe and real integration checks for these decisions:
cell-only wakes produce no session query; coalesced cell/directory hints refresh
both; spurious/stale bits cause at most a bounded drain; metadata mutation during
refresh remains pending. Force cell-capacity exhaustion and later release, BUSY
and mixed-generation copies, and recovery. Selected output must resume, retry
must not query unchanged metadata, and the timer must turn off after recovery.
Preserve hidden-view behavior, selection/activation, cancellation and shutdown.

Add a quiescent interval after startup/hints drain, with an unchanged Terminal
behind the viewer: require zero Terminal timer arms, session queries and console
directory scans. Query/reply must not manufacture MU_EXEC. Separately drive real
output and silent metadata changes and observe the expected wakes; do not infer
notification correctness from eventual pixels with a timer fallback.

Commit: `perf(terminal): sleep until view or directory changes`.

## TP4 Measure and deliver the same viewer workload

Build with `tools/build_demo.py --gem-desktop --release-compiler`, retaining
OF816, matching pinned ROM, five-second standard shell/prime autoboot, writable
combined SYS, MD5/ARC/EDX/overlays/notices and the boot/guide/licenses/checksums-only
ZIP. Audit the exact package. Use the pinned compiler and machine recorded in
the baseline; document any override rather than mixing observations.

Repeat the current idle and Counter/disk viewer scenes, four page/four line
actions each, with identical-package untraced companions. Extend the existing
observer only for directory Watch/Take/publication, Terminal timer-arm reasons
and SESSION_QUERY counts; freeze it before the cohorts. Existing before traces
lack the new directory metrics: reuse them for matched CPU/latency comparisons,
and measure the new zero-polling properties directly. Capture a small unchanged
baseline for any new metric that needs a before value.

Require zero timer-only SESSION_QUERY and no healthy idle Terminal timer, with
real metadata events counted separately. Report root/Terminal CPU and IRQ while
the viewer is ready, viewer CPU, ready/blocked budgets and completed-repaint
distributions. The before medians are 808.645/832.666 ms idle page/line and
1426.533/1566.368 ms loaded. Do not predict a gain from all remaining peer time.
If latency does not improve, document that result and stop this optimization
without adding a second drawing/scheduling change to rescue it.

Keep all current pixel, no-op, drawing-work, heap, ownership, stack/domain,
Counter progress, persisted disk bytes and EXIT gates. Require exact relative
edges/gaps/counters in observation/replay after at most one recorded global
clock-origin alignment. Repaint completion remains IRQ-observed dirty clear
after fences/END_UPDATE, separate from scanout. Retain the documented late
paints-counter-store interpretation; use actual drawing counts as the oracle.

Add history and machine-readable development evidence, update this plan/indexes,
and provide the new launcher/ZIP paths. QED and full qualification are separate.

Commit: `test(terminal): measure event-driven idle behavior in the demo`.

## Resource and completion gates

Target reserved bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 idle and
0 per public Task bytes**, including guards, alignment and unused capacity.
Compare complete `bank_zero_budget`, `task_pools` and `runtime_reservations` maps.
No extra Task or signal bit is planned. Report separately the private watch
record/Task-lease heap cost, four-watch upper bound, list bookkeeping, Terminal
handle/retry fields, code growth and observed stack changes. Check actual emitted
layouts and allocation rounding. Target upper-memory/VRAM reservation growth is
zero; justify any reservation increase before adopting it.

Completion means reliable metadata publication, zero steady-state polling,
bounded explicit retries, verified startup/teardown and measured delivery with
documented latency results. Keep controller supervision, normal preemption,
UPDATE/scene ownership, drawing limits and stream/device policy. These are
development checks; they do not qualify the full hosted system or hardware.

The initial documentation-only slice changed all guest reservations by zero.
Executable slice validation and memory comparisons are recorded in the implementation record.
