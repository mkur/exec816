# SIO driver migration record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/device-io.md) and [history index](README.md).

The [plan](../plans/sio-driver-boundary-implementation-plan.md) starts from the measured
COP refactor at `2118201`. The [resident contract](../reference/resident-drivers.md)
separates caller callbacks, worker policy and native hardware responsibilities.

## S1: contract and ordinary-Task proof

The contract fixes typed static dispatch, request state ownership, cancellation
and reply ordering, plus the public Task retention/residency facilities needed
by S3. Those lifetime APIs are selected but not implemented in S1/S2. Existing
lifecycle controls stay in place until replacement protections are executable.

`tests/programs/driver_boundary.act` uses ordinary Tasks and public ports. It
attempts Yield after dequeue but before publishing the active pointer, delivers
notifications before the worker's port Wait, and immediately reuses then frees
the replied message. No disk or SIO-specific service is used by this proof.
The focused runner builds raw/optimized code once each and checks bounded
completion, exact ownership, guards and OS restoration.
Both modes pass, and the host suite passes 199 tests. The
[S1 evidence](../development/sio-driver-contract.json) records image/compiler/platform
hashes and the unchanged complete memory maps. Artifacts remain under
`build/development/sio-driver/s1-{raw,opt}`. No compiler or release qualification
was run.

Reserved bank-zero change is **0 fixed bytes and 0 per Task**, including guards,
alignment and unused reserved capacity. Fixture data is in existing image
storage; production runtime and compiler pin are unchanged.

## S2: caller dispatch and driver-owned requests

`abi/io.json` now describes immutable SIO and immediate-test resident routes.
The generator emits typed caller dispatch and shared route constants. Existing
Open/Close/BeginIO/SendIO/DoIO/AbortIO operations validate their generic arguments
and return a route; IOCORE runs the driver callback after the gateway returns.
Forbid spans validation, common request preparation and callback execution, with
IRQs enabled. The immediate test resident asserts that SWITCHING is clear.
Its module is excluded from production images.

`lib/io/sio-requests.inc` owns open/unit counts, submission, queued/active abort,
conditional filesystem cancellation, claim, activation and completion. Claim
holds exclusion from GetMsg through active-pointer publication. Finish copies
results, clears active ownership and publishes ReplyMsg before releasing
exclusion. SendIO/BeginIO never reread a published request; DoIO only reads back
under exclusion after validating that the reply owner is its caller. The existing
exact-request collection loop remains shared by all devices.

Request controls **2/3/4/9/12** and their kernel implementations are removed.
Worker startup, readiness, stop, removal and restart still use lifecycle controls
**0/1/5/6/7/8/10/11** until S3 provides their public replacements. Lifecycle
readers use SWITCHING; driver writers use Forbid, excluding the same Task
switches. No new public selector or SIO-specific kernel shortcut was added.
Native descriptor Start/Cancel/Retire/Recovered and serial IRQ code are unchanged.

The development selection passes **199 host tests and 44 emitted-code cases**:

- Raw/optimized immediate and queued I/O cover flags, signed errors, exact
  collection and freeing a reply before the sender returns (eight cases).
- Raw/optimized native overlays check full CheckIO pointer/context restoration
  and rejection of I-masked, foreign-DP, IRQ and SWITCHING callers (ten cases).
  Two optimized DoIO cases retain invalid-owner/ignored-port fault checks.
- Raw/optimized SIO recovery covers queued, preparing, active, terminal, reuse,
  checksum, short response, claim and reply boundaries (18 cases). Test-only
  checkpoints wait through a real VBI while Forbid protects a partial update.
- Four SDFS cancellation cases cover before-send, on-wire, preparing and
  terminal state with committed-data and cleanup assertions.
- The same raw/optimized recovery images are replayed for active-abort timing:
  driver entry to terminal is 0.117/0.262 ms, within the existing alarm bound.

