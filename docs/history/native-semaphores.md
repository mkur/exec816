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

## NS2: blocking FIFO handoff

All four Action! calls are implemented. Busy Obtain and queued final Release
continue the original admitted activation before mutation; blocked callers
return Select's frame. Ownership and removal protection transfer before Ready.
Signal-wake state remains separate; no service signal bit is allocated or used.

The optimized three-waiter scene passes 48 assertions, including exact FIFO,
non-barging, recursion with queued peers, outer Forbid, Wait while owning,
unrelated bits posted before and during blocking, cleanup and pool reuse.
Queued-waiter and granted-before-run removal faults pass 23 and 25 assertions;
snapshots verify three/two semaphore-wait states and exact ownership counts.
The native and ABI cases also pass on the same image. The host suite passes
718 tests with five skips. The selected existing optimized signal Wait/Forbid
case also passes using the same shell-paced pin and release-host compiler. Masked contention and forced asynchronous boundaries
are checked in NS4's native overlay rather than adding a second masking binding.

Fast scratch remains 20 bytes. In the blocking scene the root peaks at 66 bytes,
workers 60, kernel 173. All five categories of reserved bank-zero delta remain
zero; public/private Task sizes and the five repurposed upper bytes are unchanged.
No application catalog, demo, QED or release matrix was built.

## NS3: C and loaded provider

The generated C header and selectors expose the same four operations through
huge source pointers and the native pointer gateway. Init is ordinary C code.
Emitted raw and optimized C probes pass 12 assertions each, including recursion,
full LONG results, a bank-crossing object, counter progress, blocking handoff
and retirement. Passive traces confirm zero Init requests and exactly one per
stateful wrapper. Calypsi packs record members: storage alignment is an explicit
caller requirement, checked for the emitted fixture object; the emitted ABI
probe checks size and the generated alignment constant, not natural C alignment.

APP/provider ABI advances together to 46. One selected disk APP runs twice
through the matching resident provider and retires cleanly. No catalog APPs were
built. The initial run stopped at console startup under the nongraphics pin;
the unchanged image passes with the pinned GEM custom-addons configuration.
Both use the same recorded emulator binary and ROM. The existing provider-only
builder already supports excluding catalog applications, so no new selector was
needed. The host suite passes 718 tests with five skips; affected generators pass.

The binding adds zero reserved bank-zero bytes in all five categories. Different
pre-existing console/provider pool sizes in the loaded fixture are not semaphore
reservation growth. No QED, demo refresh or release qualification was run.

## NS4: asynchronous and admission boundaries

One optimized diagnostic image passes 16 runtime-selected real-NMI checkpoints
with concurrent POKEY timer IRQs. The sites cover free/recursive mutation,
nested/final release, pre-mutation native-policy transfer, retired scratch,
enqueue/state publication, queue-pop/handoff, pre-Ready and partial restoration
through PLB/PLD/PLY/PLX/PLA. Forced post-mutation work takes Poll with no replay;
the 48-assertion FIFO/signal scene remains correct at every site. Probe helpers
borrow existing diagnostic words, preserve partial context and emit no production
instructions. Two adjacent restore sites are represented by their surrounding
checkpoints to keep the diagnostic resident code within its existing reservation.

Nine assembly-overlay cases pass: ordinary/masked immediate acquisition,
M/X/tag/unused-selector-byte/domain rejection, empty Release and genuine masked
contention by an admitted worker against its live parent owner. D, DBR, widths,
flags, stack and complete LONG result are checked. This exposed and fixed a
shared rejection-classifier gap: invalid-domain semaphore calls now take the
normal Task-service fault path instead of returning the generic context error.
All rejected operations leave depth/queues unchanged. An earlier synthetic idle
owner pilot was discarded because idle has no public Task owner object.

The selected existing signal NMI-2 case passes. Host checks pass 718 tests with
five skips. Every fixed/root/kernel/idle/per-Task reserved bank-zero delta remains
zero. Diagnostic calls add temporary stack use within the existing guards and
capacity; production fast scratch stays 20 bytes. Complete stack figures and
per-case IRQ/NMI, image, trace and result hashes are in the evidence. No package,
viewer, QED or release qualification was run.
