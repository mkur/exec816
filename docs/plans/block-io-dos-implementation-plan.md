# Block I/O and MyDOS implementation plan

Status: all ten slices complete, 2026-09-20. The
[design note](../reference/dos.md) defines the interfaces, MyDOS interpretation,
ownership rules and deliberate differences from AmigaDOS. This plan turns that
contract into ten executable slices, with validation and a separate commit after
each slice. Filesystem writes are outside this plan.

Deliver a native, read-only MyDOS handler over the existing queued `sio.device`,
including subdirectories, 128/256-byte sectors, both file-link formats and the
Amiga-style file/directory calls. Complete the milestone with eight live public
tasks, 125-kbaud traffic and measured stack/memory costs on the pinned emulator.
Physical hardware remains a separate qualification target.

## Baseline and working rules

The [device implementation](../history/device-io-sio-implementation.md) and
[concurrent qualification](../qualification/sio-concurrency.json) establish the
current 128-byte SIO path. They do not qualify 256-byte payloads or filesystem
work. Run the transport extension first so a missing prerequisite is discovered
before building the complete DOS layer.

Follow the [platform contract](../reference/platform.md),
[IRQ-permitting policy protocol](../history/kernel-critical-sections.md) and
[bank-zero rule](../reference/platform.md#bank-zero-memory-budget). Preserve COP
`$50`/`$00` routing, full native context and the one current Task API. DOS parsing,
copying and waiting execute in ordinary task context with IRQs and scheduling
enabled. No filesystem work enters an IRQ or a long kernel critical section.

Use [toolchain/actionc.json](../../toolchain/actionc.json), currently compiler
`c2268b7c742958bd9078c4e11ef9b10f3b7a0221` (bundled parser correction), and the recorded native ABI. Begin
with the [queued SIO machine/peripheral pin](../../toolchain/altirra-sio-queued.json).
Record new profile evidence and local overrides explicitly. Compiler defects
belong in actionc with focused regressions and a recorded pin update; do not add
routine-specific compiler workarounds here. Emulator fixes belong upstream too.

Keep filesystem state in upper RAM. The target is **zero additional bank-zero
reservation**, fixed or per context. One filesystem worker consumes an existing
public task slot; one SIO worker continues to serve all units. Do not allocate
a task per drive, file or request. Static service Task records must use storage
admitted by the current Task contract; allocating a record on the heap alone
does not establish task-entry or storage eligibility.

After each slice, update its status here and add an implementation-record entry
with commands, outcomes, artifact hashes and storage accounting. Commit only
after its required checks pass. Keep test-only handlers, block backends, fault
injection and private worker entry points unavailable to ordinary applications.
Do not retain parallel API versions or successful production stubs.

## Sequence and dependencies

| Slice | Executable result | Suggested commit |
| --- | --- | --- |
| 1. 256-byte transport | Real short-boot and double-density reads through the queued driver | `Qualify 256-byte SIO reads` |
| 2. Native DOS contract | Generated call shapes, records and signed results pass ABI probes | `Define native DOS and packet ABI` |
| 3. Client contexts and packets | Task-local errors and synchronous request/reply pass with a test handler | `Implement DOS client contexts and packet delivery` |
| 4. Sector adapter | Checked geometry and complete-sector reads work over SIO and a test backend | `Implement the SIO block adapter` |
| 5. MyDOS metadata | VTOC, directories and path resolution execute against independent images | `Implement MyDOS volume and directory parsing` |
| 6. File chains | Bounded reads, exact sizes and seeks execute in the parser | `Implement MyDOS file traversal and seeking` |
| 7. File API and worker | Open/Read/Seek/Close work end to end in an opt-in system fixture | `Implement the MyDOS file handler` |
| 8. Directory API | Lock/UnLock/Examine/ExNext work through DOS packets | `Implement MyDOS directory access` |
| 9. Mount and service lifetime | Rollback, unmount, offline cleanup and shutdown are complete; enable ordinary DOS use | `Complete DOS mount and service lifetime` |
| 10. Integrated qualification | Full eight-task filesystem workloads meet functional/timing requirements | `Qualify MyDOS under concurrent kernel work` |

Execute in this order by default. Slice 3 requires slice 2; slice 4 requires the
transport gate for its real-SIO acceptance. Slice 5 requires the adapter test
boundary; slice 6 extends its parser. Slice 7 joins slices 3, 4 and 6; the
remaining slices follow in order. If slice 1 exposes a transport defect, ABI and
parser work may continue against explicit test backends, but the transport gate
remains open and slices 7–10 cannot claim full acceptance.

Before slice 9, DOS filesystem entry points run only in explicitly enabled
fixtures. Ordinary builds must reject unavailable functionality, not publish a
mount whose recovery or shutdown behavior is unfinished. The existing public
128-byte `sio.device` remains available throughout. Slice 9 enables the completed
read-only interface; slice 10 establishes its integrated qualification.

## Repository integration

New paths below are proposed and should be created only in their owning slices.
Keep public definitions separate from private handler/platform details.

| Location | Work |
| --- | --- |
| `abi/dos.json`, `tools/generate_dos.py`, `lib/dos/dos-types.inc` | Native records, constants, call/result shapes and generated declarations; stale-output checks. |
| `lib/dos/dos.act`, `lib/dos/dosclient.act` | Public wrappers, client-side validation, task-local errors and packet collection on caller stacks. |
| `lib/dos/task-dos.inc`, `platform/altirraos/dos.s` | Only the small private current-context and mount-reference operations that need guarded kernel access. |
| `lib/io/blockio.act`, `lib/mydos/mydos.act`, `lib/mydoshandler.act` | Sector adapter, independently testable parser, and single filesystem worker. |
| `tools/generate_dos_mounts.py`, `config/dos-mounts.json` | Checked opt-in mount configuration and generated upper-RAM descriptors; no implicit production mount of test media. |
| [taskpolicy.act](../../lib/exec/taskpolicy.act), [tasks.json](../../abi/tasks.json), [generate_tasks.py](../../tools/generate_tasks.py) | Current-context association, admission/reuse initialization, private service selectors and worker-entry exclusion. |
| [native_program.py](../../tools/native_program.py), [task_capacity.py](../../tools/task_capacity.py), [banked_image.py](../../tools/banked_image.py) | DOS module packaging, service startup/shutdown, generated upper-memory extents and heap/image overlap checks. |
| [siodriver.act](../../lib/io/siodriver.act), [sio.s](../../platform/altirraos/sio.s), [sio.json](../../abi/sio.json) | Profile-limited 256-byte READ support, if required by the transport gate; preserve existing 128-byte admission and recovery. |
| `tests/fixtures/mydos/manifest.json`, `tools/mydos_fixtures.py` | Original-MyDOS fixture provenance, container decoding, expected files and deterministic corruptions. |
| `tests/programs/dos_*`, `tests/programs/mydos_*`, `tests/programs/block_*` | Raw/optimized emitted-code probes and hosted integration programs. |
| `tools/test_sio_sectors.py`, `tools/test_dos_abi.py`, `tools/test_dos_client.py`, `tools/test_block_io.py`, `tools/test_mydos.py`, `tools/test_dos.py`, `tools/test_dos_concurrent.py` | Executable slice suites reusing the existing builder, machine, memory and passive observer harnesses. |
| `tests/test_dos_package.py`, `tests/test_mydos_fixtures.py` | ABI/generation, packaging, configuration and fixture integrity checks. |
| `examples/dos-read.act`, `examples/dos-directory.act` | Ordinary public read/seek and directory examples after publication. |
| `docs/history/block-io-dos-implementation.md`, `docs/qualification/dos-*.json`, `docs/qualification/mydos-*.json`, `docs/qualification/block-io.json`, `docs/qualification/sio-sectors.json` | Implementation findings and per-slice reproducible evidence. |

The existing Task builder creates its own modules and validates import result
shapes. Updating a library source file alone is insufficient: include DOS in
that path and qualify LONGINT results, not just pointer/CARD returns. Only short
private operations need gateway bindings; Open/Read/Seek and packet waits must
not run as suspended shared-kernel activations.

## Slice 1: qualify 256-byte sector reads

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-1-256-byte-transport).

