# SDX guest runtime development slice

Status: partial P2 implementation, 18 October 2026.
[Plan](../plans/spartados-personality-implementation-plan.md) ·
[Patch infrastructure](sdx-patches.md) · [Execution record](sdx-runtime.json)

Two synthetic 6502 guests now execute in private upper banks on ordinary Exec
Tasks. They compute without yielding, return through guest-local service
veneers, sleep in native code, and resume their saved stacks. A native peer,
normal OS VBI, foreground ROM output and the native pointer IRQ source run
alongside them. A separate storage case reads eight real stock-810 sectors
with both guests and pointer IRQs active. **MD5 and ARC are still not admitted.**
This is a development bridge with fixed test-owned slots, not the production
loader or completed P2.
No demo or release package was rebuilt.

## Early interrupt routing

The [ROM-shadow component](../../platform/altirraos/sdx-rom-shadow.s) compares
all 14,336 CPU-visible bytes of the pinned ROM before changing the mapping.
With IRQ and NMI disabled and no live ROM activation, it saves the underlying
RAM, copies `$C000–CFFF` and `$D800–FFFF`, and patches the emulation NMI/IRQ
vectors in that RAM copy. `$D000–D7FF` remains hardware. The ROM file is
unchanged. Removal restores every saved underlying RAM byte and PORTB.

The input ROM, emulator and effective shadow hashes, plus exact vector
preimages/replacements, are recorded for each case. The standalone fixture
checks the entire effective shadow and restoration of both ROM visibility and
a known underlying-RAM pattern. A wrong expected ROM fails before mutation;
repeated install/remove calls report an ownership error.

Both early entries change to native mode in bank zero before jumping to upper
adapter code. This detail matters: an earlier implementation jumped to upper
code while still in emulation mode and failed under frequent pointer IRQs.
A nested NMI in that interval could not recover the interrupted code bank,
because E=1 interrupts do not stack PBR.

The bridge now classifies nested E=1 entry by its bank-zero PC interval and
returns to that bank-zero continuation. The synthetic guest packager excludes
that interval from guest code. A production loader must reserve equivalent
PC offsets in every guest bank; merely comparing a low PC is ambiguous when
an application can execute at the same offset. This reservation is a real
admission requirement, not memory protection.

## Page one and Task continuations

The [Task bridge](../../platform/altirraos/sdx-runtime-probe.s) is included only
with `sdx_runtime_probe=True`, under the eight-Task test profile. The ordinary
build emits none of it. Its private native-call ABI is checked against compiler
interfaces; it adds no COP selector and changes no Task or scheduler ABI.

Each guest has an upper-memory 256-byte stack image. While entering, the bridge
publishes page-one ownership, saves the displaced host image and restores the
selected guest image. Native NMIs during an owned transition acknowledge ANTIC
and retain pending work. They cannot enter ROM or schedule another owner.
The copies poll the existing raw IRQ router between at most sixteen words,
on the native Task stack with page-one ownership retained. This services byte
and fine timer edges without admitting ROM or a Task switch during a partial
copy. A completion queued by a copy poll is checked before entering the guest.

An emulation interrupt saves hidden B, X/Y, D, DBR, flags and the emulation
hardware frame. Owned short IRQs use the current Task's native stack and the
existing `signal_route`; they retain page one and avoid its full snapshot.
A VBI or native service snapshots the guest stack and restores host page one
before releasing ownership. The guest's native D remains distinct from its
private emulation D.

For VBI scheduling the bridge constructs an ordinary native interrupt frame
on the original Task stack, returning to a native resume routine. Existing
`native_nmi` runs and retires the OS VBI before existing frame validation and
scheduling. On resumption, the slot comes from that Task's own native call
frame, not a shared last-owner variable. Guest return reaches its private code
bank while E=0, then changes to E=1 and executes RTI.

The final pending check is covered by an NMI interceptor through the last
native instruction of the guest-bank return veneer. It classifies the two
restore paths and how many register bytes have already been popped: 0, 1, 3,
5, 7 or 9. Those bytes are live in the nested NMI's saved register prefix.
The interceptor copies them backwards into the original guest frame, whose
saved status and PC remain intact, and discards the nested native activation.
The complete guest frame can then be detached normally and its pending VBI
delivered before any guest instruction runs. After XCE, the ordinary emulation
NMI path captures the guest-bank continuation. No additional gateway is needed.

Owned IRQs also check ordinary deferred native work and Task wakes. After
detaching, they build the same full native frame used by an ordinary owned
IRQ and enter `interrupt_schedule` with D=DBR=0. The already-retired raw handler
is not called a second time. No driver-specific kernel operation is added.

A synthetic service adjusts the original guest JSR return for RTI and returns
to native Action code. The native caller can use ROM and block in `Sleep`
without retaining a guest, kernel or ROM activation on physical page one.
Run currently requires an IRQ-enabled native caller. Nested callbacks, arbitrary
native masked callers and nonlocal SDX error traps are outside this fixture.

## Checks and memory cost

The [standalone runner](../../tools/test_sdx_runtime.py) covers two guest banks,
two private D pages, different accumulators, decimal/status restoration, an
IRQ-masked control, real timer IRQs and four forced native-NMI transition points.
Each case retires 32 normal OS VBIs. Private `$D40F` aliases deliberately contain
`$FF`; the fixture cannot accidentally pass through the old DBR-sensitive ROM
entry. Guards and all guest DP bytes are checked.

