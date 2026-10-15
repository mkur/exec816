# Presenter quiet turn implementation record

[Implementation plan](../plans/gem4xe/presenter-quiet-turn-plan.md) ·
[PB6 baseline](presenter-bookkeeping.md)

## QT1 Conditional signal collection

The resident worker reuses its established Task pointer to check for pending
collection bits. Empty collection returns the bits already consumed by Wait;
nonempty collection still uses the public atomic SetSignal acknowledgement.
Request and unrelated bits retain their original handling. There is no change
to END notifications, the policy gate or preemption.

Development checks: 490 host tests passed with four historical skips; the
optimized production-routine signal probe passed 38 assertions, the real text
worker wake/stop/restart fixture passed 179, and the AES gate fixture passed 24.
The signal probe injects arrivals after both empty and nonempty hints and checks
that unrelated bits survive. It also verifies sixteen empty calls perform no
acknowledgement. Their combined elapsed time is 0.398 ms with fixture hooks;
this is not a whole-presenter performance result.

Local evidence: `build/presenter-quiet-turn/qt1-{signals,wake,gate}`. The signal
probe now extracts the production routine instead of retaining the old copied
implementation. The worker probe was updated for the current shared final Wait.

Reserved bank-zero delta: fixed **0 bytes**, each public Task **0 bytes**, idle
Task **0 bytes**, including guards, alignment and unused capacity. No persistent
state, VRAM or stack/DP reservation was added. Combined production code/data
and hosted stack measurements follow in QT4. No full qualification was run.

## QT2 Event-driven window cache inspection

The desktop cache now retains a six-bit candidate mask and the last observed
visibility rebuild. Native changes, completed manager paint and accepted AES
paint reports rearm the affected window; a visibility rebuild reconsiders the
window set. Each inspection consumes its bit, including rejected and already
attempted candidates. Common display/scene blocking leaves candidates pending.
Revision checks, repairs, popup precedence and the one-transfer limit remain.

Development checks: the optimized AES cache fixture passes 32 physical phases,
including full/partial repaint, hidden changes, frame recapture, move/exposure,
two-slot eviction, deletion/reuse and mixed-policy menu restoration. Four
settled states each receive twelve additional real presenter signals: none
causes another candidate geometry inspection. A full paint report without an
explicit changed rectangle produces a current image. Exact client/frame pixels,
unpinned settled storage, guards and normal return pass. The host suite again
passes 490 tests with four historical skips. Evidence:
`build/presenter-quiet-turn/qt2-cache`.

Reserved bank-zero delta: fixed **0 bytes**, each public Task **0 bytes**, idle
Task **0 bytes**. The five new upper-RAM state bytes consume four additional
allocated bytes because the candidate byte fills existing padding. No new VRAM,
DP or stack reservation. Emitted END bookkeeping grows by 111 code bytes with
its local stack peak unchanged at 70 bytes; combined timing follows in QT4.

## QT3 Layers-owned visible-damage readiness

Layers maintains one bit per slot, including the background, for manager damage
intersecting current visibility. Marking damage, rebuilding visibility, paint
retirement, deletion and saved-scene restoration update it. Already-runnable
layers need no new intersection scan when more damage is added. External repaint
obligations remain separate. The presenter's no-damage query now reads the word
after its existing paint-token and lock checks.

The intersection predicate moved into Layers. Mutating paths carry resolved slot
indices instead of searching again for every mark. No global Layers state was
added. The generated Scene and enclosing desktop Service layouts were rebuilt
together, and the current reference documents the read-only summary.

Development checks: 1,255 optimized Layers assertions with 128 geometry and 40
scene cases; an independent intersection oracle covers both sides of painting,
all nine bits, fully covered damage, later exposure, saved-image subtraction,
external handoff, failed completion and slot reuse. The small bank-crossing
layout/transaction probe passes 127 assertions in each of raw and optimized
modes. The 490-test host run found the expected desktop Service size change;
after correcting that assertion, all five affected desktop contract tests pass.
Generators and diff checks pass. Local evidence:
`build/presenter-quiet-turn/qt3-{layers,layout-raw,layout-opt}`.

Reserved bank-zero delta: fixed **0 bytes**, each public Task **0 bytes**, idle
Task **0 bytes**, including guards and unused capacity. Scene grows 9,184 to
9,186 bytes and desktop Service 18,716 to 18,718 bytes in upper RAM, including
alignment. No new per-Task state, VRAM or DP/stack reservation. The Layers/Regions
fixture reports 35,879 code bytes, no mutable globals and a maximum local stack
peak of 56 bytes. These fixture sizes are not a whole-demo code delta.
