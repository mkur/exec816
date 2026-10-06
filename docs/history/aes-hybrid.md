# Hybrid AES refactor

[History](README.md) · [Plan](../plans/gem4xe/hybrid-aes-implementation-plan.md) ·
[Current contract](../reference/aes.md)

## HY1 Shared endpoint lifetime

[Development evidence](../development/aes-hybrid-hy1.json) covers a generated
144-byte request, a 106-byte shared directory and destination-owned pools of
sixteen 32-byte records. Registration publishes each endpoint under a short
Task-side guard. Exit withdraws admission and waits for publishers while the
presenter continues serving other requests. The final publisher signals it;
retirement drains queued records before acknowledging the caller's cleanup.
The old public message/event path remains active until HY3.

Raw and optimized C/Action! layout/context probes each pass 1,041 checks in each
of two Tasks. The optimized registration fixture passes 233 checks, including
independent binding tables, receive-signal exhaustion, capacity/ID limits and a
publisher held across destination exit. Heap, signals, Task leases, stack guards
and OS restoration pass the existing ownership checks. The host suite passes
368 tests, with four unavailable historical-source checks skipped.

Reserved bank-zero delta is **0 bytes**: fixed adapter/kernel, root, every public
Task and private idle, including guards, alignment and unused capacity. The
service now occupies 1,806 upper-RAM bytes (1,808 allocated). Each registered
client uses 784 allocated bytes for its context, two ports and message pool,
compared with 216 previously. At four clients the heap increase is 2,384 bytes;
old FIFO and shared timer storage remain during this transition. Existing arena,
stack/DP and bank reservations are unchanged. The registration fixture observes
at most 167 bytes touched in its 1,024-byte C Task stacks; the presenter touches
606 bytes of its 2,560-byte stack.

This is development evidence on the recorded emulator inputs. The original latency acceptance gates remain pending; this does not qualify a
release or hardware profile.

## HY2 Caller-owned standalone timers

[Development evidence](../development/aes-hybrid-hy2.json) records standalone
`evnt_timer` moving to the caller's public `timer.device` binding. It opens
lazily, owns query/alarm records and a private reply port, and retires every
submission before reuse or exit. Combined waits still use the presenter until
HY3. RPC sequences advance only for actual RPC.

The desktop image now binds the existing public C device-I/O bridge. The image
checker also recognizes Calypsi's optional three-byte `_FillInd` spill helper at
DP offsets `$14–$16`. It fits the existing caller workspace; raw and optimized
context/bridge probes pass 1,045 checks per Task, plus 27 exact deadline vectors.
PAL and NTSC timer fixtures each pass 247 checks; the retained combined-event
fixture passes 121. The host suite passes 372 tests with four historical skips.

The passive 100-frame idle desktop observation accounts for 54 calls and 22
native expiries. Eleven standalone timer calls have exact request/client
attribution; native-reply-to-caller p95 is 3.112 ms in this cohort. Public timer
entry-to-result timing includes requested duration and context lookup, so it
is separate from the historical RPC submission interval. This is observer
validation, not acceptance of HY4's loaded latency limits.

Reserved bank-zero delta remains **0 bytes**, fixed and per Task, including all
guards and unused capacity. Each fully initialized client uses 912 allocated
upper-RAM bytes, including its 223-byte context (224 allocated) and 112 bytes of
lazy timer resources. Four clients add 512 heap bytes over HY1. The presenter's
112-byte timer allocation remains during this intermediate slice. The PAL timer
fixture observes 369 bytes touched in a 1,024-byte C Task stack; the native
presenter remains at 606 bytes in its existing 2,560-byte stack.


## HY3 Caller-owned messages and combined waits

[Development evidence](../development/aes-hybrid-hy3.json) records the atomic
migration of every message producer and consumer. Calls publish copied records
with `PutMsg`, consume with `GetMsg`, and wait on their own receive/timer signals.
One absolute deadline survives spurious wakes. Matching freezes readiness,
retires any alarm and only then consumes a message, preserving payloads on timer
failure. The presenter retains registration, endpoint retirement and GUI locks;
its FIFO, event scanner and shared alarm modules are removed. The version-3
private request is 86 bytes, with an explicit init/exit/update RPC allowlist.

