# SpartaDOS implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Scope: the [read-only implementation plan](../plans/spartados-implementation-plan.md).
The [supported contract](../reference/spartados.md) is separate from this evidence.
Release qualification and physical-hardware testing remain separate gates.

## S1 — reference media and loading baseline

The host adapter uses pinned Altirra SDFS source and existing static libraries;
it does not implement a second parser. It creates deterministic timestamps and
volume identity bytes. Fixture derivations explicitly reverse physical data
placement, free one sparse sector, and produce revision-2.0 header variants.
Altirra validates each allocation/map structure and extracts every packaged
file byte-for-byte against independently generated expected contents.

The original SpartaDOS X 4.50 cartridge is pinned by URL and SHA-256. A 6502
CIO program checks known contents, nested lookup, a fragmented 70,003-byte file,
and entries past 255. SDX rejects sparse-gap reads with status 135, consistent
with the documented restriction. Exec816's chosen zero-fill semantics are
independently checked by Altirra's host reader instead. These observations must
not be presented as original SpartaDOS zero-filling sparse files.

Fixture hashes, producer hashes, exact mutations and original-system machine
records are in [reference.json](../../tests/fixtures/sdfs/reference.json).
Regeneration uses `python3 tools/make_sdfs_fixtures.py`. Its accelerated original
DOS configuration is only interoperability evidence, never latency evidence.

The reusable `tools/measure_command_loading.py` observer records 50-Hz VBI ticks
at PROGRAMFILE phases and counts actual BLOCKWIRE transfers. It adds no waits,
allocations or yields. The comparison uses the pinned paced PAL/800XL,
65C816×8, eight-Task demo with prime background work, 128-byte media and profile
4 / GENERIC57600. HELLO is the first disk command after startup; DIR follows.
The compiler pin remains `47cd55b2dac510922949832332b7a2c3220885be`.

The [recorded MyDOS baseline](../experiments/spartados-mydos-baseline.json) measured
HELLO as follows (20-ms tick resolution, not sub-frame timing):

| Phase | PAL frames | Seconds | Sector transfers |
| --- | ---: | ---: | ---: |
| Open/lookup | 8 | 0.16 | 1 |
| Seek to EOF | 233 | 4.66 | 38 |
| Rewind/staging allocation | 3 | 0.06 | 0 |
| Payload reads | 165 | 3.30 | 19 |
| Close | 3 | 0.06 | 0 |
| In-memory load | 42 | 0.84 | 0 |
| Return, execution, prompt | 13 | 0.26 | 0 |
| **Open through prompt** | **467** | **9.34** | **58** |

The EOF phase reads HELLO's 19 data sectors twice. DIR, run immediately after
HELLO on the same demo disk, took 2,122 frames (42.44 seconds), with 342 sector
transfers. These are diagnostic-build observations; the unchanged release
compiler and platform have not been generally requalified. Guard, stack,
resource-return and OS-restoration assertions passed in this bounded session.

Development checks: 188 host tests passed; all four revision/geometry fixtures
passed independent extraction and original SDX CIO checks. One optimized
instrumented demo session covered HELLO, DIR and EXIT with stack/domain guards
and bank ownership restored. No Exec parser code changed in this slice, so no
raw/optimized parser matrix was run. Link/content checks passed.

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. S1 changes no shipped
target code. The diagnostic reads the existing VBI counter and places its own
counters inside the existing reserved static-data arena.

## S2 — backend boundary

Shared DOS objects now hold filesystem-neutral entries and cursors. The MyDOS
adapter owns the original parser structures; the parser and its on-disk rules
are unchanged. Mount IDs come from `abi/filesystems.json`; omitted IDs still
mean MyDOS. SDFS is recognized by configuration tooling but cannot mount until
its backend is registered. MOUNT inspection reports format and read-only state.

Backend steps never wait. Mount steps return failure/success and set the next
sector when needed. Entry steps distinguish entry, end, skipped entry and more
I/O (1/2/3/4); file and measurement steps return failure, completion or more I/O
(0/1/2). The existing worker supplies one sector between steps. Enumeration
positions are now 32-bit, with the same lock/FIB identity and generation checks.
The public DOS ABI and 260-byte FileInfoBlock are unchanged.

[Focused execution evidence](../development/spartados-s2.json) covers raw and
optimized relative paths, open/read/seek, directory cookies, inherited shared
cursors, active cancellation, inspection, guards and resource return. Backend
workspace failure was injected in optimized code and volume failure in raw
code. These checks reuse small scenario sets rather than a release matrix.
Build provenance now includes every new backend source. Historical qualification
records retain their original input hashes and schema-specific test matrices.

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. No worker or Task slot
was added. With the eight-byte heap rounding, upper-RAM growth is 304 bytes per
worker, 16 per mount, 176 for the first file handle/backing, 88 for another shared
handle and 88 per lock. The eight-row MOUNT snapshot grows by 16 allocated bytes.
Private object/backing sizes are 204/182 bytes; service/workspace/operation sizes
are 524/172/44 bytes, plus the 160-byte MyDOS backend workspace. The common volume
is 10 bytes plus the original 14-byte MyDOS volume. The optimized relative-path
image contains 3,046 bytes of dispatch code and 13,972 bytes of MyDOS adapter code;
these are module totals, not a net image-size claim. SDFS will use the common
metadata directly, without the MyDOS compatibility copies.

