# Caller-local AES UPDATE

[Plan](../plans/gem4xe/caller-local-update-plan.md) · [History](README.md)

## UL1: shared policy

`AESLOCKS.Attempt` owns decoding and completed transitions, including snapshot,
cache and synchronous paint-journal accounting. RPC admission retains the pending
queue; its eligible-waiter scan shares acquisition. Public UPDATE remains RPC.

Development checks: the unchanged optimized lock fixture passes 138 assertions
before and after, covering recursion, TRY, wrong-owner release, overflow, MCTRL
and pending clients. The historical fixture timeout did not reproduce on the
current pin. Stack/domain guards and cleanup pass. Host checks: 487 tests,
four historical-source skips. No full qualification matrix was run.

The clean parent `f37d5f6` was frozen with OF816 in
`build/caller-local-update/before` before production edits. Its idle dialog trace
and Files initial-window capture are retained for UL4. Both application runs
complete normally, including package boot and exit.

UL1 reserves **0 additional bank-zero bytes**: fixed 0, per public Task 0, idle 0,
including guards, alignment and unused capacity. No upper-RAM state or VRAM is
added; existing stack reservations are unchanged.

## UL2: presenter handoff

The worker claims the private policy gate before its loop condition and closes
it across input, controls, painting, settlement, caching and readiness checks.
It computes the scheduling action before publishing availability. Stop exits
retain closed ownership. Clients cannot execute policy across that boundary;
a preempted caller makes the presenter wait on its existing AES signal.

The small optimized emitted gate fixture passes **24 assertions**, forcing
claim exclusion, inherited Forbid nesting, natural VBI preemption, peer Task
progress, release before/after waiter publication, shutdown/retained-work
rejection, preservation of unrelated pending input and complete cleanup. The
real presenter still passes the **138-assertion** optimized lock fixture.
Host checks pass 487 tests with four skips. Guards remain intact; no full
qualification matrix was run.

UL2 adds **two upper-RAM service bytes**. Reserved bank-zero delta is **0 fixed,
0 per public Task, 0 idle**, including guards/alignment/capacity. There is no
new signal allocation, Task, VRAM storage or stack reservation.

```sh
python3 tools/test_aes_gate.py --output build/caller-local-update/ul2-gate
```

## UL3: caller-local BEGIN/END

The resident binding calls one private C/Action entry. A gate miss or blocking
contention releases transient ownership and submits the unchanged RPC operation.
Handled TRY failure does not submit. Local calls leave transport sequence numbers
unchanged; MCTRL remains RPC. Final END consumes the existing journal and sends
the service wake after publishing the released policy gate.

The faster path exposed an existing dependency cycle: an exiting client could
wait for a mouse owner while that owner's UPDATE upgrade waited for the pending
exit. Shared eligibility now permits the existing mouse owner to upgrade past
pending window/exit work, while retaining native readiness checks. This extends
the existing owner exception to work that itself depends on that owner. The
second contention round in the lock fixture exercises the formerly stuck case.

Development checks:

- Small raw/optimized bridge probe: full 32-bit argument, native result, both C
  stack parities, S/D/DBR, preserved C DP and VBI preemption.
- Optimized lock fixture: **181 assertions**, including zero-message nested
  local pairs, both mixed local/RPC pairs, inherited Forbid, an older unadmitted
  request, TRY, MCTRL overlap/upgrade, two contention orders, six open owned
  windows, detach and resource restoration.
- Optimized binding fixture: **324 assertions**, including ordinary/PB calls,
  multiple contexts, registration reuse and lifecycle.
- Optimized cache fixture: **220 assertions** plus 31 physical observations,
  including hidden edits, scoped sibling eligibility and exact restored pixels.
- Host suite: **487 tests, four skips**. This is development coverage, not full
  qualification or hardware qualification.

The six-window lock case peaks at 709 caller stack bytes, leaving 571 bytes above
its protected floor. The binding case peaks at 827, leaving 453. Guards remain
intact and reservations are unchanged. UL3 bank-zero delta is **0 fixed, 0 per
public Task, 0 idle**, including guards/alignment/capacity; no VRAM is added.
The bound native entry pointer uses three upper-RAM bytes. The optimized native
local entry is 783 code bytes; the common owner-upgrade fix adds 54 bytes.
UL1's shared lock refactor adds 282 native code bytes. UL2's gate routines total
1,243 native code bytes, plus their worker boundary calls.

```sh
python3 tools/test_aes_update_bridge.py --output build/caller-local-update/ul3-bridge
```
