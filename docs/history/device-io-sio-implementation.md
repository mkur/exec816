# Queued device I/O and SIO implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/device-io.md) and [history index](README.md).

Status: all eight slices implemented, 2026-09-20. The ten classic I/O calls and
resident `sio.device` now execute through one queued worker and the native
transaction engine. Ordinary OpenDevice initializes the resident on demand.
[Recovery evidence](../qualification/sio-recovery.json) covers cancellation,
malformed responses, startup rollback and the read-only public example.
[Concurrent qualification](../qualification/sio-concurrency.json) completes the
eight-task timing gate in the [plan](../plans/device-io-sio-implementation-plan.md). The
[design](../reference/device-io.md) defines the contract.

## What the probe executes

[probe.s](../../probes/sio-transactions/probe.s) and its
[engine](../../probes/sio-transactions/engine.inc) run one worker and one busy
background context. The worker starts a hardcoded transaction, performs an
atomic consume-or-block through the private COP #$50, and resumes after one
terminal post. The background advances while the transaction runs. The IRQ
engine reads/writes RAM and progresses the complete wire protocol without
worker intervention between bytes or phases. It allocates nothing and performs
no task, descriptor or queue scans.

The ordinary sequence is disk Status ($53), sector-4 Read ($52), sector-4 Put
($50, without device write verification), then Read to verify the changed media.
Commands, end-around-carry checksums, acknowledgements, result bytes and data all
travel through POKEY. SIO patching and burst transfer acceleration are disabled.
The guest constructs the nontrivial TX pattern; the host independently builds
the initial ATR contents and compares all 128 received bytes. The observer also
checks every byte accepted by the TX shifter and every RX register load/read.

TX starts at `$04:FFC0`, RX at `$06:FFC0`, and verification at `$08:FFC0`.
Each 128-byte payload crosses a bank boundary. Native 24-bit cursors advance
explicitly on low-word wrap. Buffer guards, both complete DP regions, native
stack guards and the OS stack's bottom guard remain intact. Saved A/B, X, Y,
S, D, DBR, P and E match across each worker Wait/wake pair.

The native IRQ router services RX first, TX-ready, TX-complete, then the two
alarms, with one bounded check per source. ROM serial/timer callbacks can enter
in emulation mode or native 8-bit mode; they preserve the entry mode and full
register state and retire the ROM activation before task switching. NMI remains
live throughout transfers. A keyboard case checks forwarding of an unowned IRQ.
The private COP service is diagnostic, not a new public Task/device ABI.

## Timer decision and profile limits

Use **independent POKEY timers 1 and 2**, leaving linked channels 3+4 for serial
clocking. This is a passing candidate for production integration in slice 5.
It has not yet been qualified inside the full Task kernel.

| Mechanism | Probe choice |
| --- | --- |
| Fine phase alarm | AUDF1=7, normal 64 kHz clock: 224 PAL base cycles, about 126.3 µs per tick |
| Active watchdog | AUDF2=$FF: 7,168 base cycles, about 4.04 ms per tick; 250 ticks to expiry |
| Serial clock | AUDCTL=$28; AUDF3 selects baud; AUDF4=0 |
| Rearm | Set a private countdown and clear/re-enable only its IRQ source; never restart the counters |
| Short delays | 8 fine ticks for COMMAND setup, 7 for hold, 10 after write ACK |
| Reset | STIMER only at initialization and restoration, never during a transaction |
| Counter wrap | Countdown from at most 250 to zero; no absolute timestamp comparison or wrap ambiguity |

The fine timer IRQ is enabled only during a phase delay, avoiding a continuous
high-frequency alarm load during RX/TX. The watchdog runs only while a
transaction is active. ACK, result and data phases share its remaining deadline;
an incoming byte does not restart it. This probe has no separate per-byte gap
timeout. RX is armed before COMMAND release and stays armed across
result-to-data. TX-ready must confirm the final byte entered the shifter before
TX-complete is enabled. That source is disabled when the final bit finishes.

The [machine/peripheral pin](../../toolchain/altirra-sio-device.json) declares these
limits before the acceptance run:

| Quantity | Acceptance |
| --- | --- |
| Target TX/RX byte service | Strictly before the next byte; 78.942 µs at the measured target divisor |
| COMMAND setup | 750–1,600 µs, assertion to first transmitted start bit |
| COMMAND hold | 650–950 µs, last command stop bit to release |
| Write start | 1,000–1,800 µs after the end of the command ACK byte |
| Fine/coarse alarm service lateness | At most 100 µs from hardware timer event |
| Active transaction / continuous CRITIC deferral | At most 1,020,000 µs each |

The [Altirra Hardware Reference Manual](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf)
(2026-01-02, Figure 18) specifies a 1.0–1.8 ms write-start interval; page 219 prose
instead says 10–18 ms. This probe selects **Figure 18's 1.0–1.8 ms interval for
the explicitly tested models**. The pinned disk implementation accepts it and
complete write/read-back transactions establish that limited compatibility.
This does not resolve the discrepancy for arbitrary physical peripherals;
additional profiles need their own qualification. Source hashes for the disk
model, profile table and ROM SIO implementation are recorded with the pin.

All peripheral models are Altirra's built-in high-level disk models, not separate
firmware ROM emulations. The `fastest` profile uses about **126.675 kbaud in both
command and data phases**, exceeding the requested 125 kbaud target. The stock
`810` profile uses about 18.866 kbaud host TX and 19.069 kbaud peripheral RX
(94 and 93 base cycles per bit respectively). The `happy1050` case tests only
its Quiet ($51) command, a no-data ACK/Complete transaction, at stock host TX
and about 19.488 kbaud RX. These are distinct, pinned peripheral cases, not a
claim that a stock 810 accepts the high-speed profile.

## Qualification result

The [qualification record](../qualification/sio-feasibility.json) contains all
13 observed runs and their identical-XEX uninstrumented replays, source/tool/
ROM/emulator hashes, bytes, guards, stack extents and individual timing results.
The native CPU runs at eight times the PAL base clock, about 14.188 MHz, with
fast ROM access and 1 MiB of native memory. This probe is pure ca65/ld65
assembly; raw/optimized NIR tests do not apply.

