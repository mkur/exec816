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

## FD3 Standard alerts

The alert parser, ten-object layout, three donor icons and named/AESPB binding
reuse the same session and event loop. Operational return zero is distinct from
accepted one-based buttons. Allocation/fit failures paint nothing; failed owned
resource retirement keeps both session and alert storage available for retry.

Development checks pass: 92 optimized emitted assertions, six independent pixel
comparisons (90,784 pixels), and 423 host tests with four historical skips.
The target covers all icons, one/two/three buttons, defaults including none,
escaped delimiters, decoded bounds, valid 511-byte input and rejected 512-byte
input, all new allocation/setup/retirement boundaries, message preservation,
fit rejection and heap return. Physical input covers pointer, Return, Space,
temporary close, movement, two ordinary callers and clipped cover/exposure repair.
Private layout constants are checked from emitted objects in raw and optimized
C. No shared context/bridge layout changes in this slice.

The first fixture used an unsupported window kind; another signalled before
its peer had opened, letting that peer cover the measured alert. A final report
lookup referred to an unused constant removed by the linker. These failed trials
are excluded; the corrected setup and explicit layout probes pass.

The session grows by four live bytes to 315 (320 heap-reserved); an alert owns
514 live / 520 reserved upper bytes. The three icon run tables total 896 upper
read-only bytes and are hash-pinned through existing extraction. Ordinary Task
minimum checked margin is 412 bytes. Guards, heap return and OS restoration pass.
Bank-zero delta is **0 fixed, 0 per public Task, 0 private idle**. VRAM and Task
pools are unchanged; packaged integration remains FD4 development work.

## FD4 Loadable example and packaged desktop

`C:DIALOG.APP` demonstrates an alert before opening a window, a compiled editable
form in a borrowed window, repeated Apply within START/FINISH, and application
menu/move/close handoffs. The caller checks negative results before indexing its
tree and reconstructs its full work area after borrowed-content repair. Files
and calculator keep their event-driven loops. The example is packaged alongside
them; close one GEM application before launching it within current capacity.

The exact `build/standard-dialogs/demo-ready/exec816-demo.zip` passes its extracted
OF816 walkthrough on the recorded PAL/8x 65816/VBXE configuration and pinned ROM.
It checks the five-second autoboot, full-desktop rejection without leaks,
physical text entry and repeated Apply, pre-window and borrowed alerts, independent
scene pixels, shell disk work and counter progress while a form waits, cover and
exposure, menu/move handoffs, close/Stop during a form, three launches, and desktop
EXIT with a form still waiting. Files path editing and calculator `12 + 7 = 19`
also pass. Ownership/heap baselines return after collection; final guards,
read-only disk hashes and OS display/input restoration pass.

Focused development checks add a resource-loaded form interruption to the
resource fixture (102 assertions), and outward-root-border pixel coverage to the
form fixture (194 assertions, 35,332 pixels). Paced typing captures/routes/consumes
3/3/3 keys; the bounded burst delivers 8/8/8 and inserts three before field capacity.
Fourteen signed box-extent cases pass in both raw and optimized emitted builds.
The host suite runs 423 tests with four historical skips; the affected generator
checks and local documentation links pass.

| Physical pool | Reserved stack bytes | Measured bytes above floor |
| --- | ---: | ---: |
| Root 0 | 1536 | 708 |
| Ordinary 1 | 1280 | 711 |
| Ordinary 2 | 1280 | 844 |
| Ordinary 3 | 1280 | 385 |
| Ordinary 4 | 1280 | 390 |
| Ordinary 5 | 1280 | 184 |
| Large 6 | 2560 | 1521 |
| Large 7 | 2560 | 1899 |
| Private idle | 512 | 125 |
| Kernel | 1536 | 991 |

These are cumulative physical-pool fill watermarks, including earlier occupants.
The minimum ordinary-pool margin is **184 bytes** against the
128-byte target. Private idle retains its separate existing guard/reserve policy.
No stack pool grows. Per-slice reserved bank-zero delta is **0 fixed, 0 per public
Task, 0 private idle**, including guards, alignment and spare capacity; VRAM
reservations are unchanged.

Compared with the final SH3 shared C image, the production payload grows by
15,683 bytes: 14,774 code and 909 data, including 896 icon-table bytes. GEMSYS is
180,666 bytes including its component framing. Code now occupies `$0C`, `$0E`
and 7,768 bytes of `$10`; the additional bank reserves 64 KiB of upper capacity.
The native image begins at `$110000`. DIALOG.APP is 6,277 file bytes with a
66,877-byte linked span. Context/session/alert live and heap-reserved sizes are
340/344, 315/320 and 514/520 bytes respectively. Hashes, source inputs, per-slot
measurements and the unchanged compiler/platform pins accompany the
[machine-readable record](../development/standard-dialogs.json).

Excluded trials found unpainted example margins and incorrect emitted signed
box-thickness handling/outward clipping; the corrected target code passes the
final checks. One burst snapshot preceded its final queued key; the fixture now
waits for the existing inbox to drain. A screenshot-basename mismatch prevented
one report from being saved. Another final assertion wrongly applied the
ordinary-pool headroom target to idle and discarded the measurements. The final
replay writes the expected screenshot directly, saves measurements even on
failure, and gates ordinary pools 1–5 as specified. No failed trial is acceptance
evidence. A metadata-only builder follow-up includes example sources in future
demo manifests; the tested package is unchanged and this record retains the
example build hashes.

FD1–FD4 are complete at the development tier. This does not qualify real hardware
or close the existing HY4/PI4 latency gates.
