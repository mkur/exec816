# Native semaphore delivery

[History](README.md) · [Design](../plans/native-semaphore-design.md) ·
[Implementation plan](../plans/native-semaphore-implementation-plan.md) ·
[Development evidence](../development/native-semaphores.json)

## NS0: composition baseline

NS0 is complete; NS1–NS5 remain pending. Runtime/kernel APIs are unchanged.
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