Coverage includes four fine instruction-phase offsets, three actual PAL raster
phases, stock 810 transactions, a no-data transaction, absent D2 timeout,
unsupported-command NAK, keyboard IRQ coexistence and a deliberately stalled RX
control. Raster alignment happens before a transaction with IRQs enabled.
The stock Status response also exercises the pinned model's back-to-back
Complete/data boundary. Every normal case has zero missing/corrupt bytes, late
refills or phase/alarm failures; every terminal transaction posts and wakes once.

| Observed quantity | Result |
| --- | ---: |
| Longest target-speed TX refill | 60.334 µs |
| Longest target-speed SERIN load-to-read | 56.951 µs |
| Longest SERIN load-to-read over all passing profiles | 57.515 µs |
| Target byte interval | 78.942 µs |
| Longest fine/coarse alarm service, all passing profiles | 59.630 / 61.885 µs |
| Target COMMAND setup range | 933.774–1022.303 µs |
| Target COMMAND hold range | 859.907–869.493 µs |
| Write-start range, all passing profiles | 1223.042–1305.367 µs |
| Longest terminal-post-to-worker, all passing profiles | 25.727 µs |
| Silent D2 active timeout | 1.009842 s |
| Longest continuous CRITIC deferral, including timeout | 1.010582 s |
| Longest overall masked span, passing runs | 82.326 µs |
| Deliberately late RX control | 121.797 µs; rejected as required |

CRITIC is scoped to a transaction. Stage-two VBI service runs between successive
transactions and after cleanup, while stage-one VBI/NMI service continues during
the transaction. The silent-device test reaches its independent hardware timeout
without RX input. The bound is a probe admission limit, not a promise that a
one-second deferral is suitable for every production OS service.

The negative control inserts 1,600 NOPs under SEI during read reception. The
normal byte/phase oracle must reject it and the functional transfer must fail;
its matching uninstrumented failure is required for the suite to pass. Host
regressions additionally reject exact-deadline RX service, late COMMAND edges,
late alarms, STIMER resets, missing/corrupt byte observations, altered saved
contexts and incomplete or falsely successful qualification records.

The longest overall IRQ-masked span is recorded separately from byte-service
latency. An interval longer than a byte does not establish a lost byte unless
it overlaps the relevant hardware deadline; conversely a successful terminal
result cannot override an observed deadline violation. These finite alignment
samples are not a worst-case execution-time proof.

## Ownership and restoration scope

This isolated cold-launch fixture owns serial IRQ bits $38, timer bits $03,
serial clock configuration, COMMAND and the corresponding native/ROM callbacks.
It preserves keyboard/break routing, saves the vectors and OS shadows, and
restores their values plus POKEY configuration on the tested exits. It waits
for two VBIs after releasing CRITIC before restoring the installed callbacks.
It then parks in a known emulation-mode OS stack context.

POKEY AUDF/AUDC/AUDCTL are write-only hardware settings. The harness supplies a
recorded preflight snapshot through a 32-byte diagnostic capsule; it does not
pretend guest reads of their hardware aliases recover those settings. Production
ownership must obtain authoritative values through the platform adapter.
Neither this snapshot nor the handcoded terminal cleanup qualifies live driver
acquisition, arbitrary active abort, late peripheral traffic, offline recovery,
restart or cooperation with another POKEY audio/cassette owner. Those remain
slice 5–7 work. No ROM SIOV call services the probe transactions.

## Complete storage accounting

**Production reservation change: 0 fixed bank-zero bytes and 0 bytes per task.**
No production allocator, metadata, Task pool or helper reservation changes.
Current totals, including the existing 36,864-byte OS exclusion, remain:

| Production profile | Loading | Runtime |
| --- | ---: | ---: |
| Four public tasks | 58,560 | 57,968 |
| Eight public tasks | 57,232 | 61,536 |

The diagnostic XEX has its own placement. All ranges below are inclusive and
include unused capacity; they must not be added to the production layout.

| Diagnostic reservation | Bytes |
| --- | ---: |
| Code `$00:3000–3FFF` | 4,096 |
| State `$00:2000–20FF` | 256 |
| Preflight snapshot `$00:2100–211F` | 32 |
| Existing OS stack `$00:0100–01EF`, including 16-byte bottom guard | 240 |
| Worker DP `$00:21F0–230F`, background DP `$00:23F0–250F` | 2 × 288 |
| Worker stack `$00:41F0–480F`, background stack `$00:49F0–500F` | 2 × 1,568 |
| Total during the probe | **8,336** |
| Post-probe far-inspection helper `$00:8100–86FF` | 1,536 |
| Post-probe far-inspection buffer `$00:9000–AFFF` | 8,192 |
| Total including inspection reservations | **18,064** |
| Upper-RAM buffers `$04:FFA0–05:009F`, `$06:FFA0–07:009F`, `$08:FFA0–09:009F` | **768** |

Each context costs 1,856 reserved bank-zero bytes: 256 DP bytes plus two 16-byte
guards, and 1,536 stack bytes plus two 16-byte guards. The fixed diagnostic
part is 4,624 bytes before the separate inspection helpers. The OS stack is an
existing shared range, not a second addition to the production OS exclusion.
Inspection runs only after the measured probe and checks actual MEMTOP before
using its scratch; that cold-launch scratch is not available to ordinary tasks.

Bank-zero code and oversized diagnostic stacks simplify this disposable probe;
they do not justify production placement. Actual emitted bytes and observed
stack written extents are retained per case in the record. Untouched poison is
a measurement aid, not proof of a universal stack bound. Production placement
and eight-task memory pressure must be requalified in later slices.

## Hardware probe reproduction

Use the ROM, uninstrumented emulator and SDK from the
[native IRQ correction](emulator-native-irq-fix.md). On a **separate clean source
checkout** at revision `52c18c89e354290199d6f1bbd98eb5048849b15c`, apply only the
[SIO observer patch](../../toolchain/patches/altirra-sio-observer.patch). Build
AltirraBridgeServer with the options/dependency override in the
[build record](../../toolchain/altirra-build.json). Put the resulting executable
and the unchanged SDK under `build/altirra-sio-observer/`. Keep the earlier
latency/concurrency observer binaries separate. The
[observer pin](../../toolchain/altirra-sio-observer.json) records this build's hash;
other builds require an explicitly recorded pin and a fresh qualification.

