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

## Longest presenter work units after IL3

The [presenter work-unit record](../development/presenter-work-units.json)
replays the existing optimized IL3 active-client image with additional passive
Action! and checked C call-site markers. The 100-frame scrolling call probe
and the original panel's ten gestures per idle/scroll/disk load pass. Both
reproduce their original latency distributions, samples and workload progress
exactly; the panel also reproduces its input decomposition and feedback results.
The image, compiler, machine configuration and workloads are unchanged.

The longest measured gesture-window units, ranked by charged presenter CPU,
are below. Wall time belongs to the same invocation, including interrupts and
other Tasks. These are maxima, not percentiles. Nested rows overlap and must
not be added. “Disk” identifies the concurrent workload; the timed console
presentation is repaint work, not filesystem execution.

| Unit | CPU | Wall time | Load |
| --- | ---: | ---: | --- |
| Console dirty-cell presentation, `CONSOLEDISPLAY.Cells` | 94.556 ms | 161.895 ms | disk |
| Widget strip/chunk, `DESKWIDGETS.Paint` | 47.450 ms | 113.802 ms | disk |
| One console text call, `CONSOLEBITMAP.Text` | 39.510 ms | 66.907 ms | disk |
| Desktop/AES control admission, `DESKHOST.Controls` | 25.780 ms | 61.028 ms | disk |
| Widget input/model commit, `DESKWIDGETS.Input` | 8.069 ms | 14.718 ms | idle |

Console presentation is the largest interactive unit. `Cells` permits 160
cells across up to four rows before returning. The longest scrolling example
uses 88.396 ms CPU for three text calls, including 115 `blit_glyph` calls and
three list submissions. Its disk counterpart uses 94.556 ms. The separate
100-frame scrolling probe confirms that an apparently slow paint-pump interval
actually spends 87.922 of its 96.129 ms CPU inside `Cells`; the paint pump itself
uses only 1.273 ms.

Clipping loses the console's fast text-run path. In
[`GemBitmapTextClip`](../../ports/gem4xe/hosted/hosted-dispatch.inc), the fast
`GemBitmapText` call applies only when the entire original run fits the clip.
An obscured row takes the per-glyph path even for its wholly visible cells.
The measured examples contain no `VbxeOwnerText` calls inside those three text
draws. This makes preserving the fast path for complete visible cells, with
separate handling of cut edge glyphs, a concrete optimization candidate.

List admission is expensive independently of raster size. In the 94.556 ms
console example, three `VbxeOwnerSubmit` calls consume 48.989 ms CPU. Of this,
42.569 ms occurs before the first fence in each submission. Source flow places
argument/record decoding, extent checks and work accounting in that prefix;
the remaining 6.420 ms includes upload, launch and fences. This is a boundary
measurement including call overhead, not an instruction-only validation count.
All nine fence calls together consume only 1.344 ms, including their overhead,
so blitter waiting is not the dominant charge in this example. The producer
also performs geometry checks while building commands. The trusted internal
producer/owner path is therefore a stronger candidate for avoiding repeated
checks than further timer-wrapper optimization.

Widget work has the same submission cost plus substantial fill construction.
The 47.450 ms paint invocation draws **two objects**, emits 15 `GemWidgetFill`
calls and makes three list submissions. Exclusive fill work is 15.868 ms;
inclusive list submissions cost 17.893 ms, with 15.053 ms before their first
fences. All seven fence calls together cost 0.643 ms. The existing four-object
budget does not bound CPU tightly: this case never reaches four objects.
Reducing that count alone cannot guarantee a short button-feedback interval.
Control admission is also material: the slowest measured call uses 25.780 ms,
including 16.938 ms in retained-model calls. Label patching currently stages
the admitted context and rebuilds/deduplicates its label storage; it deserves
a separate finer breakdown after the larger rendering costs.

There are **zero `vram_win` entries** in all three measured load windows.
Whole-page staging transfers therefore do not explain these interaction tails.
Startup is different: the initial `CONSOLEBITMAP.Run` takes 1028.774 ms CPU
before the first worker loop, including 284.995 ms in owner reads and 237.604 ms
in owner writes. Startup, setup and the full-redraw comparison are excluded
from the table. Across the complete presenter run, widget paint reaches
66.915 ms and control admission reaches 84.255 ms.

