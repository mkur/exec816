# Input snapshot copying implementation plan

[GEM plans](README.md) · [Route-reuse measurements](../../history/gui-route-reuse.md) ·
[Evidence](../../development/gui-route-reuse.json) ·
[AES contract](../../reference/aes.md) ·
[Testing policy](../../contributing/testing.md)

Status: IC1 complete; IC2 pending. Runtime baseline `41802444`.
Commit each passing executable slice below separately.

Reduce unnecessary copying in input refresh by returning from an empty default
route lookup before copying its complete `WindowRoute`. Start with this one
change; use the resulting measurements to choose any later work.

## Starting evidence

The existing optimized route probe has two clients, four windows and two empty
slots in the four-entry default-route table. After two warmups, eight BEGIN/END
pairs per owner produce these means:

| Owner | Pair Task CPU, ms | Input refresh Task CPU within the pair, ms |
| --- | ---: | ---: |
| Focused client | 9.566 | 5.451 |
| Other painting client | 9.838 | 5.253 |

Pair totals come from the linked evidence. Refresh costs are a passive
reanalysis of its existing `build/gui-route-reuse/after` capture, summing the
two `AESMOUSE_REFRESHSNAPSHOT` spans within each measured pair. They include
route lookup, endpoint holds, copying the latest input, eligibility and inbox
publication. They do not isolate route-copy cost or predict the saving.

`AESSNAPSHOT.Default` currently copies a full record before testing its endpoint.
`AESMOUSE.RefreshSnapshot` visits all four slots on each refresh, including empty
slots. `AESMOUSE.Lost`, the scene-test observer and the route probe also use this
lookup. All current callers inspect returned route fields only on success.

The viewer still spends about 137 ms of idle repaint CPU in UPDATE, out of
about 439 ms total. Keep lookup savings, complete-pair savings and application
repaint savings separate; do not attribute that entire UPDATE cost to copies.

## Implementation decision and boundaries

Primary production file: [aessnapshot.act](../../../lib/aes/aessnapshot.act).
Change only `AESSNAPSHOT.Default` in the first production slice:

1. Enter the existing `EXEC.Forbid` guard.
2. Test `published.defaults(slot).endpoint` before `A816MEMORY.Move`.
3. If it is null, set `target.endpoint=NULL`, leave the guard and return zero.
4. Otherwise retain the existing complete copy, endpoint hold and success path.

An empty slot means **endpoint is null**. A published client can have no focused
window and still have a live endpoint. Do not reject it because window, handle
or window epoch is zero, or because another client has focus.

On failure the endpoint is null; other target fields are unspecified. On success
the complete copied route and its one temporary endpoint hold retain their
existing meaning. Audit every caller again before implementation. If a caller
needs failure output, make that dependency explicit rather than silently using
fields left from its previous lookup.

The check, successful copy and hold remain under the same guard as publication
and withdrawal. No pointer into the private publication escapes. Callers still
drop each successful temporary hold exactly once; a miss takes no hold and
needs no Drop. Keep existing nesting and asynchronous-entry protocols. Forbid
is Task-switch coordination, not IRQ/NMI masking; no interrupt handler gains
access to these application-owned pointers.

Both outer UPDATE transitions still refresh eligibility. Keep the complete
input-sample publication and notification rules, MCTRL/capture selection,
loss handling and endpoint retirement. This slice adds no cache, dirty bit,
compact route type, field layout, ABI version, gateway or kernel operation.
It also keeps normal Task preemption and the existing drawing limits.

## IC1 Establish lookup coverage and freeze the baseline

Completed: [IC1 evidence](../../development/input-snapshot-copy-ic1.json).
The unchanged runtime passes 838 assertions, including withdrawal/reuse and
zero/one/two/four populated defaults. Emitted SIZEOF is 46 bytes. Every sweep
still performs four copies (184 bytes); the two-client sweep takes 1.297 ms
Task CPU, including 0.327 ms in the actual copy calls. Host checks pass 702
tests with four existing skips. Complete eight-Task bank-zero reservations
match the previous probe: zero added bytes in every shared/per-Task category.

Extend [aes_route_reuse.act](../../../tests/programs/aes_route_reuse.act) and
[test_aes_route_reuse.py](../../../tools/test_aes_route_reuse.py). Reuse their
native workload, passive call/return observer, CPU/IRQ attribution and cleanup
checks; do not introduce a second harness.

Add a bounded four-slot lookup sweep with zero, one, two and four populated
defaults. Build valid endpoints through the existing fixture setup. Preserve
the original two-owner UPDATE cohorts independently of these sweeps. Test:

- An empty lookup after a successful lookup and into a deliberately populated
  target: return zero, null endpoint and no added endpoint hold.
- Successful lookup: expected client/window/epoch and route values, one extra
  endpoint hold, then exact balance after Drop.