```sh
python3 tools/test_sio.py --output build/sio-transactions/qualification
python3 -m unittest discover -s tests -p test_sio_package.py
```

The runner creates disposable writable ATR images under its output directory.
Every case replays the exact observed XEX with the same initial disk bytes and
snapshot on the pinned uninstrumented emulator. Full context counters, results,
buffers, guards and stack extents must agree. A `--case` subset can diagnose a
failure but cannot qualify the full gate. Raw bridge logs stay local; the
published record hashes only the selected observation records.

Passing this probe permits development of the chosen hardware path; it does not
qualify public I/O, cancellation, four-/eight-task concurrent SIO or physical
hardware.

## Slice 2: native I/O contract

[io.json](../../abi/io.json) and [sio.json](../../abi/sio.json) now define the native
records, constants, import shapes and reserved guarded operations. The
[generator](../../tools/generate_io.py) produces
[public Action! types/constants](../../lib/exec/exec-io-types.inc) and per-build
`io.inc`/`io-action.inc` definitions. The generated Task `EXEC` module exposes
all ten declarations. Editing the minimal historical `lib/exec/exec.act` alone would
not expose this API to current Task programs.

The [ABI evidence](../qualification/io-abi.json) confirms:

| Record | Size | Alignment | Layout details |
| --- | ---: | ---: | --- |
| IORequest | 26 | 2 | Message at 0; device/unit at 16/19; command at 22; flags/error at 24/25 |
| IOStdReq | 42 | 2 | Flattened IORequest prefix; actual/length/data at 26/30/34; padding at 37; offset at 38 |
| IOSIOReq | 52 | 2 | Flattened IOStdReq prefix; wire command/aux1/aux2/direction at 42/43/44/45; profile at 46; timeout at 48 |

Message.mn_Length remains a 16-bit CARD. Pointers remain 24 bits. Transfer
length, actual count, offset, unit argument, open flags, allocation size and
timeout retain all 32 bits. Device/unit fields are opaque BYTE POINTER handles;
no public Device, Unit or Library internals are invented. Profile numbers are
unassigned until production SIO integration qualifies them. The slice-1 emulator
profiles do not register an openable driver.

### Calls, padding and signed results

Offsets below are relative to the caller's outgoing area (`S_call+1`). Direct
calls use JSL/RTL: the callee's first argument is at entry `S+4`, after the
three-byte return address. The caller cleans up the outgoing area. The generated
compiler interfaces and emitted routine metadata agree in both compiler modes.

| Call(s) | Argument offsets and widths | Outgoing bytes | Result registers |
| --- | --- | ---: | --- |
| CreateIORequest | replyPort 0/3, size 4/4 | 9 | A16 low pointer word, X low byte bank; X high byte zero |
| OpenDevice | name 0/3, unit 4/4, request 8/3, flags 12/4 | 17 | A16, signed INT |
| DeleteIORequest, CloseDevice, BeginIO, SendIO, AbortIO | request 0/3 | 3 | None |
| DoIO, WaitIO | request 0/3 | 3 | A16, signed INT |
| CheckIO | request 0/3 | 3 | Same full pointer result convention as CreateIORequest |

CreateIORequest has padding at outgoing offsets 3 and 8; OpenDevice at 3, 11
and 16. The pinned ABI requires zero padding and the least odd outgoing extent.
These calls therefore add 12, 20 and 6 bytes respectively for outgoing storage
plus direct transfer, before callee-local storage. The record contains each
emitted test callee's fixed frame and local peak; those are probe costs, not
production helper or whole-task stack bounds.

io_Error remains BYTE storage containing a signed eight-bit two's-complement
value. The test callee explicitly subtracts 256 after widening values >=128;
BYTE-to-INT conversion alone would return 254/255. Actual call results are
**-1, -2 and +9**. Pointer returns include `$AB:1234`, `$07:0000` and null;
the nonzero-bank, zero-low-word case is not mistaken for null.

Reserved guarded selectors are `$28–$2D` for OpenDevice, CloseDevice, BeginIO,
CheckIO, the private WaitIO check/collect operation and AbortIO. Misuse fault
`$FF90` is separate from signed device errors. Generation checks these against
gateway, Task/signal, heap, port and diagnostic selectors/faults. Private packets
and dispatch machinery are deferred until needed by implementation.

### Execution and integration checks

The [ABI probe](../../tests/programs/io_abi.act) executes every field offset and
array stride, then writes and reads every field (including the inherited
Message/Node fields) in bank-crossing records at `$04:FFF3`, `$06:FFE4` and
`$08:FFCE`. The host independently checks exact bytes, 16-byte adjacent canaries
and untouched structure padding. Call tests distinguish `$01:1234` from
`$07:1234`, exercise `$FFFFFFFF` sizes/units/flags, and preserve high-bit values
and byte order. The hosted launcher checks stack/DP guards, native return state,
OS vectors and ownership; the probe also performs real console output through
the OS adapter. Layout checks are split into small routines to stay within the
pinned compiler's 254-byte frame/displacement limits in raw mode.

Test callees live in module IOABI. They are never installed as EXEC bindings.
At the slice-2 boundary, all ten **actual production builds** referencing device
calls failed with an
explicit `Unimplemented device I/O import` error and produce no executable.
Package tests reject stale generated definitions, selector collisions, broken
prefixes, missing padding, narrowed results and successful-looking test-stub
bindings. A partial raw/optimized run cannot qualify the ABI gate. All 81 host
tests pass, including the seven new I/O package tests.

The existing named request/reply example is also rerun in raw and optimized
mode through the generated Task module. The slice-1 13-case SIO matrix and its
identical-image replays are refreshed after the shared harness change. Their
scope remains the two-context hardware probe, with unchanged timing results.

### Storage, version and next work

