# SpartaDOS filesystem implementation plan

Status: S1–S6 complete, 2026-09-25; see [the implementation record](../history/spartados-implementation.md).
The read-only development milestone is implemented. Release qualification and
write support remain separate follow-ups.

Add a native SDFS handler alongside MyDOS, then
make SDFS the default data filesystem for newly built shell/demo bundles.
The first milestone is read-only, matching the current MyDOS API. Filesystem
writes are a separate follow-up below.

## Outcome and scope

An application can use the existing DOS calls to open, read, seek and enumerate
an SDFS volume. HELLO, CAT, WC and pipelines work unchanged. MyDOS and SDFS can
be mounted together, using the same filesystem worker and SIO worker.

Support SDFS 2.0 and the 128/256-byte-sector subset of SDFS 2.1, nested 8.3
names, fragmented files, sparse regular-file reads and directories beyond 64
entries. Preserve Exec816 path syntax, handle inheritance, CurrentDir,
NameFromLock, foreground BREAK and cleanup behavior. Run native code through
the existing DOS API; implementing the disk format does not add the SpartaDOS
operating system or its executable ABI.

Keep the existing transport profiles: 128-byte STOCK810, and 128/256-byte
GENERIC57600 or FASTEST125 with a matching peripheral. Continue using three
128-byte boot sectors. Defer SDFS 1.x, 512-byte sectors, FAT, new block devices,
automatic format/media detection, writable mounts and disk bootstrapping.
The delivered ATR remains a data disk paired with an independently loaded XEX.

## Format references and decisions

