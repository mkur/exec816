# DOS console streams implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Work started 2026-09-22 from the [updated plan](../plans/dos-console-streams-implementation-plan.md)
and qualified actionc `ae1f555`. All seven slices are complete. The
[design](../reference/streams.md) remains the public contract.

## Slice 1: shared owned-object routing

`DOSOBJECTS.Header` is the common inline prefix: next pointer at 0, owning DosSlot
at 3, kind at 6 and backend at 7. Common lookup checks membership and owner/kind
before exposing a header. Filesystem lookup then checks the backend before
reading mount/generation fields. Files, locks and future streams use the same
list and client object count; unlink clears the retired header's ownership.

The eight-byte prefix fits the existing filesystem object allocation. Emitted
layout checks confirm 112 bytes before and after, with mount at 8, generation at
12, cursor at 16 and enumeration ticket at 108. No wrapper allocation or live
blocking dispatch frame was added. The caller and packet worker share the same
ownership implementation.

Validation uses `tools/test_dos_streams.py --suite routing`: raw/optimized object
probes in kernel banks 1 and 3, native DOS ABI, client calls and Task reuse,
concurrent file calls, directory operations, mount lifetime/retry and one complete
70,003-byte DOS Read. Results live under `build/dos-streams-slice1/verified/`.
All 20 cases pass. The [routing qualification record](../qualification/dos-streams-routing.json)
binds the results to compiler, source, image and artifact hashes.

The initial probe's host counter expected 27 checks instead of its actual 26;
the guest completed all assertions and the counter was corrected. The older ABI
harness also linked the full filesystem across its fixed cross-bank test buffers.
That callee/layout probe now selects its existing isolated DOS fixture mode.
Production routing and filesystem tests still use the ordinary system image.

The completed bank-1/bank-3 routing probes retain the complete eight-slot bank-zero
maps: 57,232 bytes during loading and 61,536 at runtime including OS, guards,
alignment and unused reserved capacity. Fixed and per-Task reservation deltas
are both zero. The four-task ABI/client fixtures also retain their complete
baseline maps. Matched file/directory/lifetime/retry fixtures add zero near-image
bytes. New routing probes use 118 near-image bytes for fixture state.

The complete single read verifies 70,003 bytes in both modes. Observed stack
bytes for reader/filesystem/SIO/kernel are 232/187/162/325 raw and
210/173/134/316 optimized; all 256-byte interrupt reserves remain untouched.
The reader is the root Task in this focused test; simultaneous eight-Task stream
qualification remains slice 7.

The host suite reports 127 passes and the already recorded historical SIO
source-hash failure in `test_sio_sector_record`; no old evidence is rewritten.

## Slice 2: NIL and destination dispatch

NIL: opens a distinct 16-byte owned upper-RAM handle in all three modes. Read
returns EOF and Write returns the full validated signed 32-bit length, without
accessing the payload. Zero-length calls bypass buffer validation; invalid
handles are rejected first. Close consumes the handle and preserves IoErr;
Seek fails explicitly. Write on a valid file returns zero for zero length and
write protection for a valid positive transfer. Existing MyDOS Read still
requires upper-RAM buffers.

Bounded name classification precedes filesystem startup and mode checking.
Unknown prefixes, unsupported CON:/CONSOLE:, unavailable RAW: and malformed
stream suffixes fail explicitly. Generation and runtime alias validation reserve
all four stream names. Headless NIL: creates no service worker. The new Write
signature preserves far pointers and signed 32-bit counts/results; archival DOS
ABI evidence retains its original ten-call scope.

All six raw/optimized cases pass in `build/dos-streams-slice2/verified2/`:
headless (41 assertions), mixed MyDOS/lock/NIL (49), and eleven-call ABI probes.
The [NIL qualification record](../qualification/dos-streams-nil.json) includes image,
source, compiler and result hashes. Eight read/write watchpoints remain armed
across NIL transfers; a deliberate payload read stops execution with those same
watches before they are cleared. Both modes verify unchanged bytes. The
zero-low-word identity probe uses an explicitly mapped test-owned header at
$0E0000, links/unlinks it through the normal ownership list, and does not pretend
that static fixture storage is heap allocated. Foreign-task and closed-pointer
checks do not claim protection against later address reuse.

