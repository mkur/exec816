# DOS console streams implementation plan

Status: complete, 2026-09-22; all seven slices are implemented and qualified. The
[DOS console streams design](../reference/streams.md) defines the public
contract and deliberate Amiga deviations. This plan delivers that contract in
seven executable slices, with a separate commit after each slice.

The result is task-owned RAW:/NIL: FileHandles, DOS Write and task-local standard
input/output. RAW: uses the existing console worker; NIL: completes in the
caller. File operations retain the read-only MyDOS backend. Streams add no Task
and target zero additional fixed or per-Task bank-zero reservation. Resident
commands can use them before the o65 loader exists.

Cooked CON:/CONSOLE:, inherited/shared handles, standard error, public async DOS,
timed readiness, buffered stdio, pipes, writable MyDOS, a complete shell and
multiple windows are outside these seven slices. Keep unsupported behavior
explicit; do not publish successful placeholders or alias CON: to RAW:.

## Baseline and working rules

Use [actionc.json](../../toolchain/actionc.json), currently revision
`ae1f555e77d0ae6caffbfc7453cbf06e3d098bee`, ABI
`action65816.native.v1`, image format 3. The [compiler qualification](../history/compiler-ae1f555-qualification.md)
covers the unchanged physical ABI and existing hosted workload. Use the
[console emulator pin](../../toolchain/altirra-console.json), the recorded AltirraOS
65816 ROM and original [MyDOS fixtures](../../tests/fixtures/mydos/manifest.json).
Record actual compiler, emulator, ROM, image and media hashes with the machine
configuration. Local overrides and any necessary pin changes need explicit
evidence. Compiler defects belong in actionc with focused regressions.

The [console implementation record](../history/console-io-implementation.md) and
[eight-task qualification](../qualification/console-concurrency.json) are the
baseline, not evidence that DOS streams already work. Preserve clean SIO
completion without an OS-service sleep, error recovery and unsafe-bus fail-stop.
Follow the [platform contract](../reference/platform.md) and
[critical-section protocol](../history/kernel-critical-sections.md). Short endpoint
transitions may use IRQ-permitting Forbid; allocation, validation of buffer
extents, copying, rendering and waits must run with scheduling permitted.

For each slice, implement the working behavior, run its relevant checks, update
the status here and record results in `docs/history/dos-console-streams-implementation.md`,
then commit before starting the next major slice. Record commands, limits,
failures, artifact hashes, stack maxima and memory deltas. New paths below are
proposals to create in their owning slices; do not prepopulate passing records.
An unresolved acceptance gate blocks dependent slices.

Execute changed behavior through emitted raw and optimized code. Host tests
cover generation, packaging, maps and result parsers; they do not replace native
execution. Rebuild existing callers when private layouts or imports change.
Keep one current ABI and implementation, without compatibility profiles.

Use one artifact root per slice, such as `build/dos-streams-slice1/`, with named
cases beneath it. Follow the [build cleanup guidance](../history/build-cleanup.md); retain
reproducible qualification evidence without accumulating duplicate toolchains
or full build trees for every retry.

## Sequence and dependencies

| Slice | Executable result | Suggested commit |
| --- | --- | --- |
| 1. Owned-object routing and stack gate | Existing files/locks use a common ownership prefix and retain stack safety | `Prepare DOS object routing for streams` |
| 2. NIL: and destination dispatch | Real null streams, Write and namespace errors work without starting services | `Implement DOS NIL streams and Write dispatch` |
| 3. Standard streams | Input/Output selections and redirection obey task ownership and cleanup | `Implement task-local DOS standard streams` |
| 4. RAW: endpoint and transfers | Multiple owned handles share one device open and perform real keyboard/display I/O | `Implement DOS RAW console streams` |
| 5. Lifetime and race qualification | Failure rollback, competing clients, reply reuse and shutdown pass deterministic tests | `Qualify DOS stream ownership and lifetime` |
| 6. Resident example | Ordinary DOS calls provide console interaction alongside a real MyDOS read | `Add resident DOS streams example` |
| 7. Integrated qualification | Eight live Tasks pass stream, stack and 125 kbaud coexistence gates | `Qualify DOS streams under concurrent SIO` |