## S3 — native files and seeking

The SDFS parser admits the supported 2.0/2.1 headers and geometry, rejects boot
and bitmap references, and walks maps with checked predecessors, bounded page
counts and explicit short-chain errors. A single tagged 256-byte map cache
serves all cursors. Sequential reads retain map position, sparse regular-file
regions produce zero bytes, and exact lengths bound the final sector.

EOF/rewind and all valid seeks finish without I/O. Read resolves the destination
map lazily. A new internal result, 3, requests a CPU checkpoint between bounded
steps; 2 still requests one sector. Public DOS registration follows in S5.
Map-only accounting includes allocated maps and data, excluding sparse holes.
Failed/canceled reads invalidate the cache; BREAK preserves completed bytes.

[Raw/optimized 128/256-byte runs](../development/spartados-s3.json) passed against
complete independent fixture bytes delivered by a memory sector provider.
They cover the full fragmented 70,003-byte file, empty/partial/sparse files,
map and 64-KiB boundaries, backward/invalid seeks, zero-I/O length queries,
header errors, short/cyclic/bad-backlink maps, reserved data, cancellation and
failure recovery. Output canaries, native guards, stack headroom, allocation
return and OS restoration passed. The 190 host checks passed. These runs make
no SIO latency or release-qualification claim.

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. Each SDFS workspace
allocates 536 upper bytes, including its map buffer, directory scratch/cursor
and currently unused namespace capacity; each SDFS volume allocates 8 bytes.
The common workspace grows from 172 to 174 bytes but remains a 176-byte heap
allocation. Per-handle storage is unchanged. These SDFS allocations are not yet
part of the published MyDOS service. Exact emitted module sizes are recorded
for each test image in the linked evidence.

## S4 — namespace and metadata

The namespace walker assembles 23-byte entries through the file cursor, retains
one validated directory header/cursor per worker, and checks parent maps and
ancestor cycles. It supports the full 24-bit directory extent with wide entry
positions, exact-name preference and rejected ambiguous folded matches. Entry
protection and valid timestamps become shared DOS metadata. Directory length
comes from its own header: independent valid fixtures leave creation lengths
in the parent entry. A zero entry status ends enumeration; deleted rows skip.

[Focused raw/optimized evidence](../development/spartados-s4.json) covers nested
paths, allocation accounting, independent expected bytes, malformed lengths,
sparse directories, open-for-write entries, parent errors/cycles, duplicate
names, protection and dates. A derived directory has 300 live files and 1,110
deleted records; its last entry is at position 1,409, beyond a map-page boundary
in both geometries. Altirra independently validates and extracts every unchanged
file; [the derivative record](../../tests/fixtures/sdfs/namespace-reference.json)
identifies its exact sector allocations. Native namespace tests explicitly
reject any read of ordinary-file payload. The 191 slice-relevant host checks
passed. Public FIB publication and DOS registration are wired in S5.

Runtime remainder required the pinned compiler's arithmetic-fault binding.
The launcher now supplies its distinct terminal raw ABI, and packaging accepts
version-4 images only with that exact address, preserving frame-map checks.
Raw and optimized division-by-zero stimuli terminate with `$FF97`, reason 1,
without continuing source execution; native guards and OS restoration pass.
No compiler revision or external-command import contract changed.

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. The fault adapter fits
the already reserved launcher FAULT segment and reuses existing report cells.
The SDFS worker context now allocates 544 upper bytes, eight more than S3 for
the directory cache identity/generation. There are no additional per-handle
buffers, Tasks or fixed upper reservations. Date conversion uses a bounded
calculation over the supported 1978–2049 range.

## S5 — public DOS and mixed mounts

Format 2 now selects SDFS through the existing filesystem worker. CPU-only
backend steps return to its cancellation checkpoint without requesting SIO.
Directory accounting uses each backend's rules; FIB publication now includes
SDFS dates and protection. Failed I/O, cancellation and mount retirement clear
cached SDFS identities. The loader and public DOS ABI are unchanged.

[Focused development evidence](../development/spartados-s5.json) covers real
GENERIC57600 SIO with SDFS on D1 and MyDOS on D2: byte-exact reads and seeks,
relative/parent paths, independent enumeration beyond 255, invalid cookies,
inherited shared cursors, write rejection, busy unmount, remount and repeated
cleanup. Raw and optimized 128-byte cases each pass 118 assertions. A 256-byte
case reuses the exact optimized image with only its mount geometry explicitly
changed at bootstrap. This is a recorded test override, not a new binary.