The message fixture passes 1,483 checks; PAL and NTSC event fixtures each pass
364, and timer fixtures each pass 249. Registration passes 233 and GUI locks 138.
Raw and optimized layout/context probes each pass 1,045 checks in each Task.
Direct calls progress while the presenter is parked. Boundary injections cover
queue-check versus arrival, spurious wakes, cancellation versus expiry and clock
failure without message loss. The host suite passes 376 tests with four skips.

Reserved bank-zero delta is **0 bytes**, fixed and per Task, including guards,
alignment and unused capacity. The service is 698 bytes (704 allocated), each
fully initialized client uses 920 heap bytes, and the presenter timer allocation
is gone. Four clients plus the service use 4,384 heap bytes, 1,184 fewer than HY2.
Focused fixtures observe at most 529 bytes touched in a 1,024-byte C Task stack
and 649 bytes in the presenter's 2,560-byte stack. Guards remain intact.
HY4 retains the native GUI and loaded latency acceptance gates.

The passive 100-frame idle observation accounts for 71 calls and 23 native timer
expiries, with zero presenter turn entries or charged CPU during the measured
window. The observer now matches shared Calypsi epilogues to active public calls
and accepts an explicitly idle window only after validating the complete trace.
Direct write public-call p95 is 19.340 ms in this cohort; full wrapper timing
remains distinct from historical RPC submission timing. Loaded comparisons
remain HY4 work.

## HY4 Integrated proof; latency acceptance remains open

[Development evidence](../development/aes-hybrid-hy4.json) records the final
optimized image and the original comparison limits. Both instrumented and
uninstrumented integration runs pass 1,363 C checks. They cover update/mouse
ownership, frozen native pixels, deferred click/drag delivery, independent
messages/timers, a CPU-only peer, disk and scroll progress, repeated client
restart and orderly shutdown. Blocked painting produces zero presenter turns.
The settled idle registration control also produces zero turns in 50 frames.
PAL and NTSC event fixtures each pass 371 checks; the host suite passes 377 tests
with four historical-source skips. Guards and OS restoration pass.

The first HY4 measurements exposed redundant clock queries in combined waits.
The final helper uses a successful terminal alarm as expiry evidence and queries
the clock again only when a message precedes that reply. It retains simultaneous
readiness and error-before-consume semantics. The spurious-wake fixture confirms
one initial query and one unchanged deadline. A clock failure after alarm
publication retires the alarm, closes its timer resources and preserves the
arriving message. In the idle cohort, combined-wait
charged CPU p95 falls from 19.756 to 12.101 ms. The same two-second window grows
from 71 to 85 completed calls; this is changed completed load, not an equal-rate
throughput comparison.

The final idle, scroll and disk call windows account for 85, 70 and 73 calls,
respectively, with **zero AES presenter dispatches** in each. The disk window
completes 16 reads and the scroll window makes native output progress. Native
timer deadline-to-reply p95 is 1.267, 0.767 and 1.409 ms, respectively. Full public
call timing, caller CPU/off-CPU intervals and registration/exit RPC intervals
remain separate metrics. Standalone timer reply-to-caller p95 is 2.722, 1.988
and 10.855 ms. GUI-lock RPC latency is not sampled by these bounded call windows.

Native GUI latency still fails acceptance:

| Active-client cohort | Before clock-query optimization, p95 | Final p95 | Original AS0 plus allowance |
| --- | ---: | ---: | ---: |
| Pointer button consumption | 32.186 ms | 29.326 ms | 14.089 ms |
| Panel button consumption, scrolling | 192.679 ms | 133.819 ms | 104.158 ms |
| Panel button consumption, disk | 167.656 ms | 126.738 ms | 90.245 ms |