Execute in order. Slice 1 checks the complete blocking call chain after object
routing changes; the qualified compiler has removed the earlier eight-byte
headroom constraint, but new dispatcher frames still need measurement. Slices 2–3 establish
dispatch and ownership without hardware dependence. Slice 4 includes working
cleanup and basic failure handling when RAW: becomes available; slice 5 expands
the adversarial coverage rather than introducing its first safe close path.
Slices 6–7 establish end-to-end usability and qualification.

## Repository integration

| Location | Planned work |
| --- | --- |
| `abi/dos.json`, `tools/generate_dos.py`, generated `lib/dos/dos.act` and includes | Add implemented public signatures/constants, retain opaque 24-bit handles and LONGINT results, generate shared definitions and bindings. |
| `lib/dos/doscalls.act`, `lib/dos/dos-implementation.inc` | Classify destinations before filesystem startup; dispatch handles by backend without deepening existing blocking file calls. |
| `lib/fs/fsregistry.act`, `lib/fs/fstypes.act`, filesystem object producers/consumers | Inline the common ownership prefix, validate identity before payload, centralize link/unlink/count rules and preserve filesystem mount lifetime. |
| Proposed `lib/dos/dosstreams.act` and private generated definitions | NIL behavior, RAW endpoint state, transfer preparation/collection, error mapping and standard-stream helpers. Keep the implementation small; no generic VFS framework. |
| `lib/dos/dosclient.act`, `lib/dos/dos-core-types.inc`, `lib/dos/task-dos.inc` | Extend heap context, reuse its reply port and preserve active/busy, object accounting, removal and slot-reuse guards. Keep DosSlot size unchanged. |
| `tools/generate_dos_mounts.py`, `config/dos-mounts.json` | Reject reserved aliases and expose configured-name classification before lazy filesystem startup. |
| `tools/native_program.py`, DOS metadata/map generation | Include new modules in production imports/provenance and explicitly place the upper-RAM endpoint registry relative to the configured kernel bank. |
| `tools/test_dos_*.py`, `tools/test_console_*.py`, `tests/test_dos_*.py` | Extend appropriate existing fixtures/oracles; add focused stream fixtures, lifecycle checkpoints and result validation. |
| Proposed `examples/dos-streams.act`, example documentation and qualification records | Demonstrate ordinary DOS calls, borrowed defaults, cleanup and concurrent disk progress. |

No new Exec Read/Write gateway, per-stream worker, public Task field or use of
tc_UserData is required. Keep the direct DosSlot association. Stream state and
owned-object traversal remain task-side; IRQ delivery still targets the known
console worker directly.

## Memory and stack gates

Compare complete generated maps for loading and runtime, including guards,
padding and unused capacity. The eight-slot bank-zero baseline is
57,232/61,536 bytes including OS. Report both fixed and per-Task reservation
deltas for every slice, including zero; report added near-image bytes separately.
Do not enlarge stacks/DP, reduce task capacity or consume the interrupt reserve
to make a test pass.

| Upper-RAM resource | Design budget to verify |
| --- | --- |
| Endpoint discovery/transition registry | One explicitly mapped 16-byte reservation in the configured kernel bank. |
| Client context | Existing 72-byte allocation expected to become 80 bytes for two selections and one transfer-request pointer. |
| Reusable console transfer request | 42 payload bytes, rounded to 48, allocated only on the first nonempty console transfer per client. |
| NIL/RAW handle | 16–32 rounded bytes per Open, including the inline common prefix. |
| Shared endpoint | At most 128 rounded bytes, including the 42-byte owning request, 27-byte PA_IGNORE port and lifetime state. |

These are planning budgets, not verified layouts. Freeze actual offsets in
generated inputs and compare emitted SIZEOF/field addresses. Report allocation
rounding, heap metadata and any change to filesystem object size. Keep the
16-byte DosSlot and existing per-client reply-port/signal count. Do not place
the registry in presumed spare alignment bytes or hardcode bank 1; test kernel
banks 1 and 3.

The qualified raw reader uses 242 of 1,024 stack bytes, leaving 526 bytes
beyond the protected 256-byte interrupt reserve. Optimized use is 218 bytes,
leaving 550 bytes. These are the integrated workload observations for ae1f555,
not whole-program stack bounds. Measure the complete blocking
call chain after routing changes and again after each new backend. Preparation
helpers must return before a blocking call where needed; merely moving code
into another nested function does not reduce live stack depth. Keep request
records and buffers in upper RAM. Check client, filesystem, console, SIO and
kernel stacks, including transient workers before retirement, with existing
guards and asynchronous-entry coverage. Stop and resolve a failed stack gate
before extending that path.