Early fixture attempts used a nonexistent AllocAbs API, omitted an explicit
ADDRESS conversion, and assumed a bank-zero MyDOS Read buffer. Those test
assumptions were corrected; no compiler workaround was introduced. Failed runs
remain in the slice artifact root. The 17 DOS host checks and generated-contract
checks pass.

Complete fixed and per-Task bank-zero reservation deltas are zero: eight-slot
loading/runtime totals remain 57,232/61,536 bytes including OS. NIL adds one
16-byte allocation (already eight-byte aligned), no endpoint/request/Task, and
no per-allocation wrapper. Client context remains 72 bytes plus its existing
32-byte rounded port. The new test uses 227 near-image bytes; the library adds
no near globals. Headless/mixed caller stack maxima are 270 raw and 247 optimized
in the root's 1,536-byte stack; mixed kernel maxima are 325/303. All Task and
kernel interrupt reserves and guards remain intact. Eight simultaneous Task
qualification remains slice 7.

## Slice 3: task-local standard streams

Input/Output return borrowed selections without allocating or changing IoErr.
SelectInput/SelectOutput accept a live caller-owned FileHandle or null, return
the previous selection, and clear IoErr on success. Invalid, foreign, wrong-kind
and reentrant calls preserve the existing selection. IsInteractive returns false
for valid files/NIL: and rejects invalid handles. RAW: becomes interactive in
slice 4. Selecting a file as Output does not grant write permission.

Accepted Close clears both matching selections before releasing an object.
ReleaseContext rejects live objects, selections, activity or bound requests;
it deletes an optional idle transfer request before its private port/context.
Context allocation is 80 bytes (eight-byte rounded), up from 72: input/output
at 71/74 and request at 77. The embedded packet remains at 6, objects at 68 and
busy at 70. DosSlot remains 16 reserved bytes (14 active); public Task is unchanged.
There are no additional ports, signals or Tasks.

The focused fixture checks unset getters and heap balance, null-selection
success versus invalid-handle failure, borrowed save/select/restore on success
and failure, reentrancy rejection, independent defaults and repeated Task reuse,
file-as-Output, wrong-kind/closed identities, accepted-close clearing and refused
context release. It performs 44 assertions in each bank/mode case. The ABI
runner now exercises all sixteen current calls; its command-line entry no longer
expects implemented DOS calls to fail packaging. Historical ten-call evidence
keeps its original scope and is not rewritten.

All ten cases pass in `build/dos-streams-slice3/verified/`: raw/optimized defaults
in kernel banks 1/3, current ABI, 260-cycle reuse and concurrent file regressions.
The [defaults record](../qualification/dos-streams-defaults.json) binds evidence to
its inputs. All 17 DOS host checks, generated contracts and document links pass.
Fixed and per-Task bank-zero reservation deltas are zero, retaining the complete
57,232/61,536-byte loading/runtime maps including OS. Added per-client upper-RAM
cost is eight bytes; matched file fixtures add zero near-image bytes. The defaults
fixture uses 219 near-image bytes. Its root stack maxima are 288/263 bytes
raw/optimized; the concurrent-file callers use 248/226, and kernel maxima across
these cases are 325/310. All stack/domain guards and interrupt reserves remain
intact. No compiler defect or workaround was required.

## Slice 4: shared RAW endpoint

RAW: uses one shared console.device open with a manually initialized PA_IGNORE
port embedded beside the owning IOStdReq. Additional DOS handles retain that
endpoint without reopening/resetting the device. Each client lazily allocates
one transfer request on its existing private reply port, borrowing only device
and unit pointers. Preparation returns before SendIO/WaitIO. Reader admission
remains held through exact reply collection and unbinding; another client may
write while that reader waits.