Use the existing driver, worker and IRQ engine in a small program before adding
DOS. Select and pin an emulated drive model that actually supports 256-byte data
sectors at the target rate. Extend a compatible timing profile or add one with
explicit length/command admission. Do not raise the stock 810 limit or silently
turn the no-data Happy profile into a sector-transfer profile.

Read sectors 1–3 as 128 bytes and sector 4 onward as 256 bytes from the same
configured disk. Exercise nontrivial full-sector patterns and buffers spanning
an upper-bank boundary. Audit every length/counter/checksum path for the value
256, including final-byte retirement, caller-buffer release and io_Actual.
Start with one client plus the SIO worker, then use the existing concurrent
harness for four/eight public tasks before declaring the profile qualified.

Pin exact ROM/emulator binaries, disk model, geometry, image hashes, command/data
rates and timeout limits. Keep serial acceleration off. Distinguish currently
implemented profile limits from historical disposable-probe limits in older
records; reconcile the new pin with the actual driver admission rules.

**Acceptance:** raw/optimized queued reads return exactly the expected sector
bytes; sector 3/4 changes length correctly; rejected lengths/profiles never reach
the wire. Cover checksum failure, short/extra data, timeout and cancellation with
one collected reply and no retained caller pointer. RX and phase timing meet
the selected profile's 125-kbaud deadlines, including alarm coincidences, with
identical-image uninstrumented replay. Existing 128-byte READ/PUT, stock timeout
and Happy no-data behavior remain correct; do not expand write support merely
because READ now accepts 256 bytes.

