# Fixed-image boot loading

[Reference](README.md) · [Platform and memory budget](platform.md#bank-zero-memory-budget)

The generated XEX loads the bank-zero bootstrap, resident adapter and manifest,
then calls setup through INITAD. OF816 runs next, before the upper-RAM kernel
payload. Its five-second autoboot or `EXEC816` returns to the reader with RTS.
Subsequent INITAD callbacks expand the kernel into its final addresses; the
guarded RUNAD enters it only after every extent is complete. The Atarimax
wrapper feeds the same XEX records to the same loader.

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
fit the existing 4,608-byte loader reservation; no upper-RAM input scratch or
new fixed/per-Task bank-zero reservation is required. Expanded kernel RAM use
is unchanged. Loader/staging retirement follows the existing startup phases;
OF816 return does not retire them early. Boot settings and earlier screen text
remain intact, and progress counts expanded bytes.
The progress accumulator emits four 16 KiB dots for a 64 KiB carry before
processing the stored remainder, so maximum-size blocks retain exact rounding.

See the [implementation measurements](../history/loader-compression.md) for
actual artifact sizes, decoder times and development-check scope.