Pointer visibility passes. Several panel visibility/consumption limits fail,
and active GUI results also regress against parts of the existing pre-hybrid
latency follow-up. Idle registered clients pass the original AS0 comparisons;
the additional frozen-disabled scroll comparison misses its consumption and
button-pixel allowances by 0.61 and 0.11 ms. All failures are retained. The
original continuous application loops and 100 ms delay are unchanged, and
completed messages/timers are recorded for each gesture cohort. No lower-rate
workload replaces the acceptance workload. **HY4 and the AS4/TD4 successor
performance gate remain open.** Further caller CPU, scheduling and presenter
latency work needs its own scope; priorities and drawing ownership are unchanged.

Reserved bank-zero delta is **0 bytes**, fixed and per Task, including guards,
alignment and unused capacity. This slice adds no heap or arena reservations.
Four fully initialized clients plus the service use 4,384 allocated upper-RAM
bytes: 1,184 fewer than HY2's transition state, and 1,712 more than the original
shared-timer implementation. The integrated image defines 4,874 bytes in its
8,192-byte global arena. The same C and native code banks remain reserved;
the evidence includes their live contents, padding and unused capacity. The
final integrated C Tasks touch at most 545 bytes of their 1,024-byte stacks;
the presenter touches 750 bytes of its 2,560-byte stack.

`build/aes-hybrid/hy4/demo/exec816-demo.zip` contains the native desktop preview,
OF816, matching SYS/WORK disks, pinned ROM, guide, licenses and checksums. The
extracted package passes the physical boot/command/scroll/exit smoke test,
including a 249-frame PAL autoboot countdown. This native preview is separate
from the optional two-GEM-client proof; the changed AES C helper is not linked
into that preview. Standard shell/prime build defaults remain unchanged. These
are development checks, not release or physical-hardware qualification.

## HY4 Timing breakdown and equal offered load

The [diagnostic evidence](../development/aes-hybrid-diagnostics.json) separates
caller CPU categories and capture → ready → selected → consumed boundaries.
The [diagnostic guide](../guides/aes-latency-diagnostics.md) describes commands,
observer boundaries and comparison restrictions. Production behavior and the
original acceptance limits are unchanged. Repeating the original 85-call idle
window, 30-motion/30-button pointer cohort and all three ten-gesture panel
cohorts reproduces their previous latency distributions exactly.

The original continuous workloads show distinct bottlenecks:

| Measurement | Result |
| --- | ---: |
| Combined-wait device I/O charged CPU, p95 | 9.124 ms |
| Combined-wait context lookup/admission charged CPU, p95 | 1.015 ms |
| Pointer button capture to consumption, p95 | 29.326 ms |
| Pointer button cumulative runnable off-CPU time, p95 | 25.591 ms |
| Scrolling panel capture to consumption, p95 | 133.505 ms |
| Scrolling panel first ready to selection, p95 | 11.248 ms |
| Scrolling panel presenter charged CPU before consumption, p95 | 78.676 ms |

These percentiles describe different samples and must not be added. Across all
pointer button samples, runnable waiting accounts for 65.7% of total observed
delay. Across the scrolling panel samples, presenter CPU accounts for 60.1%.
This supports separate investigation of scheduling delay for the pointer,
presenter work before input consumption, and caller device-I/O costs. It does
not establish that priorities alone would resolve the GUI regression. In the
warmed call window, individual `DoIO`, `SendIO`, `CheckIO` and `AbortIO` charged
CPU p95 values are 1.669, 4.031, 0.837 and 2.317 ms respectively.

The additional diagnostic offers one exchange every 20 PAL frames for 400
frames, with 16 fixed-rate physical button edges. Each exchange retains the
sender's 100 ms timer; the receiver uses a 5 s safety timeout between offers.
The comparator verifies equal external schedules and machine settings:

| Native load | Offered | Started and completed within window | Pending at window end | Completed after drain | Complete public calls in window |
| --- | ---: | ---: | ---: | ---: | ---: |
| Idle | 20 | 20 | 0 | 20 | 99 |
| Scrolling | 20 | 17 | 3 | 20 | 84 |
| Disk | 20 | 20 | 0 | 20 | 99 |