Production bank-zero delta remains **0 fixed bytes and 0 bytes per task**.
The complete four-/eight-task budgets above are unchanged, including guards,
alignment, near-data capacity, table slack and unused reservations. Declarations
add no resident device objects, queues, tasks or native helper reservations.
The ABI probe uses the existing banked launcher's reserved arenas and adds
216 bytes of upper-RAM fixture storage, including all six 16-byte canaries.
Its arrays and results fit inside the existing 2 KiB near-image arena. Final
generated maps, image hashes and compiler/ROM/emulator pins are in the record.

For this diagnostic launcher, the mapped bank-zero regions plus the complete
1 KiB table arena and 2 KiB near-image arena total **58,320 bytes**, including
the OS exclusion and unreclaimed loader/staging capacity. The existing
post-probe far-inspection helper reserves another 1,536 bytes at `$8100–86FF`,
giving **59,856 bytes** including inspection. Its full 8,192-byte `$9000–AFFF`
buffer is already counted within the OS exclusion; this isolated cold-launch
fixture borrows it only after the probe and checks MEMTOP. It is not ordinary
task scratch. The ABI slice adds no new diagnostic bank-zero reservation to
that existing harness.

At the slice-2 boundary the Task ABI remained `$0500`. No new operation could execute
yet; the plan coordinates its version update with the first production bindings
in slice 3. There is one current API, with no compatibility profile.

```sh
python3 tools/generate_io.py --check
python3 tools/test_io.py --compiler-dir build/actionc --output build/io-abi/qualification
python3 -m unittest discover -s tests -p test_io_package.py
```

Slice 3 below implements **request allocation/deletion, resident open/close and immediate
BeginIO/SendIO/CheckIO dispatch** using a test device. Production SIO stays
unavailable until its later ownership, transaction and recovery slices pass.

## Slice 3: request lifetime and immediate dispatch

CreateIORequest, DeleteIORequest, OpenDevice, CloseDevice, BeginIO, SendIO and
CheckIO are bound in the single current Task ABI `$0600`. Rebuild callers.
At the slice-3 boundary the three blocking/cancellation imports still rejected
during image construction. Slice 4 below completes their bindings. The slice-2
and slice-3 records retain their original import-availability evidence.

[IOCORE](../../lib/io/iocore.act) allocates ordinary PUBLIC|CLEAR storage and initializes
only the 16-byte Message prefix. Delete uses mn_Length and frees no other
resource. The checked native entry requires task context and IRQs enabled,
including for null deletion. Invalid create size/port returns null. Device calls
validate the Message and declared extent before touching the I/O tail; short
records fault. A complete IORequest with an insufficient command extension
completes with BADLENGTH.

[Protected policy](../../lib/io/task-io.inc) performs exact-name lookup and direct
resident dispatch. Public names are NUL-terminated byte arrays, as with
FindTask/FindPort; Action! counted string literals must be converted by callers.
The explicit test build adds `immediate.device`, unit zero,
flags zero. RESET succeeds; READ requires IOStdReq and returns zero bytes;
WRITE requires IOStdReq and returns positive error 9; other commands return
NOCMD. BeginIO preserves flags, including QUICK; SendIO clears every flag.
Quick completion publishes FREEMSG without a reply. Every nonquick completion,
including errors, appends one REPLYMSG and optionally signals its owner.
CheckIO returns the original completed pointer without unlinking it.

Device and unit handles point into a reserved upper-RAM resident slot with an
explicit open count. Separately initialized requests may borrow a live binding;
callers settle them before closing the owning open. There is no hidden request
ledger or automatic lifetime reclamation. Failed opens clear both handles and
may be closed harmlessly. Ordinary builds expose no resident devices, including
neither test device nor `sio.device`.

Reply publication is the last request access on nonblocking return paths.
The emitted SendIO thunk ends in COP/RTL. A separate reply-owner test collects
and deletes the borrowed request before SendIO returns, while retaining the
owning open in a different request.

The [lifetime record](../qualification/io-lifetime.json) covers raw/optimized
allocation, exhaustion, field/flag/error semantics, borrowed and static requests,
short-record canaries, absent production devices and that cross-task handoff.
Native-context and existing message-example checks cover result registers,
DP/stack guards, caller restrictions and restored OS vectors/ownership.
The original two-context SIO matrix was replayed against the shared harness;
this does not qualify production device timing.

Reservation delta: **0 fixed bank-zero bytes; 0 per-task bank-zero bytes**,
including all existing guards, alignment and slack. Four-task fixed reservation
remains 11,824 bytes plus five 1,856-byte context pools. Eight-task fixed remains
10,560 bytes, root 2,080, seven workers at 1,568 and idle 1,056. The table above
retains the loading/runtime totals including OS exclusions. Resident slots reserve
64 upper-RAM bytes (four active in this slice, 60 reserved); code starts after
that whole reservation in the configured kernel bank. Native helpers remain
within their existing 4,096-byte reservation. No I/O call allocates a signal,
Task or bank-zero buffer. Caller continuations use the existing guarded stacks.

Reproduce with:

```sh
python3 tools/test_io_services.py --compiler-dir build/actionc \
  --suite lifetime,handoff,short,absent --output build/io-lifetime
python3 tools/test_io.py --compiler-dir build/actionc --output build/io-abi
python3 tools/test_ports.py --compiler-dir build/actionc --suite example
python3 -m unittest discover -s tests
```

## Slice 4: queued completion and cancellation

All ten generic imports are implemented. The public layouts and reported Task
ABI remain `$0600`; the caller-private completion result is not a public ABI.
[WaitIO and DoIO](../../lib/io/iocore.act) run on the caller's own stack. The guarded
Start operation sets exactly IOF_QUICK. Quick completion returns a copied,
sign-extended error directly. Deferred completion returns an internal marker;
DoIO then enters WaitIO. Neither path rereads a request after publishing a reply
on a nonblocking return.

WaitIO calls a protected check/collect operation. Pending returns a copied signal
bit, followed by the existing Wait and another check. There is no signal clear
between checking and waiting, and no shared kernel continuation survives that
check. Completion removes the specified reply directly through its links and
sets NT_FREEMSG. It leaves unrelated messages, including the reply-list head,
untouched. CheckIO only observes. GetMsg retains its existing NT_REPLYMSG result;
GetMsg and WaitIO are alternative collection paths for one submission. Calling
WaitIO after collecting that submission with GetMsg is outside the contract.