- A live client without a focused window: successful lookup and held endpoint
  even though its default window is zero.
- Withdrawal while a reader holds an endpoint, release of its final hold, and
  empty-slot reuse by a new endpoint/window lifetime.
- Existing ordinary routes, MCTRL/nesting, focus and geometry changes, menu
  exclusion, input eligibility, zero layout epoch and complete heap return.

Record charged CPU, IRQ time, calls and copied bytes for Default, refresh and
complete BEGIN/END pairs. Add passive Default/copy-site observations where
needed. Obtain the record size from emitted compiler output or fixture SIZEOF,
not a handwritten layout. Count copies within Default separately from input
sample and publication copies. If a helper is inlined, inspect/observe its
emitted path rather than interpreting a missing routine marker as zero work.

Run optimized native code with the pinned release compiler and current machine
pin. Retain two warmups and eight measured repetitions per lookup cohort and
each existing UPDATE owner. Freeze fixture/observer hashes, sources, results,
emitted code and complete memory maps before changing production. These checks
must pass on `41802444`; run the host suite for the fixture/tool changes.

Acceptance: all behaviors pass on the original implementation, copy cost is
separately attributable, and each four-slot sweep performs four full copies.
Report actual assertion counts rather than freezing a count that includes new
coverage. Commit: `test(aes): measure default-route lookup copying`.

## IC2 Skip empty copies and validate the saving

Implement the guarded empty-slot return described above. Run the same IC1
fixture and observer with unchanged workload, compiler and machine inputs.
Inspect emitted code to establish that a miss bypasses the full-record copy.

| Populated defaults | Full copies per four-slot sweep before | After |
| --- | ---: | ---: |
| Zero | 4 | 0 |
| One | 4 | 1 |
| Two | 4 | 2 |
| Four | 4 | 4 |

For the original two-client paint-only pair, default-route copies should fall
from eight to four while the two input refreshes remain. Route rebuilds must
remain zero, and live-client inbox publication and endpoint-hold balances must
match. Preserve captured-window replacement lookups rather than counting them
as unnecessary default copies.

Acceptance requires lower mean charged CPU for the two-client lookup sweep and
both complete BEGIN/END owner cohorts on matched inputs. Measure the extra
branch cost with all four slots populated; investigate a regression above 5%
in that control before retaining the change. If results are ambiguous, repeat
only the affected small cohort. If the complete pair does not improve, record
the result and stop; do not expand into another optimization to rescue it.

Run the optimized lock and pointer suites and the host suite. Reuse the existing
pointer/scene cases for capture, loss, MCTRL handoff and endpoint retirement;
add a missing boundary only where the focused lookup checks do not cover it.
No raw matrix is needed for this unchanged layout/ABI and ordinary policy
change. Use a small raw probe only to diagnose an actual compiler concern.

After the focused gain is established, rebuild with `tools/build_demo.py` and
measure the existing idle and Counter/disk viewer scenes, four page and four
line actions each, with identical-package untraced companions. Reuse frozen
before captures only after proving relevant runtime, application, observer,
document and platform inputs equivalent; otherwise replace that before capture.
Compare viewer CPU and completion separately. A small CPU saving may not move
the frame-sampled repaint median; do not promise an application percentage.

Require the existing work-area pixel oracles, no-op, Counter progress, persisted
disk bytes, heap return, stack/domain guards, ownership and normal EXIT to pass.
Drawing work and counts must match. Replay timing comparisons may remove one
documented global scheduler-clock origin offset per run; all relative edges,
inter-action gaps and relevant runtime counters must still match exactly.

The refreshed package retains OF816, the five-second standard shell/prime
autoboot, matching pinned ROM, writable SYS with MD5/ARC/EDX and notices, and the
boot-files/guide/licenses/checksums-only ZIP. Audit the exact package. QED and
the full release qualification matrix are outside this focused change.

Add history and machine-readable development evidence with source/artifact
hashes, copy counts/bytes, before/after CPU, actual test scope, exclusions and
package identity. Update this plan and its indexes. Commit the production
change, validated evidence and delivery together as
`perf(aes): skip copying empty default input routes`.

## Resource and completion gates

Target reserved bank-zero delta: **0 fixed, 0 root, 0 kernel, 0 idle and 0 per
public Task bytes**, including guards, alignment and unused reserved capacity.
Compare `bank_zero_budget`, `task_pools` and `runtime_reservations` in the before
and after eight-Task probe and twelve-Task demo. Report code size and transient
stack changes separately. No upper-RAM or VRAM reservation is planned.

This documentation-only plan itself changes all target reservations by zero.
Plan validation is content, source-reference and local-link checking; runtime
tests and demo builds begin with the executable slices. Completion means the
one selected reduction passes development checks with measured savings. Full
hosted-system and hardware qualification remain separate. Any later compact
lookup or changed-only inbox publication needs its own measured decision.
