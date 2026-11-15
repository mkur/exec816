# AES UPDATE ownership and cursor completion migration

[GEM plans](README.md) · [Native semaphore contract](../../reference/semaphores.md) ·
[AES contract](../../reference/aes.md) · [Inline cursor design](gem-mouse-plan.md#inline-cursor-completion)

Status: prepared, 2026-11-15. Basis: `4c006f30`. Commit this plan before code;
implement AM1–AM4 in order and commit each slice. Use development checks only.

## Result and boundary

Give UPDATE a real calling-Task-owned native semaphore, release ownership in
the application Task before exit, shorten nested UPDATE and owner frame calls,
and complete eligible mouse changes in the caller before a cursor-only wake.
Measure both CPU and input-to-pixels latency in one loaded MGVIEW/Counter pair.
Application GEM calls and MGVIEW source remain unchanged.

Keep UPDATE, explicit MCTRL, scene policy and physical display grants distinct.
The scene gate still serializes presenter metadata. No drawing or hardware wait
may occur under that gate; no contended semaphore Obtain may occur there.
Normal preemption and existing IRQ/NMI/context guards remain in force.

AES admission is richer than a resource FIFO: it interleaves UPDATE/MCTRL with
older window operations, capture, retained physical effects and the mouse-owner
upgrade exception. Preserve the one existing AESWAIT eligibility queue. Native
semaphores own UPDATE and account recursion/lifetime; they do not replace that
mixed admission queue in this migration. Eligible outer acquisition uses native
Attempt under the scene gate, which must succeed by the logical ownership
invariant. A miss is an implementation fault before logical mutation. Competitors
remain in the AES queue and sleep on their existing reply hints. Native FIFO
waiting remains available to ordinary Tasks, independently of this policy.

Use one private 12-byte semaphore in the existing heap-owned AES service.
Initialize before service publication and preserve it through the last client.
No new Task, signal, per-call allocation, private COP or caller ABI layout is
needed. The current APP ABI is 46; rebuild only MGVIEW/Counter if cached APPs
predate it, then reuse those same APP bytes for final comparison. Do not change
existing demo packages or rebuild the application catalog.

## Current seams

- `AESLOCAL.Call` executes UPDATE in the calling Task. `AESLOCKS` owns logical
  admission and depth; `AESWINDOWSTATE` owns outer paint journals and view depth.
- `AESCORE.Retire` currently clears another Task's logical locks. C
  `exit_application` resets local depths after RPC rather than releasing them.
  This must change before native ownership is admitted.
- `AESGATE` carries scene handoff and presenter scheduling. Repeated nesting
  currently re-enters the scene, checks queues/readiness and refreshes the mouse.
- `AESLOCAL` wakes the presenter for a pending cursor before C attempts physical
  completion. `AESCURSOR.Wake` can notify completed revisions with its existing
  short Task guard; it requires no renderer access.

## AM1 — Native UPDATE ownership and owner-side retirement

Append the native semaphore to private service storage, without moving existing
private fields. Each successful BEGIN obtains one native recursive level; each
END releases one. Keep outer BeginUpdate/EndUpdate journal operations and exact
per-window depth publication. Check AES depth overflow before native mutation.

After form cleanup, the C owner balances all UPDATE and explicit MCTRL levels
before closing VDI/timers and submitting EXIT. A failed cleanup retains the
context, registration, remaining depths and resources for retry. The presenter
never releases a peer's native ownership: reject a direct EXIT with held locks
as BUSY before closing endpoint admission. Retire only an unowned registration.
Existing Task leases and native semaphore accounting bar premature removal.

Add a small optimized owner/contender/background-counter fixture. Check native
owned count, recursion, unrelated signal preservation, mixed lock order,
TRY/non-barging, ordinary waits, raw held EXIT rejection, owner-side nested exit
and complete Task/heap retirement. Run the existing optimized lock fixture once
for window barriers, MCTRL upgrade, readiness and overflow. No full GUI matrix.

**Commit:** `Give AES UPDATE native Task ownership and owner-side cleanup`.

## AM2 — Short recursive UPDATE and owned frame paths

Before scene entry, recognize admitted owner-only nested BEGIN and nonfinal END.
Validate the operation encoding and overflow once, adjust native recursion and
logical/view depths, and return without readiness/queue scans, mouse refresh,
snapshot publication or presenter wake. Outer transitions still use the common
scene-protected policy. Keep exact view depths and window scope; a nested scoped
BEGIN must not alter the outer scope.

For a frame setter already inside that client's UPDATE, retain scene ownership
for the actual mutation/publication but reuse the established owner admission.
Avoid duplicate queue/readiness checks; preserve handle/field/value errors,
unchanged-value no-ops, cache invalidation, slider geometry and input snapshots.
Do not introduce a parallel drawing policy or mutate shared scene data unlocked.

Extend the small fixture with named and PB calls, nesting while the scene is
unavailable, scoped depth mirrors, overflow and two slider setters. Trace exact
call boundaries to verify no scene entry or refresh on nested operations. Add
one focused existing frame/cache case as needed for the changed behavior.

**Commit:** `Shorten nested AES UPDATE and owned frame admission`.

## AM3 — Caller cursor completion before cursor-only notification

Use generated private mouse-call modes in existing request scratch: ordinary
presenter continuation, caller physical attempt and completion notification.
These change no request/context layout or public GEM opcode.

Under the scene gate, publish logical state/revision and release normally.
For admitted workstation callers, defer only the cursor-pending wake; preserve
scene waiters, policyWaiting and all independent scheduling. The C caller then
uses the existing display grant/fences. Clear its own completed wait association
and invoke a short native completion helper to notify every satisfied peer.
That helper uses the existing guarded cursor waiter scan, without scene entry,
and signals presenter continuation if any physical revision remains unfinished.

No workstation, BUSY admission, newer peer revisions, display failure and
retirement retain durable revision checks and the existing fallback wake-before-
Wait protocol. Ordinary scheduling may still switch Tasks. No target may be
installed from stale caller storage after a newer revision completes.

Use focused emitted C/native cases for completed/no-op nesting, required policy
wakes, peer notification, newer targets, no-workstation fallback, failed physical
attempt and UPDATE-held completion. Run the existing cursor fixture once for
actual pixels, selection/forms and retirement. No QED or package refresh.

**Commit:** `Complete eligible cursor changes before presenter notification`.

## AM4 — Matched scroll measurement and current documentation

Freeze a current ABI-46 baseline before AM1. Build only its two small APPs and
provider/native fixture. Reuse those APP bytes after migration; rebuild the
affected provider/native fixture only. Run one line down/up through the existing
passive MGVIEW observer, with exact pixels, Counter progress, guards and cleanup.

Compare BEGIN, slider setters, hide/show, END, presenter work/wake sites and
input-to-pixels intervals. Preserve IRQ/off-Task attribution. Report actual
latency separately from CPU reductions, including regressions or scheduling
variation; do not inherit the primitive's percentage as a GUI prediction. Keep
renderer operation limits and the one-copy-unit expectation unchanged.

Update AES/mouse/semaphore references, roadmap, indexes and concise historical/
machine-readable evidence with input, image, APP, compiler, ROM/emulator and
trace hashes. Mark completion only after required cases pass. Hosted release
qualification and further scene/MCTRL/display migrations remain separate.

**Commit:** `Measure and document AES semaphore and cursor migration`.

## Validation and memory accounting

Use the clean compiler revision in `toolchain/actionc.json`, release host build,
optimized guest code, and pinned GEM PAL 8x/4 MiB emulator/ROM. Private service
storage and existing request scratch do not change the public C/Action layout;
generated constants need host/generator checks, not a duplicate raw desktop.
Add a tiny raw bridge probe only if implementation changes a calling shape.

Run host tests after coherent slices. Compile each focused fixture once and
reuse it for runtime-selected cases, rejecting changed build inputs. No QED,
MagiC rebuild, demo refresh or release matrix. Record actual scopes and excluded
pilots. Check guards, bounded completion, OS return and heap/Task retirement.

Each slice targets **0 added reserved bank-zero bytes** for fixed, root, kernel,
idle and each public Task, counting guards, alignment and spare capacity.
Report the 12 added upper service bytes and actual allocator rounding separately;
keep public Task/context strides and all stack/DP pools unchanged. Reuse existing
native semaphore and scene scratch. Preserve per-call stack high-water evidence.
