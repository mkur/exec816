# Exec memory allocation implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

The current Task kernel exposes AllocMem/FreeMem, AllocVec/FreeVec,
AvailMem/TypeOfMem and Allocate/Deallocate through `EXEC`, reporting ABI `$0400`.
Rebuild callers with the kernel. The [design](../reference/memory.md)
defines the public contract and its intentional differences from Amiga Exec;
the [implementation plan](../plans/memory-allocation-implementation-plan.md) records
the six commit boundaries.

## Allocation and ownership

[heapcore.act](../../lib/exec/heapcore.act) implements checked first-fit allocation,
splitting and two-sided coalescing with eight-byte MemChunks.
[heappolicy.act](../../lib/exec/heappolicy.act) registers unclaimed upper banks as
MemHeader regions and retains their HEAP ownership until shutdown. Ordinary
and LINEAR requests share those free lists. Ordinary AllocMem can request
65,536 bytes; ordinary AllocVec can request 65,528 payload bytes, with its
private eight-byte prefix in the same bank. LINEAR can cross banks within one
registered region.

Persistent heap metadata occupies a reserved prefix in the configured kernel
bank. The native wrappers fit the existing 4 KiB upper-RAM helper reservation.
There is **no added bank-zero reservation**, fixed or per task. Complete budgets,
including guards, alignment, unused capacity and loading reservations, appear
in each qualification record and the [capacity note](../architecture/task-capacity.md).

Allocations have explicit shared lifetime. Another task can consume and free a
buffer after its creator exits or its execution slot is reused. RemTask does
not reclaim allocations, including storage reserved by an interrupted clear.
An IRQ consumer must be stopped before its buffer can be freed. Shutdown uses
the trusted bank-claim ledger and does not follow possibly corrupt free lists.

## Native boundary and clearing

[task-memory.inc](../../lib/exec/task-memory.inc) validates the current gateway tag,
processor widths and caller-stack packet bounds before reading arguments.
Metadata work runs under the existing SWITCHING guard, allowing IRQs when the
caller entered with I=0. IRQ/NMI never traverses heap metadata or starts a
second policy activation. Memory dispatch enters its own service family
directly, avoiding the extra general Task-routing frame during deep coalescing.

[heap.s](../../platform/altirraos/heap.s) retains twelve bytes of invocation state
on the caller's stack. After reservation, it initializes a vector prefix if
needed and clears exactly the requested bytes using caller-owned DP scratch.
It holds no continuation on the shared kernel stack. Other tasks can allocate
and free while that clear is in progress. Incoming I and Forbid nesting retain
their meaning. The private-pool pair tail-calls the compiled engine; its caller
owns serialization.

The public native imports complete prefix initialization and CLEAR before
returning. Raw allocation COP packets are the internal reservation phase, not
a replacement application API. The [example](../../examples/memory.act) shows
ordinary and LINEAR calls with their matching free operations.

## Qualification

The records separate [ABI/layouts](../qualification/memory-exec-abi.json),
[private mechanics](../qualification/memory-exec-core.json),
[registration](../qualification/memory-exec-registration.json),
[placement and queries](../qualification/memory-exec-policy.json),
[public APIs](../qualification/memory-exec-api.json),
[concurrent allocation](../qualification/memory-exec-concurrency.json) and
[integration regressions](../qualification/memory-exec-regressions.json).
Each records the compiler, machine, generated code and image hashes.

Public clear tests poison a 262,145-byte payload and verify every returned byte
with an independent byte-wise reader, plus seven padding bytes and both
neighbours. A second task allocates and frees disjoint memory while the payload
is partly cleared. Separate tests cover I=1 callers and nested Forbid.

Lifetime tests hand off an allocation, remove its creator, reuse the Task and
slot, and free the buffer in the consumer. They also remove a task during CLEAR
and check that the reservation survives until an explicit valid free.
Functional eight-task tests admit all seven workers before releasing their
start barrier, then exercise allocation, vector clearing, yields and frees.

Forced race copies stop after split/coalescing link changes and during a query
until a real POKEY IRQ and VBI execute. The IRQ reads a retained buffer and
posts to a known waiter. The probes reject a memory COP from IRQ context,
verify the waiter cannot run inside the interrupted heap activation, then
check delivery after return. These deliberately stalled probes are separate
from timing measurements.

## Four-task serial measurements

The pinned 8× PAL profile uses POKEY divisor 14: about 126,675 baud, with a
78.942 µs hardware refill deadline. The same four-task fixture also runs
Signal/Wait, Yield and timed Sleep. Every observed transfer is replayed from
the identical XEX on the uninstrumented emulator.

| Allocator workload | 4,096 bytes, raw | 4,096 bytes, optimized | 65,535 bytes, raw | 65,535 bytes, optimized |
| --- | ---: | ---: | ---: | ---: |
| Ordinary allocation/free | 65.409 µs | 60.898 µs | 69.920 µs | 71.048 µs |
| Fragmentation and LARGEST queries | 64.282 µs | 60.334 µs | 72.176 µs | 70.484 µs |
| Multi-bank vector CLEAR/free | 60.334 µs | 59.771 µs | 68.793 µs | 68.793 µs |

Entries are worst observed hardware-ready-to-refill latency. Including the
five 4,096-byte control workloads in both modes, all **458,724 measured refills**
have zero deadline misses and zero byte gaps. The worst refill is **72.176 µs**.
The fragmentation workload starts with 24 allocations of 257 bytes, frees
alternating blocks to leave 13 chunks, then churns 513-byte ordinary and
65,537-byte LINEAR allocations while querying both LARGEST modes. CLEAR uses
131,073-byte vector payloads. The tested heap has one registered region;
separate model/functional tests cover separated regions.

The longest observed IRQ-masked interval is **84.299 µs**. Such an interval can
contain the refill itself and is not equivalent to ready-to-refill delay.
The largest completion-signal-post-to-worker-resumption delay is **30.842 ms**,
during the long raw fragmentation run. IRQ byte service continues while a
serialized scan postpones task execution. These are measured maxima, not
global bounds; an RX/turnaround buffer budget still needs its own requirements
and qualification.

This is a generated-byte TX pump, not a production SIO driver or physical-board
qualification. Eight-task concurrent baud qualification remains deferred.
No BANK0 heap region, dynamic Task storage, automatic allocation cleanup,
message ports or DOS is included in this allocator qualification. The later
[messages and ports record](messages-ports-implementation.md) covers port integration.

## Reproduction

Use the repository's pinned compiler, ROM and corrected emulator builds:

```sh
python3 -m unittest discover -s tests
python3 tools/test_heap.py --suite api --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge --output build/memory-api
python3 tools/test_heap.py --suite concurrent --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge --output build/memory-concurrent
python3 tools/test_signal_concurrency.py --compiler-dir build/actionc \
  --workload compute --workload yield --workload signals --workload sleep \
  --workload mixed --workload allocate --workload fragment --workload clear \
  --count 4096 --require-deadline --output build/memory-timing-short
python3 tools/test_signal_concurrency.py --compiler-dir build/actionc \
  --workload allocate --workload fragment --workload clear --count 65535 \
  --require-deadline --output build/memory-timing-long
```

The integration record names the exact regression selection. Raw bridge logs
contain authentication data and are not committed; published measurements and
artifact hashes contain no bridge credentials.
