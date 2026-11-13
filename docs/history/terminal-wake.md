# Terminal notification signal separation

[History](README.md) · [Plan](../plans/gem4xe/terminal-wake-plan.md) ·
[Wait audit](viewer-wait-audit.md) · [TW1 evidence](../development/terminal-wake-tw1.json)

## TW1 Signal ownership

Terminal now allocates a dedicated console-view notification signal after
creating its synchronous session reply port. Subscriptions and the external
AES wait use that notification mask. A pending RPC reply therefore cannot
trigger the next refresh through `MU_EXEC`.

Failure to allocate the extra bit deletes the new reply port and returns
failure with no retained port, bit or heap allocation. Close unbinds input and
unsubscribes views before clearing/freeing the notification signal, then
deletes the reply port. A zeroed/partially opened record and repeated Close
remain safe. The message-port implementation and the 100 ms timer are unchanged.

The private Terminal record grows from 5,846 to 5,847 upper-memory bytes. Its
new bit-number field is appended at offset 5,846; existing fields retain their
offsets. The emitted layout probe checks the reply pointer, notification mask
and bit number along with the existing cell/pixel fields. No public ABI changes.

[test_gem_terminal_wake.py](../../tools/test_gem_terminal_wake.py) compiles the
actual platform source with real Exec signal/port calls. Both raw and optimized
native runs pass **35 checks**, covering complete signal exhaustion, one free
bit, exact rollback, distinct masks, a reply queued before `WaitPort`, unrelated
signal preservation, teardown ordering, pending notification clearing, repeated
Close and three reopen cycles. Stack/domain guards, ownership and EXIT pass.
Console/AES endpoints in this small probe are stubs that check ordering and wait
parameters; they do not establish real timer, input or console-view behavior.

The host suite passes 710 tests with four existing historical-source skips.
The complete eight-Task probe `bank_zero_budget`, `task_pools` and
`runtime_reservations` match the frozen IC2 probe. Reserved bank-zero growth is
**zero bytes** for fixed services, root, kernel, idle and each public Task,
including guards, alignment and unused capacity. The extra signal uses one bit
of existing Task storage. Upper-memory and VRAM reservations are unchanged;
the private allocation grows by one byte before allocator rounding.

```sh
python3 tools/test_gem_terminal_wake.py --output build/terminal-wake/probe-opt --mode opt
python3 tools/test_gem_terminal_wake.py --output build/terminal-wake/probe-raw --mode raw
python3 -m unittest discover -s tests -p 'test_*.py'
```

## TW1b Loaded APP signal bindings

The first package link exposed a missing binding: `AllocSignal`, `FreeSignal`
and `SetSignal` existed in resident C code but not the loaded APP import table.
APP ABI 37 appends these three reusable public calls, preserving all 127 earlier
ordinals. The generated native constant and current contract are updated; all
apps must be rebuilt. The kernel API and calling conventions are unchanged.

The [existing loaded relocation probe](../../tools/test_c_program.py) now
allocates bit 31, posts/snapshots/consumes its full-width mask and frees it,
checking exact signal-allocation return. Both raw and optimized APPs pass
25 native checks/four completed executions on the identical optimized native
provider, with two private instances, repeated execution, relocation, heap
return, stack/domain guards and EXIT. Generated-definition checks and 710 host
tests pass (four existing skips). See [TW1b evidence](../development/terminal-wake-tw1b.json).

The upper binding table grows nine bytes within its existing reservation.
Complete eight-Task bank-zero maps still match IC2: zero growth for fixed
services, root, kernel, idle and each public Task, including guards, alignment
and unused capacity. Upper-memory and VRAM reservations are unchanged.

TW2 real Terminal integration, matched viewer measurements and audited OF816
delivery remain pending. These are development checks, not a latency improvement
or hosted-system/hardware qualification claim.