WaitIO and DoIO require a PA_SIGNAL port owned by the current task and enabled
IRQs, including when completion is already available. BeginIO, SendIO and AbortIO
remain nonblocking and permit another task to own the reply port. All I/O entries
use the same checked task-domain guard; IRQ/NMI contexts and policy reentry are
unsupported. Caller-owned request/buffer lifetime and settled close/delete remain
preconditions; there is no duplicate-submission or allocation ledger.

The opt-in `queued.device` has one worker binding, a FIFO and one active pointer.
It supports RESET and immediate errors like the first test device; READ refuses
QUICK, requires IOStdReq and a nonempty valid 24-bit buffer extent, and queues.
A finite test-controlled completion writes `$5A` to the first buffer byte and
reports io_Actual=1. This is a generic ownership test, not a hardware driver.
The private IOPROBE control import is rejected in ordinary builds. Normal
OpenDevice still finds neither test device nor `sio.device`.

Taking a pending head and publishing active/preparing state plus a cleared
cancellation latch occur in one guarded operation. AbortIO removes a known
queued node and replies ABORTED, or latches cancellation on the known active
request. Arming preserves that latch. Terminal publication retires the active
pointer and all buffer access before replying exactly once. An abort after
terminal publication or collection does nothing; normal completion may win.
Neither generic collection nor cancellation searches tasks or reply queues.

The [queued-I/O record](../qualification/io-queues.json) records the selected
raw/optimized runs and their exact images. It covers quick results, quick refusal,
signed and positive errors, shared/coalesced/stale signals, unrelated reply heads,
specific collection out of order, completion before WaitIO, cancellation while
queued/preparing/active and after terminal/collection, and nested Forbid across
immediate and blocking DoIO. The worker progresses while the caller waits.
A separate reply owner frees a queued request before the submitter's SendIO
returns. A caller-side test checkpoint forces completion precisely between a
pending check and Wait; separate checkpoints inject real NMI during wait
publication. Fault cases retain unchanged request snapshots for wrong-owner and
PA_IGNORE waits. Selected Task/signal/port regressions retain the shared gateway,
interrupt coexistence and context/guard checks.

The SIO hardware matrix is a separate two-context assembly probe. Replaying it
against the shared harness does not qualify these generic calls, the Task worker
path, production SIO latency or eight-task concurrent serial timing. Those remain
slices 5–8.

**Slice-4 reservation delta: 0 fixed bank-zero bytes and 0 bytes per task.**
No upper reservation grows: the existing 64-byte device arena now contains two
4-byte resident slots, a 24-byte queue record (including record padding),
31 bytes of NUL-terminated resident names, and one final padding byte. Test
names are initialized directly in upper RAM; no near string literals remain. The complete bank-zero budgets above
remain unchanged. Native helpers use 3,676 of their already reserved 4,096 upper
bytes (3,790 with the existing heap race diagnostics). Checked native entries
need three transient caller-stack bytes; compiler-generated continuation frames
and platform interrupt headroom remain inside the existing guarded Task stacks.
Emitted WaitIO local stack peaks are 84 raw / 56 optimized bytes; DoIO is
54 / 42 bytes, excluding deeper callees and platform interrupt headroom. The
fixtures use two live public tasks. Eight-task device/serial qualification
is still deferred.

Reproduce the principal cases with:

```sh
python3 tools/test_io_services.py --compiler-dir build/actionc \
  --suite queues,queued_handoff,gap,queues-publication-2,queues-publication-3
python3 tools/test_io_services.py --compiler-dir build/actionc \
  --suite wait-fault-0,wait-fault-1,wait-fault-2,wait-fault-3
python3 tools/test_io.py --compiler-dir build/actionc
python3 tools/test_ports.py --compiler-dir build/actionc --suite queue-races
python3 -m unittest discover -s tests
```

Next is slice 5: integrate the qualified SIO ownership, RX/TX, alarm and descriptor
handoff primitives into the Task platform adapter. Keep production `sio.device`
unpublished until its cancellation, recovery and cleanup contract is complete.

## Slice 5: native Task adapter

The [native adapter](../../platform/altirraos/sio.s) integrates buffered SIO with
actual Task contexts and the existing direct signal producer. Its private,
[generated descriptor](../../abi/sio-adapter.json) contains no IORequest pointer.
The worker prepares inactive fields with IRQs enabled. Start publishes them
under SWITCHING with a short masked handoff; cancellation is not cleared by
arming. Terminal commit disables owned sources, clears both far pointers and
publishes one signal only after caller memory is unreachable from IRQ.
Retire consumes the durable terminal state before permitting descriptor reuse.
A 16-bit generation supplements source quiescence; it does not replace it.

Native IRQ entry preserves the existing full frame. ROM callbacks preserve
hidden B, X/Y, D/DBR and native/emulation entry mode on the OS stack. They cannot
switch across the OS activation. RX, TX-ready, TX-complete and the two timers
have bounded handlers. A watchdog IRQ rechecks RX/TX once before returning, because
a byte can arrive after the initial serial check; the extra IRQ entry plus
scanline DMA otherwise caused a measured receive deadline miss. There is no
unbounded drain loop, task search or allocation in IRQ.

A second measured correction retires a VBI scheduling hint when no ready peer,
sleeper or pending wake needs policy. The absolute VBI count remains intact.
Repeated validation of that unused hint on every subsequent byte IRQ had caused
an overrun in the integrated adapter.

Timers retain the probe's frequencies and 8/10 setup/write countdowns. The
integrated command hold uses **6** fine ticks: the probe's 7 ticks exceeded the
950-us upper bound after the longer kernel IRQ entry. Start resets STIMER once
at COMMAND assertion, before enabling sources and before any serial bits move. No phase transition
resets the serial/timer clocks. The active deadline uses a wrap-safe 16-bit
coarse-tick clock, with a maximum of 250 ticks (about 1.011 seconds). This is an
explicit private implementation deviation from the proposed 32-bit clock:
16-bit accesses are atomic on this CPU, and the accepted timeout is much shorter
than the half-wrap interval of about 132 seconds. Public timeouts remain 32-bit
microseconds; they do not imply microsecond enforcement resolution.