## Slice 1: owned-object routing and stack gate

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-1-shared-owned-object-routing).

Give file and lock objects a common inline prefix containing next link, owning
DosSlot, object kind and backend tag. Define the private representation once
and update filesystem allocation, lookup, unlink, enumeration and packet-side
validation together. Keep mount/cursor/generation payloads filesystem-specific;
do not add an allocation wrapper around every file.

Move common owner-list identity lookup and accounting into shared DOS code.
Find the candidate in the caller's owned list before reading its payload; then
check kind/backend. Only filesystem objects retain/check mounts. Maintain one
object count/list across future backends and preserve packet ownership and
removal guards. Ensure the worker-side file path and caller-side future stream
path use the same rules.

Prepare destination dispatch without adding a live wrapper frame around
DOSCLIENT.Call/WaitPort. Keep all current file and directory behavior executable;
new public stream functions are not needed in this slice.

**Acceptance:** existing DOS ABI/client/file/directory/lifetime tests pass in
raw and optimized builds. Include mixed file/lock lists, wrong-kind and foreign
identity rejection, mount generation/reference checks, close cleanup and Task
reuse. Repeat the existing single large MyDOS Read through the changed public
path and measure full stack high-water marks with the interrupt reserve intact.
Check generated layouts/provenance and kernel-bank 1/3 maps. A layout-only host
test or small read is insufficient evidence for the stack gate.

**Evidence:** `docs/qualification/dos-streams-routing.json`, recording old/new
object layouts, allocations, stack maxima and reservation deltas.

## Slice 2: NIL: and destination dispatch

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-2-nil-and-destination-dispatch).

Add the real Write import/signature to DOS generation, wrappers and packaging.
Implement owned NIL handles with Open/Read/Write/Close/Seek behavior from the
design. Link them into the same object list as files and locks; they need no
device endpoint, transfer request or filesystem mount.

Classify bounded mapped names before FSBOOT.Ensure and MyDOS component parsing.
Accept case-insensitive NIL: and reserve RAW:/CON:/CONSOLE:. Enforce the
255-byte name bound, suffix errors and reserved mount-alias rejection. Unknown
prefixes must fail before starting FS/SIO. Until slice 4, RAW: remains explicitly
unavailable with ERROR_DEVICE_NOT_MOUNTED; CON:/CONSOLE: return
ERROR_ACTION_NOT_KNOWN throughout this plan.

Move Open-mode checks behind destination classification. NIL: accepts all three
documented modes without reset/truncation behavior; bad stream modes fail with
ERROR_BAD_NUMBER. Preserve MyDOS's rejection of mutating modes. Lock on a stream
name reports wrong type without starting the filesystem.

Validate owned handle, signed length and admitted buffer extent in that order.
NIL Read returns zero; NIL Write returns the full validated length without
payload access. Zero-length Read/Write on valid handles bypass buffer checks
and transfers. File Write returns zero for zero length and write protection for
a valid positive-length operation. Stream Seek fails explicitly. Accepted Close
consumes the handle and successful Close preserves the preceding IoErr.

**Acceptance:** raw/optimized API fixtures exercise all modes, NIL EOF/discard,
zero/negative/32-bit counts, null-positive buffers, bank-crossing extents,
24-bit wrap and invalid memory. Verify payload access is absent for NIL, not
just that its return count is correct. Exercise invalid, foreign and
zero-low-word far handles, mixed file/lock/NIL lists and cleanup. A headless
no-mount build must use NIL: and reject names without creating FS, SIO or
console workers. Check aliases, boundary-length names, missing terminators,
readonly file Write and existing file regressions. Unknown/bad handles must
never fall through to a filesystem payload cast.

**Evidence:** `docs/qualification/dos-streams-nil.json`, including generated
signature checks, namespace/startup observations and exact result/IoErr pairs.

## Slice 3: task-local standard streams

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-3-task-local-standard-streams).

Add Input, Output, SelectInput, SelectOutput and IsInteractive through the
current generated DOS interface. Extend the upper-RAM client context with
input/output selections and the optional transfer-request pointer. Verify its
actual rounded size; keep DosSlot and public Task unchanged.

