# Messages and ports implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

The [implementation plan](../plans/messages-ports-implementation-plan.md) is complete in six
separately committed slices; integration evidence is described below. The [design](../reference/ports.md)
defines the public semantics and target-specific deviations.

## Current implementation

The current Task ABI reports `$0600`. MsgPort is 27 bytes with byte alignment;
Message is 16 bytes with two-byte alignment. Generated definitions come from
[ports.json](../../abi/ports.json). There is one current API.

PutMsg, GetMsg and ReplyMsg use checked task-context native imports and guarded
Action! policy. PA_SIGNAL posts directly to the known live receiver after all
queue links are complete. PA_IGNORE does not inspect its unused signal fields.
Posting and scheduling are separate steps; the dispatch finish can switch only
after publication. IRQ/NMI handlers do not traverse message queues or enter
another compiler policy activation.

GetMsg removes a head without clearing signals or changing its type. ReplyMsg
sets NT_REPLYMSG before enqueueing, or NT_FREEMSG for a null reply port. Neither
operation frees a message. PutMsg performs no message access after its COP
returns, so another task may already have replied to and reused the message.

WaitPort performs a guarded, owner-checked peek and then calls the existing
Wait if the queue is empty. Its continuation and mask stay on the caller's
stack. It never removes a message or clears a signal between the peek and Wait.
An immediate result does not consume a signal; GetMsg still transfers ownership.
I=1 is rejected even for a nonempty queue. Nested Forbid survives a blocking wait.

CreateMsgPort allocates 27 ordinary PUBLIC|CLEAR bytes (32 heap bytes), then a
signal for its caller. Signal exhaustion rolls the allocation back. Initialization
finishes before the pointer is returned; creation does not register the port.
DeleteMsgPort accepts null; otherwise it checks owner, retained allocated signal
and an empty queue before releasing either resource. An inactive PA_IGNORE port
still releases its original signal. Producer quiescence and prior removal of a
public name remain caller obligations, with no hidden ownership ledger.

AddPort, RemPort and FindPort use a private upper-RAM registry. AddPort initializes
an inactive port and inserts by signed priority, with FIFO ties; names are
borrowed and duplicates are allowed. FindPort returns the first exact match.
Use Forbid across discovery and immediate use. RemPort unlinks its known node
without emptying the queue or revoking agreed retained pointers. IRQs remain
enabled during name scans. All nine imports are implemented.

Detected misuse follows the existing
controlled task fault path; it does not promise validation of arbitrary
pointers, duplicate membership or stale storage.

## Storage and qualification

There is no added fixed or per-task bank-zero reservation. The registry uses
16 upper bytes (11 active) after heap metadata in the configured kernel bank.
At MAX_BANKS=16, code starts at bank base+$210 with four tasks or +$250 with
eight. Generated maps exclude the registry from images and heap ownership.
Every launch resets it; cleanup releases trusted bank claims without walking
port, message or name links. Port and message
records use ordinary caller-owned storage, including upper RAM and valid
contiguous bank-crossing records. It introduces no Task field, worker, port
ledger or IRQ-shared list. Queue wrappers have zero additional stack use;
WaitPort reserves eight invocation bytes and checks an 11-byte peak including
the nested Wait return address. Create/Delete use checked native tail calls to
caller-context Action! helpers: their emitted local stack peaks are 106/38 bytes
raw and 86/28 optimized, with no extra native-thunk stack use. COP frames use the
existing interrupt reserve. Context and guard checks
are exercised through emitted raw and optimized code.

The [ABI record](../qualification/ports-abi.json) covers layouts and all nine call
shapes. The [queue record](../qualification/ports-queues.json) covers FIFO/replies,
cross-bank forwarding, reuse before PutMsg returns, native contexts, detected
misuse, forced IRQ/NMI link-write races and targeted signal regressions.
The [WaitPort record](../qualification/ports-wait.json) covers stale/shared bits,
bursts, non-removing peeks, nested Forbid, a forced arrival between peek and Wait,
NMI during wait publication, and owner/action/I=1 misuse.
The [lifetime record](../qualification/ports-lifetime.json) covers resource
exhaustion/rollback, four ports in one task, exact heap/signal totals, stale-bit
reallocation, Forbid/I=1 preservation and rejected deletion before resource
release. The [example](../../examples/messages.act) returns ownership through a
terminal reply before freeing its request, then quiesces the worker and deletes
both ports. The [registry record](../qualification/ports-registry.json) covers
kernel banks 1/3, capacities 4/8, restart, cross-bank/long names, signed order,
retained pointers, safe concurrent discovery and partial-write IRQ/NMI races.

## Concurrent operation and serial timing

The [concurrency record](../qualification/ports-concurrency.json) combines a
four-task completion-request fixture with eight-task lifetime checks. The
serial worker removes a request, binds the existing completion signal, waits
for an actual POKEY IRQ, then replies; the client removes the terminal reply.
The diagnostic IRQ pumps generated bytes without calling a port API. The other
three tasks continue signal/reply, timed-sleep and root workload activity.
This is a bounded integration fixture, not a production driver.