**Evidence:** `docs/qualification/sio-sectors.json`, the profile pin and the
first implementation-record entry. Record failed experiments rather than
relaxing the deadline to make them pass. A host-backed parser read is not a
substitute for this gate.

## Slice 2: native DOS records and call ABI

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-2-native-dos-contract).

Generate the nine design-note calls plus the native `ReleaseContext` extension.
Keep `DOS` separate from `EXEC`, native 24-bit FileHandle/FileLock pointers,
LONGINT counts/results/offsets, classic modes/action numbers and DOSFALSE/DOSTRUE.
Define native FileInfoBlock/DateStamp and the private DosPacket/StandardPacket,
including Message links and all seven 32-bit argument slots. Keep handle/lock
internals opaque; do not expose a mount or execution-slot index as a file handle.

Confirm the actual compiler layout before recording sizes/offsets. Generate
symbolic DOS errors, exact result conventions and pointer-slot encoding checks.
Reserve collision-free private service selectors only where needed. No BPTR
shifts, BSTRs, assumed 68000 padding or new public Task fields are introduced.
Unavailable ordinary imports must reject; any ABI stubs are test-only.

**Acceptance:** raw/optimized emitted probes cover every field, array stride,
call argument and return width, including -1, negative seek offsets, zero,
values above 65,535, and pointer results whose low word is zero. Check records
and arguments crossing banks, adjacent canaries and rejection of nonzero top
bytes in pointer argument slots. Generator/package checks detect stale output,
selector collisions and accidental successful production stubs.

**Evidence:** `docs/qualification/dos-abi.json`, with emitted layout, call-shape
and image/compiler hashes. Host arithmetic describing a layout does not replace
the executable probe.

## Slice 3: task-local DOS state and packet delivery

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-3-client-contexts-and-packets).

Implement the upper-RAM current-context association and error cell, sized for
the configured task capacity. Reset association/error state at admission/reuse;
look up the calling context directly. Preserve `tc_UserData` and public Task
layout. IoErr must work without allocating a port or heap object, including
reporting a failed first client initialization.

Lazily allocate the client context, private reply port and reusable packet for
calls that need a handler. Add one synchronous request/collection path with
matching Message/packet links, stable dp_Port, one outstanding call and exact
packet identity checking. Reject unsupported calling contexts before publication.
Keep all allocations and waits outside guarded kernel policy.

Use a test handler to exercise immediate replies, delayed replies and explicit
errors. Implement ReleaseContext and partial-initialization rollback now; do not
postpone ownership foundations until the filesystem exists. Release refuses
while a packet or owned object remains live, and succeeds harmlessly without
a context. Successful Close-style completion preserves the prior IoErr.

