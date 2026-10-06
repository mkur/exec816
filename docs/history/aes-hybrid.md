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

## HY4 Trusted device requests

The [device I/O contract](../reference/device-io.md) now treats valid request
storage, live bindings and correct reply ownership as caller preconditions.
Exec816 is a single-user system without application memory protection. Repeated
validation is not a protection boundary. The contributor instructions record
this policy; creation/open admission and normal operational errors remain.

The generic I/O path no longer repeats request-extent or wait-owner checks, and
resident dispatch no longer invokes `Bound`. Timer queue ownership derives the
slot from an already-established unit handle. Forbid, the native timer edit
gate, exact-request collection, cancellation state transitions and interrupt
completion remain unchanged. Stack/domain guards remain enabled. The earlier
invalid-handle and wrong-owner rejection fixtures are retired; valid use still
has executable coverage across all eight timer bindings.

The [trusted-request record](../development/trusted-device-io.json) compares the
previous optimized idle window with the new image for 100 PAL frames. Compiler,
machine, linked C segments and launcher match; the native I/O sources and build
identifier differ:

| Charged CPU median | Before | After |
| --- | ---: | ---: |
| `DoIO` | 1.374 ms | 1.045 ms |
| `SendIO` | 1.975 ms | 1.699 ms |
| `CheckIO` | 0.836 ms | 0.782 ms |
| `AbortIO` | 2.021 ms | 3.305 ms |

DoIO and SendIO medians fall by about 24% and 14%. Their p95 values fall from
2.844/2.069 to 1.047/1.802 ms in these windows. AbortIO goes the other way:
its gateway and Permit contain more scheduling work, while its inclusive timer
driver median stays near 0.90 ms. The current disk/scroll runs measure AbortIO
medians near 1.82 ms, but have no matched baseline. Continuous traffic changes
execution phase and completion/cancellation mix, so these results do not prove
a uniform latency gain. Before/after idle windows contain 72/76 complete AES
calls and 24/30 native expiries.

Kernel I/O gateways still cost about 0.65 ms per DoIO/SendIO in the idle run.
Timer submission still performs the existing native edit-gate exit/poll path;
this slice does not change that synchronization or remove gateway crossings.
Those remain candidates for a separate measured change. Pointer, button and
scanout acceptance was not rerun; **HY4 and AS4/TD4 remain open**.

Optimized development checks pass: 57 valid-binding assertions, 214 concurrent
timer lifecycle assertions, 17 C API assertions and 82 generic I/O assertions,
including 32 NMI publication checkpoints and exact-reply/lost-wakeup cases.
Idle, disk and scrolling desktop windows restore ownership with intact guards;
the loaded windows also make disk/console progress. The host suite runs 388
tests with four historical-source skips. No compiler ABI or context change
requires raw-mode testing in this slice; these checks do not qualify a release.

Reserved bank-zero delta is **0 bytes**, fixed, per public Task and idle,
including guards, alignment and unused capacity. Upper-RAM reservations are
unchanged. Emitted executable code shrinks by 3,299 bytes. The existing demo
package is unchanged.

## HY4 Caller device dispatch

The [caller dispatch plan](../plans/caller-device-dispatch-implementation-plan.md)
is implemented. Generated Close, BeginIO and AbortIO dispatch selects the
resident through `io_Device` on the caller's stack. SendIO and DoIO share that
BeginIO path and prepare the request once. The established-device routing COP,
its import bindings and Task-policy resident selection are removed. CheckIO and
exact collection retain kernel operations without looking up a device first.
OpenDevice retains its admission gateway.

Forbid/Permit, native context checks, checked compiler frames, timer edit gates
and driver completion/cancellation policy are unchanged. Only DoIO reads its
request after submission, while it still owns the reply path; nonblocking calls
do not touch a published request again. The queued fixture retains its kernel
protocol through explicit test-only Begin, Abort and Close entries, rejected in
production. The public API and record layouts are unchanged; internal selectors
and bindings are updated together. See the current
[resident contract](../reference/resident-drivers.md).

The [development record](../development/caller-device-dispatch.json) uses the
previous trusted-request idle run as its baseline. Both images use the same
compiler, machine configuration, launcher and linked C segments. Each continuous
window covers 100 PAL frames:

| Charged CPU median | Before | After |
| --- | ---: | ---: |
| `DoIO` | 1.045 ms | 0.394 ms |
| `SendIO` | 1.699 ms | 1.115 ms |
| `CheckIO` | 0.782 ms | 0.703 ms |
| `AbortIO` | 3.305 ms | 1.157 ms |

