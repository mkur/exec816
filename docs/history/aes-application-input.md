# AES application input implementation

[History index](README.md) · [Implementation plan](../plans/gem4xe/aes-application-input-implementation-plan.md) ·
[Current INPUT contract](../reference/input.md) · [Current AES contract](../reference/aes.md)

Status: AI1–AI7 implemented, 2026-10-07. Caller-local input waits, the interactive
application and the extracted OF816 demo pass development checks. This is not hosted-system qualification; PI4/HY4 and the observed flicker remain open.

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


## AI5 — Public caller-local input waits

`evnt_keybd`, `evnt_button`, `evnt_multi`, `evnt_multi_moblk` and their parameter
blocks now use one local event transaction. All fifteen supported nonempty
key/button/message/timer combinations work. A button wait selects the first
matching retained edge, or an eligible level; single and inverse predicates,
quick down/up and repeatable held levels are covered. Unsupported arguments fail
before any payload is consumed, and windowless message/timer waits remain valid.

Interest precedes the final readiness check. A bounded scan copies one immutable
record per guard; timer I/O stays outside guards. The final decision reconciles
new arrivals and changed level eligibility, freezes results, retires the alarm,
and checks only source/lifetime epochs before committing. Input arriving during
cancellation stays queued for the next result. Loss retires only the lost
selected source; clock/device errors preserve all payloads. Button-loss recovery
asks the presenter once to refresh an already observed released baseline.

[Development evidence](../development/aes-application-input-ai5.json) records
396 optimized input API assertions (390 in the earlier raw wrapper run), including arrivals during cancellation, source-specific
loss after selection, close during a wait, byte-index wrap, pending unselected
loss, simultaneous timer/input readiness and newly eligible levels during clock
reads. The fixture rejects any presenter RPC for the event operations. Existing
event/timer checks pass on PAL and NTSC, and generated layouts/C/native bridges
pass in raw and optimized modes. Registration also passes with two separately
linked binding instances; its symbol renaming includes the new named wrappers.

Private wire version 8 uses two former scratch bytes for observed producer tails
and adds a two-byte level-selection flag. The inbox grows from 592 to 594 payload
bytes; combined storage grows from 1,140 to 1,142 but remains heap-rounded to
**1,144 reserved bytes per registration**. The binding dispatch table adds eight shared constant bytes; there is no new
mutable shared state, signal, Task or bank reservation. Reserved bank-zero delta is **0 fixed +
0 per public Task + 0 private idle**. An optimized 1,024-byte worker exercising
combined input waits peaks at 432 bytes, with 336 bytes above its checked floor.
The detailed evidence records code growth and every measured stack.


## AI6 — Ordinary interactive GEM application

The [GEM input example](../../examples/gem-input/input.c) now uses ordinary
windows, a private VDI workstation and a combined key/button/message/timer wait.
Its Activate control highlights on press, increments on release inside and
cancels on release outside. Escape/BREAK cancels a held control. The keyboard
label shows the translated scan/ASCII word; Tick changes after a one-second
wait. Each event starts a new timeout, so this is an inactivity indicator.
UPDATE is released before waiting. The resident wrapper owns attachment, Task
lifetime and translation of the native input-loss diagnostic into a retry.

[Development evidence](../development/aes-application-input-ai6.json) records
sixteen exact-pixel checkpoints, including buffered clicks during UPDATE,
independent instances, physical movement/close, source loss while armed and two
complete restart cycles. Task-capacity failure and exhausted-heap startup return
all allocations. The worker stack peaks are 529 and 550 bytes in 1,024-byte
pools, leaving at least 218 bytes above their checked interrupt floors.

The private model is 212 upper bytes per instance, 16 more than the counter.
The two models and wrapper use 452 zero-initialized bytes plus one initialized
byte and at most one byte of placement alignment; constants use 184 bytes.
Registration allocations and fixed reservations are unchanged. Reserved
bank-zero delta is **0 fixed + 0 per public Task + 0 private idle**. Production
body/wrapper objects contain 4,012 + 984 text bytes. AI7 packaging and cost
measurements remain pending; these checks do not qualify the hosted system.

