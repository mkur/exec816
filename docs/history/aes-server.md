# AES service foundation

[History](README.md) · [Current contract](../reference/aes.md) ·
[C application guide](../guides/aes-applications.md) ·
[Implementation plan](../plans/gem4xe/aes-server-implementation-plan.md)

The AES service runs inside the existing console/desktop presenter. The first
source profile provides registration, copied messages, independent message and
timer waits, recursive GUI locks and cooperative retirement through ordinary
Exec messages and `timer.device`. It creates no kernel extension or service Task.

The native desktop and Control Panel continue to use their retained content
interface. These results establish the client/event/ownership foundation;
GEM windows, `WM_REDRAW`, visible rectangles and independent VDI workstations
remain the next compatibility milestone. This is development evidence, not a
hosted release or hardware qualification.

## Slices and evidence

| Slice | Result |
| --- | --- |
| [AS0a](../development/aes-server-as0a.json) | Generated 132-byte wire ABI, private C contexts, raw/optimized context/layout probes and frozen native baseline. |
| [AS0b](../development/aes-server-as0b.json) | Optional presenter endpoint, shared four-request intake budget, startup rollback and idle integration. |
| [AS0c](../development/aes-server-as0c.json) | Real C registration, retained Task leases, bounded capacity/ID exhaustion and retirement. |
| [AS1](../development/aes-server-as1.json) | Sixteen-entry copied message FIFOs and independent application waits. |
| [AS2a](../development/aes-server-as2a.json) | One shared alarm, checked cancellation/collection and setup rollback. |
| [AS2b](../development/aes-server-as2b.json) | GEM deadlines, PAL/NTSC expiry, combined readiness, error preservation and CPU-peer progress. |
| [AS3a](../development/aes-server-as3a.json) | Recursion, explicit/implicit mouse holds, try acquisition, eligible FIFO waits and exit release. |
| [AS3b](../development/aes-server-as3b.json) | Quiescent native lock grants, frozen pixels, continued cursor/device work and deferred gesture replay. |
| [AS4](../development/aes-server-as4.json) | Integrated proof and measurement tools implemented. Functional checks pass; relative latency acceptance remains open. |

AS3b exercises actual Control Panel feedback, native window movement, console
scrolling and real SDFS reads under update/mouse holds. No Layers token survives
a grant, and blocked drawing causes zero presenter turns in the measured idle
window. Release resumes the retained click and drag without another input edge.
Raw and optimized emitted pointer probes each pass 31 checks; the arbitration
fixture passes 138 C checks. Shutdown restores allocator, signal, Task-lease and
driver ownership through the existing emitted-code ownership oracle.

AS4 runs two resident C applications beside the production panel, console and
nominal 57.6k SDFS traffic. The observed run and identical-image replay each pass
1,284 C checks: update/mouse holds, a CPU-only peer, sequence-checked message
exchange, three restarts and both retirement orders. The root DOS Process owns
disk work. Stack guards and resource ownership remain intact; the settled idle
presenter and the blocked-paint window each record zero turns. Development host
checks pass 368 tests with four skips; focused event, alarm, message, intake,
pointer-layout and plain-console checks are included in the record.

## Memory and execution budget

Every slice adds **zero reserved bank-zero bytes**, both fixed and per Task,
including alignment, guards and unused reserved capacity. The presenter reuses
its existing 2,560-byte stack and C direct-page workspace. The integrated proof
uses the root DOS Process, native panel, filesystem and SIO workers, two C Tasks
with 1,024-byte stacks, and the presenter: seven public Tasks in the existing
eight-pool layout. The remaining large command pool is not consumed.

The AES service payload is 1,692 bytes, reserved as a 1,696-byte upper-RAM heap
allocation. A private C context plus reply port reserves 216 bytes per attached
Task. The service timer owns a 32-byte port and two 40-byte allocations containing
38-byte request records. Deferred pointer input has sixteen copied records;
queue overflow produces loss rather than fabricated button transitions. The
outline flag consumes one byte within the existing upper global arena.

The linked C image may use banks C and E for executable code, with data in D;
only actual foreign payload banks are reserved. The image builder checks exact
executable extents before native callback admission. No donor source is modified.
The existing Calypsi partial automatic-array initializer limitation is recorded
in the [C guide](../guides/calypsi-c.md); fixtures initialize all message/input
words explicitly rather than relying on that unsupported code generation.

