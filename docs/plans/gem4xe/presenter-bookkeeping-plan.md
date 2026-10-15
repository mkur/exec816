# Presenter scheduling and bookkeeping implementation plan

[GEM plans](README.md) · [Caller-local UPDATE record](../../history/caller-local-update.md) ·
[Baseline measurements](../../development/presenter-bookkeeping-baseline.json) ·
[AES contract](../../reference/aes.md) · [Layers contract](../../reference/layers.md)

Status: implementation in progress. [Execution record](../../history/presenter-bookkeeping.md).
Implement PB1–PB6 in order, committing each executable slice separately. Reuse the existing baseline; there is no preliminary benchmark slice.

Reduce the CPU work surrounding drawing so that windows appear sooner and the
presenter returns to a safe caller-local UPDATE opportunity sooner. Start with
redundant calls and repeated checks, then remove the extra visibility rebuild
during window opening. Keep the existing policy gate and ordinary preemption.

## Baseline and scope

The passive analysis used unchanged demo packages before and after caller-local
UPDATE. The compact baseline records their hashes, machine configuration and
observer inputs. Detailed local captures are in `build/presenter-cost-analysis`.
The current package is the PB baseline; the older package also provides the
uncached-close recovery target.

| Current New Window operation | Calls | Presenter CPU ms |
| --- | ---: | ---: |
| Runnable and readiness checks combined | — | 67.7 |
| Visibility rebuilds | 3 | 33.6 |
| FindTask(NULL) in native drawing dispatch | 33 | 18.7 |
| ReplyMsg | 14 | 17.9 |
| INPUT.Take | 38, including 36 empty reads | 10.5 |
| Cache maintenance | 7 | 10.4 |

These inclusive costs overlap. The complete New Window sample takes 1,063 ms
elapsed and 431 ms presenter CPU; about 104 ms of that CPU charge is inside the
observed drawing-dispatch paths, including their bridges and fences. These are
individual matched observations, not latency percentiles or hardware results.

Uncached close regressed from 401 to 461 ms. Presenter CPU rose from 207 to
244 ms, including a readiness-check increase from 40.6 to 60.3 ms. Total
`DESKPAINT.Pump` CPU stayed near 43 ms. Extra service passes and repeated checks
are therefore a priority, alongside the cost of opening a new window.

The presenter sleeps when settled. Its gate is closed during active turns;
one New Window turn took 88.5 ms CPU over 221.5 ms elapsed. Two observed
notification-only turns cost 2.5 and 5.1 ms CPU. Shortening these turns can
improve local UPDATE availability without changing priorities or gate ownership.

Preserve the following throughout:

- One presenter, current admission/paint budgets, normal preemption and existing
  display/scene ownership. Do not add long Forbid sections or widen paint batches.
- Existing BEGIN/END semantics, RPC fallback and eligible-waiter ordering.
  Keep the outer local END notification and gate-waiter wake unchanged.
- Input capture, acceleration, loss handling, retained AES input, pointer
  presentation opportunities and the final signal-to-Wait protocol.
- Current rendering, VRAM allocation, cache validity and application preservation
  contracts. A scheduling hint never certifies cached pixels as current.

Task priorities, narrower policy-gate ownership, kernel message/reply changes,
new renderer batching and the previously reproduced Windows-menu focus failure
under Counter load are separate work. In particular, the measured ReplyMsg cost
does not justify adding a private presenter kernel service.

## Slice sequence

| Slice | Result | Focused evidence |
| --- | --- | --- |
| PB1 | Trusted native drawing dispatch without repeated task lookup | Zero dispatch identity queries; unchanged pixels |
| PB2 | Cheap readiness predicates and fewer repeated scans | Lower readiness CPU and call counts |
| PB3 | Input boundaries consume real pending work | Empty-read reduction; no lost or delayed wake |
| PB4 | Cheap cache maintenance when nothing changed | Shorter notification-only turns; correct captures/restores |
| PB5 | One visibility rebuild for opening a prepared window | Exact visibility, stacking and exposure |
| PB6 | Matched application measurements and refreshed demo | Recorded costs, latency, pixels and progress |

### PB1 Remove the per-dispatch identity query

Primary file: `lib/console/consolebitmap.act`.

Audit production callers of `CONSOLEBITMAP.Run` and document its existing
presenter-only contract at the entry. Remove its `FindTask(NULL)` comparison
and the resulting unused service lookup. Keep binding availability, device
failure handling, operation status and completion ownership checks.

Do not replace the query with a second cached-task comparison on every call.
Worker identity and lifetime remain established at service initialization.
Existing diagnostic callers must obey the same contract.