The 16-byte discovery registry is explicitly reserved in the configured kernel
bank, after the existing DOS service reservation. CLOSED/OPENING/READY/CLOSING
and reference/operation counts change under short IRQ-permitting Forbid sections.
Allocation, extent checks, device operations, rendering and waits occur outside
them. The last accepted Close clears selections, unlinks the handle, closes the
idle device, removes discovery before freeing the endpoint, then publishes
CLOSED. Generation/reference/operation counters fail before wrapping.

The emitted endpoint is 98 bytes, rounded to 104: owning request at 0, embedded
port at 42, references at 70, active operations at 72, reader at 74, generation
at 78 and device name at 82. Handles are 16 bytes. Client context remains 80
bytes plus its existing 32-byte rounded port; the lazy 42-byte request consumes
48 heap bytes. No new worker Task, signal or allocated signal port is added.
The endpoint's embedded ignore port consumes no signal. No near-image library
globals were introduced.

RAW reports IsInteractive true, preserves translated short reads without echo,
and maps input loss to ERROR_BUFFER_OVERFLOW (303). Other causal device errors
retain their signed value. Nonempty reads with a successful zero Actual and
short successful writes are rejected with IOERR_BADLENGTH. Zero-length operations
validate the handle without allocating/submitting a request or consuming input.
Bank-zero RAW buffers must belong to admitted writable image ranges; a private
DOS control operation reuses the console's existing Writable predicate. Upper
buffers use the common mapped-extent check. Existing MyDOS Read buffer rules
are unchanged.

The public RAW fixture exercises physical B/A, Ctrl-C and BREAK; all three modes;
no reset on additional open; no automatic echo; pending-read/concurrent-write
behavior; competing-reader rejection; first-opener context release; exact request
collection/reuse with file packets and NIL; allocation/open rollback; and final
resource/hardware restoration. It also writes a complete 70,003-byte buffer,
with explicit bytes around offset 65,536, scrolling and output controls. An
independent host terminal model checks retained cells and eventual physical
screen state after the source allocation is freed.

A dense all-printable 70 KiB probe reached the 240-second host checkpoint limit
while still running. The bounded ABI/semantics fixture uses a mixture of ignored
controls and printable bytes, keeping the full transfer length, bank-boundary
checks and scrolling. This is not a console-throughput benchmark; the timeout
was not raised. The fixture's first modulo-based pattern also encountered the
already documented unsupported native remainder operation; the final pattern
uses a cycling byte counter. No Exec-specific compiler workaround was added.

The mixed test exposed an existing console lifetime bug: the count-based
last-application guard mistook a retiring filesystem worker for the application
when RAW remained open. ConsoleCanRemove now excludes registered DOS/SIO worker
identities; their active producer bindings remain guarded separately. The
fixture now stops the filesystem while RAW stays open. An independent existing
direct-console removal test still requires the exact misuse fault for an
application that exits with its console open.

All twelve cases pass in `build/dos-streams-slice4/verified/`: raw/optimized RAW
fixtures in kernel banks 1/3 (51 parent and eight child assertions each), headless
NIL with payload-access watchpoints, the current sixteen-call ABI, a complete
70,003-byte MyDOS Read, and the direct-console removal guard. The last case
requires fault 4; all other cases require status zero. The
[RAW qualification record](../qualification/dos-streams-raw.json) binds these results
to compiler, source, image, machine and artifact hashes. Reproduce with:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
  python3 tools/test_dos_streams.py --suite raw \
  --compiler-dir build/compiler-ae1f555 --output build/dos-streams-slice4/verified
python3 tools/dos_streams_record.py build/dos-streams-slice4/verified \
  --output docs/qualification/dos-streams-raw.json