The pixel oracle also found a Calypsi 5.18 array-indexing defect. In
`box[2]=box[0]+127`, emitted code reads the old destination slot instead of
`box[0]`. The [minimal reproducer](../../tests/programs/calypsi_array_copy.c)
initializes every element, so its results are defined: expected
`18,68,145,91`, observed `18,68,229,126` in **both** raw and optimized native
runs. [The diagnostic runner](../../tools/probe_calypsi_array.py) retains this
external compiler issue for a future toolchain update. The application computes
rectangle endpoints directly from the work-area origin. No actionc change or
compiler override was needed. A separate exact-pixel failure corrected the
indicator damage rectangle to cover all eight font rows.


## AI7 — Coexistence, measurements and packaged demo

`tools/build_demo.py --aes-input` packages two independent input applications
beside the native shell. The no-option shell/PRIMES selection and existing
counter profile retain their startup paths. The new ZIP contains OF816, the
pinned ROM, matching disks, a short guide, notices and checksums. Its exact
extracted boot image passed the five-second autoboot (249 observed PAL frames),
pressed/released/key pixel checks, focus/movement/close, the eight-Task pipeline,
scrolling BREAK, writable-disk byte/allocation audits and cooperative EXIT.

The prompt has six Tasks, three registrations (including the controller), and
three layers. A separate four-layer cohort keeps the native Control Panel,
two input apps and verified root disk reads live with seven Tasks. It passes
rapid A/B/C during application drawing, independent input, native Toggle
progress and exact heap/ownership recovery. The load fixture warms its root
console handle before recording the heap baseline, so a lazy I/O allocation is
not misclassified as application leakage.

[AI7 evidence](../development/aes-application-input-ai7.json) records twenty
physical edges per load, with one edge outstanding at a time. Raw publication,
presenter route entry and the correct caller's `MU_BUTTON` return are matched to
the same edge. Completion means the entire control matches an independent pixel
oracle in completed scanout; it includes frame/observation delay. Values below
are **median / p95 / maximum milliseconds**, pooling press and release:

| Load | Capture → route | Route → event return | Return → visible | Capture → visible |
| --- | --- | --- | --- | --- |
| Idle | 17.7 / 30.6 / 35.1 | 7.5 / 28.3 / 28.8 | 128.7 / 185.9 / 195.2 | 154.3 / 212.4 / 214.6 |
| Scroll | 15.1 / 22.1 / 39.2 | 7.5 / 28.7 / 30.6 | 115.0 / 183.3 / 193.2 | 134.3 / 193.4 / 215.2 |
| Disk | 18.2 / 30.7 / 82.9 | 27.5 / 50.3 / 58.2 | 142.1 / 247.5 / 282.1 | 193.7 / 275.1 / 314.9 |

The redraw/presentation interval dominates this example. Median charged caller
CPU is about 68–72 ms and presenter CPU about 49–53 ms per edge over the complete
feedback interval; interrupt bodies and other Tasks are separate. This first
ordinary GEM application is functional but its redraw path needs later tuning.
These small cohorts do **not** close PI4/HY4 or establish a regression against
the differently implemented native widget control.

The same 60 edges in an unobserved replay have **zero guest-clock difference**
in capture-observation-to-visible intervals. Pointer sampling takes a median
8.04 µs in each load; maximum observed sample gaps are 317.0, 317.2 and 513.5 µs
for idle, scrolling and disk respectively. These are current absolute costs,
not an inferred before/after capture delta. Full source/ROM/emulator pins and
per-edge provenance are retained in the evidence.

Reserved bank-zero delta from AI6 is **0 fixed + 0 per public Task + 0 private
idle**, including guards, alignment and unused capacity. Production upper-memory
and VRAM reservations also remain unchanged. The older compaction-baseline tool
still reports the pre-existing larger stacks in slots 6/7; those are not AI7
growth. Packaged application stacks peak at 550 and 547 bytes in 1,024-byte pools.
The 408-test host suite passes with four expected historical skips; all observed
stack/domain guards, resource retirement and OS restoration checks pass.

The frozen distribution was built with the production builder committed in
AI6. AI7 subsequently added load/panel fixture options to that builder; the
application, wrapper and packaged source inputs are unchanged. Its SHA-256,
checksums and extracted walkthrough are recorded rather than silently replacing
the tested artifact. Broader release qualification, public forms/objects,
resource loading, rectangle events and multiple clicks remain separate work.