Each selection retains bounded completion and guards; ownership and OS state are
checked on the supported cleanup path. Offline cases retain the expected reset
requirement. Context overlays and cancellation timing reuse existing builds;
recovery cases reuse one loaded snapshot per NIR mode. The filesystem fixture
predates removal of an unused test-resident import; the final production module
set is exercised by the diagnostic HELLO and loading/BREAK runs below.
The [S2 evidence](../development/sio-driver-requests.json) pins the exact artifacts,
inputs, platform configurations and validation scope. No compiler, release or
physical-hardware qualification was run.

Reserved bank-zero change is **0 fixed bytes and 0 per Task**, including guards,
alignment and unused capacity. The complete memory map and Task reservations
match G4. Existing upper-RAM records and native-code reservation are reused;
caller frames now hold driver state across public calls, without a retained
kernel activation. The evidence records emitted local stack peaks separately
from whole-call-chain bounds; passing guards is not a worst-case stack proof.
Native code grows by 28 bytes, from 8,859 to 8,887 within the existing 9,216-byte
region. Emitted Action! routine code grows by 3,361 bytes in upper RAM. The
OpenDevice helper's emitted local peak grows from 40 to 52 bytes; DoIO stays
at 22. Driver Claim/Finish local peaks are 24/30 bytes, replacing kernel
SIOTake/SIOFinish peaks of 22/36; these are different call chains, not net
whole-stack savings.

### Checkpoint HELLO profile

One diagnostic bundle is built with the existing load-phase observer, then
reused for instruction traces and replays without CPU tracing. G4 and S2 use
the same compiler pin, PAL 8x configuration, GENERIC57600 disk profile, accurate
disk timing, 128-byte SDFS sectors and unchanged 2,359-byte HELLO payload.
Traced/untraced runs have identical relative phase ticks, transfer counts and
hardware gap intervals. All 19 data sectors remain within one DOS Read.

| Metric | G4 stopped | S2 stopped | G4 active | S2 active |
| --- | ---: | ---: | ---: | ---: |
| Mean inter-sector gap | 16.87 ms | 17.14 ms | 20.21 ms | 18.73 ms |
| Maximum inter-sector gap | 18.52 ms | 18.22 ms | 37.10 ms | 22.40 ms |
| Mean retirement/reply/collection interval | 3.21 ms | 3.46 ms | 3.76 ms | 4.32 ms |
| Payload phase | 2.50 s | 2.50 s | 2.48 s | 2.48 s |
| Open to prompt | 3.90 s | 3.90 s | 4.14 s | 4.14 s |

End-to-end loading time is unchanged. The stopped mean gap grows slightly,
while the active gaps shrink; these elapsed intervals include scheduling and
rotational waits. The retirement/reply/collection interval grows in both cases.
This checkpoint demonstrates the ownership change without claiming a loading
speedup. Passive gateway counts and nested call intervals are retained in the
evidence; nested or suspended call durations must not be added as CPU costs.

The diagnostic bundle also passes the loading/physical-BREAK/recovery smoke.
`build/demo` remains the G4 play image; S3 lifetime work and S4 final packaging
are still pending.

## S3: public lifetime and resident shutdown

SIO now admits its worker with AddTask, holds it with RetainTask, and retires it
with ReleaseTask/RemTask under Forbid. Readiness and stop callers wait on public
signals with retained stack waiter records. Concurrent first opens share one
worker; a generation distinguishes retirement from a restarted worker using the
same Task record. Failed initialization unwinds acquired resources. Automatic
shutdown stops admission, allows existing opens to close, then retires the worker.

The public feature version is `$0700`; the unchanged native packet tag remains
`$0600`. `TaskLease` is an address-bound, incarnation-checked removal hold.
RegisterResident/UnregisterResident provide generic last-application notification.
The public AltirraOS EXECPRODUCER API replaces private Bind/Release/Drain selectors
and retains both binding owner and recipient until release/draining finish.
All these calls use the existing COP `$50` gateway. The
[contract](../reference/resident-drivers.md) documents failure, ownership and reuse.