Use chapter 7 of the authors' [SpartaDOS X 4.48 User Guide](https://atariwiki.org/wiki/attach/SpartaDOS/SpartaDOS%20X%204.48%20User%20Guide.pdf#page=165)
as the format reference. It describes stored byte lengths, linked sector-map
pages, allocation bitmaps and 23-byte directory records. The format has 16-bit
sector addresses and 24-bit file lengths. Zero file-data pointers can represent
sparse holes. Check interpretation independently against the SDFS implementation
in the pinned [Altirra 4.40 source distribution](https://www.virtualdub.org/downloads/Altirra-4.40-src.7z),
particularly `src/ATIO/source/diskfssdx2.cpp`, and disks produced/read by original
SpartaDOS software. The new parser or image builder must not be its own oracle.

Publish the supported-media/API contract separately as `docs/reference/spartados.md`
in S1. Specify revision/geometry checks, name matching, entry flags, parent/root
identity, sparse reads, malformed-media errors and metadata conversion there.
Treat a directory entry marked open for write or an incomplete file as an explicit
unsupported/error case; do not silently present potentially incomplete data.
Sparse directories are outside the supported subset. Unknown revisions and
incompatible geometry fail without trying another filesystem or baud rate.

Map valid timestamps to DOS DateStamp using the reference's year encoding;
missing or unrepresentable timestamps become zero. Map stored protection to
the existing DOS protection bits; a read-only mount is a separate property.
Preserve the public meaning of `fib_NumBlocks` as occupied sectors: for SDFS,
count allocated data and file-map sectors with a bounded metadata-only walk,
excluding sparse holes. Do not substitute rounded file length. Cache this
result only for the unchanged mount/object generation. Consequently ExNext may
read map pages for allocation accounting, but must not read regular-file data
to discover its size or block count.

## Architecture and constraints

The public DOS ABI stays unchanged. Internal ownership and packet processing
remain shared. Introduce a small backend dispatch layer for mount validation,
lookup/enumeration, cursor creation, Read/Seek progression, cancellation and
destruction. Use a format tag and backend-owned upper-RAM state; keep MyDOS and
SDFS disk structures inside their respective modules. This is a two-backend
extension, not a new general-purpose VFS or a second DOS implementation.

Current coupling to remove includes:

- `FSTYPES` embeds MyDOS volume, workspace, operation and cursor types.
- `FSINIT`, `FSHANDLER`, `FSDIRECTORY`, `FSRELATIVE` and `FSABORT` invoke MyDOS
  directly; relative-parent reconstruction assumes fixed directory sectors.
- `FSINFO` has a byte enumeration index, and FSDIRECTORY hard-codes 64 entries.
- Mount validation accepts only format 1, and the shell prints a fixed MyDOS
  handler name.

Keep shared entries limited to DOS-facing metadata, backend identity and whether
an exact length is known. Do not impose SDFS size guarantees on MyDOS. Use opaque
backend enumeration positions wide enough for the supported directory extent;
retain lock/FIB identity and generation checks in the existing reserved FIB
space. Update all internal callers together, with one current representation.

Keep explicit mount selection. Retain format 1 for MyDOS and assign format 2 to
SDFS; these are Exec816 backend IDs, separate from disk revision bytes. Put the
IDs in a machine-readable input and generate shared host/Action definitions.
Existing configurations that omit the field retain their MyDOS meaning. Add an
explicit SDFS configuration rather than silently reinterpreting old images.
Move the MyDOS minimum-volume rule out of common mount validation.

One worker continues to serialize whole filesystem operations. Each backend
step performs bounded CPU work or requests one sector through BLOCKIO; only
the existing worker waits on SIO. Preserve cancellation checkpoints, causal
errors, partial-read rules, mount generations and request retirement. No waits
or unbounded parsing under Forbid or IRQ masking. This plan does not change
filesystem scheduling fairness or the native interrupt protocol.

Start with the existing 256-byte data buffer, one additional 256-byte map cache
shared by the worker, and small directory-record assembly scratch, all in upper
RAM. Copy directory records that straddle sectors; never retain pointers into a
buffer that another read can replace. Tag caches by mount, generation and sector;
invalidate them on failed reads and mount retirement. Avoid whole-file map
preloads and per-handle sector buffers. Final metadata sizes must be measured.

## Implementation slices

Each slice has its own commit after its focused development checks. Record
actual results in `docs/history/spartados-implementation.md` as work proceeds; the
planned checks below are not completed qualification.

| Slice | Deliverable | Depends on |
| --- | --- | --- |
| S1 | Supported-format contract, independent fixtures and loading baseline | Current system |
| S2 | Backend boundary with unchanged MyDOS behavior | S1 |
| S3 | Native SDFS mount, sector maps, Read and Seek | S1, S2 |
| S4 | SDFS namespace and directory metadata | S3 |
| S5 | Public DOS integration and mixed mounts | S2–S4 |
| S6 | Default SDFS play image and measured command loading | S5 |

### S1: reference disks and baseline

Pin producer binaries, reference sources and their hashes. Store small 128- and
256-byte fixtures with independently known contents and original-system
read-back evidence, covering both advertised SDFS revisions. Reuse existing
emulator/ATR tooling; do not copy compiler or emulator trees into new outputs.

Include empty files, binary/ATASCII bytes, partial final sectors, nested paths,
fragmentation, a file crossing a map-page boundary, sparse regular files,
directory records crossing sectors, and a directory with more than 256 entries.
Include a file crossing 64 KiB to catch truncated lengths. Derive damaged cases
from identified sector/field mutations; keep original images immutable.

Capture one current HELLO baseline with the pinned optimized shell, recording
open/lookup, size/seek, payload read, in-memory load and return-to-prompt times
and disk-read counts. Prefer bounded phase/sector counters to full traces.
Keep this diagnostic reusable for S6; do not rebuild a whole qualification
matrix. Record timing that is actually available rather than assigning
unmeasured delay to the filesystem.

**Checks:** fixture hashes and expected bytes agree with independent read-back;
both revisions/geometries are identified; the baseline records exact machine,
disk profile, image and compiler inputs. Fix the supported contract before S3.

### S2: separate shared DOS policy from MyDOS parsing

Introduce the backend boundary above, initially with only MyDOS registered.
Adapt object allocation/destruction, shared file backing, locks, canonical names,
relative paths, enumeration cookies, mount startup/rollback and FSABORT. Leave
the MyDOS disk parser and its behavior intact; the redundant MyDOS EOF scan is
a separate optimization, not a dependency of SDFS support.

Update the mount generator and target validation together. Recognize the SDFS
ID but reject mounting it until its backend is available. Extend inspection
records so MOUNT can report the actual backend and read-only status.

**Checks:** host/generator checks plus a focused raw/optimized MyDOS session:
open/read/seek, CD and parent resolution, directory enumeration, inherited
cursor sharing, BREAK, allocation rollback and clean unmount. Check stale
objects/enumeration cookies and unchanged public DOS layouts. Reuse the same
built fixture across small scenarios.

### S3: native SDFS files and seeking

Implement `lib/spartados/` modules for volume checks, map-page traversal and file
cursors. Validate headers and geometry at mount; validate referenced structures
as accessed. Check sector ranges, reserved-region references, map links,
premature chain termination and cycles with bounded completion. Do not scan the
entire disk at mount or claim a complete filesystem consistency check.

Read exact file bytes through the map cache, including fragmented data and
zero-filled sparse regions. Respect logical EOF independently of sector padding.
Keep sequential map position across chunked DOS reads. Seek returns the previous
position, as required by Exec816 DOS; preserve its existing offset/error rules.
Use the known length to finish EOF queries without traversing payload or map
sectors. Resolve the destination map lazily when data is next requested, and
never read preceding file payload to perform a random seek.

**Checks:** focused raw/optimized emitted parser tests against a sector fixture
provider; both sector sizes because map capacity changes with geometry. Verify
empty/partial/sparse reads, map and 64 KiB boundaries, backwards seeks, zero-I/O
EOF queries, truncation, bad links and injected read failures. Assert sector
request bounds and output canaries; check stack/domain guards and reclamation.

### S4: paths, directories and FileInfoBlock

Use directory files and their map pages for lookup, enumeration and relative
parent resolution. Assemble complete records across sector boundaries; honour
directory length/status rules and skip deleted entries. Preserve the current
case-matching policy, path/depth limits and canonical DOS names. Detect invalid
parent relationships, duplicate ambiguous names and cyclic descent.

Return exact sizes from directory metadata, protection/timestamps from their
defined conversions, and block counts through map-only accounting. Keep each
lock/FIB enumeration independent; support positions beyond 255 without changing
the public FileInfoBlock. Invalid caller cookies must not enable arbitrary reads.

**Checks:** raw/optimized root/nested lookups, CD parent/root semantics, records
crossing sectors and map pages, enumeration beyond 64 and 255 entries, concurrent
enumerators, deleted/protected entries, bad directory lengths and parent loops.
Assert that examining/listing ordinary files never reads their payload sectors.

### S5: public DOS and mixed-volume lifetime

Register the completed SDFS backend and accept explicit format-2 mounts.
Exercise ordinary Open/Read/Seek/Close, Lock/UnLock/Examine/ExNext,
CurrentDir/NameFromLock, stream inheritance and loaded-command access.
Mount SDFS and MyDOS on separate units at the same time. A format mismatch must
fail visibly; mixed mounts must not cross-contaminate caches, cursors or errors.
Keep PROGRAMFILE.Load filesystem-independent: its existing EOF/rewind seeks
obtain the stored length cheaply through SDFS. No format-specific loader branch
or staging-buffer redesign is required for this milestone.

Preserve busy-unmount rejection, stale-generation rejection, shared backing
reference counts and task teardown. Cancel lookup, directory accounting, file
reads and loading at the existing safe checkpoints. Keep mutation requests
rejected before a write reaches the device. Update parser/module packaging and
shell mount reporting alongside integration.

**Checks:** focused raw/optimized emitted DOS cases with real emulated SIO,
using 57.6 kbaud and 128-byte media as the default. Add a small 256-byte transport
integration case, one mixed-mount case, and the relevant cancellation/failure
and repeated-cleanup cases. Verify byte-exact files, no writes, independent
background progress, retained OS behavior and resource return to baseline.

### S6: package the SDFS showcase and measure it

Add a reproducible SDFS media builder or wrap an existing pinned producer.
Have an independent implementation read back every packaged file. Keep binary
commands exact; normalize only host text sources, preserving ATASCII fixtures.
Build equivalent MyDOS/SDFS images with the same commands and text for comparison.

Make SDFS explicit in the default new shell/demo configuration and keep a MyDOS
build option. Update bundle filenames, manifests, boot instructions, MOUNT
output and the demo runner together. Keep the ordinary default image at
128-byte sectors; offer a matching 256-byte configuration for capable devices.
Use the existing [compiler pin](../../toolchain/actionc.json),
[paced platform pin](../../toolchain/altirra-shell-paced.json) and eight-Task setup;
general compiler qualification remains separate.

Measure HELLO and DIR against S1 with the same payload, sector size, clock,
drive model, baud rate, cache starting conditions and background workload.
Record phase timings and separate directory/map/data reads. Require zero data
reads for size discovery and no preliminary full-file traversal during SDFS
loading. Report measured latency and any remaining loader/scheduler costs;
do not promise a speedup from the format alone or mask a regression by changing
the transport profile.

**Checks:** one bounded optimized packaged walkthrough: DIR, CD, TYPE, HELLO,
HELLO | WC, CAT STORY.TXT | WC, BREAK during a longer read/loading operation,
subsequent prompt recovery and EXIT. Repeated commands restore warmed-up heap,
handle, Image and Task totals. Reuse unchanged raw/optimized slice evidence.
Include a short emulator STOCK810 smoke with 128-byte media to check the slower
profile; it is not a claim of physical-drive qualification.

## Memory and testing gates

Target reserved bank-zero delta for every slice: **0 fixed bytes and 0 bytes
per Task**, including guards, alignment and spare capacity. No additional worker
or Task slot. Follow the [platform budget](../reference/platform.md#bank-zero-memory-budget);
report actual code, metadata, cache, allocator and per-open-object costs in upper
RAM. Check that including both backends still leaves room for the demo's two
loaded commands and pipe, and preserve measured stack/interrupt headroom.

Follow the [two-tier testing policy](../contributing/testing.md): host tests and focused emitted
raw/optimized tests for affected behavior at each code slice; content/link checks
for documents. Build once per relevant mode and reuse only when input hashes
match. Keep routine artifacts small, use one output tree per slice and enable
tracing only for a specific unresolved timing question.

Release qualification is a separate gate on frozen inputs: supported revisions
and sector/profile combinations, alternate kernel placement, eight live Tasks,
full-file and malformed-media cases, cancellation/ownership failures, transport
timing and unchanged-image replay where applicable. A real-hardware claim also
needs an identified 65816 machine, firmware and peripheral with recorded media
and speed settings. Emulator interoperability evidence alone cannot provide it.

## Later write-support milestone

Plan writable SDFS after the read path and format choices are exercised. Split
that work into 256-byte SIO write support and failure retirement; allocation and
metadata update ordering; file creation/extension/truncation; directory mutation;
and remount/original-SpartaDOS interoperability checks. Define partial-write,
disk-full, BREAK and failed-update behavior before enabling writes. Do not
describe multi-sector updates as atomic without an implemented recovery scheme.
Target formatting, repair and 512-byte sectors remain separate capabilities.