```

Use fresh output paths for a repeat; existing evidence is not overwritten.
RAW checkpoints retain the preset 240 host-second/12,000 guest-frame limit;
completion uses 600 seconds/30,000 frames. The collector rejects missing cases,
damaged guards, incomplete large transfers, missing physical keys, touched
interrupt reserves and changed bank-zero accounting. Generated contracts,
document links and all 17 DOS host checks pass. The full host suite passes 127
of 128 checks; its existing SIO sector record still expects an older
`platform/altirraos/sio.s` hash. That historical evidence was not rewritten.

Fixed and per-Task bank-zero reservation deltas are both **zero**, retaining
57,232/61,536 loading/runtime bytes including OS for eight slots. Upper-RAM fixed
reservation grows by the explicit 16-byte registry. RAW fixtures use 250
near-image bytes; the unchanged large-read fixture uses 114. No additional heap
allocation wrapper is introduced; existing allocator metadata is unchanged.
RAW root stack maxima are 322/299 bytes raw/optimized; the busiest 1,024-byte
worker slot reaches 316/297, leaving 452/471 bytes above the protected 256-byte
interrupt reserve. Console maxima are 168/148, SIO 162/121 and kernel 337/321.
The standalone full-read caller uses 242/220 bytes and its kernel 325/303.
All stack/domain guards and interrupt reserves remain intact. These are observed
workload maxima, not whole-program stack bounds.

Expanded deterministic race/failure qualification, the resident example and
eight-live-Task SIO coexistence remain slices 5–7. This slice does not claim
those gates or a new throughput qualification.

## Slice 5: ownership, failure and lifetime qualification

The lifetime fixture pauses generated private copies of DOSRAW/DOSCALLS at
opening reservation, final close, discovery removal, reader admission, queued
reply and collected reply boundaries. Production modules contain none of these
pauses. The record identifies both generated module hashes, the probe source
and the actual checkpoint sequence. The test forces real allocation exhaustion,
signal exhaustion, competing Task calls and AbortIO; its accepted-close error
and impossible successful zero-byte read are deliberate private return-value
faults after actual device operations.

The fixture checks context/port/signal rollback, generation/reference/operation
saturation, preserved selections on rejected close, consumed selections on
accepted close error, input-loss reporting and recovery, repeated context cycles,
first-opener Task exit and reuse, and file/NIL/RAW alternation on one reply port.
A completed reply remains queued while another reader is rejected; the same
rejection persists after collection until unbinding releases admission. Stale
notification bits do not create a second collection. Two admitted writers retain
whole-request order, checked against terminal cells, and cancelling a write after
source consumption begins returns -1 with the signed causal error. No retry or
false EOF is introduced. Earlier slice-4 allocation/open rollback cases retain
the same production inputs and supplement these tests.

Combined builds exercise filesystem-first and console-first startup; console-only
and headless fixtures cover operation without a mount or console. Separate
misuse cases require fault 4 for application removal with a live stream or direct
console request. Existing filesystem lifetime/retry and direct-console cleanup
regressions are included.

The existing D8 serial responders now run with an open RAW endpoint and a real
DOS Write before each transaction. Both 128- and 256-byte cases preserve their
checksum, device-error, short-input, first-cause, framing and protocol oracles.
Safe shutdown must close/free the stream and restore ownership. Unsafe `$FF93`
shutdown must retain the READY endpoint and allocated console state; that path
is explicitly distinct from successful cleanup.

Fixture bring-up corrected a misspelled private module, reset the public Task
record before slot reuse, and paired direct FIFO injection with a signal to the
console's public Task. Direct FIFO changes alone do not wake a sleeping worker;
its private context pointer is not the public Signal target. The initial dense
2,048-byte writer-order probe passed; the final lifetime matrix uses 256 bytes
with exact cell checks to keep this race test small. Full 70,003-byte output is
already covered by slice 4. No production fix or compiler workaround was needed.

All 22 groups (42 native executions) pass across raw and optimized builds.
Combined bank-1/bank-3 cases execute 170/172 assertions plus three child checks;
console-only cases execute 144 plus three. Their checkpoint sequence is
`1,2,6,5,3,4,3,3`, with six/seven/four created Tasks respectively, including
the three sequential application Task incarnations. The
[lifetime record](../qualification/dos-streams-lifetime.json) preserves the exact
case paths, compiler/image/source hashes, private overrides, fault outcomes,
stack observations and maps. The manifest under
`build/dos-streams-slice5/verified/` combines completed raw/optimized groups and
retains earlier passing case paths without replaying or relabeling their inputs.

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
  python3 tools/test_dos_streams_lifetime_suite.py \
  --compiler-dir build/compiler-ae1f555 --output build/dos-streams-slice5/repeat
python3 tools/dos_streams_lifetime_record.py build/dos-streams-slice5/repeat \
  --output build/dos-streams-slice5/repeat-record.json
python3 -m unittest discover -s tests -p 'test_dos_*.py'
```

