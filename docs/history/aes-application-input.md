# AES application input implementation

[History index](README.md) · [Implementation plan](../plans/gem4xe/aes-application-input-implementation-plan.md) ·
[Current INPUT contract](../reference/input.md) · [Current AES contract](../reference/aes.md)

Status: AI1–AI2 implemented, 2026-10-07. AI3–AI7 remain pending. Public AES input
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
