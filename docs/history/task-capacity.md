# Eight-task configuration

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/task-capacity.md) and [history index](README.md).

The Task kernel supports **eight simultaneously live public Tasks plus
private idle** on the pinned AltirraOS 1 MiB platform. Root counts as one of the
eight. A waiting Task keeps its stack and direct page; a removed Task releases
its execution context for reuse. Priorities remain stored but ignored.
The default capacity is four; `--task-capacity 8` selects this larger layout
of the same implementation.

```sh
python3 tools/native_program.py --compiler-dir build/actionc \
  --tasks --task-capacity 8 --kernel-bank 1 --console \
  --source examples/signals.act --output build/signals-eight
```

The [example](../../examples/signals.act) admits six workers alongside root and
the native console worker, filling all eight slots. It waits for their
readiness, signals each, and prints `SIGNALS OK` through DOS after all retire.
Press Return to close the console and exit.
The generated `TASKSTACKS.StackLower(slot)` and `StackUpper(slot)` expose this
build's bounds. Prepare `tc_SPReg = tc_SPUpper - 2`; do not copy the old `$600`
stack-size assumption. Slot zero is root. The public Task is the same 62-byte
record at every supported capacity; use `EXEC.TASK_SIZE` and the generated
module, not private-context offsets. Signal semantics are in the
[public design](../reference/signals.md); implementation and timing limits are
in the [signal record](signals-implementation.md).

## Checked placement and lifetime

[config/kernel.json](../../config/kernel.json) provides `kernel_bank`, default 1;
`--kernel-bank` overrides it for a build. It must be a usable upper bank below
`MAX_BANKS`. The selected bank is the start of the shared kernel/application
image, which may span further banks. Bank zero retains adapters, CPU-required
stacks/DPs and the near-data arena.

For the generated capacity profile, the bank table occupies the first
`4 * MAX_BANKS` bytes of the kernel bank. Heap metadata follows, aligned to 32
bytes, followed by the 16-byte port registry. With 16 banks, the table is
`$01:0000–$01:003F`, heap metadata is `$01:0040–$01:023F`, the registry is
`$01:0240–$01:024F`, and code starts at `$01:0250` (`$03:0250` for kernel
bank 3). The heap reservation is 512 bytes,
including its claim ledger, alignment and spare descriptors. It consumes no
additional bank-zero space. Packaging rejects every COPY/ZERO/code extent
overlapping any reservation. Bootstrap and the native manager preserve
image claims through adoption. Four-task builds retain their bank-zero table
and start code at kernel-bank offset `$0210`, after heap and registry storage.

The v3 private context, ready and wake queues, root Task and serial binding
occupy **768 upper-RAM bytes** for eight tasks plus idle: 64 bytes per context
and 192 fixed bytes including padding. The metadata base follows the highest
usable bank, `$0F:0000` on the standard map; it is independent of the kernel
bank. Public worker Task records and work buffers may also live in upper RAM.

The [pool generator](../../tools/task_capacity.py) checks complete reservations
against OS, resident, kernel, manifest, boot-record and near-image ranges.
Loader `$6800–$7BFF` and staging `$7C00–$800F` become reusable only after
`EXECMEMORY.Adopt` returns. No callback or bootstrap frame remains live there.
Task initialization then prepares the generated guards, stacks and DP domains.
The former bank table and 240-byte legacy context arena are also released from
the runtime reservation map; their replacements live in upper RAM.

| Context | D register | Stack allocation, inclusive | Stack bytes |
| --- | --- | --- | ---: |
| Root | `$2200` | `$4200–$47FF` | 1,536 |
| Worker 1 | `$2400` | `$5200–$55FF` | 1,024 |
| Worker 2 | `$2800` | `$6810–$6C0F` | 1,024 |
| Worker 3 | `$2A00` | `$6C30–$702F` | 1,024 |
| Worker 4 | `$2E00` | `$7050–$744F` | 1,024 |
| Worker 5 | `$5700` | `$7470–$786F` | 1,024 |
| Worker 6 | `$5900` | `$7890–$7C8F` | 1,024 |
| Worker 7 | `$5B00` | `$7CB0–$80AF` | 1,024 |
| Private idle | `$5D00` | `$80D0–$82CF` | 512 |

Each stack has separate 16-byte lower/upper guards and retains a 256-byte
interrupt reserve inside the allocation. Each aligned 256-byte DP has a full
512-byte reservation starting at `D-16`: both 16-byte guards and 224 bytes of
otherwise unused padding are counted and canary-checked. Kernel DP `$2600`
and stack `$4A00–$4FFF` keep their existing sizes and guards. The runtime map
is emitted in each build's `memory.json`, including `runtime_reservations`,
`task_pools` and `bank_zero_budget`.