Scrolling completes two native writes; disk completes 42 reads inside the
window. All 16 input edges are consumed in each cohort. The root pump delivers
offer notifications, so its console/DOS blocking can postpone sender admission;
the scrolling backlog is not evidence of AES service capacity alone. First use
also includes a lazy sender timer opening. No equal-rate comparison with a
pre-hybrid image is claimed. A continuous control on the same diagnostic image
passes 649 C checks and records 277 complete calls under the same fixed button
cadence.

Each fixed-offer run passes 133 C checks, drains every offer and restores
ownership with intact guards. The host suite passes 386 tests with four
historical-source skips, including nine focused observer/accounting regressions.
The original latency comparison still fails: **HY4 and the AS4/TD4 successor
gate remain open**. The diagnostic's fixed-rate input and offer distributions
do not replace the original acceptance workloads or scanout checks.

Reserved bank-zero delta is **0 bytes**, fixed and per Task, including guards,
alignment and unused capacity. Only the optional fixture changes guest code:
eight extra upper-RAM counter bytes and 182 extra C code bytes within the same
reserved banks. Production APIs, priorities, scheduler, AES, renderer and demo
package are unchanged. This is optimized development evidence, not release or
hardware qualification.

## HY4 Timer device call costs

The [I/O cost record](../development/aes-io-costs.json) and
[`--io-breakdown` probe](../guides/aes-latency-diagnostics.md#device-io-costs)
separate the C wrapper, assembly bridge, native dispatch, generic I/O, kernel
gateways and timer driver. Adding these passive observations to the original
85-call image reproduces its latency distributions exactly.

The original window charges about 0.03 ms to a C wrapper and 0.02 ms to assembly
marshalling per device call. Timer binding checks cost about 0.42 ms, mostly in
`UnitIndex`: it used general 32-bit remainder and division to identify one of
eight 24-byte open records. Queue insertion repeats that lookup. This makes
handle arithmetic a better first target than replacing the C bridge.

`UnitIndex` now checks the full address range before narrowing the offset, then
uses at most seven subtractions and rejects any remainder. Device identity,
alignment, active-binding and reply-port checks remain intact. Device records,
public APIs, Forbid/edit-gate protection and completion ownership are unchanged.

Matching builds of the current desktop fixture run the continuous exchange for
100 PAL frames. The linked C segments and launcher are identical; the only
changed recorded native source is `timerdriver.act`:

| Charged CPU median | Before | After |
| --- | ---: | ---: |
| `UnitIndex` helper | 0.336 ms | 0.046 ms |
| `DoIO` | 1.665 ms | 1.374 ms |
| `SendIO` | 2.560 ms | 1.975 ms |
| Combined-wait device I/O | 10.506 ms | 7.549 ms |

The helper median falls by about 86%. Combined-wait total charged CPU p95 falls
from 13.585 to 11.661 ms, but individual tails are mixed: `DoIO` p95 rises from
1.671 to 2.844 ms, with more gateway and Permit scheduling work in those samples.
These charges include conservative scheduling/return tails. Before/after windows
contain 75/72 complete public calls and 24 native expiries each; continuous load
does not fix offered work or execution phase. The distributions establish this
bounded optimization's observed costs, not a uniform latency gain. Pointer,
button and scanout acceptance was not rerun; **HY4 and AS4/TD4 remain open**.

Optimized development checks pass: 266 binding assertions cover all eight
distinct reply ports, every byte offset in the open table, invalid addresses,
closed handles and borrowed cancellation; 214 concurrent lifecycle assertions
cover expiry/cancel races and Task reuse; 17 C API assertions cover public I/O.
The measured desktop runs restore ownership with intact guards. The host suite
runs 388 tests with four historical-source skips. No ABI or compiler-context
change requires a raw-mode probe in this slice.

Reserved bank-zero delta is **0 bytes**, fixed and per Task, including guards,
alignment and unused capacity. Upper-RAM reservations are unchanged and emitted
executable code shrinks by 42 bytes. The existing demo package is unchanged.