Getters return null when unset and never allocate, start a service or alter
IoErr. Selectors accept a caller-owned live FileHandle or null, return the old
selection and clear IoErr on success. Failure leaves the old selection intact.
Use borrowed pointers without new references; selecting a file as Output does
not change its write permissions. IsInteractive is false for valid files/NIL:
and clears IoErr; invalid handles report the documented error.

Clear both matching selections before an accepted Close frees its object,
including backend-close failure. Reject an invalid/reentrant close before
consuming anything. Keep active/busy protection consistent during context
initialization, allocation and teardown. ReleaseContext requires no owned
objects, selected streams or outstanding work; it does not close objects for
the caller. Reset all context state before Task-slot reuse.

**Acceptance:** execute unset getters with a sentinel IoErr and unchanged heap,
port/signal and worker counts. Test selection/clear, same handle in both slots,
null previous selection versus failure, foreign/closed/wrong-kind handles,
file-as-Output, nested save/select/restore on success and command failure, and
automatic clearing on accepted Close. Include two Tasks with independent
defaults, ReleaseContext refusal/success and removal/reuse. Verify live object
counts match mixed file/lock/NIL lists. Closed-pointer tests must not claim
protection against arbitrary later reuse of the same opaque pointer address.

**Evidence:** `docs/qualification/dos-streams-defaults.json`, with ownership,
IoErr, allocation and cleanup results in raw/optimized builds.

## Slice 4: shared RAW: endpoint and transfers

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-4-shared-raw-endpoint).

Implement the generated upper-RAM registry and CLOSED/OPENING/READY/CLOSING
transitions. Under short Forbid sections reserve/publish state and generation;
perform allocation and device open/close outside them. Concurrent admission
during OPENING/CLOSING fails with ERROR_OBJECT_IN_USE. Prevent reference and
generation wrap. RAW: requires the configured console; do not add lazy startup.

Allocate one shared endpoint with an embedded, manually initialized PA_IGNORE
port and idle IOStdReq. Use this owning request only for OpenDevice/CloseDevice;
never submit it or give it the first opener's private port. Each successful
RAW Open creates a distinct task-owned handle and takes a reference. Direct
Exec ownership conflicts fail cleanly. All three supported modes share the
existing instance without clearing it on additional opens.

Lazily allocate one reusable transfer IOStdReq per client for nonempty I/O.
Initialize its own Message fields with the client's existing private DOS reply
port; borrow only io_Device/io_Unit from the endpoint. Extend the client busy
protocol across preparation, admission, I/O, exact WaitIO collection and
unbinding. A filesystem packet and console
request must never overlap on that port. Preparation failures unwind ownership
before returning and leave no reply for the next DOS call.

RAW Read submits one CMD_READ and returns its available short prefix. Track
the active reader through terminal reply collection; reject a second reader
with ERROR_OBJECT_IN_USE. Empty input blocks only its caller. Nonempty success
with zero Actual is an internal failure, not EOF. RAW Write submits one CMD_WRITE
for the entire 32-bit length and completes when the device consumes the source,
without an extra DOS spool or a wait for physical redraw. Other clients' writes
remain admissible while a read waits.

Apply common extent validation and zero-length behavior. Map input loss to
ERROR_BUFFER_OVERFLOW (303), preserve other causal device errors and return -1
on any failed transfer even if a prefix committed. No automatic retry, echo,
line editing, ATASCII conversion or Ctrl-C signal is added. Report IsInteractive
true for RAW: and retain unsupported stream Seek.

Include complete basic rollback and last-close cleanup now. Accepted Close
clears selections and consumes its handle. Keep the endpoint while another
handle exists; final close requires zero outstanding operations/replies, clears
discovery safely and releases the embedded owner request/port as part of the
endpoint allocation. ReleaseContext deletes the collected, unbound client
transfer request before its private port and context. The console resident
remains configured after the last stream closes.

**Acceptance:** raw/optimized physical-key fixtures demonstrate a short read
without Return, no automatic echo, Ctrl-C/BREAK as byte 3, and byte-exact output
controls. Check zero-length calls allocate no request and consume no input;
exercise bank crossings and a Write exceeding 65,535 bytes with an independent
expected terminal-state oracle. Verify source-buffer release after collection,
without assuming the same instant of screen visibility. Use two Task-owned RAW
handles to show a pending read, second-reader rejection and concurrent output.
Check missing console, direct Exec conflict, failed allocation/open rollback,
close/reopen and first-opener context release while another handle survives.
Run file packet calls and console I/O alternately on one private port. Repeat
stack/layout/map gates with the real blocking path.

