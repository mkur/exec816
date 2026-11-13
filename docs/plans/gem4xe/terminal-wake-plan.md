# Terminal notification signal implementation plan

[GEM plans](README.md) · [Wait audit](../../history/viewer-wait-audit.md) ·
[Signals](../../reference/signals.md) · [Ports](../../reference/ports.md) ·
[Testing policy](../../contributing/testing.md)

Status: TW1, TW1b and TW2 complete at the development tier.
Baseline runtime `067b2eff`; audit/tool baseline `f9126683`.
Commit this plan and each passing executable slice separately.

Remove Terminal's confirmed query-reply/view-notification feedback loop, then
measure the effect on the same viewer workload. The audit already supplies the
before capture: 95 complete feedback chains, 97 `MU_EXEC` returns in 118 event
waits, and unchanged Terminal cells and paints. No further baseline system build
is needed while those frozen inputs remain available and hash-identical.

## Decision and boundaries

Production scope is [platform.c](../../../examples/gem-terminal/platform.c)
and its private [Terminal state](../../../examples/gem-terminal/terminal.h).
Keep the reply port exclusively for synchronous session RPCs. Allocate an
independent caller-owned signal for console-view notifications, retaining the
existing `wake` mask used by subscriptions and `ExecAESWait`.

Store the allocated bit number explicitly in the private Terminal record. Add
it at the end so existing pixel/state offsets remain stable. `wake != 0`
indicates successful notification-signal ownership; the zeroed record remains
safe to close before Open has succeeded. Check `AllocSignal` failure before
forming the mask. If the additional allocation fails, delete the newly created
reply port and return failure with no owned resources.

Close must unbind the window and unsubscribe all views before clearing/freeing
the notification signal. Then delete the quiescent reply port. Reset ownership
state so repeated cleanup is harmless. Producers are stopped before bit reuse;
no direct writes to kernel signal fields are introduced.

Integration discovery: the first package link found that loadable APPs do not
yet import `AllocSignal`, `FreeSignal` or `SetSignal`. Add these existing public
APIs to the common C APP import table, update its version to 37 and rebuild all
APPs. Preserve existing ordinals; add no kernel selector or private Terminal
service. This necessary binding slice (TW1b) precedes TW2 delivery.

Keep the existing 100 ms timer, refresh/query frequency on legitimate wakes,
controller supervision, normal Task preemption, message-port semantics, drawing
limits and source/ABI pins. No new kernel API, Task, cache or polling policy is
part of this change. The APP binding version changes as described above;
kernel APIs and calling conventions do not. In particular, do not clear reply bits to disguise the
alias or change `WaitPort`/`GetMsg` semantics.

## TW1 Own the notification signal and check its lifetime

Completed: [TW1 evidence](../../development/terminal-wake-tw1.json) and
[implementation record](../../history/terminal-wake.md). Raw and optimized
native probes each pass 35 checks, including one-bit rollback and queued-reply
isolation. The host suite passes 710 tests with four existing skips. The private
record grows one byte; all shared/per-Task bank-zero reservations match IC2.

Implement allocation, rollback and cleanup. Extend the existing emitted C
layout probe/model for the new private field and resulting record size.

Add a bounded native probe that compiles the actual Terminal platform source
with real Exec signal/port operations. Check:

- Complete signal exhaustion: Open fails without a port/heap leak.
- Exactly one available bit: reply-port creation succeeds, notification
  allocation fails, and both signal and heap ownership roll back.
- Normal Open: reply and notification masks are distinct and allocated.
- A prequeued RPC reply: `WaitPort`/`GetMsg` remove the message while the reply
  signal remains pending; the notification mask remains clear.
- A genuine notification: consuming it leaves the unrelated reply bit pending.
- Wait configuration still requests messages/buttons and the 100 ms timer,
  with only the notification mask as its external wake.
- Subscriptions retire before signal release; Close restores the allocation
  mask and heap, repeated Close is harmless, and resources can be reopened.

The focused probe may stub console/AES endpoints to observe ordering and wait
parameters; it must state this limit. Real console/AES behavior is covered in
TW2. Execute this small C/Action probe in raw and optimized modes to cover the
private layout and language bridge; use optimized builds for system scenarios.
Preserve native stack/domain guards, ownership and normal EXIT. Run the host
suite and record actual assertion counts, source/artifact hashes and memory
changes. Commit the production change and focused evidence as
`fix(terminal): separate view notifications from RPC replies`.

## TW1b Expose existing signal APIs to loaded APPs

Completed: [TW1b evidence](../../development/terminal-wake-tw1b.json). Loaded
raw and optimized APPs each pass 25 native checks/four completed executions on
the identical optimized native provider, including bit-31 signal operations.
Generated definitions and 710 host tests pass (four existing skips). Existing
127 ordinals are preserved; three common imports are appended. Complete
bank-zero maps match IC2; the upper binding table grows nine bytes within its
existing reservation.