Use fresh output paths. Private lifecycle and serial-fault executions retain
240-second/12,000-frame bounds; existing filesystem regressions retain their
600-second/30,000-frame bounds. All 25 DOS host checks pass, including eight
record-validation controls. The full host suite passes 135 of 136 tests, with
the same pre-existing SIO source-hash mismatch described in slice 4. Generated
definitions, document links and diff checks pass.

This slice adds **zero fixed and zero per-Task bank-zero reserved bytes**, no
production upper-RAM reservation and no production allocation. Eight-slot
loading/runtime totals remain 57,232/61,536 including OS. The private fixture
uses 260 near-image bytes and explicitly mapped upper-RAM test storage. Across
all cases, root stack maxima are 330/305 bytes raw/optimized, worker maxima
310/291 and kernel maxima 343/325. The busiest 1,024-byte worker leaves 458/477
bytes above its protected 256-byte reserve. All guards and interrupt reserves
are intact; private pause frames are included in these observations.

## Slice 6: resident DOS streams example

The resident [DOS streams example](../guides/streams-example.md) uses public
Open/Read/Write/Input/Output calls and explicitly owns its handles. Its command
helper borrows the current defaults; temporary file/NIL redirection restores
both selections after a successful copy and an intentional bad-length error.
The captured command error survives selector calls that clear IoErr.

One reader Task performs a single large MyDOS Read and writes its completion
message through its own RAW handle. The parent echoes physical keyboard bytes
through its selected Output. Synchronous Read remains blocked when the separate
reader signals completion; the reader can still write to the display. Typing
`q` lets the parent finish, join the reader and close/release its own context.
The older asynchronous Exec example remains available with its multi-event
wait loop.

The fixture calls the same complete Session function as the resident example.
It adds bounded host rendezvous and independent assertions around that code:
physical `a` during the file read, then completion text before the next keyboard
byte while the parent still has an outstanding Read; physical `q`; verification
of all 70,003 file bytes; exact retained cells and eventual physical display;
joined child, collected requests, closed handles and restored OS ownership.
Both actual resident entry points also package with the pinned compiler. The
standalone NIL example executes unchanged without a console or mount.

All four executions pass: raw/optimized shared RAW sessions and raw/optimized
standalone NIL examples. Both interactive entry points also package successfully.
The [example record](../qualification/dos-streams-example.json) binds the exact
compiler, emulator, sources, images, input schedules and screen hashes. Five
negative controls reject a missing case, truncated file verification, missing
key, reduced live-Task count and touched interrupt reserve. Results are under
`build/dos-streams-slice6/`; short checkpoints retain 240 seconds/12,000 frames
and full-file/completion checkpoints retain 1,800 seconds/30,000 frames. These
are execution bounds, not a console throughput claim.