Seven cancellation scenarios pass in each mode: middle read, active wire,
open allocation, directory scan, allocation accounting, lookup and sector copy.
They check partial-read position, no late buffer writes, publication boundaries,
foreground collection and heap return. Injected SDFS workspace failure
(optimized) and volume failure (raw) both roll back and retry cleanly. A MyDOS
disk configured as SDFS fails visibly with error 225. The 193 host checks pass,
including two builder checks prepared for S6. General release/transport/compiler
qualification remains separate. The first integration attempt failed only
because its test expected 0 from a rejected Write; the DOS contract returns -1.

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. Registering SDFS adds
its 544-byte upper-RAM context to the shared worker; the MyDOS context remains
160 bytes. The common workspace stays at 176 allocated bytes, SDFS backend
volume state uses 8, and the common volume uses 16. No per-handle buffer, worker,
Task slot or fixed upper-RAM reservation was added. Exact emitted module totals
and stack observations are retained in the evidence.

## S6 — SDFS play image

New demo bundles default to a 720-sector, 128-byte SDFS 2.1 data ATR with an
explicit format-2 mount. `--format mydos` retains the previous data format;
`--sector-bytes 256` changes the media and mount geometry together. The shell
has matching explicit 128/256-byte configurations. The builder uses the pinned
Altirra producer, validates allocation metadata, and extracts every packaged
file byte-for-byte. Binary commands stay exact; only host text is normalized.

The optimized packaged image passed MOUNT, CD, DIR, HELLO, TYPE, TASKS, repeated
HELLO/WC and CAT/WC pipelines, physical BREAK during loading and active file I/O,
subsequent recovery and EXIT. Prime work continued during I/O. Repeated commands
returned heap, handles, Images and Tasks to the warmed baseline; seven Tasks
were observed during a pipeline, five at the prompt, and all retired on exit.
The warmed prompt had 186,440 free bytes, with a largest linear allocation of
186,184. Stack/domain guards, interrupt headroom, read-only media hashes and
OS display/input restoration passed. A short STOCK810 run reused the exact XEX
with a declared profile-2 bootstrap override and passed HELLO/EXIT. This is
emulator evidence, not a physical-drive qualification claim.

The [S6 evidence](../development/spartados-s6.json) records artifact hashes,
walkthrough results and exact phase/sector counts.
The diagnostic uses the same optimized instructions for MyDOS and SDFS, with
explicit mount-format and sector-label-table overrides, equivalent file bytes,
128-byte sectors, GENERIC57600, PAL 65C816×8 and the same prime background work.
HELLO is the first disk command after startup; DIR follows it. The shipped
image has no observer. The initial diagnostic table exceeded the fixed near-data
arena and packaging rejected it. Its 721 bytes now occupy unused space in the
already reserved upper kernel bank; bank-zero reservations were not enlarged.

Reserved bank-zero change: **0 fixed bytes, 0 per Task**; the budget is identical
to S1's demo. S6 adds no shipped worker, per-handle storage, heap metadata or
fixed upper reservation. The packaged image has 646,295 emitted routine bytes,
including 45,518 in SDFS modules. S5's 544-byte worker cache/context and 8-byte
SDFS volume state are unchanged. The 193 host tests and local documentation
link checks pass. Full release matrices, general compiler qualification,
filesystem writes and physical hardware remain separate work.

The comparison uses byte-identical 2,359-byte HELLO commands and one diagnostic
XEX (20-ms VBI timing resolution):

| Operation | MyDOS seconds / reads | SDFS seconds / reads |
| --- | ---: | ---: |
| HELLO, open through prompt | 9.34 / 58 | 5.20 / 23 |
| HELLO size query | 4.66 / 38 | 0.08 / 0 |
| HELLO payload | 3.10 / 19 | 3.44 / 20 |
| DIR | 42.42 / 342 | 5.82 / 22 |

SDFS HELLO uses two directory reads, two map reads and nineteen payload reads.
It does no preliminary payload traversal. DIR uses seven directory reads and
fifteen map reads, with zero ordinary-file data reads; MyDOS DIR reads 335 file
data sectors plus seven directory sectors. The updated MyDOS HELLO total agrees
with S1; DIR differs by one VBI tick (42.44 seconds in S1).

Most remaining SDFS HELLO time is payload I/O (3.44 seconds), followed by
in-memory loading (0.76) and open/lookup (0.50). These are measured phase costs,
not a claim that filesystem work or wire transfer alone accounts for them.
The image and transport profile were kept identical between the two replay
runs; the earlier S1 image remains separate baseline evidence.

A subsequent [matched-profile comparison with original SpartaDOS X
4.50](../experiments/spartados-dos-comparison.md) measures the same nineteen HELLO
data sectors at 3.005 seconds under Exec816 versus 2.202 seconds under SDX.
The MyDOS/SDFS table above compares Exec816 backends; it is not a comparison
with original DOS. The new experiment records the different phase/cache
boundaries and the demo's active background worker.