Append `AllocSignal`, `FreeSignal` and `SetSignal` to
[c-program.json](../../../abi/c-program.json), advance the single supported APP
ABI from 36 to 37, regenerate native definitions and update the current contract.
These are existing public Task APIs; the kernel ABI and selectors are unchanged.

Extend the existing loaded relocation probe to allocate bit 31, post/snapshot/
consume its full-width mask, free it and verify exact signal-allocation return.
Run this small APP probe with raw and optimized C emission on the optimized
native runtime. Retain relocation, two private instances, repeated execution,
heap return, stack/domain guards and normal EXIT. Run generated-definition and
host checks. Record the binding delta and commit this integration prerequisite
as `feat(c): expose public signal allocation to loaded apps`.

Rebuild the entire demo in TW2; no old-version APP is retained or compatibility
profile added. Report other APP import-thunk/relocation changes separately from
the intentional Terminal behavior change when comparing the old captures.

## TW2 Integrate, measure and deliver

Completed: [TW2 evidence](../../development/terminal-wake-tw2.json) and
[implementation record](../../history/terminal-wake.md#tw2-packaged-measurements).
Both scenes contain zero reply-driven external wakes; four extracted OF816
runs pass exact replay with zero clock offset. Median page/line latency falls
24.0%/17.4% in idle and 22.7%/11.9% under Counter/disk load, while mean viewer
CPU is nearly unchanged. Drawing, pixels, heap, guards, Counter/disk bytes and
EXIT pass. Two IRQ samples precede the final paints-counter increment; linked
instruction order and full drawing counts establish unchanged physical work.
Real Terminal integration and the package audit pass. The additional wake
observation records 83 genuine view wakes and 120 timer wakes in 207 waits.
Host checks pass 711
tests with four existing skips. Complete demo reservations match the before
package, including all bank-zero guards/alignment/unused capacity.

Build a fresh optimized package with `tools/build_demo.py --gem-desktop
--release-compiler`, including OF816, the pinned matching ROM and five-second
standard shell/prime autoboot. Retain writable combined SYS, MD5/ARC/EDX,
overlays/notices and the boot/guide/licenses/checksums-only ZIP. Audit that exact
package with the existing package checker.

Run the existing optimized Terminal integration scenario on the rebuilt
program/media: genuine shell-output notification and exact viewport/exposure
pixels, keyboard editing, session creation/switching, cancelled/confirmed close
and normal shutdown. Include its missing-Terminal startup-failure scenario if
the required dedicated fixture media is needed; allocation failure is already
covered in TW1, so do not expand to a general startup matrix.

Use `trace_viewer_waits.py` for four page and four line actions in idle and the
same Counter/disk scene, each with an identical-image untraced companion. Add
only observer fields needed to distinguish reply and view signals; freeze the
observer before running the matched cohorts. Reuse baseline audit/dense
captures only after checking guest, compiler, machine, document, geometry and
observer equivalence, with Terminal's intentional change identified explicitly.

Require zero captured query-reply-driven external wakes. Keep genuine view,
input and timer behavior. Compare controller query counts and peer CPU, viewer
CPU/IRQ, blocked versus ready time, and completed-repaint distributions. Report
latency independently of CPU and do not set an invented speedup threshold.
If latency does not improve, document it and stop this slice rather than add
another optimization. Source scopes remain inclusive; CPU and IRQ stay separate.

Preserve whole-work-area pixels, drawing counts, boundary no-op, warmed heap
return, stack/domain guards, ownership, Counter/disk progress, persisted bytes
and EXIT. Observed/untraced relative timings, gaps and counters must match
exactly after at most one documented global clock-origin alignment per run.
Settled scanout pixels are checked separately from repaint completion time.

Record before/after measurements, exact inputs and artifact hashes in history
and machine-readable development evidence. Update this plan and relevant
indexes, and provide the new launcher/package path. Commit as
`test(terminal): measure isolated notification wakes in the demo`.

## Resource and completion gates

One additional allocated bit in the existing Terminal Task uses existing signal
storage. Target reserved bank-zero growth is **0 fixed, 0 root, 0 kernel,
0 idle and 0 per public Task bytes**, including guards, alignment and unused
capacity. Compare the complete before/after demo `bank_zero_budget`,
`task_pools` and `runtime_reservations`; report the private record/code/stack
change separately. No new upper-memory or VRAM reservation is planned.

Completion means both slices pass their stated development checks, the signal
feedback is removed, the current package is audited, and the actual latency
result is documented. Full release, hosted-system and hardware qualification
remain outside this task.