**Acceptance:** two tasks hold different errors/results while preempting each
other; stale signals and a reply before the sender starts waiting do not cause
lost wakes or duplicate collection. Unrelated Exec I/O replies remain untouched.
Inject failure at each allocation/signal step, recover original resource totals,
and repeat more than 255 properly released task lifetimes without inheriting
old context state. A returned packet may be reused immediately without a handler
read-after-reply. Externally removing a task with live DOS resources remains
unsupported, not a new cancellation service.

**Evidence:** `docs/qualification/dos-client.json`; raw/optimized execution plus
focused Task, signal, message-port and allocator regressions for changed hooks.

## Slice 4: checked block adapter

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-4-checked-sector-adapter).

Implement the design's sector-size and ReadSector operations over an immutable
descriptor: unit, profile, sector count, data-sector size, boot layout and mount
generation. Validate full-width values before narrowing to Aux1/Aux2; distinguish
generic block bounds from the MyDOS minimum volume extent. A byte-reader helper
is optional and must not become a prerequisite for a sector-chain filesystem.

Retain one owning open request per unit and one reusable transfer request that
borrows the selected binding. Allocate the 256-byte scratch buffer in upper RAM.
Require zero io_Error and exact io_Actual; errors have zero valid sector bytes.
Collect each transfer before rebinding/reusing/freeing anything. Cache keys must
include mount identity/generation and sector number. Geometry is immutable within
that identity, validated before attachment and changed only by detach/reattach;
it does not need a separate cache snapshot or comparison on each request.

Provide an explicit test backend with the same sector-operation contract for
parser tests and controlled failures. It supplies sector bytes, not an alternative
filesystem implementation. Container headers/offsets belong to host fixture code;
the guest adapter never interprets an ATR header. Real mounts use SIO only.

**Acceptance:** emitted raw/optimized tests cover sector zero, first/last/outside
range, sector 3/4, high auxiliary bytes, `$FFFF` increment/overflow, both sizes,
undersized buffers, address wrap, bank crossings, failed/short completion and
two units with separate owning opens. Compare real 128/256-byte reads with the
host image's expected sectors. Failed reads never yield a valid cache entry;
binding/resource rollback leaves no leaks. Closing an owner is forbidden while
its borrowed transfer remains outstanding.

**Evidence:** `docs/qualification/block-io.json`, distinguishing backend tests
from actual wire transfers and preserving the slice-1 timing profile limits.

## Slice 5: MyDOS metadata, directories and path lookup

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-5-mydos-metadata-and-paths).

Build the parser in Action! against the sector-operation boundary. Acquire
small valid images produced by a pinned original MyDOS version, with source
provenance, hashes, geometry and independently extracted expected contents.
Follow the source/archive reference in the design note; fixture expectations
must not come solely from a host clone of the new parser. Normalize host text
line endings when reading fixture metadata, but preserve disk and ATASCII bytes.

Validate the VTOC marker/header and descending reserved extent using 32-bit
arithmetic. Explicit mount geometry is authoritative; do not discover capacity
from VTOC free counts, require bootable media or probe density with mismatched
wire lengths. Decode the eight-sector/64-entry directory layout on both sector
sizes, including standalone directory flags, deleted/unclosed entries and
per-file link-mode metadata.

Resolve mount-relative paths iteratively with the design's component/path/depth
bounds, stored-name rules, exact-before-folded lookup and ambiguity detection.
Validate subdirectory count/extent and ancestor overlap. Keep directory-entry
ordinal separate from physical sector address for later ten-bit file checks.
Record descriptor/cursor storage explicitly in upper RAM.

**Acceptance:** raw/optimized parser code recognizes nonbootable MyDOS, root and
nested directories, all 64 entries, empty/end/deleted entries, protected entries,
mixed link flags, single/extended VTOCs and both sector sizes. The upper half of
a 256-byte directory sector must never become extra entries. Reject malformed
names/flags, overlong paths, excessive depth, repeated/overlapping ancestors,
bad extents and unsupported formats without out-of-range I/O. Cover exact and
ambiguous folded names, absent components and file-in-place-of-directory errors.
Include large-geometry metadata near the sixteen-bit sector limit.