## Complete bank-zero budget

| Reservation | Four-task layout | Eight-task layout | Delta |
| --- | ---: | ---: | ---: |
| Fixed runtime, excluding OS | 11,824 | 10,560 | −1,264 |
| Root | 1,856 | 2,080 | +224 |
| Each other public Task | 1,856 | 1,568 | −288 |
| Private idle | 1,856 | 1,056 | −800 |
| Runtime, excluding OS | 21,104 | 24,672 | +3,568 |
| Runtime, including OS | 57,968 | 61,536 | +3,568 |
| Loading, excluding OS | 21,696 | 20,368 | −1,328 |
| Loading, including OS | 58,560 | 57,232 | −1,328 |

The fixed saving is the full 1,024-byte table arena and 240-byte old-context
arena. The complete 2 KiB near-data and manifest arenas remain reserved, even
when partly unused. OS reservations total 36,864 bytes. Loading retains root
and first-worker reservations and boot-only loader/staging; additional task
pools become live after adoption. Diagnostic register capture for all eight
tasks temporarily reserves 128 additional bytes at `$2100–$217F`; it is absent
from production images. Burst queue snapshots use existing upper metadata
padding and do not enlarge bank-zero storage.

## Qualification and limits

The [capacity record](../qualification/signals-capacity.json) records simultaneous
admission, waiting workers, a timed sleeper, rejected ninth admission with
unchanged storage, direct IRQ delivery under Forbid, removal/reuse, static
work buffers, upper-table adoption and complete guard checks. It includes raw
and optimized code at kernel banks 1 and 3, all eight native contexts, and a
full eight-target pending-wake queue including root. The first worker's Task
crosses a bank boundary; other descriptors have odd addresses.

A VBI-disabled burst proves that pending IRQs survive masking and are serviced
between protected drain transactions. Passive 8× measurements keep the normal
burst separate from that deliberately stalled race probe:

These are historical measurements before the
[interruptible-policy change](kernel-critical-sections.md); whole-target
drains no longer hold I=1. Eight-task concurrent baud qualification remains a
separate milestone.

| Queue population | Maximum single post | Maximum masked nonempty drain | Maximum complete drain |
| --- | ---: | ---: | ---: |
| Four targets | 24.388 µs | 599.186 µs | 2,577.607 µs |
| Eight targets | 22.837 µs | 570.851 µs | 4,880.466 µs |

An eight-live-task diagnostic IRQ byte pump also passes 65,535 bytes with
**59.771 µs** worst refill against the **78.942286 µs** deadline, zero gaps or
misses, correct sequence and final-byte completion. Its uninstrumented replay
matches the image, memory and counters exactly: seven admitted workers,
65,535 IRQs, 267 VBIs, twenty switches and thirty gateway calls. Six bystanders
are parked; root makes no kernel calls during the transfer, and there are no
timed sleepers or other ready peers. The one completion post takes 22.555 µs,
the same measured time as the four-task block-completion run despite four
additional bystanders. This restricted experiment preserves the earlier limit
on concurrent kernel activity; it is not a production SIO driver.

The small single-target variation reflects emitted placement and hardware
phase, not a speedup guarantee. Posting and one-target delivery have no loop
over unrelated tasks; the complete drain grows with the number of queued
wakes. These observations do **not** make the masked intervals acceptable for
125 kbaud. Functional capacity does not qualify SIO under concurrent kernel
work; see the [integrated timing limits](signals-implementation.md#integrated-signal-qualification--complete-with-timing-limits).

```sh
python3 tools/test_task_capacity.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/test_upper_table.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/test_task_capacity.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge --kernel-bank 3 --flags 0xf9
python3 tools/test_task_capacity.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge --kernel-bank 3 --mode raw --burst 3
python3 tools/test_task_capacity.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-signals-bridge --kernel-bank 1 --mode opt \
  --burst 2 --observe
```

The generator accepts candidate capacities 2–16 and aligned stack reservations
512–1,536 bytes, rejecting overlap and configurations that do not fit. Only
**eight with 1,024-byte workers and 512-byte idle** is the new qualified layout.
Four retains its historical 1,536-byte pools and rejects conflicting stack
options. Stack guards and compiler checks bound the tested workloads; they do
not prove that arbitrary application call depth fits. Twelve/sixteen tasks and
other stack sizes remain unqualified targets. [Message ports](messages-ports-implementation.md)
add eight-task functional lifetime checks. A production asynchronous SIO driver,
DOS, RX/turnaround, cancellation and real-device timing remain separate milestones.