## Timing and limits

The AS4 comparison uses the same native panel gestures under idle, console-scroll
and nominal 57.6 kbit/s SDFS loads, first with AES disabled, then enabled and idle,
and finally with two resident GEM clients. Button pixels have an independent
oracle; intermediate sampled pixels must match their before/after colours.
The observer samples completed scanouts, so visibility has up to one frame of
observation quantization. Label observations follow the button check and can
substantially overestimate first label visibility.

The original AS4 panel p95 observations, in milliseconds, were:

| Native workload | AES state | Button consumption | Button pixels | Complete button/label feedback |
| --- | --- | ---: | ---: | ---: |
| Idle | Disabled | 20.90 | 179.04 | 379.87 |
| Idle | Enabled, idle | 11.05 | 179.29 | 379.87 |
| Idle | Two active clients | 18.88 | 199.25 | 479.90 |
| Scroll | Disabled | 85.57 | 239.16 | 540.28 |
| Scroll | Enabled, idle | 89.36 | 239.41 | 540.03 |
| Scroll | Two active clients | 104.26 | 259.63 | 600.40 |
| Disk | Disabled | 79.75 | 219.30 | 520.47 |
| Disk | Enabled, idle | 90.87 | 239.25 | 520.08 |
| Disk | Two active clients | 100.21 | 279.35 | 540.36 |

These are functional passes, **not a latency-gate pass**. The frozen AS0 panel
image was replayed with the current oracle and reproduced its original results.
Its scroll feedback p95 was 479.90 ms: the final disabled build still adds about
60 ms, and the active build about 120 ms. Against the matched disabled build,
active GEM traffic also adds about 100 ms to idle complete feedback and 60 ms
to disk button pixels. All exceedances, including small ones, remain in the
machine-readable comparison; the original allowances have not changed.

Pointer comparisons use AS0's raw-event window and unchanged keyboard preflight,
with the production panel and a quiet application. The widget test window is a
different fixture and is not substituted for that baseline. Disabled and idle
AES pass these pointer comparisons. Active clients give 19.52 ms consumption
and 106.53 ms visible-motion p95, exceeding the frozen allowances.

The implementation removes repeated clock reads on unrelated GUI turns, avoids
redundant empty-port gateway calls and bounds AES intake during painting. It
captures input at active request/paint boundaries, prioritizes the existing GUI
paint quantum ahead of new console work, and continues ready paint without an
extra voluntary Yield. VBI preemption remains responsible for Task fairness;
blocked paint still sleeps on signals. No rendering quantum is enlarged. All
sampled intermediate button pixels satisfy the before/after-colour oracle.

AES call timing uses passive boundaries in the emitted image: binding submission,
service admission, public `ReplyMsg` invocation, and the binding's checked-result
epilogue. Timer observations separate the actual VBI deadline from native device
reply and later AES reply. Requested timer duration and VBI rounding are not
reported as device latency. Equal-named C static routines are resolved by checked
instruction prefixes, not an ambiguous linker symbol name.

The final 100-frame idle/scroll/disk call cohorts record 43/28/42 completed calls
and 16/8/14 native expiries. Native deadline-to-device-reply maxima are
1.40/0.22/0.73 ms; device-to-AES-reply maxima are 24.80/56.84/32.48 ms. The latter
includes presenter scheduling and event processing. In the idle active-client
cohort, Controls uses about 554 ms charged CPU over the two-second window;
event matching and alarm maintenance account for about 276 ms of that total.
The remaining work is to reduce presenter/IPC cost and resolve the native
complete-feedback regression before accepting AS4 and timer TD4.

The long observed proof enables instruction history for GUI lock/idle checks,
then uses state/progress checks for the CPU, exchange and restart phases. The
bounded call probes supply separate latency/CPU distributions; `--trace-calls`
retains whole-run instruction observation when explicitly requested.

## Latency follow-up

The [follow-up record](../development/aes-server-latency.json) keeps the original
AS0 limits and AS4 failures intact. It separates native widget cost from the
additional active AES workload:

- The panel uses the epoch, revision and state copied into its action event for
  an ordinary status patch. It reads a snapshot only to recover from loss or a
  rejected stale patch. The emitted fixture forces that recovery path.
- Small widget updates copy the live object/text prefix into staging and commit
  only that prefix. Validation remains transactional; capacities, allocation and
  immutable geometry are unchanged. Focus changes damage the title and focus
  underline instead of repainting the entire client.
- Clock reads no longer enter the timer queue-edit gate. They still use a checked
  snapshot under the public I/O protocol. PAL/NTSC deadline conversion uses
  equivalent smaller arithmetic, with the full 32-bit duration and 64-bit
  overflow cases retained.
- Event matching uses one client scan and acquires a fresh clock only when a
  timed wait needs it. The presenter handles expiries that arrive during painting
  or console work before yielding. Drawing gets its existing quantum before a
  reserved AES admission; both intake phases still share four slots.
- A pending native control gets a bounded opportunity after painting releases
  the scene, before another console write takes it. This does not add an idle
  wake, frame delay, service Task or kernel scheduling operation.

The final matched panel complete-feedback p95 is:

| Native workload | AES disabled | AES enabled, idle | Two active clients |
| --- | ---: | ---: | ---: |
| Idle | 279.58 ms | 299.54 ms | 379.87 ms |
| Scroll | 339.70 ms | 339.70 ms | 419.78 ms |
| Disk | 379.62 ms | 359.77 ms | 419.87 ms |

The disabled configuration now passes every frozen panel and pointer comparison.
Against the original AS4 run, native scroll feedback improves by about 201 ms
and active-client scroll feedback by 181 ms. All three panel cohorts pass their
functional/stale-retry checks and report zero sampled invalid button pixels.
Active pointer visible-motion p95 falls from 106.53 to 46.66 ms; consumption p95
is 17.43 ms, still above both frozen and matched relative allowances.

**The AES latency gate remains open.** Active clients add about 100/80/40 ms to
complete feedback against the new disabled idle/scroll/disk cohorts. The idle
AES scroll/disk consumption comparisons also miss their limits. The record
retains every failed row, including the active idle button-pixel increase of
20.21 ms against the unchanged 20.1 ms allowance. Renderer maximum CPU growth
passes throughout. Do not accept AS4 or timer TD4 on these functional results.

The final observed integrated proof and its identical-image unobserved replay
each pass 1,292 checks with restored ownership; blocked painting and settled idle
still record zero presenter turns. The intake test passes 166 checks, observes
12 deferred admissions and a maximum of four admissions per entire turn.
Focused timer checks cover 46 quick clock reads while an alarm is outstanding,
both conversion rates/overflow, and six actual NMI snapshot boundaries. Host
checks pass 368 tests with four skips. These are development checks.

The final 100-frame active-client idle/scroll/disk probes complete 46/32/45 calls,
with device-to-AES-reply maxima of 12.30/46.88/34.60 ms. Native deadline-to-device
reply maxima are 1.27/0.68/1.22 ms. Idle Controls uses about 566 ms charged CPU;
the client loops complete more calls than the original 43-call run, so these
fixed-window totals must not be mistaken for a per-call cost comparison.

An experiment that yielded immediately after a semantic widget action delivered
its application patch sooner but worsened button visibility. It was removed.
Additional callbacks inside event matching also failed to improve the measured
input tail and were removed. These diagnostic builds are not acceptance evidence.

The event fault fixture now explicitly admits its four timed clients before
injecting the shared clock error. The alarm transport fixture treats its
controller stage as work even with no application event waiting. These changes
remove dependence on the old pump timing; error, message-preservation, cancellation
and single-collection assertions remain. Intake accounting now includes the
post-paint admission and exercises both queues during a real repaint.

All three implementation slices reserve **zero additional bank-zero bytes**,
fixed or per Task, including alignment, guards and spare capacity. The new
presenter flag and automatic locals fit the existing upper arena and stack
reservations. Widget storage capacities and AES service allocations are unchanged.

Existing widget-feedback targets and the 125 kbit/s SIO timing gate remain open.
No periodic presenter polling or deliberate frame wait is introduced. The
optional proof is separate from the standard five-second shell/prime autoboot;
this work does not refresh or qualify the distributed demo package.