The timing unit also matters. The older panel observer's “turn” runs from
one paint-pump entry to the next. Observing the actual worker-loop boundary
instead gives a maximum measured turn of 137.784 ms CPU, while the longest
gap between input-service entries is 105.590 ms CPU / 162.052 ms wall time.
Input can be serviced between portions of one worker turn, so the turn maximum
is not itself an input-latency bound. Conversely, preemption or Yield lets
other Tasks run but does not make this presenter process input while it is
still inside a long synchronous draw.

Input consumption and model commitment have separate boundaries.
`DESKWIDGETINPUT.Advance` defers while `scene.busy` is set; the paint token can
survive several strips. Shorter drawing continuations must therefore preserve
the existing ordering/coherent strip publication while providing a safe model
commit boundary. Merely adding more input polling cannot resolve that wait.

The next candidates are: retain batched console text under clipping; remove
repeated admission work for internally constructed VBXE lists; then introduce
shorter measured rendering continuations/input boundaries and inspect widget
fill construction and label patching. These are recommendations, not changes
or claimed speedups. The raw-pointer cohort's off-CPU tail remains separate;
this investigation does not attribute the previous HY4 regression to IL1/IL2.
HY4 and the transient-pixel issue remain open.

This is optimized development evidence, not release or hardware qualification.
Guards and ownership checks pass in the replay. Only this analysis and its
record are added; the guest and demo are unchanged. Reserved bank-zero delta
is **0 bytes**, fixed, per public Task and idle, including guards, alignment
and unused capacity.

## Prepared VBXE lists

The first recommendation from the presenter work-unit analysis is implemented.
Private `VbxeOwnerSubmit` now submits records constructed by an admitted
internal producer without decoding and checking them again. Public
`VbxeSubmit` owns the existing complete raw-list validation. Both paths retain
the same uploader, chaining, dependency fences, deadlines and fault recovery.
Producer geometry checks and the 64-record / 8,192-work limits are unchanged.
The [driver notes](../../platform/altirraos/vbxe.md) and private header describe
the general, cursor and outline producers' obligations. There is no new kernel
operation or public ABI change.

The [development record](../development/vbxe-prepared-submit.json) compares the
original IL3 active-client panel image with a rebuilt optimized image using
the same passive observers and ten gestures per load. Maximum widget-paint
CPU drops from **47.450 to 33.319 ms** across the measured windows; maximum
console dirty-cell presentation drops from **94.556 to 53.863 ms**. The clipped
text path, object/cell budgets, worker scheduling and retained-model protocol
are unchanged.

| Panel p95 | Before | After |
| --- | ---: | ---: |
| Button consumption, idle | 42.370 ms | 38.077 ms |
| Button consumption, scrolling | 118.915 ms | 79.507 ms |
| Button consumption, disk | 103.243 ms | 71.666 ms |
| Button pixels, idle | 219.204 ms | 159.082 ms |
| Button pixels, scrolling | 299.283 ms | 199.246 ms |
| Button pixels, disk | 259.537 ms | 179.375 ms |

All functional, final-pixel, guard and ownership checks pass. The feedback
observer records no invalid-color pixels in any of the sixty measured edges;
its post-model observation window and pointer exclusion are unchanged, so this
does not establish whole-gesture flicker freedom. The continuous AES workload
completes fewer exchanges in the shorter gesture cohorts: messages change
from 98/134/120 to 90/108/105 and timer waits from 49/68/60 to 45/55/53 for
idle/scroll/disk. These are the original completion-paced workloads, not an
equal-offer comparison. Individual component maxima can still rise: widget
input/model commitment reaches 8.750 ms instead of 8.069 ms, and control
processing remains roughly 25 ms.

**HY4 remains open.** Idle panel consumption still exceeds its 28.374 ms
frozen limit. The raw-pointer cohort and complete frozen/matched-native
comparator were not rerun for this focused change. The timing evidence does
not qualify the entire GUI or close the earlier transient-pixel issue.

Optimized development checks pass:

- Four G3 cases: pattern/public raw-list rejection, NMI at mapping boundaries,
  busy timeout recovery and failure to quiesce. Public wrong-owner/empty calls,
  invalid later-record rejection without drawing a prefix, maximum and
  bank-crossing lists remain covered.
- All 87 G4 rendering cases, including clipping, pixels, invalid batches,
  fault/reopen and OS restoration.
- All 62 cursor cases, including edge nibbles, list contents and recovery.
- Fifteen widget pixel stages. Three new stages check maximum-screen and
  minimum-size prepared XOR outlines, invalid replacement and exact restoration
  after move/hide. Existing stages cover clipped glyphs, offscreen widget
  continuation and rejected continuation geometry.
