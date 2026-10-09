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

## FD2 Caller-local forms

`form_do` now runs editable and button-only trees on the caller's Task, including
radio groups, keyboard traversal, repeat calls inside START/FINISH and selected
EXIT results. Input loss and outside releases cancel feedback. Borrowed-window
policy messages interrupt the loop unchanged; temporary movement is accepted
and temporary close dismisses. Ordinary WM-shaped messages retain provenance.

The optimized emitted gate passes 194 assertions and 34,560 independently
expected pixels. Two ordinary Tasks keep separate live forms. The fixture also
covers formatted/multiple fields, disabled/hidden controls, capacity 128,
no-editable-field Space activation, Default, press cancellation, movement,
cleanup, resource return and message order. Paced typing captures/routes/consumes
all three offered keys and inserts three. An eight-key burst captures/routes/
consumes eight and inserts the three characters that fit; the NUL remains intact.
The durable-loss fault supplies a physical key wake before release. This is a
bounded input check, not a claim of unbounded paste support.

Host checks pass (422 tests, four historical skips); ABI generators and content/
links are checked. FD1's small raw/optimized context probes remain applicable:
this slice changes no shared context layout or bridge. The C component ABI is
version 8 and includes the new export. The fixture's Calypsi inline member-address
cast failed in both optimization modes; the established explicit typed TEDINFO
pointer expression compiles. No compiler pin was changed. Initial physical test
trials missed the closer and omitted a wake from a synthetic loss; they are
excluded from acceptance evidence.

The session is 311 live / 312 heap-reserved upper bytes. The fixture uses 11,787
bytes in the additional code bank, including test code; FD4 records production
size. Minimum ordinary-Task checked margin is 242 bytes, above the 128-byte target;
all guards, heap return and OS restoration pass. Bank-zero delta is **0 fixed,
0 per public Task, 0 private idle**; VRAM and Task pools remain unchanged.
Packaged integration follows in FD4. These are development checks only.