**Evidence:** `docs/qualification/dos-streams-raw.json`, including physical key
schedules, retained output, request/reply identities, resource counts and memory
costs. Direct FIFO injection may supplement fault tests but is not keyboard
qualification.

## Slice 5: ownership, failure and lifetime qualification

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-5-ownership-failure-and-lifetime-qualification).

Add deterministic checkpoints around endpoint reservation/publication, read
admission, device completion/reply collection and final-close discovery removal.
Use focused private test hooks or fixture control, without a public stream
registry or production polling loop. Exercise actual operations between Tasks
rather than relying on probabilistic scheduling to hit a race.

- Fail each allocation and device-open step in first-open and later-open paths;
  include context/port/signal and lazy transfer-request failures. Compare heap,
  object counts, references, selections and ownership against the pre-call
  checkpoint. Exercise reference/generation saturation without wrapping.
- Make a second Open collide with OPENING/CLOSING and make an opener fail after
  reserving state. No caller may observe a half-built or freed endpoint. Retry
  after rollback and verify a usable first open.
- Let the first opener close its handle, ReleaseContext and exit while another
  Task reads/writes through its own handle. Close a third handle during a pending
  read without aborting that reader. Test simultaneous writers' whole-request
  FIFO order and release of reader admission only after terminal collection.
- Alternate file packet, RAW read/write and NIL operations on one private port.
  Inject stale notification bits and early replies. Check exactly one collection,
  an empty reply queue and an unbound idle transfer request before reuse.
  Cover device-level completion/cancellation races without adding DOS AbortIO.
- Force input loss, partial completion errors and recovery. Check -1 plus the
  causal IoErr, including sign extension, no false EOF and no silent retry.
  Distinguish rejection before Close acceptance from an accepted close error:
  only the latter consumes the handle and clears selections.
- Test clean-input final-close/reopen, repeated context cycles, refused context
  release/removal while objects or operations are live, and clean Task-slot reuse.
  Include console-only, combined and headless builds and both service startup
  orders. Count zero extra resident Tasks or per-client reply ports/signals;
  account separately for the endpoint's one embedded PA_IGNORE port.

Verify normal final application retirement restores display/hardware and frees
endpoint/client state. Keep the existing unsafe-SIO oracle: `$FF93` parks before
ordinary console/heap teardown. Capture independent resource checkpoints for
safe stream cleanup and unsafe fail-stop; the unsafe path must not be reported
as normal cleanup. Use the pinned [128-byte](../../toolchain/altirra-sio-queued.json)
and [256-byte](../../toolchain/altirra-sio-sectors.json) fault responders for transport
recovery cases, preserving their existing causal error and teardown assertions.

**Acceptance:** all cases terminate within preset bounds or reach their exact
expected fail-stop. Raw/optimized executions retain stack/domain guards and
balanced ownership in kernel banks 1 and 3. Expected failures require exact
results and resource-state checks, not just a nonzero exit. Existing direct
console and filesystem clients still pass their relevant lifetime regressions.

**Evidence:** `docs/qualification/dos-streams-lifetime.json`, with checkpoint
schedules, fault coverage and per-case cleanup/fail-stop results.

## Slice 6: resident DOS streams example

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-6-resident-dos-streams-example).

Add a small resident example that opens RAW:, selects the same handle as Input
and Output, then echoes with Read(Input(), ...) and Write(Output(), ...).
Keep echo/editor behavior in the application. A second application Task performs
a real single large MyDOS Read and writes a completion message through its own
RAW handle while the first waits for input. Close each Task's owned handles,
restore borrowed selections where appropriate and ReleaseContext explicitly.

Demonstrate a small command routine that borrows its defaults, plus temporary
file input/NIL output using save/select/run/restore on success and failure.
Provide a bounded test exit and cleanup protocol: synchronous Read cannot also
wait for an unrelated completion signal. Do not promise that a blocked shell
Task notices disk completion before another key arrives. Keep the existing
asynchronous Exec-I/O example; replacing its wait loop with synchronous Read
would change that behavior.

