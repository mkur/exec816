# Caller-local AES UPDATE implementation plan

[Analysis](caller-local-update-analysis.md) · [GEM plans](README.md) ·
[AES contract](../../reference/aes.md) · [Layers contract](../../reference/layers.md) ·
[Testing policy](../../contributing/testing.md)

Status: UL1–UL2 complete; UL3–UL4 pending. Implement UL1–UL4 in order,
with a separate commit after each executable slice. The physical-bridge
measurement and UPDATE analysis are preparatory records; keep implementation
commits scoped to their slice.

The preceding [binding cleanup](../../history/aes-binding-cleanup.md) removes
duplicate context queries and repeated direct-entry endpoint audits. UPDATE
still uses RPC; shared policy is implemented in UL1. Use the cleaned binding for the UL1
baseline.

## Objective and limits

Let `wind_update(BEG_UPDATE)`, `ExecAESBeginUpdate(window)` and
`wind_update(END_UPDATE)` execute the existing native AES policy in the calling
Task whenever the presenter has published a safe opportunity. Successful local
operations make no UPDATE request/reply exchange. Contention and unavailable
safe points retain the existing RPC path.

Keep one lock policy and the current nesting, window scope, implicit/explicit
mouse ownership, paint-journal and cache semantics. MCTRL stays RPC-based.
Preserve eligible-waiter ordering and the existing owner's recursion/upgrade
exception. Ordinary and parameter-block GEM calls reach the same implementation.

Use one private policy gate and the existing AES signal. Keep normal preemption,
physical renderer arbitration, rendering batches and cache contents unchanged.
No new kernel operation, signal allocation, Task, client waiter queue or generic
semaphore. Trust admitted bindings and caller-owned pointers; keep the required
state transitions and existing public error results without another validation
layer.

## Common handoff contract

The gate protects AES/presenter metadata only while BEGIN/END policy executes.
It is released before application drawing starts. It does not reserve the
display or prevent an already admitted client from using the blitter during
unrelated presenter CPU work.

Use three private states, initially closed:

| State | Meaning |
| --- | --- |
| Closed | Presenter owns its policy turn, or startup/retained work/shutdown prevents local admission. |
| Available | Presenter has left protected code at a safe boundary. |
| Caller | One client is executing bounded native UPDATE bookkeeping. |

Add one presenter-waiting flag. Gate changes and waiter publication use short
Forbid sections. The snapshot/cache work runs outside those sections, preserving
any inherited caller Forbid nesting. IRQ/NMI never reads or writes this gate.

The presenter claims Closed before the worker loop condition, signal collection
or any subsequent shared GUI-state access. If Caller is observed, publish its
waiting flag, wait on the existing AES service bit and retry. Preserve other
input/display/stop bits for normal processing; do not poll them while parked.
Gate release publishes its state before notifying a parked presenter.

At the end of a turn, compute the wait/yield/continue decision and native
readiness while still Closed. Only then may the presenter publish Available.
After publishing it, execute only the selected scheduling action or reclaim
Closed before any shared-state access. In particular, the next loop condition,
`DESKPAINT.Ready`, cache pump and stop checks must not run past that boundary
without reclaiming the gate.

Availability requires the current readiness contract: no retained scene token,
console fragment/DMA, non-idle gathered batch or visible drag outline, with
window/input publication settled. Evaluate owner-side `DISPLAY.Blocked()` only
from the presenter. Pending queues are checked again by local BEGIN under the
claimed gate; a queued peer must not be bypassed because `lockCount` has not
yet reflected its message.

A client may claim only Available. A miss makes no lock/depth/journal changes.
After claiming, execute the common policy without drawing, waiting, callbacks
or asynchronous work. Release the gate on every completed or rejected attempt,
including failures requiring RPC fallback. Local outer END sends one existing
AES wake signal after retiring its journal; combine this with any gate-waiter
wake. Other local operations signal only if the presenter parked on the gate.
Notification requires no reply, but ordinary scheduling may still switch Tasks.

## Slice sequence

| Slice | Executable result | Main evidence |
| --- | --- | --- |
| UL1 | One reusable native UPDATE policy, still reached through RPC | Existing semantics and focused lock coverage |
| UL2 | Presenter gate and safe boundaries, public UPDATE still RPC | Controlled handoff/preemption/wake tests |
| UL3 | Local BEGIN/END with RPC fallback | ABI, ownership, journal/cache and lifetime checks |
| UL4 | Measured application behavior and refreshed demo | Matched timings, fast-path counts and package smoke |

### UL1 — Share the native UPDATE transitions

Primary files: `lib/aes/aeslocks.act`, `aeswindowstate.act`, the lock fixture and
its focused runner in `tools/test_aes_server.py`.

- Separate request decoding and pending-request queue management from completed
  acquire/release transitions. Both future entry paths must use the same
  native helpers; retain the current RPC behavior in this slice.