**Evidence:** `docs/qualification/mydos-metadata.json` and the fixture manifest.
The parser can now find entries; no public file API or general disk repair is
claimed by this slice.

## Slice 6: bounded file chains, reads and seeks

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-6-bounded-file-chains-reads-and-seeks).

Implement the file cursor and trailer decoder, selecting ten-/sixteen-bit links
from each file's entry. Decode high-byte-first chain links independently of
little-endian directory fields. In ten-bit mode validate the parent-directory
entry number. Strip three-byte trailers and copy only validated payload bytes.

Track logical position, derived sector/offset, traversal state and any known
exact size. Maintain hop/cycle detection across successive short reads. Support
canonical empty entries, empty terminal sectors, partial terminal payloads and
EOF/count consistency. Restart bounded walks for backward seeks; derive exact
EOF by traversal when required. Check overflow before updating position.

Implement the design's failure transaction: an unsuccessful Read/Seek retains
the starting logical position and invalidates any derived cursor that cannot be
restored cheaply. Read returns -1 even if a prefix was copied; that call's buffer
is unspecified. Only normal EOF produces a successful short read. Do not eagerly
traverse an entire large file on Open, or reset cycle detection at every API call.

**Acceptance:** compare byte-for-byte results and seek outcomes with independently
known files, including fragmented chains, 125/253-byte payload boundaries, both
link modes on one disk, file lengths above 65,535, positions/links above 32767,
bank-crossing output and unchanged ATASCII. Exercise all seek origins, exact EOF,
zero/negative lengths, signed overflow and past-EOF rejection. Inject cyclic
chains, wrong file IDs, bad counts, metadata links and late sector errors. Prove
bounded failure across repeated one-byte reads and correct logical rollback.
Do not advertise global cross-link detection or repair.

**Evidence:** `docs/qualification/mydos-files.json`, with raw/optimized machine
code and explicit hop/read bounds for damaged-image cases. Use sparse test
backends for limit cases that do not have a qualified physical geometry.

## Slice 7: filesystem worker and file API

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-7-filesystem-worker-and-file-api).

Admit one private filesystem worker from the existing pool and initialize its
upper-RAM state. Wire per-mount request ports, shared arrival signal and a distinct
SIO reply port. Integrate packaging and entry binding so private helpers cannot
be admitted as arbitrary application tasks. Use the parser and block adapter
from earlier slices; do not fork them for the hosted handler.

Implement Open/Read/Seek/Close packets through the same DOS client path tested
in slice 3. Open performs bounded path lookup and produces a task-owned handle;
each open has its own cursor even for the same file. Reject directories opened
as files, unsupported modes and invalid pointer/length extents before changing
state. Root-relative lock arguments remain zero in this absolute-path subset.

Implement the minimum mount-reference and object-lifetime machinery required
for correct file use now: lookup acquires a transient reference before exposing
the port, successful Open transfers ownership to a handle, and Close releases
it exactly once. A lookup paused before PutMsg must keep its destination alive.
Replies transfer ownership only when collected; never access the packet after
ReplyMsg. Initialize all failure results, including failed Open handle storage.

Start with an opt-in mount list and diagnostic system fixture. The worker serves
one complete DOS operation at a time and waits through SendIO/WaitIO. Check mount
queues fairly between operations and document the resulting long-operation
queue latency. No sector-by-sector handler scheduler is required in this slice.

**Acceptance:** raw/optimized applications open a nested file on real 128/256-byte
MyDOS media, read across boundaries, seek and close. Two clients retain distinct
cursors and IoErr values while a compute task progresses during SIO waits.
Test missing files, wrong types, read-only mode errors, allocation failure,
immediate reply/reuse and valid pointer values with zero low words. Resource
totals return after close/context release, and the media image is unchanged.

**Evidence:** `docs/qualification/dos-files.json`. Handler entry points and mount
configuration remain opt-in until the complete service lifetime passes slice 9.