Document build/run commands, console enablement, physical-key expectations,
RAW short-read/no-echo semantics, source-buffer versus display completion and
the absence of CON:, shell parsing and o65 loading. Report actual task/heap and
stack costs rather than counting new application clients as stream workers.

**Acceptance:** the example runs in raw and optimized configurations; a pending
keyboard Read does not stop file progress or the second client's output. Verify
the MyDOS payload and result length, returned keyboard bytes, selected-stream
restoration and complete resource cleanup. Observe retained state and eventual
screen output with preset bounds. The no-mount/headless NIL example also works.

**Evidence:** `docs/qualification/dos-streams-example.json` and
`docs/guides/streams-example.md`, with commands and measured limitations.

## Slice 7: integrated concurrency and timing qualification

Status: complete; [implementation and evidence](../history/dos-console-streams-implementation.md#slice-7-integrated-concurrency-and-timing-qualification).

Extend the existing console/DOS concurrency harness with public DOS stream
clients. Keep eight simultaneously live public Tasks plus private idle, physical
typing, sustained console writes, a single large MyDOS Read and independent
memory/message/signal work. Use markers/counters to prove overlap and stream
routing rather than just completion of a sequential workload.

Run raw and optimized FASTEST125 cases for both 128- and 256-byte media, with
functional coverage in kernel banks 1 and 3. Retain the established bank-1
timing matrix and STOCK810 regression scope. The 256-byte fixture must verify
the complete 70,003-byte file; the 128-byte fixture's 777-byte short result is
not evidence of a 70,003-byte transfer. Preserve checksums and actual lengths.

Use physical press/release events and record their schedule. For each timing
case, replay the identical image and input schedule with passive observers
disabled. Preserve the FASTEST125 byte deadline (about 78.9423 microseconds),
zero RX/TX deadline misses or TX gaps, and the 100-microsecond alarm/watchdog
limit. Keep existing phase and bounded-completion checks. Maintain TX coverage
through the existing transport fixture; MyDOS Read alone does not exercise
sector payload transmission.

Measure endpoint Forbid duration and active interrupt-masked intervals
separately. Idle SEI/WAI time is not CPU work delaying a pending byte; whole-run
masked maxima alone do not establish serial failure or success. Do not add a
successful-transfer sleep, lower the baud target or relax bounds to pass.
Retain negative controls that make the timing/result oracle fail when a known
deadline or payload error is introduced.

Measure additional DOS call cost with a small fixed direct-Exec versus DOS
comparison on the same console workload, separating first-open/allocation cost
from steady-state transfer/collection. Report keyboard-to-reply and visible-echo
latency separately from serial IRQ service. The existing heavy-scroll baseline
can approach one second of visible-echo delay; streams do not automatically fix
it. Set workload/completion bounds before runs and investigate any regression
rather than silently retuning the oracle. This is a focused overhead check,
not a new benchmark framework or a cooked-console responsiveness claim.

**Acceptance:** payloads, stream results, default ownership, exact reply
collection, all stack/domain guards and 256-byte interrupt reserves pass.
Compare full bank-zero maps and upper-RAM allocations against the budgets;
record zero fixed/per-Task bank-zero growth only if demonstrated. Eight Tasks
must remain live during the measured overlap. Trace/replay outcomes and preset
completion limits must agree. Re-run affected fault-recovery cases if integrated
work changes admission, teardown or transport paths.

**Evidence:** `docs/qualification/dos-streams-concurrency.json`, the implementation
record, updated README/roadmap and relevant platform-budget references. Record
the precise qualified matrix and remaining limitations. Do not describe host
tests, another compiler build or an older console run as stream qualification.

## Completion and follow-ups

Implementation is complete when all seven slice gates pass and their
implementation and evidence commits exist. The design's acceptance groups map
to slices 1–2 (API/routing), 3 (defaults/ownership), 4 (real device I/O), 4–5 (concurrent
ownership), 5–6 (system lifetime) and 7 (eight-task timing), with stack and
memory checks throughout.

The next console stages need separate designs/qualification: cooked CON: line
discipline and reachable EOF/break behavior; process-owned inheritance and
duplication; non-consuming timed readiness/asynchronous DOS; and independent
windows/focus. Preserve the endpoint/instance boundary for those stages without
adding their machinery or changing this milestone's RAW: contract.