Check the emitted routine for absence of the task lookup. Use one focused
optimized drawing observation covering frame, text/fill, cursor and asynchronous
copy completion; reuse the existing window observer where possible. Require
unchanged final pixels and normal shutdown. No new test is needed just to mirror
the removed comparison.

Commit: `Remove repeated presenter identity checks from drawing dispatch`.

### PB2 Reduce readiness bookkeeping

Primary files: `lib/desktop/deskhost.act`, `deskinput.act`, `deskmenu.act`,
`deskpaint.act`, `deskwidgetinput.act`, and `lib/console/consoledriver.act`.

Replace compound value-return expressions with explicit early returns where
only the presence of work matters. In particular, a menu with no pending change
must return before calling native/display readiness and lock helpers. Preserve
any required side effects; only pure queries may be skipped.

Review the worker's pre-cache and scheduling tail together. Reuse boolean results
between adjacent checks when the relevant state has not changed. Re-evaluate
after input/control admission, painting, cache transfer startup or settlement
that can change the answer. Use a few local scalars and the existing helpers,
not a global scheduler snapshot or a second ready queue.

The policy gate does not freeze interrupt producers, incoming messages or an
already admitted application's physical drawing. Do not retain their false
readiness results across operations that can let those sources advance. Preserve
durable signal delivery at the final Wait boundary and the local BEGIN queue
check; a cached hint must never authorize a mutation or display borrow.

Checks: one matched close/New Window observation, plus the affected existing
UPDATE handoff cases for pending requests, blocked painting and wake-before-Wait.
Observe predicate call counts and CPU, not just total elapsed time. Require
lower readiness work, zero settled idle turns and continued request completion.

Commit: `Reduce repeated presenter readiness scans`.

### PB3 Stop forcing empty input reads

Primary files: `lib/desktop/deskinput.act`, `deskhost.act` and
`lib/console/consoledriver.act`.

Keep the existing input boundaries after control admissions and paint steps,
but stop passing `DESKINPUT.Mask()` as if each boundary received a new signal.
Service already retained input until an actual empty read; replay queued AES
input independently of fresh hardware notification.

At active boundaries, use the registered presenter's received-signal bit as a
cheap read-only hint. Only when set, acknowledge that input bit with the existing
`SetSignal` operation and feed the returned bit into input service. The initial
worker Collect result remains an input source. Do not add `INPUT.Pending()` or
an unconditional kernel call at every boundary, and do not write task signal
fields directly. Resolve the presenter Task once through its existing lifetime.

A late signal remains pending for the next boundary or Wait. A nonempty drain
keeps the existing continuation hint when its budget is exhausted. An empty read
clears only that local hint; it must not erase a concurrently delivered signal.
Preserve move/button ordering, loss delivery and applying acceleration once.

Use a small optimized emitted boundary case for input arriving after the signal
hint, during the drain, and between empty observation and Wait. Also cover a
budget-exhausted drain and retained input becoming eligible after MCTRL release.
Reuse existing pointer/button and desktop input fixtures rather than a new
transport harness.

Acceptance: empty reads follow real drain attempts, rather than every service
boundary; pointer/button response under active drawing does not regress. Do not
replace frequent servicing with once-per-turn input handling.

Commit: `Avoid forced empty input reads at presenter boundaries`.

### PB4 Make idle cache maintenance cheap

Primary files: `lib/desktop/deskhost.act`, `deskcache.act`, `deskmenucache.act`
and the worker's notification-only branch.

Use existing state to reject a no-work pass before expensive readiness and
visibility queries: the two repair records, each window's visual revision and
capture attempt, and the popup key/attempt. Call patch processing only for a
ready repair. Avoid searching both repair slots for every unrelated window.

Share the settled decision from PB2 where no intervening operation invalidates
it. Keep the physical-display/scene checks required immediately before starting
a transfer, and re-evaluate scheduling if one starts. Cache maintenance remains
limited to one new transfer per eligible pass and yields precedence to input
and visible repair.

Use the current revisions and attempt records; do not introduce another cache
validity protocol or a persistent scheduler-wide dirty map. An occluded candidate
may remain eligible for a future attempt, but must not keep the presenter awake.
Maintain the existing behavior when it becomes visible or finishes painting.

Keep every successful outer local END notification. The optimization is a cheap
no-work path after that notification, without weakening gate or waiter wakes.

Checks: unchanged UPDATE followed by idle; acknowledged local edit followed by
patch/restore; hidden edit followed by exposure; previously occluded candidate
becoming visible; and dropdown save/restore. Reuse the existing preservation and
keyboard observers. Require current pixels, no repeated capture/eviction loop,
and sleep after completion. Aim for at most 2 ms presenter CPU in the matched
notification turn that starts no maintenance; record any remaining excess.

