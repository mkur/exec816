# SpartaDOS filesystem contract

This is the supported SDFS subset for the implementation in
[the six-slice plan](../plans/spartados-implementation-plan.md). Completion evidence is
kept separately in [the implementation record](../history/spartados-implementation.md).
Exec816 implements the filesystem, not SpartaDOS CIO or its executable ABI.

## Media and mounts

Exec backend ID 2 means SDFS; ID 1 remains MyDOS. These IDs are separate from
on-disk revision bytes `$20` (2.0) and `$21` (2.1). A mount explicitly supplies
its format, sector count, sector size, unit and SIO profile. There is no format
fallback, baud-rate guessing or media-change detection.

Support 128- and 256-byte sectors, 16-bit sector addresses and three initial
128-byte boot sectors. The configured geometry must agree with the filesystem
header. Revision 2.1 must declare the matching sector size, 62 or 126 data
pointers per map page, and one physical sector per logical sector. Reject other
revisions, clustered sectors and 512-byte sectors. STOCK810 supports only 128;
the existing FASTEST125 and GENERIC57600 profiles support both sizes.

Validate the root-map address, total/free counts and bitmap extent at mount.
The bitmap must cover sectors 0 through the declared final sector. Boot and
bitmap sectors cannot serve as maps or file data. Do not scan all allocation
bits, directories or files at mount: this is not a filesystem checker. Validate
referenced structures as they are accessed, including sector ranges, map
back-links, missing pages, cycles and bounded traversal.

The delivered ATR is a data volume paired with an independently loaded XEX.
Disk bootstrapping and the SpartaDOS operating system are outside this driver.

## Files and maps

A map page contains little-endian next/previous sector addresses followed by
16-bit data-sector addresses. Directory entries store exact 24-bit byte lengths.
The first map has no predecessor. A missing required map is corruption, not
EOF. A zero data pointer in a regular file denotes zero-filled bytes; sparse
directories are unsupported. Data padding past logical EOF is never returned.
Zero filling is Exec816's chosen read behavior, also implemented by Altirra's
host reader. Original SpartaDOS X instead rejects reads into a sparse gap
(User Guide, section 6.3.6); its CIO verifier therefore checks that error,
while Altirra verifies the complete zero-filled byte stream.

Retain a sequential map position between reads. Backward/random seeks resolve
maps lazily on the next read; they do not read preceding payload sectors.
`Seek` follows the existing DOS contract: return the previous position, reject
negative or past-EOF destinations, and leave the position unchanged on error.
Length queries and rewind require no media I/O. A canceled read retains its
already-transferred count and cursor position under the existing DOS rules.

The filesystem worker owns one additional 256-byte map cache and 23-byte
directory-record scratch in upper RAM, shared across mounts. Cache identity
includes volume, generation and sector. Failed reads and retirement invalidate
it. The existing BLOCKIO buffer remains the data-sector buffer; file handles
do not acquire sector buffers.

## Directories and names

Directories are mapped files of 23-byte records. Record zero contains the
parent map address and authoritative directory length; root has parent zero.
A subdirectory's length field in its parent entry may be stale and is ignored. Remaining
records contain status, first map, byte length, padded 8.3 name and timestamp.
Records may straddle sectors and map pages. Directory length must be at least
23 and divisible by 23, with no sparse region in the required extent.

An active entry has status bit `$08`; `$10` marks deletion, `$20` a directory,
and `$01` write protection. Open-for-write/incomplete entries (`$80`) are
accepted only when a live writer in this mount owns them; other incomplete
entries fail explicitly. Deleted entries are skipped; a zero status marks the directory end. Unknown live status combinations are
not silently accepted. The parser preserves stored names and uses the existing
exact-match-first, ASCII-folded fallback policy; ambiguous matches fail.

Preserve Exec816 paths (`D1:TOOLS/FILE`, current-directory relative paths, and
existing root/parent forms), the 255-byte path and 16-level directory limits.
Check parent identity on descent and detect repeated ancestor maps. Do not
accept SpartaDOS CIO's `>` spelling as a new public path syntax.

Enumeration positions are wide enough for the full 24-bit directory extent.
Each FIB cookie retains its lock pointer, FIB pointer and object ticket; it
cannot be reused with another lock/FIB or stale generation. The public 260-byte
FileInfoBlock and its 32 reserved bytes remain unchanged.

## DOS metadata and errors

`fib_Size` is the stored length for regular files, zero for directories.
`fib_NumBlocks` counts occupied data **and map sectors**, excluding sparse
holes. A bounded map-only walk may be needed for this count; neither size nor
block accounting reads ordinary-file payload. Protection maps to
`FIBF_WRITE | FIBF_DELETE`; mount read-only status is reported separately.

Dates use day/month/year and hour/minute/second from the record. Years 50–99
mean 1950–1999; 00–49 mean 2000–2049. Convert valid dates on/after 1978-01-01 to
DateStamp days, minutes and 50-Hz ticks. Missing, invalid or unrepresentable
dates yield an all-zero DateStamp. Text and binary reads preserve every byte,
including ATASCII `$9B`.

Mutation requires an explicitly writable mount and follows the
[filesystem write contract](filesystem-writes.md). An unrecognized mount
header returns `ERROR_NOT_A_DOS_DISK`; malformed structures in an admitted
volume return `ERROR_DISK_NOT_VALIDATED`. Preserve causal SIO errors and BREAK
through the existing packet/retirement path. Unsupported names receive the
existing component-name error; absent paths retain object-not-found behavior.

## References and interoperability scope

The format reference is chapter 7 of the authors'
[SpartaDOS X 4.48 User Guide](https://atariwiki.org/wiki/attach/SpartaDOS/SpartaDOS%20X%204.48%20User%20Guide.pdf#page=165).
The independent producer/reader is Altirra's `diskfssdx2.cpp`, pinned by
[the host wrapper](../../tools/sdfs_reference.py). Fixture creation and deliberate
derivations are documented in [the fixture directory](../../tests/fixtures/sdfs/README.md).
Original SpartaDOS X read-back is emulator interoperability evidence; it does
not qualify any physical peripheral or 65816 machine.
