# Standard GEM dialogs development record

[Current AES contract](../reference/aes.md) ·
[Design](../plans/gem4xe/standard-dialogs-design.md) ·
[Plan](../plans/gem4xe/standard-dialogs-implementation-plan.md) ·
[Evidence](../development/standard-dialogs.json)

## FD1 Dialog host lifetime

FD1 adds `form_dial`, centering without an application window, temporary
window/workstation ownership and durable local repair of borrowed application
content. Deferred application messages precede that repair; queued messages
retain their order. No self-message allocation is required when the queue is
full. A failed resource retirement retains the session for retry or `appl_exit`.

Development checks pass: 149 optimized emitted assertions, raw and optimized
context/layout probes (1,081 checks per client), and 422 host tests with four
historical skips. The form fixture covers setup failures, close/delete/grant
retirement failures followed by retry, capacity exhaustion, lock rejection,
borrowed resource preservation, repair epochs and heap return. The initial
fixture wrongly assumed there could be no queued GUI redraw among its ordinary
messages; the corrected fixture distinguishes provenance and checks ordinary
FIFO order. The failed trial is not acceptance evidence.

The context grows from 318 to 340 live upper bytes (320 to 344 heap-reserved).
The initial session fields occupy 159 bytes, rounded to 160 by the upper heap.
The C linker now permits another code bank at `$10`; the form fixture uses
997 bytes there. Actual production payload growth will be recorded with FD4.
Bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**, including
guards, alignment and spare capacity. VRAM and Task pools are unchanged.

The fixture's form runs on root (818 bytes of measured margin); its ordinary
peers retain at least 842 bytes. This is not yet a stack proof for a loaded
application's deeper `form_do`/alert path. FD2–FD4 provide that coverage.
These checks do not qualify real hardware or close HY4/PI4.