`SIODRIVER.Control`, selector 51, its native thunk/types, `task-sio.inc`, worker
entry injection and SIO-specific scheduler hooks are removed. Generated static
admission describes the existing Task/lease storage and registered Worker entry;
an unrelated duplicate Worker invocation returns without touching hardware.
DEVICEINSPECT reads a synchronized driver snapshot. DOS and console register
their own stop notifications and no longer inspect SIO identity or bus state to
decide lifetime. Their remaining device/service policy is outside this migration.

The final inputs pass **201 host tests and 37 emitted-code cases**:

- Ten raw/optimized ordinary-Task cases cover lease storage, copied/stale and
  duplicate releases, hold exhaustion, protected removal, producer lifetime,
  resident signal ownership and late registration after root exit. Invalid
  pointers at the top of the 24-bit address space cannot wrap into a stack range.
- Twelve raw/optimized SIO cases cover concurrent opens under inherited Forbid,
  worker protection before binding and after release/drain, stop versus open,
  retirement followed by immediate restart, and last-application shutdown.
- Fourteen raw/optimized FASTEST125 recovery cases cover queued/active/terminal
  cancellation, binding/capacity rollback, bound-worker removal and duplicate
  entry. The same loaded snapshot serves each mode's selected scenarios.
- One optimized active-abort timing replay reuses the recovery image and checks
  the existing alarm bound. Fatal ownership cases retain their expected fault
  or reset requirement rather than attempting unsupported recovery.

The final eight-Task diagnostic image also passes HELLO, CAT | WC, MEM, physical
BREAK during loading, a subsequent HELLO, normal EXIT and ownership restoration.
Its smoke reaches seven live Tasks. Guards remain intact throughout the selected
tests; successful cleanup checks OS ownership restoration. Test-only lifetime
checkpoints are absent from production. The
[S3 evidence](../development/sio-driver-lifetime.json) records exact current inputs,
artifacts, compiler/platform pins, cases and stack metadata. This is development
validation; compiler, release and physical-hardware qualification were not run.

Reserved bank-zero change is **0 fixed bytes and 0 per Task**, including guards,
alignment and unused capacity. The complete memory map matches S2. Hold count,
incarnation and resident mask consume ten former padding bytes in each unchanged
64-byte upper-RAM context, plus two unused bytes in the selected 12-byte budget.
The 12-byte SIO lease and waiter pointer fit its existing 64-byte bus reservation
(60 bytes used); the 256-byte device arena is unchanged. Temporary waiter leases
use the caller's existing guarded stack.

Native adapter code grows by 42 bytes, from 8,887 to 8,929 within its unchanged
9,216-byte reservation. Emitted Action! routine code grows by 9,519 upper-RAM
bytes. Start/Stop/Worker local stack peaks change from 16/14/20 to 48/54/38 bytes;
WaitChange and AdmitWorker have local peaks of 20/32 bytes. These are emitted
per-routine peaks including outgoing argument transfers, not whole-call-chain
or whole-system stack bounds. No kernel activation is retained across driver
callbacks or lifecycle waits.

S4 reuses this diagnostic bundle for final measurements before rebuilding the
play image. The compiler pin remains `47cd55b`.

## S4: final profile and play image

S4 reuses the final S3 diagnostic XEX for stopped/active HELLO traces and replay
without CPU tracing. Its compiler, PAL 8x machine, ROM, emulator, GENERIC57600
profile, accurate disk timing, 128-byte SDFS media and 2,359-byte HELLO payload
match G4 and S2. Traced and untraced runs have identical relative phase ticks,
transfer counts and all 18 hardware gap intervals. The 19 data sectors remain
within one DOS Read. The existing load-phase observers are present in both
diagnostic runs; the play image is built separately without them.

