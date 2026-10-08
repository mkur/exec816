# Compressed kernel loader measurements

[Historical records](README.md) · [Current loading contract](../reference/boot-loading.md)

The streaming LZ4 loader reduces the full standard OF816 XEX from **903,505 to
314,057 bytes**, and VBXE from **947,374 to 339,432 bytes**. The actual emitted
decoder takes **4.38/4.68 seconds** respectively on the pinned 8x PAL machine
(14.18758 MHz nominal CPU clock). These replace the initial
[host-only projections](boot-compression.md).

The implementation and measurements are on `experiment/boot-compression`,
following host experiment `ecb2a59`. Exact pins, input hashes, artifact sizes
and selected test results are in [loader-compression.json](../development/loader-compression.json).

## Implementation

Host liblz4 1.10.0 produces HC12 raw blocks with independent history and up to
32 KiB output. Each block is streamed through the existing 1 KiB staging area;
the native decoder can pause anywhere in its input. Indexed forward copies
handle overlapping matches. Unprofitable blocks remain RAW, and zero-fill
retains its existing representation.

Decoding stays in emulation mode, preserving the OS reader's live stack and
interrupt environment. There is no native-mode transition, DP scratch, interrupt
masking or upper input scratch bank. A first optimization removed repeated
source-operand setup from metadata-byte reads; the standard 8x measurement
improved from 4.75 to 4.38 seconds. No compiler/runtime primitive was changed.

The original optimized kernels from `e74c2b041ec7b57dd6573a633b90d957baddbb73`
were repackaged with `build_demo.py --refresh-loader`. Their native image bytes,
compiler pin `6510ea1d148c93edea595be8a5afa9630d5a75e3` and runtime memory ABI
are unchanged; no compiler override or full kernel recompilation was used.
OF816 remains first, including its five-second autoboot, settings and screen
preservation. Cartridges reuse the same compressed XEX.

## Sizes and RAM

Sizes are exact bytes; XEX sizes include OF816, the new loader and all transport
overheads.

| Image | Original XEX | Compressed XEX | Saved | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Standard | 903,505 | 314,057 | 589,448 | 65.24% |
| VBXE | 947,374 | 339,432 | 607,942 | 64.17% |

| Image | Expanded nonzero payload | Stored payload, including block headers | Loader before | Loader after |
| --- | ---: | ---: | ---: | ---: |
| Standard | 856,575 | 276,107 | 1,674 | 2,702 |
| VBXE | 899,390 | 300,788 | 1,706 | 2,734 |

The complete loader grows by 1,028 bytes, inside its existing 4,608-byte
reservation. Remaining capacity is 1,906/1,874 bytes. Reserved bank-zero deltas
are **0 fixed bytes and 0 bytes per Task**, counting guards, alignment and
unused capacity. Expanded kernel RAM use is unchanged. No production upper-RAM
input buffer is allocated. Atarimax BIN/CAR images remain the format's fixed
1 MiB size; the smaller XEX leaves more cartridge payload capacity.

## Decoder speed

Measurements sum actual decoder call entry/exit observations in the pinned
emulator. They include OS interrupts and Atari bus stalls, and exclude record
admission, progress output, XEX transport and OF816's countdown. Throughput uses
only output bytes from compressed blocks, excluding RAW and zero-fill bytes.

| Image | 14.18758 MHz decoder | Throughput | 1.7734475 MHz decoder | Throughput |
| --- | ---: | ---: | ---: | ---: |
| Standard | 4,382.3 ms | 190.9 KiB/s | 50,726.3 ms | 16.5 KiB/s |
| VBXE | 4,678.6 ms | 187.7 KiB/s | 54,143.1 ms | 16.2 KiB/s |

The observed native-loading phases with Altirra's host XEX reader are
4,403.4/4,751.6 ms at 8x and 50,965.2/54,995.1 ms at 1x. These are not floppy
boot timings. Compression saves about 590/608 KB of transport, but physical SIO
boot savings and physical accelerator timings were not measured. The decoder
is usable at the normal accelerated configuration; its cost is substantial at
the base Atari clock. The earlier approximate 65816 block-copy estimate was
not a measurement of this streaming parser.

## Development checks

- Host suite: 400 tests passed, including independent compressed transport
  reconstruction, bank/offset preservation, RAW/zero fallback and orphan rejection.
- Twelve emitted decoder cases: maximum output, multi-record input, byte
  fragments, overlapping matches, bank boundaries, RAW fallback, malformed
  offsets/lengths and final-literal errors. Destination guards remain intact.
  The context case restores A/B, X/Y, D, DBR, flags and stack position with real VBI.
- Four OF816 return cases: two page-one depths, manual/autoboot paths and masked
  caller IRQ state; live frames and context remain intact.
- Eight progress/failure cases: one byte, exact/remainder 16 KiB, 32 KiB compressed
  output, zero-fill, malformed encoding, incomplete input and MEMLO rejection.
- Actual standard/VBXE expanded images match all 857,138/909,705 bytes, including
  zero-fill, after OF816 returns. Snapshot diagnostics run after timing and restore
  their existing scratch; their temporary NMI masking is not interrupt evidence.
- Standard/VBXE XEX shell smoke and old-standard/new-VBXE Atarimax boot checks:
  five-second autoboot, settings, disk commands, ownership/stack/domain guards and EXIT.

Test fixtures were updated for RAM startup diagnostics, supported COPY directory
destinations and compressed input truncation. A 2 KiB output fixture now fits
inside its first compressed record, so retaining that whole record cannot test
an incomplete load. MEMLO rejection uses the generated limit plus one.

This is development-tier evidence on the pinned AltirraOS 65816 configuration.
No full release matrix, XLOS compatibility claim or physical-hardware qualification
was made. Assembly changes do not introduce compiler-facing behavior; the reused
resident kernels are optimized builds, with no new raw-NIR matrix.

## Reproduce

Install shared liblz4, retain the matching native development builds, then:

```sh
python3 tools/build_demo.py --refresh-loader --output build/compressed-loader/standard
python3 tools/build_demo.py --refresh-loader --output build/compressed-loader/vbxe
python3 tools/test_loader_compression.py --output build/compressed-loader/native-cases
python3 tools/measure_loader_compression.py \
  --bundle build/compressed-loader/standard --output build/compressed-loader/standard-timing
python3 tools/measure_loader_compression.py \
  --bundle build/compressed-loader/vbxe --output build/compressed-loader/vbxe-timing
```

Both clock selections run the same decoder; only the recorded clock multiplier
changes. The first selection verifies the full image, after timing. Keep logs,
manifests and results in the development directory. Demo ZIPs contain only boot
files, disks, guides, licenses and checksums; add cartridge files using the
[normal packaging command](../contributing/building.md#build-the-demo).