## Slice 8: locks and directory enumeration

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-8-locks-and-directory-enumeration).

Implement Lock/UnLock/Examine/ExNext and their packet actions using the same
mount lifetime and error path. Support task-owned shared locks only, real locks
for metadata calls and independent enumeration through each lock/info pair.
ExNext requires the state initialized by Examine; end of enumeration returns
zero with ERROR_NO_MORE_ENTRIES, distinct from a failed sector read.

Fill native FileInfoBlock fields as specified: stored names/case, exact file
size, occupied sectors, file/directory types, protection and absent metadata.
Compute file size with the bounded chain walker, keeping directory enumeration
state intact while the shared sector buffer is reused. Avoid placing the full
FileInfoBlock or directory arrays on a small task stack. Unsupported exclusive
locks and namespace mutations must fail explicitly without wire writes.

**Acceptance:** raw/optimized enumeration covers root/subdirectories, all 64
entries, both sector sizes, interleaved client enumerations, recursive traversal
using separate lock/info pairs, empty directories and a corrupt entry/chain.
Verify exact metadata against the fixture oracle, correct end/error distinction,
null UnLock, wrong owner/type rejection where defined, and reference cleanup.
Confirm stored file protection is distinct from the mount's read-only policy.

**Evidence:** `docs/qualification/dos-directories.json`. All nine requested DOS
calls and ReleaseContext now execute in the opt-in system configuration.

## Slice 9: mount rollback, media errors and orderly shutdown

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-9-mount-and-service-lifetime).

Complete static mount configuration validation: unique aliases/units, explicit
geometry, MYDOS type, qualified profile and supported boot layout. Initialize
the worker, buffers, ports and owning device requests before publication, then
validate disk metadata. A failed mount has no discoverable partial entry.
Retain direct transient-reference accounting across lookup/publication races.

Implement busy unmount without changing publication when handles, locks or
transient packets remain. Idle unmount removes discovery atomically before
teardown. Assign fresh mount generations, clear caches on unmount/transport
failure, and never redirect a retained reference to replacement media. Keep
stable-media/no-raw-writes-while-mounted restrictions explicit in examples.

Exercise bus-offline propagation across all SIO-backed mounts. Preserve the
first transport error, collect accepted requests, fail pending work without
further wire transfers, and permit Close/UnLock/ReleaseContext on unavailable
media. Do not clear the driver's reset-required latch by remounting, silently
retry, or return through unsafe ROM SIO ownership.

Coordinate normal system shutdown with the existing resident SIO worker:
stop new opens/locks, settle accepted packets, let clients release their
objects/contexts, unpublish mounts, close owning device opens and terminate
the filesystem worker before the SIO service can be retired. Update the
last-application/worker bookkeeping so an idle filesystem task does not keep
the system alive forever, and so SIO cannot stop with DOS requests still live.
Retain explicit caller cleanup; this is not automatic reclamation for forcibly
removed tasks. Reject or fault detected misuse instead of freeing live storage.

**Acceptance:** raw/optimized tests inject failure at every startup allocation,
signal, task admission, device open and metadata read; original counts and guards
are restored. Test full task capacity, duplicate mount configuration, lookup
paused before PutMsg, busy unmount, unmount/remount generation, safe read errors,
unsafe bus-offline recovery, queued clients during failure and normal shutdown.
All accepted packets receive one collected reply; no worker/port/buffer or open
binding is freed early. On an unsafe SIO shutdown, preserve the existing
reset-required platform outcome rather than claiming a normal ROM return.

**Evidence:** `docs/qualification/dos-lifetime.json`. Enable ordinary DOS
packaging only after these cases pass, add the two public examples, and document
how to supply an explicit mount list. Builds without DOS mounts should not
consume a filesystem task or create client ports eagerly.

## Slice 10: concurrent filesystem qualification