- Keep first-BEGIN snapshot/cache initialization, nested depth publication,
  synchronous final-END paint accounting and mouse snapshot publication in
  those helpers. Preserve the outer scoped/all-window choice.
- Keep operational errors and TRY semantics at their existing boundary. Do not
  remove guards or alter painting to make a performance result easier to reach.
- Address the previously recorded standalone lock-fixture timeout before using
  it as evidence. Repair fixture coordination if that is the cause, or select a
  small deterministic emitted fixture covering the same affected semantics.
  If a production bug is exposed, record and fix it explicitly.

Before the first production edit, retain one matched preemptible parent build
for UL4. Use an existing image only if its recorded production inputs match;
the older demo containing the preemption experiment is unsuitable. Capture the
small idle dialog/Files sequence defined below. This is part of UL1 preparation,
not a separate baseline project or qualification matrix. Reuse that build and
capture for the final comparison.

Checks: focused optimized lock behavior for recursion, TRY, wrong-owner release,
overflow, MCTRL overlap and eligible queue ordering; retain cleanup and stack
guards. Run the host suite after the coherent code change.

Acceptance: unchanged RPC-visible results, shared policy ready for a second
execution context, and a passing focused lock fixture with its scope recorded.

Commit: `Share native AES UPDATE policy between admission paths`.

### UL2 — Publish safe presenter handoffs

Primary files: `lib/aes/aesstate.act`, `aeshost.act`,
`lib/console/consoledriver.act` and `lib/desktop/deskhost.act`.

- Add the private gate and waiting flag. Close admission throughout startup,
  retained conflicting work and shutdown; never free the service with a caller
  still executing policy.
- Integrate presenter claim/release around the entire protected turn, including
  continuation adoption, input/control handling, scene/model work, settle,
  cache maintenance and all readiness queries in the scheduling tail.
- Compute scheduling decisions before publication. Cover the loop condition,
  all `EXIT`/stop paths and error cleanup as part of this change.
- Add the nonblocking client claim/release helper, exercised by a test Task.
  Public `wind_update` continues to use RPC until UL3.
- Keep waiting on the existing AES signal. A caller publishes release before
  waking the parked presenter; pending wake delivery must survive the final
  check-to-Wait interval. Preserve unrelated wake bits.

Use a small optimized emitted fixture with controlled scheduling at these
boundaries:

| Boundary | Required observation |
| --- | --- |
| Presenter passed a paint/readiness check but has not begun mutation | Client cannot claim the gate. |
| Available published, presenter has not yet waited/yielded | Exactly one side claims; presenter rechecks before continuing. |
| Client owns the gate and is preempted | Presenter parks; another ordinary Task and interrupts can progress. |
| Release before/after presenter waiting-state publication | Presenter resumes without a later unrelated event. |
| Input/display wake already pending | No retry loop; events remain available after gate reclaim. |
| Retained scene/DMA/batch/outline or shutdown | Local admission stays closed; existing completion/stop work advances. |

Acceptance: no shared-policy overlap or missed wake, no new long Forbid section,
no physical display reservation around the presenter turn, and no idle polling.
Use test-only markers/hooks for forced boundaries; leave them out of production.

Commit: `Add safe presenter handoff for caller-side AES policy`.

### UL3 — Enable local UPDATE calls and preserve fallback

Primary files: `c/calypsi/aes.c`, the resident C/Action bridge and startup binding
generator, `lib/aes/aeslocks.act`, plus the relevant focused AES fixtures.

- Bind one internal native UPDATE entry using the established library bridge
  convention. Pass the admitted request/binding; keep native service layouts
  private. Reuse the existing bounded client lookup instead of adding a new
  handle/registration scheme.
- Return a private handled/fallback indication, separate from the GEM Boolean
  and AES diagnostic. A handled TRY failure is not fallback. On fallback,
  release the gate and restore the context's transient busy state before
  invoking `ExecAESSubmit` with the original operation/flags.
- Preserve the cleanup's single caller-context lookup per public UPDATE
  operation, including scoped BEGIN and parameter-block dispatch.
- Mark the context busy while direct policy executes. Advance local depth only
  after a successful result, once, for either path. Preserve inherited Forbid
  nesting and all C/native register, DP and stack conventions.
- Local BEGIN respects both admitted waiters and older service-port requests,
  subject to the existing owner's recursion/upgrade exception. A gate miss
  never becomes a new GEM error. TRY keeps its flag on RPC fallback.
- Local END consumes the current paint journal completely before returning,
  clears only the corresponding hold, and sends the outer-END wake. Keep
  MCTRL calls on RPC. Local calls do not advance the transport sequence;
  later RPCs remain consecutive at both ends.
- Keep native input eligibility publication and cache begin/end processing
  synchronous. Do not replace END with an asynchronous journal pointer or
  introduce another journal buffer.

Run a small raw/optimized ABI probe for the new bridge only. Use optimized
behavioral checks for:

- Successful local pairs and forced fallback in both mixed combinations:
  local BEGIN/RPC END and RPC BEGIN/local END.
- Nesting, TRY, MCTRL overlap/upgrade, scoped versus all-window updates and
  ordinary `aes_call` dispatch.
- Two competing clients, an older request not yet admitted, pending native
  output, and owner release/exit. Other Tasks must keep making progress.
- Visible and hidden edits, empty/unreported updates, immediate journal reuse,
  reported paint failure and cached re-exposure; an untouched scoped sibling
  must retain its cache eligibility.
- Normal close/detach/stop, intact guards, restored context and no retained
  Tasks or policy owner. Existing renderer faults keep their recovery contract.

Measure application stack headroom through the relocated native snapshot/cache
work, including the bounded maximum supported owned-window case. Keep stack
checks enabled. Increase the relevant stack reservation if needed and report
the full per-Task bank-zero cost rather than restructuring the GUI solely to
avoid a justified increase.

Update current AES/Layers ownership documentation: one serialized policy
implementation now executes in either the presenter or a caller. Prefer no
wire/import ABI change; if a shared layout actually changes, regenerate it and
rebuild clients without a compatibility mode.

Acceptance: a controlled eligible BEGIN/END pair makes zero UPDATE messages,
all shared state and pixels agree with the RPC path, and contention still uses
the original queue with no held policy gate across a reply wait.

Commit: `Execute uncontended AES UPDATE in the caller`.

### UL4 — Measure real use and refresh the demo

Extend the existing passive GUI tracing only where needed to observe local
entry/return, gate claims and fallback reasons. Keep diagnostic counters/hooks
out of production. Record separate misses for presenter execution, retained
native work, ownership/gesture conflict and earlier pending requests.

Use the frozen UL1 parent and final optimized build on matching compiler, ROM,
emulator, PAL/CPU, media, geometry and pointer inputs. Keep the workload bounded:

1. The existing three-batch idle dialog capture, separating BEGIN, END, complete
   UPDATE pairs and complete dialog time. This is bookkeeping attribution, not
   an input-latency percentile.
2. One fixed Files initial-paint and selection sequence in an uncovered window,
   followed by cover/expose restoration. Count drawing and UPDATE work as well
   as visible completion; include scoped updates and the unchanged summary line.
3. One short concurrent sequence with visible Counter, Shell output and pointer
   input, checking continued progress and recording fast-path misses. Reuse
   relevant UL3 functional evidence; do not repeat a full desktop test matrix.

Report caller CPU, presenter CPU, interrupts, off-Task time, elapsed completion,
local/RPC counts and paired BEGIN/END success rate. Native policy moving into
the caller is not eliminated CPU. Whole-application time, including fallback
cost, is the primary outcome. Keep original command/pixel counts so reduced
work cannot masquerade as cheaper ownership.

Acceptance:

- Controlled eligible pairs always avoid both exchanges. In normal settled
  idle application drawing, the fast path serves most complete pairs and
  reduces measured UPDATE and application completion time.
- If the conservative gate still sends most idle pairs through RPC, identify
  the missed safe boundary and refine that boundary before claiming completion;
  do not silently replace this plan with fine-grained locks or relaxed safety.
- The focused concurrent sequence shows progress, correct input and cache
  restoration. Investigate a visible latency regression; the benchmark alone
  does not establish UI responsiveness or a new input p95.
- No acceptance target requires removing the policy work or eliminating normal
  scheduling. Do not compare the candidate directly with the obsolete
  non-preemptible package or promise recovery of all historical off-Task time.

Build the final preview with `tools/build_demo.py --gem-desktop --release-compiler`.
Include OF816, five-second autoboot, matching system disk, pinned ROM, notices,
guide and checksums. Run one focused boot/application/EXIT smoke on the exact
package and provide its launch command. Keep traces/intermediates in `build/`;
distribute only the normal `exec816-demo.zip` contents.

Save compact results and hashes under `docs/development/`, a measurement record
under `docs/history/`, and update the relevant indexes/roadmap. Record actual
development coverage without claiming full release or hardware qualification.

Commit: `Record caller-local UPDATE performance and refresh demo`.

## Resource and validation budget

Target **0 additional fixed, per-public-Task and idle bank-zero bytes**, including
guards/alignment/capacity. The policy state and bound entry live in upper RAM;
no VRAM allocation is added. Report actual upper state/code growth and reserved
bank-zero delta after every implementation slice. Stack increases, if required
by UL3, are explicit exceptions with measured justification and per-slot costs.

Use the pinned compiler and platform inputs. Run host checks for coherent code
changes, focused emitted tests for the behavior changed in each slice, and
content/link checks for documentation-only follow-ups. Raw mode is confined to
the small new bridge probe or a compiler-defect reproducer. Once selected checks
pass, repeat them only for changed inputs or unresolved failures. No full
qualification matrix or compiler test suite is part of this plan.
