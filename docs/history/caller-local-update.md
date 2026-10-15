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