Complete: [implementation and evidence](../history/block-io-dos-implementation.md#slice-10-concurrent-filesystem-qualification).

Build a full eight-task workload: root/coordinator, SIO worker, filesystem
worker and five application tasks. Include multiple DOS readers/enumerators and
compute, signal/port and allocator activity. Prove all eight are simultaneously
live, including waiting clients; sequential slot reuse is not capacity evidence.
Use both sector sizes, multiple mounted units, short cached reads and longer
fragmented reads/seeks. The latter deliberately expose handler queue latency.

Run raw/optimized builds at kernel banks 1 and 3. The minimum matrix is full
functional and observed 125-kbaud timing at bank 1 for both sizes and four/eight
tasks, plus functional bank-3 coverage for both sizes and capacities. Include
stock-speed 128-byte regression cases, faults and retained keyboard/VBI activity.
Every timing-observed successful image also runs unchanged without the observer.
If timing is not measured for a placement, label that placement functional-only.

Define byte/phase deadlines, alarm/CRITIC bounds and per-workload completion
limits before collecting results. Base the first two on the qualified transport
profile; derive operation bounds from finite fixture paths/chains, sector counts,
driver deadlines, quiet intervals and queued work. Retain a finite host watchdog.
Measure IRQ byte service, terminal-post-to-worker, DOS packet turnaround, queue
wait, total throughput and background progress separately. A slow filesystem
request does not excuse a missed wire deadline; a fast wire does not establish
acceptable file latency.

**Acceptance:** every expected byte/metadata result matches, no missed replies,
lost wakes, allocation leaks or unexpected writes occur, and all relevant stack,
DP, native context and OS guards hold. Rejected mutations must issue no write
command; before/after image hashes also match. Require the actual 256-byte
transport gate and an end-to-end large MyDOS fixture with extended links; label
maximum-sector parser-only tests separately. Report the observed maximum worker
stack use and complete reservation deltas; resolve overflow without discarding
interrupt headroom or silently reducing task capacity.

Run changed-behavior suites and focused regressions for Task lifecycle, Lists,
signals, ports, allocator, generic I/O, SIO profiles/recovery and loader placement.
Once they pass, repeat only for new changes, failures or unresolved concerns.
Package checks and host tests supplement, rather than replace, emitted execution.

**Evidence:** `docs/qualification/dos-concurrency.json`, selected integration
results in `docs/qualification/dos-regressions.json`, and a completed
`docs/history/block-io-dos-implementation.md`. Update README, roadmap and design status
to describe exactly the supported geometries, profiles and API subset.

## Evidence and memory accounting for every slice

Each qualification record must identify source/build revision or patch hash,
compiler/ABI pin, ROM/emulator/profile, fixture hashes, optimization mode, task
capacity, kernel bank, reproducible commands, finite acceptance limits and
pass/fail outcomes. Keep synthetic backend, fault-responder, actual emulated
disk and physical-hardware evidence distinct. Store concise measurements and
artifact hashes rather than unfiltered emulator logs or credentials.

Report fixed, per-mount, per-client and per-open-object upper-RAM costs, including
heap rounding, plus the complete bank-zero reserved map. Count guards, alignment,
unused capacity and loading/runtime differences. The current eight-task baseline
is 61,536 bank-zero bytes at runtime including OS and 57,232 during loading;
each non-root public slot already reserves 1,568 bytes. Using the filesystem
worker consumes one such slot, not a new reservation. Separate active usage
from reserved size and identify any test-only storage.

Use the compile-time kernel bank and final image map for all code/state; update
overlap checks before allowing the heap to own newly occupied extents. Publish
compiler frame costs and measured call-chain/interrupt stack headroom. If the
zero-growth target cannot be met, update the design/budget with measured reasons
and requalify the resulting layout before calling the slice complete.

## Completion boundary

Implementation is complete only when the nine file/directory calls and ReleaseContext
work through ordinary DOS packaging, an application can open/read/seek/close a
nested MyDOS file on actual qualified 128- and 256-byte emulated media, independent
clients can enumerate/read while other tasks run, and mount/error/shutdown and
eight-task timing gates pass. Directory and file contents must agree with
independent original-MyDOS fixtures, including extended links.

Filesystem writes, automatic media changes, public asynchronous DOS packets,
Process/CLI services, physical hardware and 12–16-task capacity remain outside
this completion claim. Do not fold them into an unfinished read-only slice.