Commit: `Skip unnecessary presenter cache maintenance work`.

### PB5 Prepare window stacking before showing it

Primary files: `lib/display/layers.act`, `lib/desktop/deskstate.act`,
`lib/aes/aeswindow.act`, and the Layers reference/tests.

Prepare bounds and final stacking while an opening window is hidden. Place an
ordinary window immediately below the menu-bar layer, leaving the popup above
the bar and the desktop below application windows. Then Show once and publish
focus/window state against the final visibility. Handle reopening an existing
hidden window as well as a newly created window.

Add a small reusable `LAYERS.OrderBelow(scene,id,anchor)` operation, sharing the
existing reorder implementation where practical. Hidden reordering changes no
visible regions or damage; shown reordering retains normal invalidation and
rebuild semantics. Keep existing live-ID, background and active-transaction
rules. Desktop code must not edit Layers arrays directly.

Use this placement for AES opening. Keep `Create`'s hidden-at-front contract and
existing `Order` callers intact. Borderless desktop opening retains its bottom
placement. Normal Focus must find the menu layers already ordered, avoiding
another rebuild. Publish no intermediate visibility and do not defer rebuilding
across a public call, callback, gate release or drawing transaction.

This adds one ordinary Layers operation, not a generic Begin/Commit mutation
framework, another region buffer or a new kernel ABI.

Extend the small optimized Layers scene oracle for hidden placement, shown
placement, no-op ordering and transaction exclusion. In the packaged New Window
case require one rebuild inside the AES open request, unchanged final stacking
and hit testing, one initial content paint, and exact close exposure. Dropdown
dismissal has its own legitimate rebuild and is measured separately.

Commit: `Prepare hidden window stacking before rebuilding visibility`.

### PB6 Measure application results and refresh the demo

Integrate only the needed passive markers from the local presenter analysis into
the existing observers. Preserve compact before/after records under
`docs/development`; keep raw traces and binaries under `build`. Record counts,
presenter CPU, off-task time and interrupts separately. Distinguish an active
presenter turn from a CPU scheduling quantum or time spent asleep.

Use one final optimized demo build for these focused observations:

| Observation | Required comparison |
| --- | --- |
| New Window and uncached close | First frame, complete window, pre-BEGIN delay, readiness CPU, rebuilds and drawing calls; exact pixels and one initial paint |
| Settled Files selection and Shell/SYS focus switching | Local UPDATE/fallback counts, unchanged selection/summary pixels and preserved cache restores |
| File/View dropdown switching | Warm restore behavior and no duplicate application redraw |
| Short dialog and repeated text run | Local BEGIN/END success, presenter gate occupancy and cost of notification-only turns |
| Small Counter plus console-output case | Input feedback, queued-client progress and eventual completion of background output |

Reuse existing matched baseline traces. Start with one focused replay; use three
matched samples when timing phase or PAL-frame sampling makes the result
ambiguous. Do not claim p95 from these small samples or rerun the full benchmark
and qualification matrices after each slice. The known Windows-menu focus issue
remains separately recorded; use the established direct focus route for load
measurements.

Acceptance requires zero identity queries in native drawing dispatch, fewer
empty input reads and readiness checks, one open-request visibility rebuild,
and lower measured bookkeeping CPU in the matched window operations. Recover
the uncached-close regression toward the earlier approximately 401 ms result
while preserving the current dialog/Files gains. If that latency objective or
the quiet-turn objective remains unmet, report it as open and identify the
remaining measured cost; do not broaden this work into scheduler changes.

Refresh through `tools/build_demo.py`: include OF816, the five-second autoboot,
matching system disk, pinned ROM, licenses, checksums and `exec816-demo.zip`.
Provide the launch command with the resulting demo. Add an execution record and
update the plan/index/roadmap status with the actual checks and limitations.

Commit: `Record presenter bookkeeping gains and refresh the demo`.

## Memory and validation limits

All slices target zero additional reserved bank-zero bytes, fixed and per Task,
including guards, alignment and unused pool capacity. Task stacks and direct
pages retain their reservations. Use existing upper-RAM records and small local
scalars; report code size, any upper-RAM growth and observed stack headroom per
slice. No new Task, signal, VRAM reservation, heap queue or permanent region is
planned.

Follow the [development testing tier](../../contributing/testing.md): affected
host checks and focused optimized emitted behavior. PB3 needs targeted input
race coverage; PB5 needs independent scene/visibility checks. Raw/optimized
duplication is needed only if an actual compiler-facing change is introduced.
Documentation-only preparation requires content and link checks, not a build.