- The matched active-client panel run described above, plus 389 host tests
  with four historical-source skips and documentation/link checks.

Linked panel C executable code shrinks by **1,010 bytes** (73,751 to 72,741);
the unused public raw-list decoder is no longer linked into this image.
Reserved bank-zero delta is **0 bytes**, fixed, per public Task and idle,
including guards, alignment and unused capacity. Upper-RAM/VRAM reservations
and the existing demo package are unchanged. These are development checks,
not release or physical-hardware qualification.

## Trusted renderer geometry

BR1 of the [command builder plan](../plans/gem4xe/vbxe-builder-refactor-plan.md)
removes mode and full source/destination extent validation from private
`blit_mask`. Clipping and fixed screen, atlas, raster-strip and widget-strip
layouts establish geometry at the producer. Queue splitting, work/count limits,
upload and recovery are unchanged; public validation remains at its boundary.

[Development checks](../development/vbxe-builder-br1.json) pass: 389 host tests
(four historical skips), 87 renderer cases, 15 widget pixel stages and 62 cursor
cases including fault recovery. The original ten idle-load panel gestures also
pass pixels, feedback, ownership and guards. Maximum widget-paint CPU in that
window is 29.308 ms, versus 33.319 ms in the prepared-submit
baseline. Button-pixel p95 falls from 159.083 to 139.125 ms; consumption p95 falls
from 38.077 to 17.870 ms. These completion-paced samples do not close HY4.

Linked panel C code shrinks by 72 bytes. Reserved bank-zero delta is **0 bytes**
fixed, per public Task and idle, including guards/alignment/capacity. Upper-RAM
and VRAM reservations are unchanged. This is development evidence, not hosted
system qualification; no demo was refreshed.


## Table-based command construction

BR2 uses generated upper-memory tables for row limits, work, common strides,
indexed command offsets and screen rows. Queued records advance a pointer by
21 bytes. Work accounting is now 16-bit; VRAM addresses remain wide. Emitted
private construction no longer calls general multiply/divide helpers for these
operations. Strip-row calculation drops its wide shift loop; its inline code
shrinks from 53 to 35 bytes. Public text-fill area admission still multiplies.

[Development checks](../development/vbxe-builder-br2.json) pass: 393 host tests
(four skips), 87 renderer cases, 15 expanded widget stages, 62 cursor cases and
raw/optimized table-load probes. The original ten idle panel gestures pass
pixels, feedback, ownership and guards. Maximum idle widget-paint CPU falls
from BR1's 29.308 to 19.820 ms. Consumption p95 falls from 17.870 to 11.050 ms;
button-pixel p95 stays at 139.125 ms, while combined-visible p95 falls from
279.579 to 259.369 ms. These are completion-paced development samples, not HY4
qualification or a whole-gesture flicker proof.

Tables could not fit alongside the instrumented renderer's BSS in bank `$0D`;
the failed link is retained. They occupy 35,082 bytes of read-only bank `$0F`,
reserving the full 65,536 bytes including 30,454 unused bytes. Native code now
starts at `$100000` for images with tables. Queue state grows by two upper-RAM
bytes. Linked panel C code grows by five bytes versus BR1. Worker stack peak
falls from 727 to 715 bytes in this sample. Reserved bank-zero delta is **0 bytes**
fixed, per public Task and idle, including guards/alignment/capacity; VRAM is
unchanged. Cursor cases used the initial bank-D build; final bank-F loads and
renderer/widget pixels were checked separately. No demo was refreshed.


## Reserved widget glyph runs

BR3 admits complete nonzero-ink widget label cells once, reserves a fitting
prefix, then encodes records without per-glyph capacity or extent checks.
Actual records/work are published once per prefix; blank cells remain free.
The extraction patch preserves the atlas and general clipped/zero-ink path.
Mixed batches retain their existing order and capacity.

[Development evidence](../development/vbxe-builder-br3.json) passes all 16
widget stages, including sixteen run cases, negative screen edges, 63/64/65
cells, blank/mixed runs, count/work boundaries, staging, cursor restoration and
a failed second submission before the next chunk. Reopen resets the queue.
Also passing: 393 host tests (four skips), 87 renderer cases, 62 cursor cases,
four selected display recovery/NMI cases and raw/optimized table loads.
The original idle/scroll/disk panel protocol passes all thirty gestures.

