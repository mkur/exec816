# AES application input implementation

[History index](README.md) · [Implementation plan](../plans/gem4xe/aes-application-input-implementation-plan.md) ·
[Current INPUT contract](../reference/input.md) · [Current AES contract](../reference/aes.md)

Status: AI1–AI4 implemented, 2026-10-07. AI5–AI7 remain pending. Public AES input
waits are not implemented yet. These are development checks, not hosted-system
qualification; PI4/HY4 and the observed flicker remain open.

## AI1 — Capture route policy and button qualifiers

[Evidence](../development/aes-application-input-ai1.json) records nine focused
emitted-code runs, the 406-test host suite with four expected historical skips,
and generated-definition checks.

INPUT version 4 adds `ROUTE_UNFILTERED` for keyboard routes. The Task-side native
transaction publishes route identity and filter policy with IRQ masked; NMI can
tick without switching across the publication. IRQ checks one resident byte.
Unfiltered routes receive Ctrl-C/Escape as keys; physical BREAK stays durable,
and existing shell/native routes retain their configured filters.

Pointer button edges and baselines capture Shift/Control qualifiers, including
retained BUTTON output after simultaneous relative movement. Pure motion and
idle sampling do not read additional modifier state. Physical tests cover
Shift-click, held-key Control-click and clearing modifiers after key release;
standalone Control-click remains outside the platform's hardware contract.

Optimized capture, relative decoding, interrupted route publication and 57.6k
SIO checks pass. The disk case observes fifteen addressed pointer samples with
zero losses and checks transfer bytes, ownership and restoration. Small native
registration and C bridge/layout probes pass in raw and optimized modes.
The publication fixture's completion lookup now selects its own module after
the recent merge introduced another symbol named `phase`.

Reserved bank-zero delta is **0 fixed + 0 per public Task + 0 private idle**,
including guards, alignment and unused capacity. Two upper descriptors grow
from 144 to 160 bytes; keyboard capture reuses one padding byte. Existing upper
reservations stay unchanged. The matched console-enabled adapter gains 34 code
bytes in signal code and 48 in native work code, within its existing extents.

## AI2 — Bounded inboxes and safe wakeups

Private wire version 7 allocates one inbox with each registration's existing
message pool. Separate sixteen-entry key/button FIFOs retain immutable input
records. Selected-input interest reuses the existing receive-port signal, and
publication holds cover the producer's final wake. Source-specific loss stops
admission without overwriting a selected record; acknowledgement purges only
that source. Close/reopen changes the window epoch, and endpoint withdrawal
retains storage until publication holds retire.

[Development evidence](../development/aes-application-input-ai2.json) records
252 optimized transport assertions: both full FIFOs, unchanged ordinary-message
capacity, immutable selected data across loss, unrelated input/messages retained,
latched wake before Wait, eligibility handback, wrapped indices, identity
exhaustion, close/reopen and failed-allocation rollback. Registration (233), GUI
delivery (101) and existing combined events (371) pass. Raw/optimized layout and
context probes each pass 1,045 assertions in each of two C Tasks. The host suite
passes 406 tests with four expected historical skips.

The registration fixture now uses a blocking update acquisition to prove
progress while another client's exit is held. Its earlier assumption that TRY
must succeed was invalid while native painting still owns the display. Failure
diagnostics retain the source line so this distinction is visible.

Reserved bank-zero delta is **0 fixed + 0 per public Task + 0 private idle**.
The inbox is 592 bytes, including unused selection scratch for the later wait
slice. Combined registration storage grows from 548 to 1,140 bytes, heap-rounded
from 552 to 1,144: **592 additional reserved upper bytes per registration**,
or 2,368 at four registrations. The shared directory grows sixteen bytes.
There is no extra allocation, signal or Task for each input wait. Existing
fixed bank and stack reservations are unchanged.

The optimized private fixture emits 3,607 bytes for the new native inbox module
and 367 bytes for the C input helper object, separately from data costs. Its
root stack peaks at 380 bytes, leaving 900 above the checked floor; the
presenter remains within its existing stack. Physical routing and public event
matching remain pending in AI3–AI5.


## AI3 — Keyboard translation and capture-time routing

Every open GEM window now owns an unfiltered native keyboard route. Closing
withdraws focus, invalidates the open epoch, drains capture and retires the old
route before completing. Reopening cannot inherit an earlier capture identity.
The presenter translates each key before publishing it to the original
recipient's inbox, even when another application now has focus. Translation
runs outside the console input guard; native console delivery retains a short
per-record guard.

The machine-readable mapping pins GEM4XE's scan/ATASCII reference and source
hash. Generated shared data implements GEM scan/ASCII words and Task-side
KEYDEF translation, including Return, Shift-Tab, cursor chords, Ctrl-letter
shortcuts and shared Caps state. Captured repeats are preserved; there is no
repeat timer. Physical BREAK becomes one Escape, while a title gesture consumes
Escape/BREAK without also delivering it to the application.

[Development evidence](../development/aes-application-input-ai3.json) covers
original-recipient delivery with two AES clients and the native console,
close/reopen, source-specific loss, physical Ctrl-C/BREAK, title cancellation,
window controls and console publication races. The console race probe was
updated to include the worker's existing desktop wake mask after the integration
merge; its former probe string no longer matched the worker.

Reserved bank-zero delta is **0 fixed + 0 per public Task + 0 private idle**.
The new shared upper data has 84 payload bytes (64 scans, a three-byte array
reference, one Caps byte and a sixteen-byte key snapshot), plus at most one byte
of placement alignment. Per-registration storage and stack reservations are
unchanged. The evidence records emitted routine growth and measured stacks;
public input waits and pointer gesture routing remain pending.


## AI4 — Content gestures and GUI locks

The presenter now classifies each fresh physical sequence once. A focused GEM
work-area press retains its application through release, including outside
coordinates and later focus changes. Activation, title and close sequences
remain native through release; accepting `WM_TOPPED` cannot cause click-through.
Mouse-control owners receive content input outside their window, while a
windowless owner provides exclusion only.

Application routing happens before the native deferral decision. Update locks
therefore freeze native actions without blocking content release. Competing
locks wait for a physical sequence to end; its application owner may acquire
and recurse. Released deferred native work does not prevent an update owner
from upgrading or unlocking. Baselines and idle motion in that queue do not
mistakenly acquire gesture ownership. Deferred title gestures also own BREAK.

Close and loss cancel application capture until an observed release. Raw/
normalized loss and input FIFO overflow retain source-specific diagnostics;
there is no synthetic successful release. Coherent snapshots and eligibility
are refreshed after focus and lock changes, with a wake when ownership handback
makes a level match possible without a new edge. Windowless registrations also
receive pointer snapshots for the later combined-wait output contract.

[Development evidence](../development/aes-application-input-ai4.json) covers
131 normalized presenter/lock assertions, physical window controls, inbox and
lock regressions, and native widget interaction. The inbox fixture explicitly
isolates its synthetic eligibility from production routing. The older widget
continuation probe now names `PAINT_CONTENT`; literal phase 1 had become title
painting during PI3 and could no longer hold an object continuation.

Reserved bank-zero delta remains **0 fixed + 0 per public Task + 0 private
idle**. Shared upper data gains 27 payload bytes plus at most one alignment byte.
Per-registration storage, fixed banks and stack reservations are unchanged.
The pointer fixture measures a 355-byte root stack peak and 177 bytes on its
1,024-byte peer Task; all checked floors and domain guards pass. Broader UI
latency work and PI4/HY4 remain open.