The adapter owns all four POKEY channels. AltirraOS has no complete shadows for
its write-only audio registers. Therefore initialization establishes a known
silent baseline and maintains private shadows; shutdown restores that baseline.
It does **not** claim to restore arbitrary pre-existing audio settings. Borrowing
active timers is rejected. Audio/cassette ownership sharing needs another
platform protocol and is unsupported. SKCTL, owned interrupt-enable bits,
serial/timer vectors, COMMAND control bits and the original CRITIC are saved
and restored; unrelated enable/PIA bits are merged. No write-only alias is read
as a saved audio value. This replaces the probe's debugger-supplied snapshot.

Serialized console calls and forwarded ROM COP calls return busy while the
adapter owns POKEY. This deliberately conservative initial exclusion covers
untracked ROM serial and sound changes. Immediate VBI and unowned IRQ handling
continue; Retire restores the original CRITIC, and the fixture provides two
VBI ticks between transactions. An originally nonzero CRITIC stays nonzero.
No request is serviced through SIOV.

[Adapter evidence](../qualification/sio-adapter.json) records the exact images,
compiler modes, observations and replay scope. The executable fixture exercises
real read/write/read-back transactions, crossed bank boundaries, timeout and
clock wrap, cancellation before arming, an NMI between the low-word and bank
writes of an inactive descriptor, and real timer callbacks during a protected
emulation-mode OS activation. Raw/optimized signal and context regressions are
listed separately. Parser controls reject missed RX/TX and phase deadlines.
This is not yet queued-device recovery or eight-task timing qualification.

The upper helper reservation grows from 4,096 to **8,192 bytes**, including unused
capacity. The descriptor reserves **128 additional upper bytes** at Task arena
+$0800, excluded from public writable Task admission. Total new upper reservation
is **4,224 bytes**; the metadata bank was already unavailable to the heap.
The ROM vector bridges fit existing bank-zero code arenas. Fixed and per-task
bank-zero reservation deltas are **zero**, with every guard, alignment byte and
unused reserved byte retained: runtime totals including OS remain **57,968 /
61,536** bytes for four/eight public tasks; loading totals remain **58,560 /
57,232**. The fixture uses existing contexts and two separately reserved 256-byte
upper buffer arenas; no additional bank-zero diagnostic arena is introduced.

The private Start import checks 19 local stack bytes, covering the deepest
cancellation-to-terminal-to-signal path. Other private imports conservatively
advertise the same bound. Native byte access uses six activation-local bytes
plus its JSR frame, and terminal signal posting uses the existing twelve-byte
scratch plus saved D. The full native IRQ peak is 34 bytes including its
13-byte interrupted frame, before possible NMI nesting; existing interrupt
headroom and OS/private stack guards remain in force. The emulation diagnostic
checks its private stack before transferring to the already reserved OS stack.

Reproduce the two measured images and identical uninstrumented replays with:

```sh
python3 tools/test_sio_adapter.py --case raw --trace --output build/sio-adapter-raw
python3 tools/test_sio_adapter.py --case opt --trace --output build/sio-adapter-opt
```

`--variant 1` selects a silent device, `2` starts with CRITIC=3, `3` cancels
before arm, `4` crosses the coarse clock wrap, `5` forces emulation callbacks,
and `6` forces the inactive-descriptor NMI. These diagnostic imports are rejected
outside explicit I/O fixture builds. Ordinary `OpenDevice("sio.device", ...)`
is still unavailable at this slice.


## Slice 6: queued transactions

One resident worker now consumes a private FIFO for disk IDs $31–$38. Each open
holds a per-unit reference; all units share the hardware. Signals 31 and 30 belong
to the worker for submissions and terminal hardware posts. There are no tasks,
signals, ports or buffer allocations per transaction. The request itself supplies
the queue node. Admission, dequeue and reply publication run under SWITCHING;
buffer/profile validation and descriptor preparation run in the worker with IRQs
enabled. This also keeps the raw-code validation call chain off the shared kernel
stack. No bank-zero stack enlargement was needed.

The test fixture uses the public OpenDevice/SendIO/WaitIO/DoIO/CloseDevice calls,
with explicit test-only driver startup. It submits two units together, collects
the second request first, and checks reads and write/read-back on disposable
media. A request at $0AFFF0 crosses a bank, as do RX/TX buffers; the write buffer
comes from a LINEAR allocation. An independent task records progress during
hardware activity. Invalid extents, lengths, directions and profiles return
through the same reply path. The worker retires the descriptor and waits two
VBIs between transactions, giving the OS a stage-two opportunity.

The upper device arena grows from 64 to **256 reserved bytes** (+192): the
existing test residents, one SIO bus/private MsgPort, eight unit records, one
62-byte public worker Task, and a NUL name, including padding. The descriptor
and native helper reservations from slice 5 are unchanged. **Bank-zero fixed,
per-task, stack, DP, guard and slack deltas are all zero**. The complete four/eight
context budgets remain those in the platform contract. Each worker consumes one
existing execution slot; it does not reserve a ninth application context.

Initial profiles accept at most 128 payload bytes and upper mapped RAM only.
Timeout zero selects 1,000,000 us; explicit timeouts span 4,041–1,000,000 us and
round up to the private watchdog period. Command setup starts the deadline.
There is no retry or baud fallback. NONE uses zero payload; READ and WRITE count
only payload bytes. These deliberately narrow platform profiles are distinct
from the general 32-bit IOStdReq fields.

The pinned headless emulator ignored the drive argument to MOUNT. The isolated
[host bridge patch](../../toolchain/patches/altirra-headless-mount.patch) forwards it
to ATImageLoadContext, using the normal simulator disk-loading path. The
[queued-test pin](../../toolchain/altirra-sio-queued.json) records new observed and
uninstrumented binaries. CPU and peripheral emulation are unchanged; earlier
qualification records retain their original binaries. Two-drive execution is
the regression for this setup defect.


## Slice 7: recovery and ordinary registration