The added four-task workload builds queues of eight requests, drains two reply
ports sharing one signal, and grows/drains an eight-port registry. Names contain
33 bytes plus NUL, with a 32-byte common prefix; lookup checks the last entry and
a missing suffix. Each iteration also allocates/frees 257 bytes and clears/frees
a 4,097-byte vector. All component progress counters require completed operations
before the final refill. The existing mixed signal/sleep/yield and 131,073-byte
linear CLEAR controls are retained and rerun separately.

The pinned 8× profile completed both transfer lengths in raw and optimized code.
Each observed run replayed the identical XEX and workload on the pinned
uninstrumented emulator, with matching results and counters. All four added
runs had **zero late refills and zero byte gaps**:

| Bytes | Mode | Max ready-to-refill, µs | Max I=1, µs | Completion post → worker, ms | Completion post → client, ms |
| ---: | --- | ---: | ---: | ---: | ---: |
| 4,096 | Raw | 66.537 | 68.017 | 16.068 | 167.369 |
| 4,096 | Optimized | 59.771 | 68.934 | 6.142 | 175.774 |
| 65,535 | Raw | 68.793 | 81.832 | 2.164 | 36.890 |
| 65,535 | Optimized | 72.176 | 70.766 | 18.545 | 140.959 |

The hardware refill deadline is approximately **78.942 µs**. I=1 intervals
include native/ROM interrupt handling and DMA; the 81.832 µs maximum did not
cause a refill miss at the observed phase. These runs are measurements, not a
worst-case bound for every interrupt alignment. Serialized work and application
Forbid sections can still delay worker execution by milliseconds.

The client endpoint is a marker after GetMsg and identity/type validation. In
this deliberately busy client, collection follows the current workload batch
and worker shutdown; its values include that application delay and are not
isolated ReplyMsg/GetMsg costs. The worker endpoint immediately follows Wait.
Neither endpoint establishes an RX, turnaround or worker-buffer budget.

The eight-task fixture admits all seven workers before releasing its startup
barrier. Seventeen ports share eight contexts: each client has two reply queues
sharing a signal, and the root has two service queues plus a handoff queue.
It checks 56 once-only replies and seven heap messages held until their
allocating tasks have exited, then frees them. Every port owner releases its
resources after producer/request quiescence. Heap totals, signal masks, bank
ownership and stack/domain guards are checked in both compiler modes and both
kernel banks. External removal of a blocked WaitPort caller is tested separately
after producer quiescence; its abandoned continuation must never resume.

## Regression scope and remaining work

The [regression record](../qualification/ports-regressions.json) identifies freshly
executed Task/signal context and dispatch-exit checks, allocator operations and
CLEAR, Lists, native/cooperative/preemptive contexts, banked loading, and forced
IRQ/NMI queue-write races. Earlier slice records remain evidence for their named
cases, including registry-write races and WaitPort publication; they are not
presented as a new rerun of every historical test. Host checks also reject a
qualification record that combines functional success with failed serial timing.

All slices retain the original complete bank-zero budget: 57,968 runtime and
58,560 loading bytes for four tasks; 61,536 runtime and 57,232 loading bytes for
eight, including the 36,864-byte OS reservation. Full guards, padding and slack
are included in every record. Native helper code occupies 3,368 bytes normally
or 3,482 with the serial diagnostic, within its existing 4,096-byte upper-RAM
reservation. Code growth can consume additional image banks; final image maps,
not a fixed advertised heap size, determine available memory.

Public port calls remain task-only; PA_SOFTINT, public IRQ ports, eight-task
serial timing, RX/turnaround and physical hardware remain unqualified. Queued
device I/O is the next design milestone, followed by DOS.

## Reproduction

Use the pinned compiler, ROM and emulator binaries. The ordinary functional
runner defaults to the 1 MiB functional pin; the timing runner verifies the
8× pin, passive observer and replay binary independently.

```sh
python3 tools/test_ports.py --compiler-dir build/actionc --suite capacity \
  --output build/ports-capacity
python3 tools/test_ports.py --compiler-dir build/actionc --suite wait-removal \
  --output build/ports-wait-removal
python3 tools/test_ports.py --compiler-dir build/actionc --suite queue-races \
  --output build/ports-final-queue-races
python3 tools/test_signal_concurrency.py --compiler-dir build/actionc \
  --workload ports --count 4096 --require-deadline \
  --output build/ports-timing-4096
python3 tools/test_signal_concurrency.py --compiler-dir build/actionc \
  --workload ports --count 65535 --require-deadline \
  --output build/ports-timing-65535
```

Both compiler modes run by default. Other named port suites reproduce the
individual slices; each qualification record identifies the selected cases.
Only parsed observer records and hashes are published. Raw bridge logs contain
authentication data and must stay outside committed qualification records.