The optimized [Task runner](../../tools/test_sdx_tasks.py) exercises two guests,
a non-yielding native peer, native sleeps, two foreground ROM writes, and the
pointer driver's real timer IRQ stream. It checks all 256 DP bytes per guest,
distinct page-one sentinels, hidden B and the complete service return frame,
Task collection, native stack/domain guards, and image ownership restoration.
A separate forced case holds the first owned IRQ in its E=1 entry until a real
VBI interrupts it. That artificial hold is not IRQ-latency evidence. The raw
case is a smaller single-guest native-call/service-return ABI check.

Eleven optimized boundary cases use one-shot WAI instructions to force real
VBIs after the pending load, before each register pop, after the last pop,
and before SEC, XCE, PLP and RTI in the guest-bank veneer. Both restore branches
are exercised; the shared pending-check site is forced once. Device IRQs are
disabled in these cases. A guest-entry shim records any pending VBI that
escapes the return, and all complete register/stack/DP checks still apply.
The deliberate waits are test stimulus, not production latency measurements.

The storage case checks all 1,024 payload bytes from eight 128-byte sectors,
observes serial IRQs interrupting guests and deferred-work handoffs, and checks
native guards and ownership restoration. ROM console calls correctly return
`$FF02` while native SIO owns POKEY; the other cases exercise successful ROM
output. The traced storage run and an untraced replay use the identical XEX
and produce identical checked runtime results.

Tracing first exposed a command-hold deadline miss caused by copying page one
with no intermediate IRQ service. With copy polling, the recorded maximum RX
service delay is **72.74 us**, TX refill delay **59.21 us**, and command hold
**862.73 us**, within this stock-810 profile's checked limits. The byte deadline
is **530.04 us**. The trace's largest continuous I=1 interval, **9.99 ms**, is
the explicit ROM-shadow removal after the reads, not a serial byte-service
delay. These are observed development-case maxima, not worst-case bounds for
all code paths or qualification of faster disk profiles.

Production reserved bank-zero growth is **0 fixed bytes and 0 per-Task bytes**,
including guards, alignment and unused capacity. Test entry stubs consume
existing resident padding; upper code fits the existing 8 KiB native-work
reservation: 6,905 bytes used in the ordinary probe, versus 5,473 without it
and without CRC support. Return-injection variants use up to 7,043 bytes.
The synthetic Task fixture separately borrows **512 bytes** at
`$7E00–7FFF` after loader retirement: 256 per guest. These are diagnostic pages,
not a production guest DP allocator. Production pool reservation remains open.

The Task fixture reserves 32 KiB in bank `$28` for ROM image, backup, state and
stack images (including unused capacity), plus two complete 64 KiB guest banks:
163,840 upper-memory bytes in total. Each guest's 512-byte descriptor allocation
includes its 256-byte stack image and spare capacity. Native continuations use
existing guarded Task stacks. Exact emitted code sizes and touched-stack lower
bounds are in the execution record.

The current Task development checks comprise **15 cases and 8,334 assertions**,
plus the identical-image storage replay. The seven unchanged standalone
component records remain applicable to their recorded sources. The unchanged
43-check native patch fixture also passes. In the host suite, 503 tests pass
and four are skipped. Two existing host failures
remain: the C-package ABI expectation is 19 versus current 20, and the provider
payload expectation is 1,807 versus current 1,844 bytes. The default resident,
native-work, signal and blitter assembly payloads remain byte-identical to the
previous patch-component build with the runtime probe disabled.

## Remaining P2 work

- Replace fixed test slots and borrowed diagnostic DP pages with generated,
  accounted reservations and ordinary lifetime ownership; test exhaustion,
  failed admission, collection and reuse.
- Extend asynchronous-entry coverage beyond the forced return boundaries,
  including deep guest stacks and repeated nested entries. The pending flag
  still coalesces notifications; lossless per-VBI accounting and production
  worst-case service bounds are not established.
- Extend storage checks to writes, cancellation, failures and faster profiles,
  including native return redirection under concurrent completions. Stock-810
  read development evidence does not qualify general storage coexistence.
- Establish the supported ROM-shadow lifetime, including mapping conflicts and
  shutdown failure handling. Reset, self-test, DLI and third-party PORTB changes
  remain unsupported. Installation/removal temporarily disable interrupts.
- Add callback activation records and SDX trap semantics, then the native
  loader/Process integration and MD5's fourteen services. Keep module manifests
  at `patch-probe-only` until the remaining admission gates pass.

## Reproduce

Use the pinned compiler, ROM and paced emulator in the repository's
[build instructions](../contributing/building.md).

```sh
python3 tools/test_sdx_runtime.py --output build/sdx-runtime/bank2
python3 tools/test_sdx_runtime.py --bank 3 --output build/sdx-runtime/bank3
python3 tools/test_sdx_runtime.py --masked --output build/sdx-runtime/masked
# Repeat with --phase 1, 2, 3 and 4 for the transition cases.
python3 tools/test_sdx_tasks.py --output build/sdx-tasks/return-normal
python3 tools/test_sdx_tasks.py --early-entry --output build/sdx-tasks/return-early
python3 tools/test_sdx_tasks.py --case raw --output build/sdx-tasks/return-raw
python3 tools/test_sdx_tasks.py --return-boundary 1 --output build/sdx-tasks/return-1
# Repeat --return-boundary for 2 through 11.
python3 tools/test_sdx_tasks.py --sio --trace --output build/sdx-tasks/return-sio
python3 tools/test_sdx_native.py --case opt --output build/sdx-native/return-regression
```
