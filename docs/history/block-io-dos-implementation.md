# Block I/O and MyDOS implementation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Status: all ten slices of the
[implementation plan](../plans/block-io-dos-implementation-plan.md) complete, 2026-09-20.
All nine file/directory calls and ReleaseContext are available in ordinary Task
builds with explicit read-only MyDOS mounts.

## Slice 1: 256-byte transport

FASTEST125 now accepts exactly 256 payload bytes for READ command `$52` in
addition to its existing 1–128-byte payload range. Larger writes, intermediate
lengths 129–255, other commands at length 256 and lengths above 256 are rejected
before dispatch. STOCK810 remains limited to 128 bytes and Happy1050 to NONE.
No native IRQ-engine change was needed: its descriptor, remaining-byte counter,
checksum retirement and 24-bit buffer advancement already handle length 256.

The [sector pin](../../toolchain/altirra-sio-sectors.json) records the actual ROM,
ordinary emulator, passive observer, fault responder, drive profiles and timeout
counts. The compiler remains at `e7266982c22527040dfc2a46508be8475581fe8f`, with
no override. The platform is PAL AltirraOS 3.44, 8× 65816, 1 MiB, shadow ROM,
serial acceleration off. FASTEST125 is the emulator's built-in fastest disk
model with double-density ATR media; this is not physical-drive qualification.
A separate test-responder patch extends the existing D8 fault injection to
256 bytes. It does not alter production peripheral timing.

Raw and optimized queued reads return complete expected bytes for sectors
1, 2, 3, 4, 720, 1024, 32768 and 65535 on a 65,535-sector image. Boot sectors
remain 128 bytes; sector 4 switches to 256. The buffer crosses an upper-bank
boundary with adjacent canaries. Eight accepted requests produce eight terminal
posts; all invalid-length/profile/command cases produce none. Image hashes,
caller-pointer retirement, resource ownership and native/OS guards are checked.

Four/eight-task workloads use two units, two queued requests per client, three
read rounds, retained keyboard/VBI activity and concurrent allocator, registry,
port and signal work. Each observed image is replayed unchanged on the ordinary
emulator, requiring identical runtime counters, request ordering and ownership.
At the measured 126.675-kbaud rate the byte deadline is **78.942 µs**.

| Build / live tasks | Max RX service µs | Max command TX refill µs | Max terminal-to-worker ms |
| --- | ---: | ---: | ---: |
| Raw / 4 | 64.282 | 56.387 | 20.343 |
| Raw / 8 | 65.973 | 67.101 | 33.320 |
| Optimized / 4 | 68.229 | 37.216 | 15.344 |
| Optimized / 8 | 69.920 | 75.559 | 21.867 |