OpenDevice with the exact NUL name `sio.device` initializes one worker before
publishing a successful handle. The blocking initialization rendezvous preserves
Forbid nesting. Existing opens and disk IDs share that worker. Startup failures
release allocated signals and the admitted context; a occupied serial binding
or full context pool leaves no openable partial resident. The worker's entry
address lives in the private upper descriptor and is excluded from public
AddTask admission. Removal is rejected while the worker owns its producer.

AbortIO directly removes a queued request, or latches cancellation for the
known active request. The hardware sees that latch before arming and at IRQ
entry. Preparation does not clear it. A committed terminal result wins a later
abort. First error wins when a device Error is followed by a broken/short data
frame. None of these paths retries a command or reverses an issued write.

Before posting terminal completion, the IRQ clears both caller pointers.
Private receive handling remains enabled in terminal, recovery and idle states;
it only discards bytes and latches an offline indication. In the original slice,
the worker published the reply, then slept three VBIs (at least two complete
PAL frame periods) to provide an OS service/quiet interval before reuse. The
[clean-completion update](#clean-completion-without-an-os-service-sleep) removes
this sleep on success and retains it for errors. A fully consumed response,
NAK, or complete checksum-failing frame can recover. A timeout, framing/overrun,
protocol error, active cancellation or unexpected late byte leaves the bus
**offline until platform reset**. An Error with short data remains DEVICE as the
first request error while independently latching unsafe bus state.

Queued and new requests on an offline bus return BUSUNAVAILABLE; reopening
cannot reset it. ROM entry remains excluded. When an offline owner shuts down,
or a fatal kernel exit interrupts an uncertain active transfer, the image parks
at the normal diagnostic rendezvous with status **$FF93**, IRQs and NMI disabled,
and retained hardware/kernel ownership. This is an explicit reset-required exit,
not a return to AltirraOS. A clean shutdown instead disables/drains sources,
restores owned state, releases the producer and signals, and removes the worker.
After the final application task exits with all opens closed, the idle resident
shuts itself down. Closing one handle does not tear down other clients' worker.

The original [20-case suite](../../tools/test_sio_recovery.py) executed in both compiler modes.
It covers queued/preparing/active/terminal abort, absent device, counter wrap,
NAK, overrun, rejected bound-worker removal, both startup failure paths, private
entry rejection, Error-plus-data, checksum, short/extra/late data, framing and
protocol failures. Collected buffers are immediately poisoned and checked after
recovery; stale alarm callbacks leave them intact. A pinned test-only D8 responder
changes real peripheral bytes/stop bits through the existing POKEY receive path;
it never calls the guest kernel. The overrun control deliberately masks IRQs.
The first-cause and exactly-once terminal/reply assertions pass. Clean cases also
restart the resident; unsafe cases verify $FF93 and retained ownership.

Measured cancellation entry-to-terminal latency was 187.14 us raw / 105.03 us
optimized in the forced active-abort fixture, within the watchdog-period bound.
Silent deadlines (including wrap) were enforced 37.08 us raw / at most 28.62 us
optimized after their hardware deadline, within the 100 us lateness limit.
These are cancellation/deadline observations, not eight-task byte-timing claims.

The ordinary, test-registration-disabled [read-only example](../../examples/device-io.act)
uses CreateMsgPort/CreateIORequest, OpenDevice, SendIO/WaitIO and ordered close /
buffer/request/port deletion. Its initial public profile is FASTEST125; changing
the selected peripheral requires explicitly selecting its matching profile.
Only the pinned fastest/810 read/put and Happy NONE transactions have executable
compatibility evidence. Physical drives and arbitrary audio owners remain
unqualified. Console/forwarded ROM calls still report BUSY while the resident
owns POKEY; no ROM SIO fallback is used.

No reservation grows in this slice. Seven private descriptor bytes use existing
128-byte capacity; the helper image occupies 6,258 of its reserved 8,192 bytes.
**Bank-zero fixed, per-task, DP, stack, guards and slack deltas are all zero**;
the complete four/eight-task runtime and loading budgets remain unchanged.

## Clean completion without an OS-service sleep

The dedicated Exec workload no longer sleeps three ticks after a successful
SIO transaction. `RunRequest` snapshots the descriptor's error before publishing
the reply, then calls `Recovered` immediately on success. The recipient may
free/reuse its IORequest as soon as it collects that reply, so the worker must
not read it again. Error completions retain `Sleep(3)`; timeout, active abort
and other uncertain outcomes still latch the bus offline until platform reset.

The hardware path is unchanged. Terminal handling clears caller pointers before
posting; retirement restores CRITIC; private receive handling discards stray
bytes and latches offline; Start checks offline again before asserting COMMAND
and exposing the new buffer. The removed sleep was an OS-service opportunity,
not a hardware deadline or a proof of bus recovery. Exec's scheduling tick runs
before the ROM's stage-two VBI and remains active throughout serial traffic.
Continuous queued traffic has no guaranteed stage-two OS-service interval.
Clean shutdown still restores owned state; an unsafe shutdown still parks at
`$FF93` with ownership retained.

The [verification record](../qualification/sio-fast-completion.json) records the
current inputs and checks. The raw/optimized recovery suite now has 22 cases.
Its two additions cover freeing/recreating a collected request immediately,
and a real delayed peripheral byte arriving after the next descriptor has been
prepared but before it is armed. The latter pauses the worker at the existing
test checkpoint, confirms the bus is still online, leaves IRQ/NMI enabled,
and requires BUSUNAVAILABLE, one hardware terminal post, exactly one reply per
request and an unchanged caller buffer with poisoned ends and a known interior.
Checkpoint and late-byte waits are bounded. An explicit cleanup marker prevents
the expected `$FF93` shutdown from concealing an earlier assertion failure.
This specifically covers the gap before Start; it does not
establish behavior for every faulty peripheral's arbitrary late stream after
another command has already been armed.

See the [large-read comparison](dos-read-throughput.md#verification-without-the-successful-transfer-sleep)
for throughput. This change adds **0 reserved bank-zero bytes**, including
**0 bytes per task**, with no changed stack, DP, guard or interrupt reserve.
The evidence applies to the pinned emulated profiles, not physical hardware.

## Slice 8: concurrent qualification

The ordinary public-build fixture admits root, the resident worker and all
clients before releasing its barrier. Four public contexts provide two clients;
eight provide six. Idle is additional. Each client submits paired requests to
two reply ports sharing one signal bit, and collects the second request first
with WaitPort/WaitIO. The three rounds are READ, PUT and READ-back of all 128
payload bytes. Two disposable drives share the one bus FIFO. There are 12
transactions at four tasks, 36 at eight, with peak outstanding depths 4 and 12.
The Happy profile repeats its supported zero-payload QUIET transaction instead.

Root fragments and clears heap memory, publishes and searches four 64-character
port names, exchanges message bursts, signals/waits, sleeps and yields during
traffic. Every round checks those counters; each client checks both request
identities and payloads. A key is injected at a stopped real serial IRQ and then
delivered by the ordinary unowned-IRQ path. The short Happy exchange can finish
between root's phase samples, so its active progress uses independent CPU routine
entries in root's direct-page context while the transaction is live. It does not
require an artificial delay in the driver to make a sampling counter increase.

[Concurrency evidence](../qualification/sio-concurrency.json) includes raw and
optimized timing for all three advertised profiles at four/eight contexts in
kernel bank 1, with an identical-XEX replay on the uninstrumented emulator.
Kernel-bank-3 runs qualify functionality only. The observer compares command,
checksum and payload bytes against submission identity and FIFO order; measures
RX register service, TX refill/continuous shifter timing, final-byte completion,
COMMAND setup/hold, write turnaround, fine/watchdog alarms, Forbid sections,
terminal-post-to-worker, next start and client collection. Guards and heap,
signal and bank ownership are checked through normal shutdown. No task, signal,
port or buffer is allocated per transaction by the driver.

Across the accepted four/eight-task raw/optimized runs, the 125-kbaud profile
observed at most **70.49 us RX service** and **74.44 us TX refill**, below its
78.94 us byte deadline. At eight tasks alone, RX was at most 60.90 us and TX
74.44 us. Stock-speed maxima were 69.93 us RX / 63.72 us TX; the longest observed
CRITIC superset was 1.032 s. Across all profiles, post-to-worker reached 36.39 ms
and a workload Forbid section reached 24.34 ms. Hardware handles every byte and
phase without depending on those task rescheduling times.

A raw eight-task baseline exposed a 14-base-cycle TX gap despite correct data.
The next payload byte is now prefetched into the existing SD_VALUE field after
SEROUT refill. First-byte setup primes it; final-byte handling never reads past
the admitted extent. RX and TX payload phases use that field exclusively. The
same native stack bound applies: the prefetch tail call retains no additional
activation. A simultaneous fine alarm and watchdog also exposed 106.51 us of
watchdog lateness. The watchdog now checks the absolute deadline before a fine
alarm starts another phase; serial RX/TX remain first in service order.

STOCK810 cold seek/rotation plus a sector transfer exceeded the original one-second
active budget. Its zero/default and explicit maximum are now **2,000,000 us**;
FASTEST125 and Happy remain at 1,000,000 us. The minimum remains 4,041 us. The
conversion is bounded by 495 additions and all intervals remain far below the
16-bit clock half-wrap. Emitted raw/optimized tests reject out-of-range values,
exercise both zero/default and explicit two-second deadlines on an absent unit,
and check timeout lateness, offline ownership and returned-buffer safety.
This changes device-operation latency allowance, not byte deadlines or baud.

Acceptance limits are declared in the [timing oracle](../../tools/sio_concurrent_trace.py):
50 ms for workload Forbid sections, 100 us alarm service, 100 ms post-to-worker,
200 ms post-to-next-start, 2.5 s post-to-paired-client collection and 2.12 s for
the conservative CRITIC interval. The interval from sio_start entry to sio_retire
entry contains actual CRITIC ownership; it includes worker rescheduling. Masked
intervals include idle SEI/WAI/CLI waits with no interrupt pending. WAI wakes on
an asserted IRQ even with I set; actual arrival-to-service measurements include
that wake and are the byte deadline test. Maxima are observations on the named
pin, not a worst-case proof for arbitrary workloads or physical devices.

Separate eight-task functional variants abort queued requests among normal
transactions, and time out an absent unit while other clients have requests
outstanding. They check all completions, queue progress or BUSUNAVAILABLE,
resource totals, and poison collected buffers before allowing more IRQ activity.
The unsafe timeout path retains ownership and exits with reset-required $FF93.
Edited real traces deliberately miss RX, TX and phase deadlines to test the
oracle; malformed/partial evidence records are rejected by host tests. Actual
IRQ-stall/overrun and the full recovery corpus are rerun as integration checks.
See [the exact regression record](../qualification/io-sio-regressions.json), which
also records Task, signal, port, heap, Lists, loader/context/OS and public-example
cases and their image/input identities.

No production reservation grows. The native helper uses **6,271 of 8,192 reserved
upper bytes**; its 128-byte descriptor and 256-byte device arena are unchanged.
The fixture reserves 512 diagnostic upper bytes for public Task records: six
64-byte slots (62-byte Task plus two padding bytes) and 128 spare bytes. Clients,
requests and buffers use heap storage. Fixed and
per-task **bank-zero deltas are zero**, including DP, stacks, guards, alignment,
near-data capacity and slack. Complete runtime/loading totals remain 57,968 /
58,560 bytes for four public contexts and 61,536 / 57,232 for eight, including
36,864 OS bytes. Existing root, client and idle pools are unchanged.

Reproduce a case with, for example:

```
python3 tools/test_sio_concurrent.py --case raw --capacity 8 --trace --key
python3 tools/test_sio_concurrent.py --case opt --capacity 8 --speed 1 --trace --key
python3 tools/test_sio_concurrent.py --case raw --capacity 8 --bank 3
python3 tools/test_sio_concurrent.py --case opt --capacity 8 --fault timeout
```

Use separate `--output` directories when running cases concurrently. Speed 0
is FASTEST125, 1 STOCK810 and 2 Happy NONE. The published record lists each final
image, compiler, ROM/peripheral configuration, source hashes and measured limits.
DOS/block integration, additional drive profiles, arbitrary audio coexistence and
physical-hardware qualification remain separate work.