Bank-zero fixed/per-Task reservation deltas are **zero**, preserving the complete
57,232/61,536-byte loading/runtime maps including OS. The RAW fixture uses 333
near-image bytes and NIL uses 120; no library reservation grows. Five Tasks stay
live at the input/read/completion checkpoints; the NIL example creates no additional Tasks.
RAW root stack maxima are 354/329 bytes raw/optimized; reader maxima are 232/216,
console 168/149, filesystem 187/173, SIO 170/137 and kernel 337/321. The reader's
1,024-byte stack retains 536/552 bytes above the protected 256-byte interrupt
reserve. Every stack/domain guard and reserve remains intact. Generated
definitions, Python compilation, document links and diff checks pass.

## Slice 7: integrated concurrency and timing qualification

The existing eight-Task console harness now also runs public DOS stream clients.
The root owns RAW Input/Output; the reader owns its own RAW Output and makes one
MyDOS Read; the producer uses DOS Write for thirty 40-byte flood requests while
allocating memory, exchanging messages and signalling independent peers. Console,
filesystem and SIO remain the three service Tasks. All eight public Tasks plus
private idle are live at admission and during the read. Streams add no Task.
The fixture shares the resident example's reader and stream setup/cleanup code.

Physical press/release events type eight distinct lowercase characters during
scrolling and disk activity. Markers distinguish raw keyboard capture, worker
reply preparation, return from DOS Read after exact collection/unbinding, and
the client's first observation of the glyph in physical screen RAM. The final
screen must match retained cells and cursor state. Full payload verification,
independent work counters, ownership restoration and collected requests are
required before normal retirement.

The [concurrency record](../qualification/dos-streams-concurrency.json) preserves
the following matrix. Each bank-1 case has a second execution of the identical
image and actual input schedule with passive tracing disabled. Kernel-bank-3
cases provide functional coverage.

| Artifact name | NIR | Media sector bytes | SIO profile | Kernel bank | Verified file bytes |
| --- | --- | ---: | --- | ---: | ---: |
| `target128-raw` | raw | 128 | FASTEST125 | 1 | 777 |
| `target128-opt` | optimized | 128 | FASTEST125 | 1 | 777 |
| `target256-raw` | raw | 256 | FASTEST125 | 1 | 70,003 |
| `target256-opt` | optimized | 256 | FASTEST125 | 1 | 70,003 |
| `stock128-opt` | optimized | 128 | STOCK810 | 1 | 777 |
| `bank3-raw` | raw | 128 | FASTEST125 | 3 | 777 |
| `bank3-opt` | optimized | 128 | FASTEST125 | 3 | 777 |

This is the pinned AltirraOS ROM and console bridge at PAL 14.18758 MHz, with
drive mechanics enabled. It does not qualify physical hardware or a different
emulator/ROM. The large reads take 48.745/48.691 emulated seconds raw/optimized,
or 1,436/1,438 bytes/s measured around the single DOS Read, excluding Open,
verification and cleanup. The 777-byte cases are short-file regressions.

All five timing cases have zero RX/TX deadline misses and zero TX gaps. The
FASTEST125 byte deadline remains 78.942286 microseconds; maximum RX service is
73.867 microseconds and maximum FASTEST125 command-byte refill is 66.537.
Maximum alarm/watchdog lateness is 94.660 microseconds, below the unchanged
100-microsecond gate. Existing phase, collection and next-sector bounds pass.
Separate raw/optimized transport fixtures perform actual sector writes and
readback with concurrent physical input/output; both identical-image replays
pass. Their measured write turnarounds are 1,248.416/1,260.821 microseconds.
Three trace controls deliberately remove a key, delay RX service and corrupt
an actual sector payload byte; each fails its expected oracle.

Endpoint Forbid attribution uses emitted DOSRAW caller PCs and native
Forbid/Permit entries, with no guest instrumentation instructions. Each timed
workload records 103 endpoint intervals: 47 transfers with admission/release
pairs, four intervals across three opens, and five across three closes. IRQs
remain permitted during these intervals. CPU masked
intervals and idle SEI/WAI/CLI intervals are classified separately by the native
idle CLI return PC. A mask overlapping a live transaction is not necessarily
overlapping arriving bytes; the per-byte deadline checks above establish serial
service. No production critical section, baud rate, successful-transfer delay
or acceptance bound changed in this slice.

