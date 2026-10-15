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
