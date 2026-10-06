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
