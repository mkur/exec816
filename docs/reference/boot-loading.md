# Fixed-image boot loading

[Reference](README.md) · [Platform and memory budget](platform.md#bank-zero-memory-budget)

The generated XEX loads the bank-zero bootstrap, resident adapter and manifest,
then calls setup through INITAD. OF816 runs next, before the upper-RAM kernel
payload. Its five-second autoboot or `EXEC816` returns to the reader with RTS.
Subsequent INITAD callbacks expand the kernel into its final addresses; the
guarded RUNAD enters it only after every extent is complete. Current builds
require BASIC disabled and no cartridge; the historical Atarimax wrapper
conflicts with the high bank-zero Task pools and is unsupported.

The bootstrap and OF816 remain uncompressed. The host packages kernel copy/code
extents as independent raw LZ4 blocks, using HC level 12 and up to 65,535 bytes
of output per block (the 64 KiB class, limited by the 16-bit length). Extents
retain their bank boundaries, kinds and gaps. A block
is stored raw when compression plus its four-byte header would not shrink it.
Zero-fill extents retain their metadata-only representation.

## Transport records

[memory-v1.json](../../abi/memory-v1.json) is the machine-readable layout.
The eight-byte staging header uses little-endian integers:

| Offset | Bytes | Field |
| --- | ---: | --- |
| 0 | 2 | Extent index |
| 2 | 2 | Output offset within that extent |
| 4 | 2 | Count |
| 6 | 1 | Extent kind: copy 0, zero 1, executable copy 2 |
| 7 | 1 | Encoding: RAW 0, LZ4_BEGIN 1, LZ4_CONTINUE 2 |

For RAW, count is the output size, at most 1,024 bytes. Copy records carry that
many payload bytes; zero records carry none. For compressed records, count is
the number of staged payload bytes, also at most 1,024. BEGIN starts with two
16-bit lengths: expanded output and compressed input, followed by the raw LZ4
block. Its first record includes the complete four-byte header and at least
one compressed byte. CONTINUE carries the next compressed bytes and repeats
BEGIN's extent index, kind and starting output offset. It cannot start a block.

The decoder resumes across records even within length extensions, literal runs
and two-byte match offsets. It advances the committed output offset only after
the entire block ends with exact input/output lengths and final literals.
This transport extension leaves the runtime memory ABI and manifest layout
unchanged. The former reserved record byte now selects the encoding; regenerate
the bootstrap when repackaging a native image.

## Context, bounds and lifetime

Callbacks stay in emulation mode with eight-bit A/X/Y. They preserve P, A/B,
X/Y, DBR, D and the live page-one stack; decoding uses no direct-page scratch,
native-mode transition or IRQ/NMI masking. OS interrupts continue normally.
The character-output helper borrows and restores IOCB0.

Record admission checks the expected extent, offset, kind, input count and
descriptor output bounds. Every literal/match run is bounded before copying;
matches cannot refer before their block, and zero offsets and overflowing
lengths are rejected. A malformed block can leave partial output inside its
admitted destination, but prevents kernel entry. An unfinished block also
prevents entry. Callbacks are sequential and are not a public decompression
service.

Compressed input reuses the existing 1 KiB staging area. Decoder code and state
fit the generated loader reservation; no upper-RAM input scratch or
new fixed/per-Task bank-zero reservation is required. Expanded kernel RAM use
is unchanged. Loader/staging retirement follows the existing startup phases;
OF816 return does not retire them early. Boot settings and earlier screen text
remain intact, and progress counts expanded bytes.
The progress accumulator emits four 16 KiB dots for a 64 KiB carry before
processing the stored remainder, so maximum-size blocks retain exact rounding.

See the [implementation measurements](../history/loader-compression.md) for
actual artifact sizes, decoder times and development-check scope.

The ROM error line includes the hexadecimal `boot_errors` status from
[memory-v1.json](../../abi/memory-v1.json) and current MEMLO/MEMTOP. Bounds,
manifest, record and incomplete-loading failures remain distinct. Printing the
diagnostic adds no reservation: code and text fit the existing loader arena,
with zero fixed/root/kernel/per-public-Task/idle bank-zero growth.

For FujiNet's virtual XEX disk, the split profile can select SYS on D2 at build
time with `--system-drive 2`; D1 remains the boot transport and WORK stays D8.
See the [split boot guide](../guides/fujinet-split-boot.md).

## Boot-only SIO reader

SIO demo builds use `--boot-sio auto` by default. The small initial reader loads
at standard speed, then requests FujiNet's `$3F` HSIO index. Index 8 selects the
nominal 57,600 baud profile after a checked STATUS reply. `--boot-sio standard`
keeps bulk loading at divisor 40. Both policies explicitly establish the native
driver's divisor-8 profile before native entry; standard boot does not change
native mount configuration. Other high-speed indices and turbo protocols are
unsupported.

The split XEX begins with an ordinary, guarded prefix in `$4000–$5FFF` and an
early INITAD. Its generated [descriptor](../../abi/boot-sio.json) identifies D1's
DOS-linked `AUTORUN` file, the canonical payload offset/length, image identity
and known local callbacks. It uses directory/sector links, without relying on
PicoBoot's private state. Once selected, this reader owns the stream and never
returns to the outer loader. If D1 is absent or unrelated, it restores the INIT
caller and lets a direct emulator XEX loader continue normally. Selection is
independent of the native SYS drive.

The split and ATR backends share one bounded streaming XEX parser and one
boot serial engine. Repeated `$FFFF` markers, sector-boundary headers, exact
24-bit EOF, INITAD clearing and guarded RUNAD are enforced. Failed frames stay
private. Timeout, BREAK, malformed images, invalid links and source changes
after monitor return stop with a diagnostic and require reset.

The engine runs in emulation mode using the pinned ROM's serial IRQ vectors.
It temporarily sets CRITIC, masks serial IRQs while publishing/restoring the
six-byte vector set, and keeps ROM VBI active. A VBI can see a partially changed
serial vector set only while serial IRQs are disabled; CRITIC prevents deferred
OS callbacks from starting I/O. Descriptors are complete before IRQs can use
them. Each transaction has a finite 100-PAL-frame deadline. It restores the
saved vectors, POKMSK, SKCTL shadow, CRITIC, COMMAND control and caller flags;
POKEY audio/clock registers return to the cold-launch silent baseline rather
than being read through write-only aliases.

The `$3F` request changes the peripheral's speed after replying. Recovery tracks
that transition: up to three standard-rate STATUS attempts exercise the pinned
firmware's two-bad-frame reset. Loading continues only after a verified reply;
uncertain speed stops with `$CB`. A device unable to meet the native profile
stops with `$CC`. Corrupt frames are not silently retried as payload.

Generated local loader/OF816-copy callbacks retain fast ownership. Other
callbacks, including interactive OF816, receive a confirmed standard-speed bus
and the restored OS serial environment. On return the split reader verifies
the selected prefix identity, preserves its partial sector and renegotiates.
Before native entry it finishes all serial work and restores vectors, so no
boot handler points into storage reused as Task stacks. The peripheral remains
at the native rate; the native driver programs its own UART clock before the
first request.

The complete reader reservation is 8,192 bytes, including guards, buffers,
alignment and unused capacity. The split profile borrows idle Task stack pools
until native initialization; the ATR already reserves the same arena. Runtime
fixed/root/kernel/per-public-Task/idle growth is **zero bytes**. Actual placement,
timings and development scope are recorded in the
[implementation record](../history/boot-only-fast-sio.md).

## Bootable system ATR

The SIO `--bootable-atr` profile cold-boots one 8,192-sector SDFS 2.1 ATR with
256-byte data sectors and three short boot sectors. Its first stage loads the
ordinary, contiguous BOOT.LDR file from a generated locator. That reader follows
the root EXEC816.XEX file's maps and exact 24-bit length, including fragmentation,
then performs the existing XEX/OF816/INITAD/RUNAD sequence. The monitor does not
implement a second filesystem or load a separate kernel by itself.

[boot-atr.json](../../abi/boot-atr.json) defines the boot layout and locator.
BOOT.LDR and EXEC816.XEX are ordinary allocated, protected files. Their final
bytes, allocation, locator and filesystem are independently read back after
construction. The reader rejects malformed transport and live-reader overlap;
the existing native loader owns manifest/extent/decompression validation.

Boot sectors use $3000–$317F before OF816; the reader owns $4000–$5FFF until
native entry. These reuse native stack storage before Task initialization.
Runtime reservations grow by **0 fixed/root/kernel/per-public-Task/idle bytes**.
The boot report supplements the native memory map with **8,192 additional live
loading-phase bytes**, including all guards, alignment and unused capacity;
the first-stage range is already within the loading kernel-stack reservation.
Native initialization/runtime retain their existing reservations. See the
generated boot report and [development record](../history/bootable-system-atr.md)
for phase unions, per-pool borrowing and image-specific accounting.

The boot serial transaction completes before each callback and final native entry. No reader
Task, ROM SIO fallback or private kernel operation survives into Exec. The
reader retains its partially consumed sector and file position through OF816,
which keeps the five-second countdown and interactive return. The loader's
final progress write finishes before native display snapshot/ownership.
Native EXIT restores the OS display and parks rather than returning into
retired reader storage. The boot header's DOSINI selects ROM cold start.

The combined disk mounts once as writable SYS/D1. WORK: is a directory assign;
see [SYS](sys-volume.md). The [guide](../guides/bootable-system-atr.md) covers
launching, saved data and error messages. Development evidence and transport
limits are in the [record](../history/bootable-system-atr.md).