Across the same 67 idle `GemWidgetText` calls, charged label CPU falls from
61.853 to 37.003 ms (40.2%); maximum label CPU falls from 3.020 to 2.529 ms.
Widget lists retain the same count and size distribution. Full idle paint CPU
falls from 859.818 to 830.669 ms. The largest paint is fill-dominated and stays
near 19.8 ms. Inclusive routine costs are nested and must not be added together.

Idle consumption p95 rises from BR2's 11.050 to 19.132 ms; button-pixel p95
stays at 139.125 ms. The longest idle input-service gap falls from 66.940 to
45.944 ms elapsed, with essentially unchanged maximum charged CPU (32.701 to
32.708 ms). Neither of the two slowest input intervals contains widget paint:
the worst has 23.538 ms runnable off CPU; the next includes cache/presenter
work. Retain this unfavourable sample. Lower label cost does not guarantee
lower per-run input p95 under completion-paced scheduling. HY4 remains open.

Two capacity tables add 2,050 bytes in the same reserved bank `$0F` (37,132
payload bytes, 28,404 unused, no table padding). Linked panel C code grows by
1,426 bytes; ordinary C data/BSS remain 3,559/12,359 bytes. Panel worker stack
peak is 743 bytes versus BR2's 715, leaving 1,561 above its interrupt floor.
Reserved bank-zero delta is **0 bytes** fixed, per public Task and idle,
including guards/alignment/capacity. Added upper-bank/VRAM reservations are
zero for this slice. No demo was refreshed.


## Integrated builder results

BR4 completes the [builder refactor](../plans/gem4xe/vbxe-builder-refactor-plan.md)
at the development tier. The [comparison record](../development/vbxe-builder-br4.json)
uses the retained prepared-submit image and the same compiler binary/ABI, ROM,
emulator configuration and original active-client panel protocol: ten gestures
under each load, sixty button edges. Extra passive internal markers do not
insert guest instructions. All selected renderer, widget, cursor and display
checks pass; ownership, stack/domain guards, cleanup and final pixels pass.

| Load | Maximum widget-paint CPU, ms | Button-pixel p95, ms | Input-consumption p95, ms |
| --- | ---: | ---: | ---: |
| Idle | 33.319 → 19.804 | 159.082 → 139.125 | 38.077 → 19.132 |
| Scroll | 31.317 → 18.006 | 199.246 → 159.081 | 79.507 → 77.486 |
| Disk | 33.184 → 18.601 | 179.375 → 159.072 | 71.666 → 54.237 |