| Metric | G4 stopped | Final stopped | G4 active | Final active |
| --- | ---: | ---: | ---: | ---: |
| Mean inter-sector gap | 16.87 ms | 16.51 ms | 20.21 ms | 19.66 ms |
| Maximum inter-sector gap | 18.52 ms | 17.09 ms | 37.10 ms | 38.23 ms |
| Mean retirement/reply/collection interval | 3.21 ms | 3.46 ms | 3.76 ms | 3.68 ms |
| Payload phase | 2.50 s | 2.48 s | 2.48 s | 2.46 s |
| Open to prompt | 3.90 s | 3.88 s | 4.14 s | 4.16 s |

The final open-to-prompt result differs by one PAL VBI tick in each direction.
The architecture migration has no meaningful loading-speed improvement or
end-to-end regression in this workload. Stopped gaps improve slightly; active
maximum latency grows by 1.12 ms against G4. Compared with the intermediate S2
checkpoint, the active mean grows from 18.73 to 19.66 ms and the maximum from
22.40 to 38.23 ms. The largest gap, after sector 75, spends 18.75 ms in the
map-lookup/block-preparation interval while other Tasks run, outside SIO's short
claim/activation regions. Identical-image replay reproduces this schedule.
These are elapsed scheduling/interrupt intervals, not isolated CPU costs.

The final mean completion-to-worker interval is 1.07/1.20 ms stopped/active;
inclusive consume is 4.24/5.13 ms, and submission-to-driver-request is
4.10/4.88 ms. Inclusive consume includes copying and can include preemption.
The evidence retains the complete nonoverlapping phase breakdown and nested
call timings; nested timings must not be added as CPU costs.

Passive counts below cover **all matching CPU events in the captured replay**,
including startup, HELLO, DIR and shutdown. They are not HELLO-only counts.
G4 did not retain these fast-path markers; S2 uses the same replay sequence.

| Gateway marker | S2 stopped | Final stopped | S2 active | Final active |
| --- | ---: | ---: | ---: | ---: |
| Fast-path entry | 5,735 | 5,833 | 6,044 | 6,155 |
| Fast completion | 1,154 | 1,314 | 1,231 | 1,408 |
| Fast-path fallback | 157 | 164 | 175 | 181 |
| Full dispatcher | 4,822 | 4,759 | 5,192 | 5,135 |

Measured task-exclusion intervals start after Forbid returns and end before
Permit is called, paired by caller DP. They include IRQ time and exclude any
rescheduling inside the final Permit. These means/maxima cover all completed
marked regions in the captured replay, not just the 18 payload gaps.

| Region | Stopped mean / max | Active mean / max |
| --- | ---: | ---: |
| Claim | 0.132 / 0.142 ms | 0.132 / 0.142 ms |
| Activation | 0.022 / 0.024 ms | 0.022 / 0.024 ms |
| Finish/reply | 1.243 / 1.297 ms | 1.238 / 1.297 ms |
| Stop check | 0.096 / 0.866 ms | 0.095 / 0.864 ms |
| Generic Submit including callback | 2.114 / 2.430 ms | 2.139 / 2.864 ms |

The [S4 evidence](../development/sio-driver-integration.json) records all profiles,
identical-image checks, pins, artifact hashes and the fresh play smoke. The
play bundle is refreshed at `build/demo`, with `program.xex` and `sdfs.atr`;
the previous G4 bundle is retained at
`build/development/sio-driver/s4-previous-play`. Its production source is S3
commit `815e0df`. The banner carries `-dirty` because the two pre-existing
untracked command-size analysis documents were present at build time; exact
runtime source hashes match the committed implementation and diagnostic build.

The new play image has no guest load-phase or lifetime test probes and passes
HELLO, CAT | WC, MEM, physical BREAK during loading, subsequent command recovery,
EXIT and ownership restoration, with seven live Tasks at peak. Reserved
bank-zero change is **0 fixed bytes and 0 per Task**, including guards, alignment
and unused capacity; complete memory maps and upper reservations match G4/S2.
Compiler pin, native serial engine, disk profile and command payload are
unchanged. This completes S1-S4 at the development tier; full release and
physical-hardware qualification remain separate.
