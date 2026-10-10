# AES UPDATE admission latency

[Plan](../plans/gem4xe/update-admission-latency-plan.md) ·
[Starting measurements](text-viewer-performance.md) ·
[Evidence](../development/update-admission-latency.json)

UA1 is implemented. **No production optimization is accepted:** all nine UA2
trials miss at least one frozen input, cancellation or stack-headroom gate.
The renderer, application code and memory map remain at TVP4. UA3 retains the
comparison evidence; its acceptance/package gate remains open. These are
development checks, with no new hosted-system or hardware qualification.

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

## Initial production experiment

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
before production editing. The completed baseline retires the child in 1356.3 ms
after the offer, with ownership, heap and EXIT checks passing.

UA1 changes **0 fixed bank-zero bytes, 0 per public Task and 0 private idle**,
including guards, alignment and unused reservation. Guest code, upper RAM and
VRAM are unchanged. These are development diagnostics, not hosted-system or
real-hardware qualification; HY4/PI4 and the earlier twofold page target remain
open.

The detailed trace is 255,577,897 bytes, below the 256 MiB cap. All 20 BEGIN
and 20 END/hold observations reproduce the earlier trace exactly. The frozen
passive-marker comparison tolerance is 0.01 ms; IRQ-sampled UI tolerance remains
20.05 ms. The host suite passes 429 tests with four historical skips.

## UA2 experiments and acceptance

All times below are milliseconds. A–E and G have three matched runs (30 actions
per operation); F, H and I stopped after the first 10-action cohort exposed an
acceptance failure. The JSON retains line timings, individual cancellation
observations and comparisons against both TVP4 and each immediately preceding
trial. None of these intermediate trials is an accepted production version.

| Trial | Page median / p95 | First page band median / p95 | Panel gesture median / p95 | Files Stop | Failed gate |
| --- | ---: | ---: | ---: | ---: | --- |
| TVP4 | 942.6 / 964.7 | 178.6 / 525.9 | 538.3 / 781.8 | 1356.3 | Reference |
| A | 644.7 / 687.1 | 198.3 / 244.0 | 546.3 / 803.8 | 1688.7 | Panel p95; cancellation; stack 123 < 128 |
| B | 631.3 / 699.7 | 158.4 / 198.3 | 507.9 / 843.2 | 1603.5 | Panel p95; Files Stop |
| C | 620.3 / 699.7 | 178.3 / 198.6 | 422.9 / 789.2 | 1656.4 | Files Stop |
| D | 904.9 / 941.2 | 178.3 / 443.1 | 526.6 / 757.3 | 1226.6 | Files stack 126 < 128 |
| E | 903.9 / 927.4 | 178.5 / 499.2 | 548.6 / 671.5 | 1841.4 | Files Stop |
| F | 908.0 / 947.3 | 191.7 / 459.8 | 522.7 / 728.8 | 1506.5 | BREAK; Files Stop |
| G | 906.0 / 921.3 | 158.4 / 483.3 | 528.1 / 783.6 | 1599.0 | Files Stop |
| H | 903.4 / 948.6 | 158.4 / 439.0 | 542.9 / 663.4 | 1776.7 | BREAK; Files Stop |
| I | 902.3 / 920.5 | 439.0 / 482.5 | 546.2 / 763.4 | 1279.4 | First-content median |

A narrows slider damage to the old/new thumb union. B adds culling of wholly
clipped arrow/sizer groups. C also culls outline edges and avoids paper/outline
fills that the rail immediately overwrites. D keeps only C’s frame changes,
restoring full-rail damage. E adds 16 stack bytes to D’s slot 5. F uses only
group culling plus fixed-size constant/unused-argument cleanup. G combines
the full D frame changes with that cleanup. H adds a Files status-only repaint
after Stop. I returns to D and transfers 16 reserved stack bytes from slot 4
to slot 5. Every production edit is reverted.

