# Native semaphore delivery

[History](README.md) · [Design](../plans/native-semaphore-design.md) ·
[Implementation plan](../plans/native-semaphore-implementation-plan.md) ·
[Development evidence](../development/native-semaphores.json)

## NS0: composition baseline

At NS0 runtime/kernel APIs were unchanged.
The optimized small Task fixture exercises a minimal Forbid/Permit composition
with cached identities and preallocated waiters/signals. Leases pin participants
outside timing. Fourteen assertions check free/recursive pairs, FIFO handoff,
empty queues, resource cleanup and a background counter advancing while the
owner runs a tight loop with the semaphore held. The counter advances five
times, with thirteen Task switches and four native NMIs in the measured run.

Thirty-two complete fixture pair spans per case include the obtain/release
wrappers. Task CPU includes kernel execution and bus stalls; native interrupts
and time assigned to another Task are separate.

| Composition pair | Median charged CPU | Minimum | Maximum |
| --- | ---: | ---: | ---: |
| Free acquire/release | 0.292 ms | 0.285 ms | 0.302 ms |
| Recursive acquire/release | 0.287 ms | 0.273 ms | 0.853 ms |

These are baseline costs, not native-semaphore results or GUI latency claims.
The fixture uses the pinned shell-paced PAL 8x/4 MiB machine. The compiler is
the clean pinned revision, built as a release host executable; guest NIR is
optimized. The evidence records exact hashes, stack peaks and reservations.

One completed guest image was reused for three guest runs. The first two passed
the guest assertions but were excluded from timing while correcting the host
manifest path and starting the passive profiler. Earlier name/type shadowing
was rejected before emission; a slow debug-host emission was stopped. No raw,
QED, demo or release matrix was run. The host suite passes 715 tests, with five
existing skips. Heap, stack/domain guards and OS return pass.

The implementation boundary is fixed: simple cases commit in native code and
use ordinary fast completion; busy Obtain and final queued Release decline
before mutation into the original validated operation. A parked caller returns
Select's frame, never an ordinary Poll that can requeue it as runnable.

Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 idle and 0 per
public Task**, including guards, alignment and unused capacity.

Before NS0, verified compression of old mouse validation, retained records and
saved media plus removal of rebuildable Rust incremental cache reclaimed
7,062,302,720 bytes. Current MGVIEW captures, pinned toolchains/firmware, source
checkouts and current packages remain available. The local cleanup manifest
retains archive hashes and the completed per-file content verification counts.

## NS1: native try and release

Init, Attempt and Release now use the generated 12-byte object and pointer
imports. Init issues no COP; each stateful call issues one. The successful
native fixture records native completions without policy replay. Blocking
Obtain remains unavailable in this slice. The Task feature version is `$0900`;
the existing packet tag is `$0700`.

Development checks pass: 718 host tests (five skips), generated Task declarations,
one raw ABI probe and ten selected optimized cases. These cover free/recursive
ownership, a competing try, two owned objects, outer Forbid, a bank-crossing
object and caller-prepared Task, and six faults (empty/extra/wrong-owner release,
owner removal, depth overflow and distinct-owned overflow). Fault snapshots
confirm no partial depth/accounting/queue mutation. Bank-crossing guards, normal
retirement, heap/domain guards and OS return pass. Earlier successful pilots
were repeated after fixing the host's obsolete contiguous-padding assumption.

Private context stride remains 64 bytes and public Task size 62. Five upper
padding bytes now hold owned-count and waiting association. Fast scratch remains
20 bytes below the complete 13-byte frame. Root and worker peaks are 58 bytes,
kernel 166 in the native functional case. Reserved bank-zero deltas remain
**0 fixed, 0 root, 0 kernel, 0 idle, 0 per public Task**. No QED, demo build or
release qualification was run. Per-case hashes and maps are in the evidence.