These are the initial slice-1 measurements. The linked sector record is refreshed
after later ISR changes; [slice 10](#slice-10-concurrent-filesystem-qualification)
describes the latest refinement and its current evidence.

All observed byte/phase checks pass. Maximum alarm/watchdog lateness is 92.405 µs
against the existing 100-µs bound. The worker latency is intentionally separate
from the byte deadline: the IRQ engine receives the complete payload. Largest
observed conservative CRITIC span is 335.522 ms, below the existing 2.12-s bound.
These are measured maxima for the recorded runs, not worst-case guarantees for
all interrupt alignments. Idle SEI/WAI/CLI intervals remain included in masked
interval statistics; actual arrival-to-service time determines byte acceptance.

Both compiler modes cover queued, preparing, active and terminal cancellation,
absent-device timeout, bad checksum, short and extra responses at length 256.
Safe failures allow a subsequent read; unsafe cases retain the reset-required
latch and expected `$FF93` shutdown. Each accepted request is collected once and
no caller buffer remains armed. Existing 128-byte FASTEST125 READ/PUT, cold stock
810 READ/PUT and Happy NONE regression suites also pass. The generalized
concurrency fixture's 128-byte queued-abort and bus-offline variants pass again
at eight tasks in both modes.

Evidence: [sio-sectors.json](../qualification/sio-sectors.json). Reproduce with:

```sh
python3 tools/test_sio_sectors.py --case raw --suite --output build/dos-slice1/final-raw
python3 tools/test_sio_sectors.py --case opt --suite --output build/dos-slice1/final-opt
python3 tools/sio_sector_record.py --input build/dos-slice1/final-raw/results.json --input build/dos-slice1/final-opt/results.json
python3 -m unittest discover -s tests
python3 tools/generate_io.py --check
```

Each boundary/recovery case is bounded to 12,000 frames and 240 host seconds;
concurrent cases use 30,000 frames and 600 seconds. Full ignored build records
contain emitted images, compiler frames, memory maps and filtered timing data.
The committed evidence keeps hashes and concise measurements. The earlier
[sio-concurrency.json](../qualification/sio-concurrency.json) is explicitly tied to
its original source revision; it does not claim that later code produced those
historical observations.

One initial raw build rejected an oversized validation frame. Moving the
self-contained payload-length predicate into `PayloadLength` brings
`SIOValidate` to a 214-byte fixed frame / 226-byte local stack peak, and the
predicate to a 64-byte frame. This is an ordinary compiler-supported procedure
split; no compiler workaround or pin change is introduced. Both final emitted
modes and their full stack guards pass after that change.

### Storage

**Reserved bank-zero growth is zero**, fixed and per task, including guards,
alignment and unused capacity. Four-task runtime/loading reservations remain
57,968/58,560 bytes including OS; eight-task reservations remain 61,536/57,232.
Each non-root eight-task slot still reserves 1,568 bytes. No additional task,
fixed upper-RAM descriptor, mount or open object is introduced. The existing
native helper retains its 8,192-byte upper reservation and 6,271 active bytes.
Only compiled validation code changes within the generated application image.

The sector-boundary fixture adds 320 guarded upper bytes (256 payload + two
32-byte guards). Concurrent clients allocate two sector buffers (512 payload
bytes each client at double density), with existing request/port accounting;
the diagnostic observation area is 512 upper bytes. These are fixture costs,
not new kernel reservations. All dynamic allocations return to the baseline.

## Slice 2: native DOS contract

[abi/dos.json](../../abi/dos.json) and [generate_dos.py](../../tools/generate_dos.py)
define all nine requested DOS calls plus ReleaseContext, in the separate DOS
namespace. Counts, seek offsets, positions, Boolean results and IoErr use
32-bit LONGINT; handles/locks use native 24-bit pointers. Opaque source tokens
supply distinct pointer types; their one-byte placeholder is not an object
layout or a caller allocation size. DOS owns actual object storage.

The public [types](../../lib/dos/dos-types.inc) follow the classic
[dos.h](https://developer.amigaos3.net/autodocs/include_h/dos/dos.h) field order,
modes and errors. Private [packets](../../lib/dos/dos-packets.inc) have all seven
32-bit argument slots. Native records require two-byte alignment; no BPTR
shifts, BSTRs or 68000 pointer/padding assumptions are carried over.

| Record | Size / alignment | Selected offsets |
| --- | --- | --- |
| DateStamp | 12 / 2 | Days 0, minute 4, tick 8 |
| FileInfoBlock | 260 / 2 | Name 8, size 124, date 132, comment 144, owners 224/226, reserved 228 |
| DosPacket | 46 / 2 | Link 0, port 3, action 6, results 10/14, arguments 18–42 |
| StandardPacket | 62 / 2 | Message 0, DosPacket 16 |

The private pointer-slot validator checks the full 32-bit value before a caller
can narrow it to a pointer, accepting `$00000000` through `$00FFFFFF` and
rejecting all nonzero top bytes. Null remains representable; each later action
must decide whether it accepts null. Selectors 52 and 53 are reserved for short
current-context and mount-reference operations; neither is bound in this slice.
Generated constants reject collisions with gateway, Task, signal, memory, port,
I/O and diagnostic selectors.

Raw and optimized emitted probes cover all fields, record array strides,
adjacent canaries, upper-bank crossings, negative/zero/above-65,535 values and
pointer results with a zero low word. Each mode completes 271 runtime assertions. The compiler's actual public
declaration shapes are checked against the same contract; the largest fixed
frame among the ten test callees is 50 bytes, with complete native stack guards
checked at return. All ten unfinished ordinary
imports reject before publishing an executable; probe callees are local test
routines. Packet and file ABI availability is not a successful filesystem stub.

Evidence: [dos-abi.json](../qualification/dos-abi.json). Reproduce with:

```sh
python3 tools/test_dos_abi.py --output build/dos-slice2/abi --record docs/qualification/dos-abi.json
python3 tools/generate_dos.py --check
python3 -m unittest discover -s tests
```

The diagnostic uses the pinned AltirraOS 3.44 native emulator at the ABI test's
8× clock; this is functional ABI evidence, not new serial timing evidence. Each
execution has a 6,000-frame/180-second bound. Compiler and ROM pins are unchanged.
The prior disposable SIO feasibility record is now tied to its matching source
revision, preserving its measurements when build tooling changes.

**Fixed and per-task bank-zero reservation deltas remain zero**. Full four/eight
runtime/loading maps are unchanged from slice 1. No client, mount, service task
or open object is allocated yet. The probe's four guarded upper-RAM extents use
508 bytes, and its observations/stride arrays use 944 active bytes of the
existing bank-zero near arena; these diagnostic active bytes do not enlarge that reservation. FileInfoBlock
will live in upper RAM in applications, rather than on small worker stacks.

## Slice 3: client contexts and packets

[DOSCLIENT](../../lib/dos/dosclient.act) now implements lazy per-task contexts,
synchronous packet delivery, IoErr and ReleaseContext in explicitly enabled
DOS fixtures. Ordinary builds still reject the unfinished DOS public imports and
the private context helper. No filesystem or mount is published yet.

The [short private accessor](../../platform/altirraos/dos.s) uses the checked native
caller domain and COP `$50`. [Kernel hooks](../../lib/dos/task-dos.inc) index a
configuration-sized upper-RAM table directly from the current private task slot.
Admission initializes its exact Task owner, null context, error zero and activity
flag, including when the same public Task pointer is reused. Public Task layout,
`tc_UserData`, context capacity and DP/stack reservations are unchanged.

IoErr reads the pre-existing error cell without allocation. Ensure allocates a
client containing one reusable StandardPacket, then a private signal reply port.
A one-byte activity flag covers initialization, publication and teardown while
IRQs and scheduling remain enabled. RemTask rejects a live context or an active
initialization/release; this detects misuse, not automatic reclamation. A busy
context is rejected before a second caller could change the retained packet.
Failed initialization unwinds allocations and leaves a reportable IoErr.

Call publishes one packet, uses WaitPort/GetMsg to collect it, and verifies the
exact Message, both links and both stable reply-port fields. Signals alone never
constitute completion. The handler accesses no packet storage after ReplyMsg.
Successful END and context release preserve prior IoErr; release refuses live
objects or an outstanding packet and succeeds harmlessly when no context exists.

Raw/optimized evidence includes two preempting clients with distinct results and
errors, stale signals, delayed replies, immediate packet reuse and a forced
reply-before-WaitPort interleaving. An unrelated Exec reply queue remains intact.
Allocation-result injection covers context and port allocation failures; actual
signal exhaustion covers the final creation step, followed by a successful retry.
All safe cases restore heap totals and signal ownership. A separate workload
performs 260 released lifetimes on the same Task record/slot without inheriting
context or error state. Native probes cover a nonzero DBR, result width, S/D/P
restoration and rejection of I=1, foreign DP, IRQ-depth and switching contexts.
Task removal with a live context faults before returning to the client.

The focused Task reuse, signal-mask, port lifetime, allocator API and generic
I/O queue suites run in both modes. Eight-task 256-byte 125-kbaud traffic also
passes with the passive observer and unchanged-image replay. Maximum RX service
was 63.72 µs raw / 69.36 µs optimized against the 78.94 µs deadline. The 95 host
tests and local documentation links pass. These serial cases
do not claim eight simultaneous DOS clients; filesystem concurrency is slice 10.
Evidence: [dos-client.json](../qualification/dos-client.json).

The first raw generic-I/O regression exposed an 18-byte increase in the common
Dispatch frame (180 to 198 bytes), causing a deep queue-completion path to hit
the shared kernel stack guard. Routing DOS through the existing general Route
function restores Dispatch to 180 bytes. The regression and affected matrices
were rerun after the fix; no stack reservation or interrupt headroom was reduced.

### Client storage and stack costs

The side table reserves **16 upper bytes per configured public slot**: 11 active
bytes plus alignment/spare capacity, hence 64 fixed bytes for four slots or 128
for eight. It follows the compile-time kernel bank and is included in image/heap
overlap accounting. An initialized client uses a 72-byte context (including its
62-byte packet) and a 27-byte MsgPort rounded to 32 heap bytes: **104 upper heap
bytes and one signal**, with no extra task. There are no mount or open-object
allocations in this slice. The native helper grows by 79 active upper bytes
(6,350 of its unchanged 8,192-byte reservation).

**Reserved bank-zero delta is zero**, fixed and per task. Runtime/loading totals
remain 57,968/58,560 for four slots and 61,536/57,232 for eight, including OS,
guards, alignment and unused capacity. Each non-root eight-slot context still
reserves 1,568 bank-zero bytes.

Raw/optimized local stack peaks are respectively 190/144 bytes for NewClient,
88/72 for Ensure, 142/102 for ReleaseContext and 210/186 for Call. A separate
three-task packet workload runs with the eight-slot profile's 1,024-byte worker
stacks. The client touches 558 raw / 436 optimized stack bytes, leaving 210 / 332
untouched bytes above its compiler floor, plus the 256-byte interrupt reserve.
The shared kernel stack touches 1,166 raw / 1,052 optimized bytes in this
packet workload, within its unchanged 1,536-byte reservation.
These touched-byte watermarks are recorded alongside full native guards. They are a lower bound on reserved frame depth, not a proof of all interrupt
alignments or a substitute for compiler stack checks.

Stack bytes are captured immediately at the completion breakpoint, before the
host far-memory inspection helper reuses retired bank-zero space. An initial
post-inspection watermark mistakenly included that helper's writes into the
retired idle stack; moving capture before inspection removed this measurement
artifact. The eight-slot ownership check likewise reads the upper bank table
through the existing far-memory helper, rather than the bridge's 16-bit MEMDUMP.

Reproduction commands for every client/context/regression case are embedded in
the record. The supplementary commands are:

```sh
python3 tools/test_dos_stack.py --case raw --output build/dos-slice3/verified-stack-raw8
python3 tools/test_dos_stack.py --case opt --output build/dos-slice3/verified-stack-opt8
python3 tools/test_dos_publication.py
python3 tools/generate_dos.py --check
python3 -m unittest discover -s tests
```

Test-only source overrides and their hashes are recorded explicitly. Kernel,
client and ABI source hashes, compiler pin, ROM/emulator and finite watchdogs
accompany each case. The emulator and compiler pins remain unchanged.

## Slice 4: checked sector adapter

[BLOCKIO](../../lib/io/blockio.act) supplies checked SectorBytes, ReadSector and cached
Fetch operations over an attached immutable descriptor. Attach validates the
full-width unit/profile, one-based sector count, sector size, short-boot layout
and nonzero generation before opening anything. The generic block minimum is
one sector; the MyDOS minimum of 368 belongs to the parser.

One adapter retains a reply port, reusable IOSIOReq and 256-byte upper scratch
buffer. Each volume owns a separate open IOSIOReq. A transfer copies only the
selected device/unit binding; it never copies Message queue links. DoIO collects
the reply before the binding and caller-buffer pointer are cleared. Zero error
and an exact io_Actual are both required. The first causal Exec/SIO error is
retained, and any failed/short sector has zero valid cached bytes.

Cache identity includes the volume pointer, generation, full-width sector number,
sector count, data size, unit, profile and boot layout. Invalid reads, attach,
detach and explicit invalidation discard it. A busy transfer or retained volume
reference prevents detach; an adapter with owners or an active transfer cannot
be destroyed. This is a private single-worker boundary, not a public concurrent
block API. ReadSector validates the actual destination extent against physical
upper RAM before copying. Fetch exposes the shared sector buffer to the parser.

[BLOCKWIRE](../../lib/io/blockwire.act) always performs queued SIO in production. The
explicit fixture replacement only provides deterministic sector bytes and
controlled completions. It is copied into an isolated test build, with a recorded
hash; production has no successful backend stub or ATR-container parser.

Raw and optimized emitted execution each pass **1,868 checks on actual emulated
SIO** and **3,314 checks with the fixture provider**. Two retained unit opens serve
128-byte and short-boot/256-byte images. Tests cover sector zero, first/last,
sector 3/4, high auxiliary bytes through 65535, full-width out-of-range values,
undersized destinations, bank crossing, address wrap and unmapped/bank-zero
buffers. Only the ten expected real reads reach the wire; both image hashes
remain unchanged. The fixture verifies immediate cache reuse, generation and
geometry invalidation, short completion, positive SIO errors, negative Exec
errors and io_Error even when the provider return value is zero. A callback
attempts owner/adapter teardown while the borrowed binding is actually live;
both refuse. Every safe case restores heap ownership and native/OS guards.

Seven allocation/open failure points run in each compiler mode: adapter, reply
port, transfer request, sector buffer, volume, owning request and device open.
All unwind to their original heap and signal totals. Tests have a 240-second
host watchdog and 12,000-frame bound. [block-io.json](../qualification/block-io.json)
records each result, exact source/compiler/platform inputs and reproduction
commands. Actual wire cases use the pinned FASTEST profile with serial
acceleration disabled. This slice does not repeat the passive timing matrix;
its geometry/profile limits retain the [slice-1 transport gate](../qualification/sio-sectors.json).

### Compiler correction

A valid scalar comma group followed by a named/native type, such as
`CARD a,b LONGCARD c`, was misparsed in parameter and field declarations.
The correction lives in actionc, commit
`c2268b7c742958bd9078c4e11ef9b10f3b7a0221`, with focused parser and native-CLI
regressions, including LF/CRLF source and both emission modes. The broader
compiler checks pass 2,596 tests (two existing ignored tests). No optimizer or
code-generator workaround was added to Exec816.

The later [compiler issue audit](compiler-issues.md) tracks integration into the
current compiler line and separates defects from frame/allocation limitations.

The compiler pin includes a [small Git bundle](../../toolchain/actionc-comma-groups.bundle)
containing that local commit and its required base. The README setup command
imports it before checkout; publication of this commit upstream is not assumed.
The ABI files are unchanged. [test_compiler_block_fix.py](../../tools/test_compiler_block_fix.py)
rebuilds slice 3's packet workload and verifies identical XEX bytes in both modes
against its committed qualification hashes. Prior execution evidence therefore
still applies to those exact images.

### Adapter memory and stack costs

All adapter state and owning requests use upper heap RAM. The 38-byte adapter
rounds to 40, its 27-byte port to 32, and its 52-byte transfer request to 56;
with 256 scratch bytes this is **384 bytes and one signal per adapter**. Each
volume uses a 22-byte descriptor rounded to 24 and a 52-byte owning request
rounded to 56: **80 bytes per mounted unit**. Two test units use 544 upper heap
bytes in total. There is no additional fixed upper reservation, client allocation
or task beyond the existing SIO worker. During open, the idle scratch buffer
holds the NUL-terminated device name, avoiding a bank-zero string initializer.

**Reserved bank-zero delta is zero**, fixed and per task, including guards,
alignment and unused capacity. Four/eight-slot runtime totals remain
57,968/61,536 bytes including OS; loading totals remain 58,560/57,232. An existing
non-root eight-slot context reserves 1,568 bytes. The fixture's diagnostic state
and guarded crossing buffer are explicit test image extents.

Raw/optimized local stack peaks are 198/162 bytes for Attach, 126/112 for Fetch,
182/170 for transfer retirement and 172/134 for ReadSector. Admission and request
preparation are separate procedures so their temporary storage is not retained
through the blocking transfer. The functional caller uses the four-slot root's
1,536-byte stack with the normal 256-byte interrupt reserve and native guards.
This does not establish the future filesystem worker's complete call-chain
bound; that must be measured with the parser and eight-slot workload.

## Slice 5: MyDOS metadata and paths

[MYDOS](../../lib/mydos/mydos.act) validates the VTOC header and descending reserved map,
then decodes eight-sector directories and resolves paths iteratively. Explicit
block geometry remains authoritative. Both sector sizes use only the first 128
bytes of each directory sector, with 64 entries total. Directory count and
extent, live flags, stored names, ancestor overlap and bounded depth are checked.
Lookup prefers an exact stored name; folded matches must be unambiguous.

The [fixture manifest](../../tests/fixtures/mydos/manifest.json) pins an original
MyDOS **4.50** executable separately from the authors' 4.51 format source used
by the design. The producer downloads and verifies the original disk, boots its
unchanged DOS.SYS/DUP.SYS, and invokes CIO to format, populate and read back each
known file byte-for-byte. Committed targets contain our generated data; original
DOS.SYS/DUP.SYS stay in the ignored build directory. The formatter writes its
standard boot sectors, but neither target contains system files or boots a DOS.
They include 64 root entries, nested directories, mixed link formats, protection,
case collisions and ATASCII. The 256-byte target also contains a fragmented
70,003-byte file above sector 1023. Host extraction independently agrees with
known producer bytes, sizes and hashes; it is not the sole contents oracle.

The fixture producer uses accelerated ROM SIO only to create media. Parser tests
replace BLOCKWIRE explicitly with a provider of sector bytes and controlled
completions. Neither establishes actual filesystem wire timing. Production
BLOCKWIRE remains the queued SIO adapter qualified in slices 1 and 4.

Raw/optimized execution on both sizes passes **1,099 checks per case**, comparing
all root entry fields and stored names. Tests cover exact/folded lookup,
ambiguous names, malformed names/flags/extents, skipped deleted/unclosed entries,
end markers, zeroed directories, protected files, 16 accepted directory levels
and rejection of level 17, repeated/overlapping ancestors, checksum/short reads,
unsupported VTOCs and a too-small volume rejected before I/O. Synthetic extended
maps and a directory at sector 65,520 on a 65,535-sector descriptor exercise
unsigned bounds; those large-volume cases are parser-only. A poisoned upper
half of a 256-byte directory sector never becomes extra entries. All cases
restore heap ownership and preserve native/OS guards under finite watchdogs.

[mydos-metadata.json](../qualification/mydos-metadata.json) records exact inputs,
compiler/platform pins, fixture provenance, commands, request sequences and
local stack costs. `tools/mydos_metadata_record.py` rejects an incomplete or
mixed-source matrix. `tests/test_mydos_package.py` verifies original-media hashes,
known file bytes, fragmentation and failure of incomplete publication records.

The shared workspace is **116 bytes, rounded to 120 on the upper heap**; each
parser volume is **14 bytes, rounded to 16**, in addition to the slice-4 block
records. There is no new task, signal or fixed upper allocation. The 17 ancestor
slots hold root plus at most 16 subdirectories. ResolveStep returns before each
blocking read, so directory parsing frames do not remain on the I/O call chain;
Resolve's raw local peak is 42 bytes. Complete worker call-chain measurements
remain required in the later service slices.

**Bank-zero reservation delta is zero**, fixed and per task, including alignment,
guards and unused capacity. Four/eight-slot runtime totals remain 57,968/61,536
bytes including OS; loading totals are 58,560/57,232. Existing non-root eight-slot
contexts reserve 1,568 bytes. Provider staging, diagnostic globals and expected
bytes are test-only image storage, not production parser state.

## Slice 6: bounded file chains, reads and seeks

[MYDOSFILE](../../lib/mydos/mydosfile.act) implements a private file cursor and an operation
state machine. Open copies the resolved entry and known ancestor extents without
reading the whole file. BeginRead/BeginSeek and ContinueOperation perform no I/O;
the caller fetches the requested sector between steps. The convenience Run driver
serves standalone parser tests. The filesystem worker can drive the same state
machine directly without retaining another frame during a blocking transfer.

Each cursor retains the directory ordinal, per-file link format, sector/offset,
logical position, exact size when known, hop count and Brent cycle state across
successive Reads. Directory fields are little-endian; trailer links are decoded
high byte first. Ten-bit links validate the parent-directory entry ordinal.
Bounds exclude boot sectors, VTOC/root and all known ancestor directories before
payload is copied. EOF must agree with the directory sector count. Canonical
zero-count/zero-start entries, empty terminal sectors and zero-byte intermediate
payloads are accepted; walks remain bounded by the entry count and cycle checks.

Read returns validated payload bytes with trailers removed. Seek supports all
three origins and returns the old position. Negative lengths, invalid extents,
signed overflow, unknown origins and positions past EOF fail explicitly. A
zero-length Read does not access its output pointer. Any failed Read or Seek
returns -1, restores its starting logical position and invalidates derived
traversal state. A copied prefix from a failed Read is unspecified. Subsequent
reads rebuild a bounded cursor; cycle detection is not reset on successful short
reads. Exact size is derived from validated payload counts, never count times
sector payload capacity. Backward seeks restart from the first sector.

Raw and optimized emitted tests compare known original-MyDOS contents on both
sector sizes, including a fragmented **70,003-byte** file, nested files, protected
files, empty files and unchanged ATASCII bytes. Tests exercise 125/253-byte payload
boundaries, bank-crossing output with canaries, a valid output with low word zero,
full-width results, all seek origins and exact EOF. Controlled sectors provide
valid ten-bit links on the double-density image as well as its original extended
links. Sparse metadata/data reads at sectors 32,768 and 65,535 test unsigned link
limits independently of any qualified physical-drive geometry.

Corruption cases include self/two-sector cycles, wrong file IDs, invalid payload
counts, premature EOF, too-small directory counts, metadata/out-of-range links,
and late checksum/short-transfer failures. Both Read and Seek preserve position
on late failure. Repeated one-byte reads detect each test cycle within eight
hops and 2,001 calls; the two-sector cycle uses four physical reads per walk.
The complete harness has 600-second/30,000-frame watchdogs and at most 4,096 sector
requests. All safe completions restore heap ownership and native/OS guards.

[mydos-files.json](../qualification/mydos-files.json) records the four-case matrix,
source/compiler/platform and fixture hashes, assertion counts, per-phase reads,
trace hashes, local stack costs and commands. The provider only supplies sector
bytes and injected completions. These are parser tests in the four-slot root;
actual filesystem SIO, worker stack headroom and concurrent DOS clients remain
requirements of subsequent slices. The publication validator rejects missing
modes, damage cases, maximum-sector reads, large-file data or intact guards.

A cursor is **92 bytes, rounded to 96 on the upper heap per open file**. One
operation record is **44 bytes, rounded to 48 per worker**, shared across requests.
SIZEOF assertions check both layouts in emitted code. Existing parser workspace,
volume and block-adapter costs are unchanged. There is no new fixed upper state,
task or signal. Raw/optimized local peaks are 220/176 bytes for Open, 208/170 for
BeginRead, 136/104 for BeginSeek, 116/104 for ContinueOperation and 70/66 for Run.
Trailer decoding and link validation use separate bounded frames.

**Bank-zero reservation delta remains zero**, fixed and per task, including guards,
alignment and unused capacity. Four/eight-slot runtime totals are 57,968/61,536
bytes including OS; loading totals are 58,560/57,232. Each existing non-root
eight-slot context reserves 1,568 bytes. Diagnostic globals, provider staging and
the guarded upper output extent belong only to the test image.


## Slice 7: filesystem worker and file API

One private filesystem task now serves Open/Read/Seek/Close packets over the
existing SIO worker. Its static Task record and service registry live in upper
kernel RAM. Admission accepts only the compiled private worker entry and an
existing execution slot. The public Task layout and tc_UserData are unchanged.
The task-local DOS slot uses three previously reserved bytes for its owned-object
list; removing a task with a live DOS context/object remains unsupported.

Each mount has a request port sharing the filesystem arrival signal. The sector
adapter owns a separate SIO reply port. The worker selects mount queues in round
robin order and completes one whole DOS operation before selecting again. Long
reads and seeks therefore delay other queued DOS operations; unrelated runnable
tasks continue, including while the worker waits for an accepted SIO request.
There is no per-sector fairness or IRQ filesystem parsing.

Open acquires a mount reference before exposing its port to the caller. Successful
collection transfers that reference to the task-owned handle; failed collection
releases it. Each file has an independent cursor. Other handle calls take a
transient reference before sending, and Close drops the persistent reference
exactly once. The caller retains its transient reference until collecting the
reply. The handler clears its packet state before ReplyMsg and never touches the
returned packet afterward. Private dp_Arg7 carries the caller's DOS slot identity;
this bookkeeping does not change any public call shape. Root-relative lock
arguments remain zero in this absolute-path API.

The generated DOS module contains actual native wrappers with signed 32-bit
results and native pointers. Six implemented call shapes are checked against
the emitted image. Directory imports still reject, and ordinary builds cannot
use the unfinished service. The opt-in builder takes an explicit mount list;
there is no default production fixture mount. Alias storage is bounded to 31
ASCII bytes in a 32-byte descriptor field; the complete path remains at most
255 bytes. Complete configuration/recovery/publication follows in slice 9.

Blocking transport calls run directly from the worker loop. BeginFetch and
FinishFetch share the existing adapter's validation, cache and ownership rules;
the standalone Fetch wrapper drives those same steps. Metadata resolution and
file traversal also return between bounded CPU steps. This keeps parsing frames
off the blocking I/O call chain without increasing bank-zero stacks or reducing
interrupt headroom. Compiler frame guards exposed and prevented several deeper
initial call chains; the final raw worker frame is 182 bytes.

[dos-files.json](../qualification/dos-files.json) records raw/optimized runs on real
128- and 256-byte original-MyDOS media, with serial acceleration disabled. Root,
filesystem worker, SIO worker, second DOS client and compute task are live
concurrently in the eight-slot profile. Both clients retain independent positions
and IoErr values; the compute task progresses while a request is accepted and
the filesystem task is waiting. Tests cover nested paths, bank-crossing data,
zero-low-word pointers, EOF, seeks and rollback, wrong-owner handles, read-only
mode errors, missing files/directories, immediate packet reuse, actual upper-heap
exhaustion, busy Stop, explicit cleanup and unchanged media hashes.

Separate test-only post-collection overrides inject a checksum result or short
io_Actual on a late file sector after real SIO. Both retain the causal error,
return -1 and restore the initial position across repeated calls. These are
public completion-path tests, not physical wire-fault measurements. The earlier
transport gate supplies wire-fault evidence. Adapter, metadata, complete file
parser and client lifetime suites run against the refactored paths in both
compiler modes; unavailable ordinary publication still rejects.

The largest observed filesystem stack use is 708 bytes of its existing 1,024,
leaving 60 bytes above the untouched 256-byte interrupt reserve. The SIO worker
uses 648 and the second DOS client 636 bytes in this workload. Watermarks are
lower bounds and supplement native frame/domain guards; full eight-task/timing
qualification remains slice 10.

Fixed upper storage adds **96 reserved bytes, 90 active**, including the service
Task. Client slots remain 16 reserved bytes (14 active), and clients remain 104
heap bytes plus one signal. A worker Service is 70 bytes (72 on the heap); its adapter, parser
workspace, operation and control port total **656 upper heap bytes**, with two
signals. Each mount adds **192 heap bytes**, including its port and owning SIO
request; each file object is **108 bytes rounded to 112**. Boot metadata reserves
128 bytes plus 44 per configured mount in the already owned metadata bank.
The full image map prevents overlap with heap ownership. Four/eight-task emitted
code prefixes are now $3B0/$430 relative to KERNEL_BANK.

**Bank-zero reservation delta remains zero**, fixed and per task, including
alignment, guards and unused capacity. Four/eight-task runtime totals remain
57,968/61,536 bytes including OS; loading totals remain 58,560/57,232. The worker
consumes one existing 1,568-byte non-root execution slot in the eight-task layout.
Diagnostic globals and guarded data buffers are fixture storage only.

## Slice 8: locks and directory enumeration

Complete: [raw/optimized evidence](../qualification/dos-directories.json).

Lock/UnLock/Examine/ExNext now use the same client packet and mount-reference
path as file calls. Lock accepts SHARED_LOCK and returns a task-owned native
pointer for a file, directory or root. Exclusive locks fail with
ERROR_DISK_WRITE_PROTECTED. Null UnLock does nothing, including no allocation;
successful UnLock preserves the caller's previous IoErr. Wrong-owner and wrong-kind
objects fail without dereferencing an unrecognized caller pointer. The classic
LOCATE_OBJECT argument slots remain root lock, name and mode; native pointers
replace BPTR/BSTR encoding.

The handler fills the 260-byte native FileInfoBlock in caller memory, including
buffers crossing an upper-bank boundary. Names preserve stored case; the root
uses the mount alias. Files report exact validated payload bytes and their
occupied-sector count. Directories have size zero and eight blocks. Root,
subdirectory and file types are ST_ROOT, ST_USERDIR and ST_FILE in both type
fields. MyDOS's stored protection bit maps to FIBF_WRITE | FIBF_DELETE; ordinary
files do not acquire those bits merely because the mount is read-only. Dates,
comments and owner fields are zero where MyDOS has no corresponding metadata.

Exact file size uses a shared measurement cursor and the existing bounded
MYDOSFILE validation/advance routines. It does not disturb an open file's cursor,
and it does not infer length from directory count times payload capacity. The
worker returns between reads and CPU steps. Metadata calls can therefore walk
an entire large chain and delay the next queued DOS operation, as specified by
the whole-operation worker policy.

Examine initializes enumeration state in the FileInfoBlock's reserved bytes.
That state binds the lock's unique object ticket and the FIB address to the next
directory ordinal. It is independent for each lock/info pair and must remain
opaque to applications. A copied FIB at a different address, an uninitialized
FIB, a different lock or a newly allocated lock reusing an old address requires
a new Examine. Tickets never wrap; exhaustion fails allocation. Object lookup
also validates the mount generation. No global enumeration cursor exists.

ExNext skips deleted/unclosed entries, decodes at most 64 live directory slots,
and preserves enumeration position on entry/chain failure. End of enumeration
returns zero with ERROR_NO_MORE_ENTRIES, including repeated calls at end. A file
lock passed to ExNext reports ERROR_OBJECT_WRONG_TYPE. Subdirectory extents and
ancestor overlap/depth checks use the same resolver as path lookup. Reply
publication clears borrowed packet, client, buffer, path and cursor pointers
before transferring ownership back to the caller.

The qualification harness compares every metadata field against the original
MyDOS fixture oracle, including all 64 root entries, nested files, protected and
unprotected files, empty files and the double-density image's 70,003- and
278,300-byte files. It interleaves two FIBs on one lock and a second task's own
lock/FIB. Separate declared media copies test an empty subdirectory, malformed
stored name and cyclic file chain, including retry after failed ExNext. Native
checks cover wrong owners/kinds, stale enumeration state after lock reuse,
read-only mode rejection, exact FIB canaries, resource totals and packet-pointer
retirement. Ordinary application publication remains gated until slice 9.

All four normal compiler/geometry cases pass 1,532 guest assertions, plus nine
checks in the independent client. All six empty/damaged-media cases pass in
both compiler modes. File API and metadata-parser regressions also pass. The
record validator checks actual emitted shapes for all ten calls and exclusion
of private routines from application task admission. The largest observed
filesystem stack use remains 708 bytes, leaving 60 bytes above the untouched
256-byte interrupt reserve; the second client reaches 662 bytes. Kernel/OS,
stack and direct-page guards remain intact, and all contexts/ownership are
released. Watermarks supplement native frame checks; they are lower bounds.

The initial 600-second host watchdog expired during the large double-density
metadata walk, with the guest still waiting/running rather than reporting an
API/stack failure. Double-density runs therefore use a finite 3,600-second host
allowance; 128-byte runs retain 600 seconds. The guest limit remains 30,000 PAL
frames and the driver's active/byte deadlines are unchanged. This is a host
execution allowance, not a relaxation of wire latency. Full-stack timing remains
slice 10.

The worker Service is **170 bytes, rounded to 176**, including a 92-byte shared
measurement cursor. Complete worker heap cost is **760 bytes**. A file or lock
object is **112 bytes**, including a unique 32-bit ticket; it still occupies the
same 112-byte heap allocation as the previous file object. The FIB uses a
16-byte enumeration record inside its existing 32 reserved bytes. No additional
task or signal is introduced. Mounts remain 192 heap bytes and clients 104.
Emitted SIZEOF assertions check the new record sizes. The slice-7 documentation
and record were corrected from 72/106 to 70/108 for Service/Object structure
sizes; their previously reported 72/112-byte heap allocations were already correct.

**Bank-zero reservation delta remains zero**, including padding, guards and idle
capacity. Four/eight-task runtime totals remain 57,968/61,536 bytes including OS;
loading totals remain 58,560/57,232. Fixed upper service storage remains 96 bytes,
90 active; each eight-task non-root execution slot still reserves 1,568 bytes.

## Slice 9: mount and service lifetime

Ordinary `--tasks` builds now supply the implemented DOS module. Mounts are
explicit; [config/dos-mounts.json](../../config/dos-mounts.json) defaults to an empty
list. `IoErr` and an empty `ReleaseContext` allocate nothing, and an unused DOS
service consumes no worker slot. The read and directory examples exercise the
public API without a fixture-enabling build flag.

Pass `--dos-mounts my-mounts.json` to the builder. For example, a 720-sector,
128-byte MyDOS volume on SIO D1 uses:

```json
{"mounts":[{"alias":"D1","unit":49,"sectors":720,"sector_bytes":128,"profile":1,"boot":1,"format":1}]}
```

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks \
  --task-capacity 8 --source examples/dos-read.act \
  --dos-mounts my-mounts.json --output build/dos-read
```

Use the pinned 8× AltirraOS machine and matching mounted media. Profile 1 is
FASTEST125 (128/256-byte data); profile 2 is STOCK810 (128 only). Boot layout 1
means three 128-byte boot sectors; format 1 is MyDOS. Geometry describes the
actual media; the guest neither decodes ATR headers nor discovers density.
Aliases are 1–31 legal ASCII bytes, unique after case folding. Units 49–56 may
appear once each; sector counts are 368–65535. The host rejects unknown fields,
non-integers, narrowing, duplicates and unsupported combinations. Native startup
independently checks descriptors before publishing any mount. Media must remain
stable, with no raw writes while mounted.

Private management packets share the worker's arrival signal. Control and
mount queues alternate between whole operations; neither gains a separate
worker. A caller holds a control reference before exposing the control port and
until reply collection. Busy unmount preserves publication; idle unmount removes
discovery under `Forbid` before freeing its port, parser and owning open request.
Remount validates metadata again and assigns a fresh, non-wrapping generation.
A failed remount rolls back only its partial mount and leaves the other units
available. A lookup paused before `PutMsg` retains its destination throughout.

Quiescing rejects new opens/locks while existing objects can drain. Busy stop
leaves publication intact. Stop checks object, transient-packet and control
references atomically, and prevents restart until its caller has observed actual
worker removal. Returning from the last application automatically wakes the
filesystem for cleanup, closes its SIO bindings, retires that worker and then
allows the existing SIO shutdown policy to run. Forced removal of a task with
live DOS resources remains unsupported.

An unsafe transport failure invalidates the sector cache and marks every mount
unavailable with the first causal error. Accepted packets still receive their
reply; subsequent data/metadata calls issue no further transfer. Close, UnLock
and ReleaseContext remain usable. Unmount/remount does not clear SIO's offline
latch. The physical short-response fixture verifies a queued caller on a second
unit, exactly one further serial terminal post, released software resources and
the existing `$FF93` reset-required platform outcome.

[Lifetime evidence](../qualification/dos-lifetime.json) covers raw/optimized
startup failures at each new allocation, signal, task-admission and device-open
step, metadata failures, duplicate native descriptors, generation exhaustion,
actual task-capacity and heap exhaustion, remount/retry, quiescing, automatic
shutdown, and both ordinary examples. Fault-only source overrides are recorded
and never shipped. Failed filesystem startup restores its heap/ports/bindings;
a global SIO worker that was already started retains its existing warm lifetime
until the last application exits. It is not forcibly stopped while another
client could use it. Repeated client-context/task reuse is also rechecked.

The mount's saved causal error increases its record from 62 to **66 bytes**,
rounded from 64 to **72**. Complete per-mount heap cost is now **200 bytes**.
The queue-turn byte fits existing Service padding: its record remains **170**,
rounded to 176; complete worker heap remains **760 bytes**. Client and file/lock
costs remain 104 and 112 bytes. No new signal, task or fixed service reservation
is added. The fixed upper registry remains 90 active bytes in 96 reserved.

**Bank-zero delta remains zero.** Complete four/eight-task runtime reservations
remain 57,968/61,536 bytes including OS; loading reservations remain
58,560/57,232. Each eight-task non-root slot still reserves 1,568 bytes, including
its DP stride, guards and 1,024-byte stack with 256 bytes reserved for interrupts.
The evidence reports touched-byte stack watermarks alongside native frame/domain
guards. These are lower-bound observations, not a static worst-case proof.
Integrated eight-live-task DOS timing follows in slice 10 below.

Refreshing transport evidence exposed a watchdog-service delay of **101.99 µs**
against the existing **100 µs** bound. The IRQ dispatcher now skips disabled
sources before reading POKEY; it rechecks the enable shadow after each handler,
so terminal completion still disables later sources immediately. Serial remains
first. The previously failing eight-task optimized workload then measured
**91.21 µs**. The complete transport matrix is rerun with unchanged deadlines.
The observer also now distinguishes an alarm explicitly cancelled by IRQEN from
one awaiting its ISR: ROM serial acknowledgement can briefly enable an otherwise
disabled timer. Its observed cancellation took 0.56 µs. Acknowledgement followed
by re-enable still requires the ISR deadline, and the original 101.99 µs trace
still fails the corrected oracle.

The refreshed raw eight-task run also exposed a **220.83 ms** delay between
queued transfers, above the existing 200 ms bound. Timeout preparation used a
248/495-iteration arithmetic walk. It now uses nine binary-division steps with
the same upward rounding, without adding Forbid or IRQ masking. **1,488 emitted
cases per compiler mode** check defaults and every admitted quotient boundary
against an independent integer oracle. The full eight-task runs now observe
179.32 ms raw and 166.07 ms optimized between transfers, with identical-image
replays. These transport refinements are separately qualified in the refreshed
sector record; individual filesystem cases retain their exact build hashes.

## Slice 10: concurrent filesystem qualification

Qualification passes on the pinned emulator. The fixture fills every public task slot: at eight
there are a root coordinator, one filesystem worker, one SIO worker and five
applications. At four there is one application. A startup barrier records the
actual live count; completed applications remain alive at a second barrier until
all peers finish. Waiting clients therefore count as concurrent task occupancy,
not sequential slot reuse.

Each client opens and reads an independently produced MyDOS file, checks every
byte, seeks backward, reads the tail and performs short cached reads. It also
locks and enumerates a nested directory on the other unit, checking names,
exact size, type and sector count. The double-density workload includes a
70,003-byte fragmented file with sixteen-bit links beyond sector 1023 and a
linear buffer spanning banks. Invalid lengths, rejected write opens, EOF and
cleanup exercise task-local errors. The root performs allocator/CLEAR,
message-port and signal work, counting progress during actual serial transfers.

The required matrix is raw/optimized × 128/256-byte media × four/eight tasks ×
kernel banks 1/3. Bank 1 records passive timing and injects a keyboard event
while SIO is active, then replays the identical image without the observer.
Bank 3 is functional-only. Additional eight-task stock-810 runs cover 128-byte
media. Every successful run checks native context, DP/stack/domain and OS guards,
restored heap/bank ownership, released bus buffers and unchanged media hashes.

Packet timing uses emitted call boundaries, without adding guest instructions:
entry to the client's `PutMsg`, return from the handler's `GetMsg`, and return
from the client's `GetMsg`. The native A16/X8 result identifies the complete
24-bit message pointer, while DP identifies its caller. The oracle checks
unique call sites, one outstanding packet per caller, exact expected packet
counts and complete collection, including reused packet addresses. Queue wait
includes gateway/dequeue overhead; dequeue-to-collection includes scheduling the
caller. These figures are distinct from IRQ byte service and terminal-post to
SIO-worker latency.

Bounds are declared before execution. FASTEST125 retains its physical 78.942-µs
byte period, 100-µs alarm limit, 100-ms terminal-to-worker limit, 2.12-s conservative
CRITIC limit and 50-ms Forbid limit. The finite fixture workloads allow at most
512 sectors for single density and 1200 for double density. Each sector allows
its one-second fast or two-second stock active deadline plus 0.3 seconds for
preparation/recovery, with 60 seconds of total CPU/setup margin. The resulting
whole-workload bound also conservatively bounds any queued packet; it is not a
low-latency file-service guarantee. Host watchdogs remain separate. Masked
interval maxima include idle SEI/WAI/CLI spans; actual byte arrival-to-service
measurements determine serial acceptance.

Two early raw fixture versions tripped the native stack guard during lazy DOS
context creation. Splitting selection, open, readiness and directory test phases
reduced the call chain. Production stack sizes and the 256-byte interrupt reserve
were unchanged. The longer traces also justified replacing repeated RX searches
with binary search and parsing the log once. Reprocessing all four retained
transport concurrency traces gives identical measurements.

The focused integration regressions cover Task reuse beyond 255 admissions,
Lists metadata and shared-list interrupt checkpoints, signal masks, port lifetime,
heap calls, generic I/O queues and bank-3 loading in both compiler modes. The
[refreshed transport](../qualification/sio-sectors.json) and
[lifetime](../qualification/dos-lifetime.json) records retain stock/fast profiles,
cancellation, safe/unsafe recovery, startup rollback, queued two-unit failure and
DOS context reuse with unchanged filesystem/kernel policy sources. Retained
cases keep their original SIO hashes; the ISR refinement below has its own full
transport refresh and final DOS matrix. Those DOS fault cases are not relabeled
as eight simultaneous DOS-client tests.

**Reserved bank-zero delta is zero**, fixed and per task. Runtime totals remain
57,968/61,536 bytes including OS at four/eight tasks; loading totals remain
58,560/57,232. Each non-root eight-task slot still reserves 1,568 bytes including
DP, guards and its 1,024-byte stack. Fixed upper service storage is still 96 bytes
(90 active); complete worker heap is 760 bytes, each mount 200, each client 104,
and each file or lock 112. The test adds 2,272 bytes of static upper fixture
storage plus its temporary heap buffers and FileInfoBlocks; these are not kernel
reservations. Stack watermarks are lower-bound observations accompanied by native
frame/domain guards, not a static worst-case proof.

The first raw eight-task single-density timing run exposed a command-byte
refill exactly at its 140-base-cycle deadline. The first byte had been sent
from the fine-alarm handler; TX-ready asserted during prefetch, and scanline
DMA plus a full IRQ return/re-entry delayed the second byte. The dispatcher now
checks TX-ready once after servicing that alarm. It adds no loop or shared state
and rereads the enable shadow before servicing the pending byte. The upper
native helper grows by 39 active bytes, from 6,445 to 6,484, within its existing
8,192-byte reservation. All final concurrency images are rebuilt after this
change and the complete transport profile/recovery matrix is refreshed.

The command trace oracle now groups bytes by COMMAND assertion/release even
when the shifter idles inside a frame. The original trace remains a rejecting
control: the missed refill must appear in both gap and latency checks. All four
previously passing transport traces retain identical measurements under the
corrected parser. The long-workload host watchdogs are 3,600 seconds for single
density and 7,200 for double density; guest, sector and wire bounds are unchanged.

The emitted local costs below exclude callees. The qualification record also
retains complete observed task/kernel stack watermarks and guard results.

| Routine | Raw fixed frame / local peak | Optimized fixed frame / local peak |
| --- | ---: | ---: |
| Filesystem worker | 172 / 182 bytes | 84 / 94 bytes |
| SIO worker | 70 / 78 bytes | 46 / 54 bytes |
| Application fixture entry | 16 / 20 bytes | 2 / 6 bytes |
| Lazy DOS client creation | 178 / 190 bytes | 132 / 144 bytes |

### Observed bank-1 results

All eight observed runs and their identical-image replays pass. The eight
bank-3 functional cases and two stock-speed cases also pass.

| Build | Sector bytes | Live tasks | Max RX service µs | Max TX refill µs | Max terminal-to-worker ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw | 128 | 4 | 64.845 | 63.718 | 22.766 |
| raw | 128 | 8 | 70.484 | 64.282 | 26.123 |
| raw | 256 | 4 | 74.431 | 63.718 | 22.528 |
| raw | 256 | 8 | 73.867 | 64.845 | 62.469 |
| opt | 128 | 4 | 69.356 | 64.282 | 21.273 |
| opt | 128 | 8 | 72.740 | 63.718 | 24.187 |
| opt | 256 | 4 | 76.123 | 63.154 | 22.223 |
| opt | 256 | 8 | 73.304 | 64.845 | 38.974 |

| Build | Sector bytes | Live tasks | Max queue wait s | Max packet turnaround s | Verified file bytes/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw | 128 | 4 | 0.043 | 3.403 | 55.3 |
| raw | 128 | 8 | 8.932 | 10.890 | 58.2 |
| raw | 256 | 4 | 0.032 | 51.417 | 579.5 |
| raw | 256 | 8 | 54.024 | 55.331 | 500.8 |
| opt | 128 | 4 | 0.036 | 3.313 | 59.0 |
| opt | 128 | 8 | 8.774 | 10.867 | 56.8 |
| opt | 256 | 4 | 0.042 | 50.378 | 603.7 |
| opt | 256 | 8 | 53.073 | 54.136 | 510.8 |

The initial handler completes whole operations serially. In the large-file
workload, a client waits up to **54.024 seconds** in the queue; useful throughput
is about **501–604 bytes/s**, including verified tail and cached rereads. The
throughput interval runs from the first sector-transfer start to SIO shutdown
entry, including the remaining mount work. These figures expose a file-service performance limit even though
the IRQ meets the serial deadline. They do not promise interactive file latency.
They are whole-workload useful-byte rates, not the drive's sequential transfer
rate. The separate [single large-read measurement](dos-read-throughput.md)
isolates one Read and distinguishes mechanical timing from serial transfer and
software overhead.

The largest observed RX service is **76.123 µs**, TX refill **64.845 µs**, and
alarm/watchdog latency **98.607 µs**. These are maxima for the recorded workload,
with a small remaining alarm margin, rather than worst-case bounds for every
possible interrupt alignment or application.

Across all eight-task cases, including stock speed and bank 3, the filesystem
worker touches at most **744 bytes raw / 582 optimized**, and SIO **656 / 510**.
A raw client touches
**748 of its 1,024 stack bytes**, leaving only **20 bytes above the protected
256-byte interrupt floor**. Applications must budget their own call depth.
The largest observed kernel watermark in this matrix is **1,201 of 1,536 bytes**.
No test reduces interrupt headroom or task capacity to obtain a pass.

The [concurrency record](../qualification/dos-concurrency.json) contains the complete
16-case geometry/capacity/placement matrix, two stock-speed cases, eight identical
image replays, source/image/media hashes, packet measurements, compiler frames
and complete memory maps. The [regression record](../qualification/dos-regressions.json)
contains 16 focused native cases, retained lifetime/fault evidence, the four
unchanged trace-oracle comparisons and the rejecting command-refill control.

For example, reproduce a full eight-task, double-density timing case with:

```sh
python3 tools/test_dos_concurrent.py --case raw --size 256 --capacity 8 --bank 1 --trace --key --output build/dos-slice10/raw-256-8-bank1
```

Use a fresh output directory for each run. The concurrency record lists all
matrix commands. After collecting their results, regenerate the checked records:

```sh
python3 tools/dos_regression_record.py
python3 tools/dos_concurrency_record.py
python3 -m unittest discover -s tests
```

These are pinned-emulator results. Filesystem writes, automatic media changes,
Process/CLI services, physical hardware and twelve/sixteen-task layouts remain
outside this qualification.

Final host validation passes all 117 tests. DOS, I/O, ports, heap and Task ABI
generators pass their `--check` modes; documentation links and diff whitespace
are checked separately. These checks supplement the native execution above.
