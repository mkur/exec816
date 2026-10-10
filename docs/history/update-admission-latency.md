# AES UPDATE admission latency

[Plan](../plans/gem4xe/update-admission-latency-plan.md) ·
[Starting measurements](text-viewer-performance.md) ·
[Evidence](../development/update-admission-latency.json)

## Admission attribution

UA1 extends the existing physical viewer workload without changing its executable
image. The passive observer follows the request address, sequence, client and
Task through submission, presenter dispatch, eligibility, acquisition, snapshot,
reply and resumption. It records the first physical display admission separately.
Emitted call sites and stack pointers identify returns; native argument reads
use the compiler's frame metadata. No guest counters or polling are added.

The representative page's second `wind_update(BEG_UPDATE)` takes 343.3 ms.
Inside it, `ExecAESSubmit` takes 342.4 ms. Presenter dispatch reaches the lock
request at 56.9 ms; acquisition starts at 330.7 ms, completes at 333.0 ms, and
reply starts at 333.1 ms. The caller spends 331.2 ms blocked and 7.3 ms runnable off CPU. The presenter
uses 279.0 ms CPU and 59.5 ms in interrupts during this wait. The first subsequent
physical display admission takes only 0.9 ms, with no off-CPU wait.

The queued request repeatedly observes the same busy
scene token, 232, while the presenter advances native paint strips. The first
successful eligibility check is followed promptly by acquisition.

This identifies retained scene painting as the dominant delay in that interval.
It is not evidence that all viewer off-CPU time is UPDATE contention. Each policy
test observes state at that instant; transitions between tests are bounded by
observations. Inclusive presenter work spans may overlap and must not be added
to the reconciled CPU/interrupt/blocked/runnable totals.

Replies can make the caller runnable before the presenter has returned from
`AESSTATE.Reply`. Attribution therefore allows those spans to overlap. Physical
display admission and the presenter's later `OwnerDrop` remain distinct from
the logical UPDATE grant.

The unobserved replay reproduces the first two page timings, 887.2 and 905.1 ms,
and line timings, 900.3 and 886.9 ms. Its Panel raise/action observations are
1222.9 and 1004.1 ms. These are individual diagnostic actions, not new cohort
percentiles. The original TVP4 30-action cohorts remain the comparison baseline.

## Selected production experiment

Before changing production code, select a reduction in the native work retained
under the existing paint token. `AESWINDOW.Request` currently invalidates the
whole vertical rail for `WF_VSLIDE` and `WF_VSLSIZE`, including unchanged arrows
and the size gadget. Scrolling changes the thumb geometry. Limit that damage to
the bounding union of the old and new thumb, and omit damage when rounded pixel
geometry is unchanged. Continue publishing the caller's logical slider values.

This experiment preserves the complete scene transaction, request admission
budget, UPDATE/MCTRL policy, physical owner and input-service boundaries. It
requires no scheduling, timer, I/O or public ABI change. The matched measurements
must decide whether it improves both completion and input response.

## Cancellation controls

Cancellation is appended after the existing timing prefix. Escape is offered
100 ms after an observed replacement load enters READ; it must retire I/O and
retain the previous document. Shell BREAK is offered 1000 ms after CAT's
foreground scope publication, independently of Panel completion. The unchanged
image retires these cases in 954.0 and 273.8 ms respectively; Escape reaches
settled viewer state at 1061.3 ms.

The initial Files Stop pilot used a 2000 ms offset after the child's READ
boundary, but menu navigation missed that offer time. That is a fixture failure,
not a passing cancellation measurement. The 5000 ms pilot also missed setup, measured at 5858.4 ms. The offer is
now frozen at **6500 ms**; its baseline run was started on the unchanged ZIP
before production editing. The result is pending.

UA1 changes **0 fixed bank-zero bytes, 0 per public Task and 0 private idle**,
including guards, alignment and unused reservation. Guest code, upper RAM and
VRAM are unchanged. These are development diagnostics, not hosted-system or
real-hardware qualification; HY4/PI4 and the earlier twofold page target remain
open.

The detailed trace is 255,577,897 bytes, below the 256 MiB cap. All 20 BEGIN
and 20 END/hold observations reproduce the earlier trace exactly. The frozen
passive-marker comparison tolerance is 0.01 ms; IRQ-sampled UI tolerance remains
20.05 ms. The host suite passes 429 tests with four historical skips.