| Case | Endpoint Forbid max, ms | All Forbid max, ms | CPU masked overlap max, µs | Idle masked overlap max, ms |
| --- | ---: | ---: | ---: | ---: |
| 128 raw | 2.148 | 6.809 | 125.885 | 3.999 |
| 128 optimized | 1.542 | 6.506 | 126.167 | 3.987 |
| 256 raw | 2.680 | 6.889 | 134.131 | 3.996 |
| 256 optimized | 4.812 | 6.636 | 215.118 | 3.962 |
| STOCK810 optimized | 2.800 | 6.508 | 113.902 | 3.975 |

The largest endpoint interval includes asynchronous execution with IRQs enabled;
it is not an IRQ blackout. CPU-mask maxima cover the whole transaction envelope,
including intervals without arriving bytes. Idle maxima include time asleep.

Keyboard latency is separate from the serial IRQ gate. Each row below contains
eight physical keys; values are milliseconds, median / maximum. Collection and
visibility are upper bounds that include scheduling and client observation.

| Case | Capture to collected DOS Read | Capture to observed visible echo |
| --- | ---: | ---: |
| 128 raw | 19.99 / 62.68 | 143.52 / 1,656.76 |
| 128 optimized | 33.92 / 57.83 | 128.34 / 1,695.50 |
| 256 raw | 28.01 / 79.01 | 158.64 / 549.25 |
| 256 optimized | 20.49 / 45.91 | 130.51 / 443.14 |
| STOCK810 optimized | 20.91 / 72.81 | 131.45 / 181.97 |

The short-file echo maximum exceeds the older direct-console baseline. The
trace identifies FIFO output contention: the new reader writes `\nDISK DONE\n`
while keys are still being echoed, causing two scrolls at the bottom row.
For raw key `c`, input is collected at 50.07 ms and the echo enters endpoint
admission at 53.50 ms; the reader releases its completion write at 1,557.36 ms,
then the root releases its echo at 1,613.54 ms. There are 48 display quanta and
27 independent allocation cycles between collection and observed visibility.
The optimized key `d` shows the same ordering, with 54 display quanta and 29
allocation cycles. The 256-byte case finishes its disk read after the eight
keys, so its completion text does not contend with those echoes. This explains
the regression without changing the FIFO or hiding it with a larger test bound.
Improving scrolling responsiveness remains a separate console follow-up.

The fixed overhead fixture writes the same 40 upper-RAM bytes once and then
eight more times through each API, with matching caller helpers and no scrolling.
It separates initial open, first transfer and steady transfers, and replays the
identical image without observers. Times include checks, gateway calls, console
work and scheduling; they are completion costs, not isolated CPU instruction
costs. Open and first transfer each have one sample; steady values are means of
eight samples.

| Stage | Raw direct Exec / DOS, ms | Optimized direct Exec / DOS, ms |
| --- | ---: | ---: |
| Open including owned allocations | 11.25 / 75.96 | 10.40 / 58.82 |
| First 40-byte transfer, including DOS lazy request | 31.73 / 56.95 | 38.85 / 52.65 |
| Steady 40-byte transfer mean | 40.44 / 47.89 | 38.00 / 45.51 |

Additional mean steady completion time is 7.45/7.51 ms raw/optimized. These
small, scheduled samples do not establish a console throughput or responsiveness
guarantee. No production change was needed for this qualification, so the
slice-5 real 128/256-byte fault responders remain applicable: the collector
verifies every recorded library/platform/ABI input still matches, preserving
their distinct normal cleanup and unsafe `$FF93` fail-stop outcomes.