C is the fastest trial, at 620.3 / 699.7 ms for page completion and 609.4 /
639.6 ms for lines. Its fixed Files Stop is 1656.4 ms, versus 1356.3 ms on TVP4.
It passes the baseline UI tolerance but still misses the twofold page p95
target of 660.8 ms. D passes the timing checks but misses the prescribed stack
margin by two bytes. Fixing that capacity shortfall changes the sampled timing:
E regresses Files Stop, and I regresses first-content median. Those failures
remain failures; neither resources nor timing tolerances are waived.

E consumes the 16-byte gap before staging: slot 5 grows by 16 and later stack
bases move up by 16. I instead retains slot 5’s top and all later addresses,
transferring 16 bytes from slot 4 (D’s observed margin was 413) to slot 5
(D’s margin was 126). E’s bank-zero delta is +16 in public slot 5; I’s fixed,
idle and aggregate public deltas are zero, with per-public-slot deltas
`[0,0,0,0,-16,+16,0,0]`. Both include guards, alignment and unused capacity.
Both maps pass focused raw/optimized eight-Task capacity/guard checks. Their
memory changes are reverted.

The [slider experiment](../development/update-admission-slider-experiment.patch)
and [frame experiment](../development/update-admission-frame-experiment.patch)
retain the exact A and D source changes. Applying both reproduces C’s
production changes. The logical-slider regression checks remain useful for
a future retry. No accepted UA2 implementation commit or new recommended
demo is claimed.

## Cancellation phase findings

The passive Files companion reproduces the fixed Stop results for TVP4 and G.
G’s parent finishes its first post-Stop UPDATE at 770.7 ms (TVP4: 839.0 ms),
yet the child reaches `TextCancel` at 1170.1 ms (TVP4: 337.0 ms).
`ExecBreakProgram` requests a cooperative GEM close; it does not abort the
child’s synchronous DOS Read. The extra delay precedes child cleanup; this
trace alone does not separate disk completion from event service. H’s narrower
parent status repaint does not resolve it.

The scoped BREAK companion reproduces all elapsed observations. TVP4 timestamps
match exactly; H has a uniform one-frame startup offset across all offers and
completions, with unchanged elapsed times and non-time fields. H delivers BREAK
at 23.5 ms (TVP4: 26.5) and enters console `AbortIO` at 25.9 ms (TVP4: 28.9).
A later root Task `DOSCANCEL.Transfer` starts at 205.5 ms and its wait service
occurs at 861.8 ms, versus 217.2 and 243.7 ms on TVP4. Slow keyboard routing or
a late abort does not explain this case. The end-to-end return to the shell
still fails; prompt/output completion must remain included.

Next, resolve these post-abort output and child Read-to-close intervals before
retrying the renderer. No I/O, cancellation, input-service or lock policy was
changed during these experiments.

Final bank-zero growth is **0 fixed, 0 per public Task and 0 idle**, including
guards, alignment and unused capacity. Guest code, upper RAM and VRAM deltas
are zero. The TVP4 OF816 package remains the reference. The twofold page target,
HY4/PI4 and scanout/flicker qualification remain open.

## Development fixture scope

The focused optimized lock (138 checks) and presenter intake/order (182 checks)
fixtures passed with candidate A; later candidates change only the C frame
callback. Candidate C passes 245 window/geometry/pixel checks and 168 physical
display/borrow checks. Exact packaged viewer, Files and loaded Panel workflows
provide the native output, disk, counter, input and cancellation integration
coverage. The standalone desktop proof and console fairness runners currently
fail before guest execution: the proof exceeds the Task-entry table, and the
bitmap fairness fixture needs a larger data arena and then also exceeds that
table. The text fallback reports overlapping image/import regions. These are
retained failed attempts, not passing integration runs.

Several debug-host compilations also exceeded their 600-second host timeout.
The selected retries use a release build of the same clean pinned compiler,
`6510ea1d148c93edea595be8a5afa9630d5a75e3`, after comparing all 1619 native
routines and emitted segments against the retained debug-host output. They
match exactly. Build records identify the actual host binary and local profile
override; guest execution limits and compiler ABI are unchanged.

Final host checks pass 429 tests with four historical skips. Relative links and
retained patch applicability are checked; executable source directories have
no diff against TVP4. The cancellation/reporting follow-up is committed as
`eb80ef7`, after UA1’s `eccf006`.
