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

This is development evidence on the recorded emulator inputs. HY2–HY4 and the
original latency acceptance gates remain pending; this does not qualify a
release or hardware profile.