DoIO and SendIO medians fall by about 62% and 34%. The new traces contain no
I/O gateway interval inside either call, or inside AbortIO. SendIO p95 falls
from 1.802 to 1.159 ms. DoIO p95 rises from 1.047 to 1.495 ms: its longest samples
charge about 1.154 ms to native dispatch/return, while median native dispatch
remains about 0.052 ms. The earlier AbortIO window also contained substantial
scheduling charges. These continuous windows have different execution phases,
with 76/82 complete AES calls and 30/28 native expiries, so cancellation and
tail improvements cannot be attributed solely to the removed routing work.

The current disk and scroll windows pass with 16 reads and one complete console
write respectively, restored ownership, intact guards and zero AES failures.
Their DoIO medians are about 0.394 ms and SendIO medians 1.141/1.067 ms. They
provide current load evidence without matched before/after load measurements.
Pointer, button and scanout acceptance was not rerun; **HY4 and AS4/TD4 remain
open**.

The remaining SendIO cost is concentrated in timer-driver work: about 0.647 ms
exclusive of queue and binding helpers in the idle run. The existing native
exit/poll behavior remains unchanged. CheckIO still spends about 0.603 ms in its
kernel observation, and AbortIO about 0.808 ms in task-side ReplyMsg. These are
measured candidates for later work, not additional changes in this slice.

Development checks pass: the 23-assertion direct/diagnostic dispatch probe runs
raw and optimized; five optimized generic I/O cases cover lifetime, immediate
and queued reply handoff, 32 NMI publication checkpoints and the collect/Wait
gap. Timer binding, concurrent lifecycle and C API checks pass. Together these
execute 420 assertions. Five native context cases cover a valid register/stack
round trip and rejection of masked, wrong-DP, IRQ and switching contexts. The
context harness needed its platform include path restored and a four-byte entry
for its jump overlay; failed harness attempts and successful replacements are
retained in the evidence. The host suite runs 388 tests with four historical
source skips. This is development evidence, not release qualification.

Reserved bank-zero delta is **0 bytes**, fixed, per public Task and idle,
including guards, alignment and unused capacity. Upper-RAM reservations are
unchanged; emitted executable code shrinks by 1,500 bytes. The existing demo
package is unchanged.

## HY4 Caller completion observation

IL1 of the [I/O latency plan](../plans/io-latency-implementation-plan.md) moves
CheckIO to a checked caller-side helper. It observes the published completion
byte once, returning NULL while pending or the original full pointer otherwise.
It neither collects the reply nor changes signals. The obsolete kernel selector
and dispatch branch are removed; public signatures and layouts stay fixed.

The [IL1 development record](../development/io-latency-il1.json) compares the
previous caller-dispatch image with the same continuous, 100-frame PAL workload.
CheckIO median charged CPU falls from **0.703 to 0.111 ms** (84%); p95 is also
0.112 ms. DoIO remains about 0.394 ms and SendIO about 1.117 ms. These windows
complete 82/87 public AES calls and 28/29 native expiries, so scheduling tails
and cancellation costs are not equal-load comparisons. Linked C code, compiler
and machine configuration match. GUI acceptance remains pending IL3.

Development checks pass: 323 assertions across raw/optimized dispatch and
optimized timer binding/lifecycle fixtures, plus six native context cases.
These cover pending/terminal full-pointer results, repeated checks without
dequeue, stack and DP restoration, and rejection of masked, wrong-DP, IRQ and
switching contexts. Y remains call-clobbered under the compiler ABI. The host
suite runs 388 tests with four historical-source skips. This is not release
qualification.

Reserved bank-zero delta is **0 bytes**, fixed, per public Task and idle,
including guards, alignment and unused capacity. Upper-RAM reservations stay
fixed; emitted executable code shrinks by 119 bytes. The demo is unchanged.

## HY4 Timer edit exit

IL2 of the [I/O latency plan](../plans/io-latency-implementation-plan.md) removes
the timer edit exit's redundant Poll. Leave first retains an armed-queue hint,
then clears its edit and source-block gates. Every callback returns through the
existing IOCORE Permit; both its fast and general native return paths admit
completion under an outer Forbid. No driver-specific kernel operation is added.
The forced hint remains necessary when the first request becomes due between
its clock snapshot and queue publication. Budgets, ordering and cancellation
policy stay fixed.

The [IL2 development record](../development/io-latency-il2.json) uses identical
passive observers before and after the change. On the unchanged IL1 image, the
expanded observer reproduces all previous per-operation CPU distributions.
SendIO median charged CPU falls from **1.117 to 0.644 ms** (42%); p95 falls from
1.141 to 0.669 ms. DoIO remains 0.393 ms and CheckIO 0.111 ms. The timer exit's
inclusive median falls from 0.534 to 0.003 ms, while Permit rises from 0.056 to
0.115 ms as it takes over native source service. The measured saving therefore
includes that transferred work. The old Poll alone cost 0.530 ms.