These are before/after figures for the complete refactor. Relative to BR2,
the idle input p95 regression and its trace investigation remain recorded
[above](#reserved-widget-glyph-runs). The refactor reduces construction work;
it does not add an input-service opportunity inside a paint operation.
Maximum input-service gaps remain 45.944/90.824/90.703 ms elapsed for
idle/scroll/disk, down from 82.003/96.556/108.532 ms. Other presenter and
scheduling work still limits response.

Widget submission counts and complete size histograms are identical to the
retained sample: 107/108/108 lists, median 15, p95 38, maximum 40 records.
Observed queued work peaks at 5,226/7,840/7,840 units, below 8,192; emitted
fixtures separately reach the exact 64-record and 8,192-work limits. Fixed
cursor/outline bounds remain separate. No extent-validation calls appear in
the measured windows. The linked private builder has no general arithmetic
helper calls for chunk sizes/work, covered strides, record addressing or run
capacity. Other multiplication remains visible elsewhere; signed division in
label centering and partial-glyph coordinates remains a separate follow-up.

The feedback observer finds no invalid sampled pixels on all sixty edges.
It begins after model observation and excludes the pointer, so this does not
prove whole-gesture flicker freedom. Work is completion-paced: scrolling
completes two writes in both cohorts, while disk reads change from 27 to 22
and AES exchange counts also differ. These shorter gesture cohorts are not an
equal-offered-load throughput comparison. **HY4 remains open**; its full
frozen/matched comparisons and raw-pointer cohort were not rerun.

## Presenter input boundaries

PI1 of the [presenter latency plan](../plans/gem4xe/presenter-input-latency-plan.md)
is implemented at the development tier. Native admissions now service input
once per accepted/deferred request, matching the existing AES boundary. The
presenter also services input after cache/move token retirement and after
releasing a console borrow. Four shared admissions, endpoint alternation, the
late AES opportunity, widget commit ordering and scene ownership remain intact.
The boundaries introduce no Yield, timer binding or periodic idle wake.

The [PI1 record](../development/presenter-input-pi1.json) compares the retained
BR4 image with the same ten idle gestures and sixty-seven paint calls. Native
code grows by 332 bytes; foreign C segment payloads are byte-identical. New
passive markers distinguish individual native opcodes, deferral, widget input
advancement and input boundaries without adding guest instructions.

| Idle measurement, ms | Before median → after | Before p95 → after | Before maximum → after |
| --- | ---: | ---: | ---: |
| Input consumed | 2.966 → 7.260 | 19.132 → 25.449 | 38.583 → 25.700 |
| Model commit | 12.417 → 18.549 | 28.665 → 37.125 | 48.257 → 44.867 |
| Button pixels | 98.706 → 118.915 | 139.125 → 138.872 | 139.126 → 139.125 |
| Combined visible feedback | 179.038 → 159.081 | 259.370 → 259.370 | 259.621 → 259.382 |

Maximum charged CPU between input-service entries falls **32.708 → 31.615 ms**.
The corresponding elapsed intervals are 45.944 → 70.454 ms: the latter contains
32.263 ms off CPU. These intervals are selected by maximum CPU, not maximum
elapsed time. The two slowest input samples after PI1 spend 21.875/22.133 ms off
CPU and only 2.951/2.545 ms charged to the presenter. The original input p95
and button median regressions remain part of the result.

Because that cohort is completion-paced, an additional paired diagnostic uses
initially parked clients, twenty fixed offers over 400 PAL frames and sixteen
physical button edges. Both builds complete every offer inside the window and
consume every edge. Input median is 2.793 → 2.807 ms, while p95/maximum falls
49.855 → 48.815 ms; charged-CPU p95 falls 39.933 → 39.043 ms. The comparator
checks equal external schedules and machine settings. The baseline uses the
two pre-PI1 production modules from `5465f54`, with overrides recorded and
checked against those sources; compiler/ABI and memory layouts match.

This supports scheduling/workload phase as a contributor to the original
cohort's regression, rather than establishing a uniform improvement. The
fixed-offer diagnostic does not measure pixel latency. **Overall response-time
acceptance remains open.**

The longest steady native admission is `UPDATE_WIDGETS`, at 23.326 ms CPU.
The complete trace, including setup and the full-redraw comparison, contains
a 73.640 ms `SET_TREE`; closing and unregistering peak at 10.120/6.033 ms.
An input boundary cannot divide these individual operations. Maximum idle
widget-paint CPU is essentially unchanged at 19.802 ms. PI2–PI4 and any later
model-operation continuation remain distinct work.

Development checks pass: 395 host tests with four historical-source skips;
182 intake assertions with 69 injected/copied input samples consumed, native
deferral and arrival just before Wait; 138 C GUI-lock checks; twelve complete
cache/move pixel scenes; and the bounded eight-Task console/SIO fairness case
with 24 flood writes, eight small writes and a completed disk read. The settled
presenter records zero turns in fifty idle PAL frames. Guards, ownership and
cleanup pass. Twenty original idle button edges have no invalid sampled
feedback pixels; the observer still starts after model observation and excludes
the pointer, so this is not a whole-gesture flicker proof.

Reserved bank-zero delta is **0 bytes fixed, 0 per public Task and 0 idle**,
including guards, alignment and unused capacity. Upper-RAM and VRAM reservations
are unchanged; native data payload remains 10,118 bytes. The idle-only panel
worker touches 716 stack bytes, leaving 1,588 above its interrupt floor; this
is not a stack-saving comparison with the earlier three-load run. No demo was
refreshed. Original scroll/disk latency, raw-pointer and full HY4 comparisons
were not rerun; **HY4 remains open**.

The final tables use 37,132 bytes in one additional reserved 64 KiB CPU bank,
including 28,404 unused bytes; no table padding. Mutable renderer state grows
by two upper-RAM bytes. Linked C code grows from 72,741 to 74,100 bytes; worker
stack peak changes from 776 to 743 bytes in the original three-load protocol.
Every slice has **zero added reserved bank-zero bytes**, fixed, per public Task
and idle, including guards/alignment/unused capacity. VRAM reservations are
unchanged. BR4 itself changes no guest code or reservation. This is development
evidence, not hosted-system qualification; no demo was refreshed.

To reproduce the measurement on an existing optimized active-client image:

```sh
python3 tools/profile_vbxe_builder.py BUILD/program OUTPUT
python3 tools/analyze_vbxe_builder.py OUTPUT
```

The committed wrapper reproduces the measured observer definition exactly.
The analyzer excludes native IRQ/NMI and off-Task time from charged CPU,
retains kernel/C return tails and bus stalls, and reconciles exclusive work
with each enclosing span. Inclusive component times overlap. Table generation,
linked placement, image, trace, observer and tool hashes are retained in the
slice evidence; the failed initial bank-D link remains recorded as well.

## Widget paint input steps

PI2 of the [presenter latency plan](../plans/gem4xe/presenter-input-latency-plan.md)
is implemented. The [PI2 record](../development/presenter-input-pi2.json) retains
optimized development measurements and the PI1 comparison. Each widget C call
examines at most eight objects and draws at most one object part. The worker
can drain four ready steps of the same strip, with input between calls, without
renewing control admissions or adding a Yield. Actual frame work is separate;
client-only strips skip it. Scratch-only writes preserve the existing screen
change hint instead of requesting another pointer redraw.

One object was insufficient for a 63-character string clipped vertically:
the complete C call reached 67.000 ms CPU. Wide text on that fallback path now
resumes through disjoint 96-pixel clips, reducing that case to 15.045 ms. Whole
glyph rows retain the run encoder. Selected/disabled controls and focus XOR
retain exact pixels. The largest call in the expanded pixel fixture is
17.498 ms; eight maximum-depth rejected objects take 3.162 ms without setup or
publication, and 5.786 ms including final strip publication. These are measured
cases, not worst-case execution bounds. Strips remain sixteen rows high.

Only a two-byte horizontal offset survives in upper C storage; the existing
native index and stage retain traversal progress. The scene token still freezes
the model through the full repaint, and incomplete scratch is never published.
A fresh first chunk resets the offset. No client pointer or callback is retained
by the C renderer between calls.

The same ten idle gestures produce these results against PI1:

| Measurement, ms | Before median → after | Before p95 → after | Before maximum → after |
| --- | ---: | ---: | ---: |
| Input consumed | 7.260 → 5.739 | 25.449 → 20.388 | 25.700 → 23.428 |
| Model commit | 18.549 → 16.785 | 37.125 → 28.979 | 44.867 → 31.462 |
| Button pixels | 118.915 → 118.916 | 138.872 → 139.124 | 139.125 → 139.124 |
| Combined visible feedback | 159.081 → 198.994 | 259.370 → 279.580 | 259.382 → 279.580 |

Maximum idle widget-paint CPU falls 19.802 → 16.369 ms, and the longest charged
CPU gap between input-service entries falls 31.615 → 29.939 ms. The latter still
contains a 23.684 ms `UPDATE_WIDGETS` admission. The 20 ms gap target remains
open. Frame/strip work stays below 18 ms in this trace, including setup and the
full-redraw comparison; the complete run still has a 74.219 ms CPU gap around
larger atomic control work.

Button-pixel latency is effectively unchanged, while combined status feedback
regresses. Smaller C steps increase calls from 67 to 134 and total widget-paint
CPU from 825.701 to 944.228 ms. Widget list submissions rise from 107 to 174;
all submissions including the pointer rise from 361 to 427. Observed fence
calls rise from 809 to 1,008, with total fence CPU 51.732 → 54.388 ms. These
inclusive costs overlap and must not be added. Shorter work units have not
established a general visible-latency improvement.

PI1 is retained. Disabling its native-admission/cache/post-console boundaries
on the same PI2 renderer raises the longest idle CPU gap to 35.031 ms and the
whole-run gap to 100.531 ms, with essentially identical button pixels. Its
original input p95 is better without PI1 (11.050 versus 20.388 ms), but model
p95 is worse (32.447 versus 28.979 ms). Neither variant dominates every timing
measure; the extra boundaries remain useful for bounding consecutive work.
The comparison uses the pre-PI1 host module from `5465f54` and removes only the
post-console boundary from the current worker in isolated diagnostic builds.
The two foreign C images are byte-identical.

The fixed-offer diagnostic uses twenty exchanges over 400 PAL frames and sixteen
button edges. All three cohorts complete every exchange and consume every edge,
with 99 measured public calls and twenty expiries. PI1 → PI2 input median is
2.807 → 2.818 ms, but p95/maximum regresses 48.815 → 58.277 ms and charged-CPU
p95 rises 39.043 → 46.098 ms. PI2 without PI1 gives 2.700 ms median and 59.350 ms
p95/maximum. Equal offered load therefore does not establish an input-tail gain
from PI2. This diagnostic has no pixel observer and does not replace the
original panel results or HY4 acceptance.

Development checks pass: 396 host tests with four historical-source skips;
22 exact pixel scenes, including odd edges, overlapping objects, long labels,
disabled/focus effects, unpublished hidden-tree continuations and fault/reopen;
ten complete presentation scenes with 49 assertions; and 122 interaction
assertions including physical motion/press/release and hide/patch/close while
an object strip is held open. The fixture's settled-damage reader was corrected
to traverse the current damage list. The timing parser now matches the entry
stack at shared C returns; otherwise nested primitive returns truncate samples.

The intake case passes 182 assertions, consumes all 69 injected samples,
retains four admissions per turn and twelve late AES admissions. Console
fairness and zero presenter turns over fifty settled PAL frames pass. Passive
paint tracing observes at most four steps per turn and verifies input service
between consecutive steps. Guards, ownership and cleanup pass. The original
feedback observer finds no invalid sampled pixels, but still begins after
model observation and excludes the pointer; whole-gesture flicker freedom is
not established.

Reserved bank-zero delta is **0 bytes fixed, 0 per public Task and 0 idle**,
including guards, alignment and unused capacity. Upper-RAM and VRAM
reservations are unchanged. Native code grows 664 bytes (647,474 → 648,138),
C code grows 544 bytes (74,100 → 74,644), native data stays at 10,118 bytes and
C BSS grows two bytes (12,359 → 12,361). The idle panel worker touches 742 stack
bytes, leaving 1,562 above its interrupt floor in the existing 2,560-byte stack.
No demo was refreshed. PI3/PI4, the 20 ms gap target and **HY4 remain open**;
original scroll/disk and raw-pointer acceptance cohorts were not rerun.

## Bounded presenter text

PI3 of the [presenter latency plan](../plans/gem4xe/presenter-input-latency-plan.md)
is implemented. The [PI3 record](../development/presenter-input-pi3.json) compares
the retained PI2 image from `391cdc3` with the final candidate using the original
ten gestures under idle, scrolling and disk loads. Compiler/ABI, foreign C image,
ROM, emulator, machine settings and mouse cadence match. The candidate also
includes the separately committed [guarded interrupt-return fix](interrupt-reply.md#guarded-adapter-interrupt-returns)
`93bc2fd`, needed after the changed workload exposed a nested NMI during SIO's
guarded IRQ return. The old code fails its focused reproducer; corrected guarded,
ordinary and private-COP return cases pass.

Bitmap presentation now starts at most 32 glyphs from one dirty row. Dirty
endpoints advance only when the whole segment completes. A new visible edit
waits for the previous repair, preventing repeated scrolls from starving lower
rows. Retained commands, titles and console exposure carry a scalar glyph/row
offset; frame background, title and close mark have separate stages. The worker
services input between ready steps, preserving four paint steps and four control
admissions per turn. Text mode retains its four-row/160-cell budget.

Thirty-two logical glyphs were insufficient across overlapping clips: one
console text step still reached 42.643 ms CPU. The private presenter now returns
after one visible fragment, retaining the scene token and re-resolving cells
under its next borrow. Vertically clipped text uses at most sixteen glyphs per
step because its raster fallback is more expensive. Public drawing drains the
same traversal synchronously. No borrowed source/view pointer survives a return,
and the existing scene token still freezes geometry and model data through the
entire operation. Cancellation, hide/show and drawing failure between fragments
preserve the accepted 64-byte prefix and release the token before cleanup.

| Maximum charged CPU, ms | PI2 → PI3 |
| --- | ---: |
| Scrolling console `Present` | 49.675 → 7.472 |
| Disk-load console `Present` | 49.168 → 7.929 |
| Idle input-service gap | 29.939 → 29.910 |
| Scrolling input-service gap | 57.021 → 26.561 |
| Disk input-service gap | 57.777 → 30.131 |

These samples exclude interrupt and off-Task time. The final steady gaps are
dominated by atomic `UPDATE_WIDGETS` admissions, reaching 23.735 ms CPU. The
whole run, including setup and full-redraw comparison, still has a 74.184 ms
CPU gap and a 72.526 ms `SET_TREE` admission. The **20 ms gap target remains
open**; the smaller text steps are measured cases, not worst-case bounds.

| Response, ms | Before median/p95 | After median/p95 |
| --- | ---: | ---: |
| Idle input consumed | 5.739 / 20.388 | 7.002 / 23.174 |
| Idle model commit | 16.785 / 28.979 | 20.957 / 34.132 |
| Idle button pixels | 118.916 / 139.124 | 118.915 / 139.124 |
| Idle combined feedback | 198.994 / 279.580 | 199.242 / 279.326 |
| Scrolling input consumed | 27.974 / 54.499 | 7.764 / 12.311 |
| Scrolling model commit | 46.480 / 78.819 | 19.612 / 37.360 |
| Scrolling button pixels | 138.873 / 179.036 | 98.959 / 139.124 |
| Scrolling combined feedback | 179.291 / 259.370 | 179.037 / 259.622 |
| Disk input consumed | 11.798 / 46.406 | 9.023 / 28.553 |
| Disk model commit | 30.138 / 68.983 | 30.366 / 58.310 |
| Disk button pixels | 119.159 / 179.049 | 119.159 / 179.112 |
| Disk combined feedback | 199.238 / 299.495 | 219.172 / 319.606 |

Scrolling feedback improves; idle button pixels stay unchanged, and disk
combined status feedback regresses. Background completions are two → one scroll
writes and 21 → 24 disk reads. AES message/timer counts are 88/44 → 88/44 idle,
102/51 → 92/46 scrolling, and 94/46 → 96/47 disk. These cohorts are completion
paced, so both duration and scheduling phase affect the offered background work.

The existing fixed-offer comparator passes identical relative schedules: twenty
exchanges over 400 PAL frames and sixteen physical button edges. Both images
complete all offers and consume all edges, with 99 public calls and twenty
native timer expiries. Input median is 2.818 → 2.795 ms, p95/maximum is
58.277 → 5.131 ms, and charged-CPU p95 is 46.098 → 4.274 ms. This supports
retaining PI3 despite the original idle input regression, but the diagnostic
has no pixel observer and remains sensitive to execution phase. It does not
establish a uniform visible-response improvement or close HY4.

Full repairs cost more in some cases. On the same expanded retained-text fixture,
replacing only PI2's painter reduces a long-title/70-glyph-command maximum
25.973 → 11.120 ms; total paint CPU rises 81.948 → 86.678 ms, and settled time
rises 240.670 → 280.782 ms. A partial-height repair falls 49.148 → 15.368 ms per
step, while total CPU rises 49.148 → 60.052 ms and settled time 120.335 →
160.447 ms. Exact pixels match. Settled times include two PAL frames.

In the overlapping-console fixture, fragment continuation reduces the
intermediate PI3 maximum 42.643 → 15.426 ms. Its two scrolling stages take
6.939 → 7.922 s and 10.589 → 10.971 s to settle. This compares two PI3 policies,
not the original PI2 binary. The accepted tradeoff is more frequent input
service at the cost of some throughput; broad console optimization remains
separate.

Development checks pass: 396 host tests with four historical-source skips;
nineteen exact presentation scenes with 117 assertions; the same final image's
fragment-fault replay with 111 assertions; twelve retained/background scenes
with 41 assertions; twenty-four existing batch-lifetime cases and six new
partial-row cases; eight bitmap failure cases; and eight-Task console/SIO
fairness with 27 flood writes, eight short writes and two disk reads. Earlier
non-desktop bitmap cases exercise the same ordinary path; final fragment and
retained-text fixtures use the final production image. Guarded return and native
IRQ regressions are recorded with the prerequisite fix. Guards, ownership and
cleanup pass. Passive traces retain the list ceilings and confirm input between
consecutive paint steps without exceeding four steps per turn.

The feedback observer finds no invalid sampled idle/scroll pixels. Disk has six
invalid sampled frames, at most four pixels, compared with five frames/four
pixels before. The observer starts after model observation and excludes the
pointer; whole-gesture flicker freedom is not established. Raw-pointer/outline
acceptance and release qualification were not rerun. **HY4 remains open.**

Reserved bank-zero delta is **0 bytes fixed, 0 per public Task and 0 idle**,
including guards, alignment and unused capacity. New continuation state uses
eleven live upper-RAM bytes: nine in the console fragment traversal and two in
the retained painter. The matched linked executable payload grows 3,952 bytes
(738,412 → 742,364), crossing into code bank `$1A`: one additional **64 KiB
upper-bank reservation**, including unused capacity. Native data grows
10,118 → 10,129 bytes within existing storage. The panel worker touches 796
stack bytes, leaving 1,508 above its interrupt floor; kernel peak remains 287.
VRAM reservations and production stack/data-arena sizes are unchanged. The
batch-lifetime fixture alone expands its small test arena from 2 to 4 KiB.
No demo was refreshed. PI4 remains the next comparison/attribution slice.