There are 20 new native executions: five observed/replay workload pairs, two
bank-3 functional runs, two transport TX pairs and two fixed-overhead pairs.
The record binds compiler, platform pin, production and fixture sources, images,
maps, results, trace hashes and replay schedules. Reproduce an individual
workload with the table's options, using `--speed 0` for FASTEST125 or `1` for
STOCK810, and `--trace` for the five bank-1 cases:

```sh
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
python3 tools/test_dos_streams_concurrent.py --compiler-dir build/compiler-ae1f555 \
  --case raw --sector-size 256 --speed 0 --bank 1 --trace \
  --output build/dos-streams-slice7/target256-raw
python3 tools/test_dos_streams_overhead.py --compiler-dir build/compiler-ae1f555 \
  --case raw --output build/dos-streams-slice7/overhead-raw-final
PYTHONPATH=tools python3 - <<'PY'
import json
from native_program import ROOT, compiler
from test_console_tx import run
toolchain = compiler(ROOT / 'build/compiler-ae1f555')
for mode in ('raw', 'opt'):
    out = ROOT / 'build/dos-streams-slice7' / ('tx-' + mode)
    result = run(out, mode == 'opt', toolchain)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
PY
python3 tools/test_dos_streams_trace.py --probe build/dos-streams-slice7/target128-raw \
  --output build/dos-streams-slice7/qualified-controls
python3 tools/dos_streams_concurrency_record.py build/dos-streams-slice7 \
  --output build/dos-streams-slice7/repeat-record.json
```

Use a fresh output root for a repeat and run both modes where listed. The
collector requires all seven workload names, `tx-raw`/`tx-opt` from the existing
`tools/test_console_tx.py` fixture, both `overhead-*-final` names and controls.
Short concurrency checkpoints retain 180 host seconds/9,000 guest frames;
completion retains 1,800 seconds/30,000 frames. Overhead uses 240 seconds/12,000
frames. The existing transport fixture retains its own recorded limits.

Fixed and per-Task bank-zero reservation deltas are **zero**. The full eight-slot
maps remain 57,232/61,536 loading/runtime bytes including OS, guards, alignment
and unused capacity, following the
[platform budget](../reference/platform.md#bank-zero-memory-budget).
Concurrency fixtures use 387 near-image bytes. Production
upper-RAM reservations and allocations are unchanged: the complete stream layer
has its 16-byte registry, 104-byte rounded shared endpoint, 16-byte handles,
80-byte client contexts with existing 32-byte ports and lazy 48-byte requests.
Three application clients use the same endpoint and existing console worker;
they are not three additional stream workers. Allocator metadata is unchanged.

Across observed/replay and alternate-bank workloads, stack maxima are:

| Stack | Reserved bytes | Raw touched bytes | Optimized touched bytes |
| --- | ---: | ---: | ---: |
| Root console client | 1,536 | 369 | 349 |
| Console worker | 1,024 | 184 | 159 |
| Reader | 1,024 | 232 | 216 |
| Filesystem worker | 1,024 | 190 | 173 |
| SIO worker | 1,024 | 172 | 134 |
| Allocator/message/writer client | 1,024 | 318 | 291 |
| Signal peer | 1,024 | 78 | 72 |
| Message receiver | 1,024 | 96 | 82 |
| Private idle | 512 | 50 | 54 |
| Kernel | 1,536 | 371 | 321 |

All 256-byte interrupt reserves and stack/domain guards remain intact. The
busiest 1,024-byte worker leaves 450/477 bytes beyond its protected reserve.
TX and fixed-overhead cases remain below these caller/worker/kernel maxima.
These are observed workload costs, not whole-program stack bounds.

All 35 DOS host checks pass, including ten concurrency-record checks. The full
host suite passes 145 of 146 tests; its sole failure remains the historical SIO
sector source-hash mismatch recorded in earlier slices. That evidence was not
rewritten. Generated DOS definitions, Python compilation, local document links
and diff checks pass. No compiler defect or workaround was required.