These are continuous 100-frame PAL windows, with 87/82 complete public AES calls
and 29/28 native expiries. Component percentiles are not additive and scheduling
phases differ. Linked C code, compiler and machine configuration match.

Development checks pass with 371 assertions. A new emitted probe injects one
real VBI at each of six boundaries, with and without an outer Forbid: after the
snapshot, before Leave, before/after clearing the edit flag, after unblocking,
and after Leave returns. It then disables further VBIs and inspects the reply
before another kernel call. All twelve cases complete exactly once with the
original exclusion depth; the first-enqueue cases confirm raw VBI produced no
hint before publication. Queue capacity/FIFO, concurrent expiry/cancellation,
six interrupted snapshot words and the C API also pass. Host checks run 389
tests with four historical-source skips. These are optimized development
checks, not release qualification.

Reserved bank-zero delta is **0 bytes**, fixed, per public Task and idle,
including guards, alignment and unused capacity. Upper-RAM reservations stay
fixed; executable code shrinks by another 11 bytes. The demo is unchanged.
Visible GUI acceptance remains pending IL3.

## HY4 GUI rerun after I/O reductions

IL3 completes the [I/O latency plan](../plans/io-latency-implementation-plan.md).
The [development record](../development/io-latency-il3.json) rebuilds native,
registered-idle AES and continuously active AES fixtures from `f17934d`, for
both the panel and the AS0 raw-event pointer window. It retains the original
10 panel gestures per idle/scroll/disk load, 30 pointer motions and 30 button
edges per cohort, quiet pointer application, physical keyboard/BREAK checks
and unchanged continuous GEM exchange with a 100 ms sender timer.

All six functional runs pass, with intact guards and restored ownership.
Panel scrolling and disk reads continue. Active panel cohorts complete
98/134/120 messages and 49/68/60 timer waits for idle/scroll/disk respectively;
the pointer cohort completes 42 messages and 21 timer waits. Registered-idle
clients complete no background exchanges. Three additional 100-frame call-cost
windows pass with zero AES failures, 16 disk reads and one complete console
write in the respective loaded windows. CheckIO medians are 0.106–0.111 ms,
SendIO 0.574–0.644 ms and DoIO 0.393–0.394 ms.

**HY4 and the AS4/TD4 successor latency gate remain open.** The unchanged
comparator fails 18 of 70 rows across frozen-AS0 and matched-native comparisons;
these include repeated comparisons of the same measurement against different
controls. No allowance or workload was relaxed. Active-client input p95 is:

| Capture to button consumption | Previous HY4 | IL3 | Frozen limit |
| --- | ---: | ---: | ---: |
| Panel, idle native load | 33.279 ms | 42.370 ms | 28.374 ms |
| Panel, scrolling | 133.819 ms | 118.915 ms | 104.158 ms |
| Panel, disk work | 126.738 ms | 103.243 ms | 90.245 ms |
| Raw pointer window | 29.326 ms | 35.102 ms | 14.089 ms |

API savings do not produce a uniform improvement in GUI tails. These are
continuous workloads with different completion counts and scheduling phases,
not equal-throughput comparisons. Active pointer visibility passes, but panel
button pixels and combined visibility also fail several comparisons. Two small
registered-idle misses remain: disk button consumption is 91.372 ms against
90.245 ms, and pointer-button consumption is 9.107 ms against 9.089 ms. The
record retains these and the 0.014 ms active disk-pixel miss without rounding
them into passes. All render-quantum growth comparisons pass.

The actual active-pointer p95 sample divides into 22.202 ms runnable off CPU,
10.680 ms charged presenter CPU and 2.221 ms interrupt time. The presenter was
already runnable at capture. In the scrolling and disk panel passive-p95
samples it was already selected, then spent 77.908/68.766 ms charged CPU before
consuming input, plus 24.695/18.046 ms runnable off CPU and 15.960/16.151 ms
in interrupts.
These are single-sample decompositions, not sums of independent percentiles.
They point the next investigation toward input service within presenter turns
and time lost between its turns. Further timer entry optimization alone does
not address those observed delays.

Final pixel/model checks pass. Intermediate feedback crops retain small
invalid-color observations under active GEM traffic: two idle-load edges
(10 observed frames, at most four pixels) and one disk-load edge (one frame,
one pixel). Native and registered-idle cohorts have none. The observer starts
after model/application observation and excludes the pointer footprint; it is
not a continuous scanout or whole-gesture flicker proof. No flicker-free claim
is made.

This slice changes documentation/evidence only. It uses the IL2 host result
(389 tests, four historical-source skips), plus content/link checks. These
optimized emulator measurements are development evidence, not release or
physical-hardware qualification. Reserved bank-zero delta is **0 bytes**,
fixed, per public Task and idle, including guards, alignment and unused
capacity; upper reservations also match across all six fixtures. The existing
OF816 demo package is unchanged.
