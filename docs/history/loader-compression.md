# Compressed kernel loader measurements

[Historical records](README.md) · [Current loading contract](../reference/boot-loading.md)

The initial measurements below describe 32 KiB blocks at `53e1f63`. The
[64 KiB follow-up](#64-kib-follow-up) switches the current default to 65,535 bytes.
The [upstream desktop integration](#upstream-desktop-integration) keeps the shared
GEM runtime in that compressed image.

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
Check out `53e1f63` to reproduce the original 32 KiB default; current builds use
the larger block limit below.

## 64 KiB follow-up

The commands branch now uses up to **65,535 output bytes** per block. This is
the largest nonzero 16-bit length, retaining the existing wire header and
bank-bounded extents. A full 65,536-byte extent still splits into 65,535 plus
one byte. Staging remains 1 KiB, with no upper input scratch or new fixed/per-Task
bank-zero reservation. Removing the earlier 32 KiB admission check more than
pays for progress-carry handling: the loader is **five bytes smaller**.

| Image | 32 KiB XEX | 64 KiB XEX | Further saving | Decoder before → after, 14.18758 MHz |
| --- | ---: | ---: | ---: | ---: |
| Standard | 314,057 | 290,008 | 24,049 bytes | 4,382.3 → 4,274.1 ms |
| VBXE | 339,432 | 315,240 | 24,192 bytes | 4,678.6 → 4,579.5 ms |

Stored payload including block headers falls from 276,107 to 252,603 bytes
for standard (**8.51%**) and 300,788 to 277,123 for VBXE (**7.87%**).
Decoder time improves by **2.47%/2.12%**. Its observation scope and emulator/ROM
pins are the same as the original accelerated measurements. The expanded
native images and compiler pin are unchanged. The base 1x clock and physical
SIO boot were not remeasured in this follow-up.

Progress accumulation handles the seventeenth carry bit by emitting four dots
for its 64 KiB contribution, then retaining the ordinary remainder. Two emitted
cases cover exactly 65,536 total bytes and a nonzero remainder after carry.
The thirteen decoder cases include maximum output and a 33,000-byte match
offset; all pass with destination guards and the live caller/VBI checks intact.
All ten feedback/failure cases and 400 host tests pass. Full-image checks after
OF816 return verify 857,138/909,705 bytes, including zero-fill. Generated memory
definitions and distribution checksums match.

This remains development-tier evidence. No compiler-facing behavior changed,
and no raw-NIR, full release, shell-command or cartridge matrix was repeated.
Exact source, input, artifact and result hashes are in
[loader-compression-64k.json](../development/loader-compression-64k.json).

The follow-up artifacts are under `build/compressed-loader-64k`. Reproduce the
decoder and accelerated measurements with:

```sh
python3 tools/test_loader_compression.py --output build/compressed-loader-64k/native-cases
python3 tools/test_of816_loading.py --bundle build/compressed-loader-64k/standard \
  --output build/compressed-loader-64k/feedback --case feedback
python3 tools/measure_loader_compression.py --bundle build/compressed-loader-64k/standard \
  --output build/compressed-loader-64k/standard-timing --multiplier 8
python3 tools/measure_loader_compression.py --bundle build/compressed-loader-64k/vbxe \
  --output build/compressed-loader-64k/vbxe-timing --multiplier 8
```

## Upstream desktop integration

The merge of upstream `901ff53` into the commands branch retains its desktop,
menu, application and renderer changes. The shared C runtime and lookup tables
stay in the compressed boot image, replacing upstream's `GEMSYS.BIN` bootstrap.
Panel, counter, Files and calculator remain independent disk-loaded APPs.
Current behavior is described by the [platform contract](../reference/platform.md)
and [C loading contract](../reference/c-program-loading.md).

The fresh optimized GEM desktop contains 158,900 initialized C bytes, all
loaded before native startup. Its expanded initialized payload is 1,150,756
bytes; stored payload is 386,143 bytes. The full OF816 XEX is **426,676 bytes**,
leaving **605,515 bytes** of Atarimax payload capacity. Both cartridge formats
are generated from that same XEX.

The 8x PAL decoder takes **5.875 seconds**, including interrupts and bus stalls
but excluding XEX transport, progress output and application loading. After
OF816 handoff, all 1,164,539 image bytes across 60 extents match, including
zero-fill. The compiler remains at its clean recorded pin without an override.

Fixed, per-public-Task and private-idle bank-zero reservation deltas are **0**
relative to the local parent, counting guards, alignment and unused capacity.
All loading/runtime reservation totals match that parent. The loader occupies
2,857 bytes of its existing 4,608-byte capacity. Removing the shared component
loader also removes its extra 512-byte upper arena allowance; desktop globals
use 4.5 KiB for shell and menu state.

Development checks pass: 420 host tests, 16 ABI generator checks, one generated
memory check, 13 emitted decoder cases, six optimized SIO deadline cases,
raw/optimized C bridge probes and one guarded interrupt-return boundary. The
extracted XEX and new Atarimax cartridge each pass five-second OF816 autoboot,
three loaded GEM applications, counter progress, shell/disk and RAM commands,
guards, ownership cleanup and EXIT. This focused smoke does not repeat the full
desktop/menu/Files/calculator walkthrough, old/manual cartridge route, 1x timing
or release qualification. Exact inputs and selected scope are recorded in
[upstream-compression-merge.json](../development/upstream-compression-merge.json).

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_demo.py --gem-desktop \
  --output build/upstream-compression-merge/gem-desktop
python3 tools/test_gem_desktop_boot.py --bundle build/upstream-compression-merge/gem-desktop --smoke
```
