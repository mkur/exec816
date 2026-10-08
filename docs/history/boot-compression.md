# Boot image compression experiment

[Historical records](README.md) · [Current loading contract](../reference/platform.md#bank-zero-memory-budget)

This preserves the initial host-only experiment at `ecb2a59`. The subsequent
[compressed-loader implementation](loader-compression.md) records real bootable
images and emitted-code speed; today's [loading contract](../reference/boot-loading.md)
uses streaming input rather than an upper-RAM scratch area.

LZ4-HC level 12 with independent 32 KiB output blocks reduces the current
standard resident payload by **67.71%**, and VBXE by **66.50%**. This is enough
to justify a small native decompressor experiment before changing the loaders.
Full measurements, build hashes and reproduction arguments are in the
[evidence record](../development/boot-compression.json). The experiment tool is
[measure_boot_compression.py](../../tools/measure_boot_compression.py).

This is a host experiment on existing emitted images, not an implementation of
compressed boot. No 65816 decompression time or cold-boot improvement was
measured. Production XEX/cartridge files, OF816 and loaders are unchanged.

## Inputs and method

The two input revisions are the current branch baseline `e74c2b0`, including
the optional desktop libraries, and preview.3 `f7ea9b0`, which removes those
dependencies from the ordinary shells. Both have standard and VBXE builds.
Their optimized compiler pin matches `toolchain/actionc.json`; there is no
compiler override. The evidence records the full revisions and image hashes.

The tool normalizes the actual `program.a816.json` extents using the existing
banked-image rules. It coalesces adjacent regions of the same kind, retains
gaps and code/data distinctions, and splits at bank boundaries. It also checks
that the OF816 XEX ends with the exact staging records for that image.

Each image is measured with 1, 16, 32 and 64 KiB maximum output blocks, using
LZ4, LZ4-HC level 12 and raw DEFLATE level 9. Existing extent normalization
limits a single extent to 65,535 bytes, so the 64 KiB setting never requires a
65,536-byte length. Every block starts with an independent compression history.
Blocks that do not shrink are stored raw. Zero-fill extents carry metadata only,
as they already do in the current loader.

The experiment writes nonbootable `EBC1` archives under `build/`, using a
16-byte archive header and 12 bytes per block for address, kind and lengths.
These are measurement overheads, not a public ABI proposal. Every saved archive
is read back and decompressed with the host libraries, then compared with the
original addresses, kinds, lengths and bytes. All **48 cases passed**.

## Results

The following sizes are exact bytes. Compressed columns include experiment
headers and raw-block fallbacks, with a maximum output block of 32 KiB.

| Image | Resident payload | LZ4 | LZ4-HC12 | DEFLATE9 |
| --- | ---: | ---: | ---: | ---: |
| Current standard | 856,575 | 335,665 | 276,599 | 223,692 |
| Current VBXE | 899,390 | 362,916 | 301,328 | 243,594 |
| Preview.3 standard | 728,653 | 287,293 | 237,163 | 191,741 |
| Preview.3 VBXE | 771,476 | 313,833 | 260,970 | 210,888 |

Increasing the block size improves LZ4-HC compression noticeably:

| Current image | 1 KiB blocks | 16 KiB blocks | 32 KiB blocks | 64 KiB blocks |
| --- | ---: | ---: | ---: | ---: |
| Standard | 494,133 | 304,357 | 276,599 | 252,991 |
| VBXE | 526,393 | 328,642 | 301,328 | 277,551 |

Independent compression at the current 1 KiB staging granularity loses many
matches. Compression blocks should therefore span several transport records.
Moving from 32 to 64 KiB saves another 23,608/23,777 bytes on the current
standard/VBXE images. A 32 KiB input scratch area also has a smaller worst-case
requirement than a 64 KiB area, making 32 KiB a reasonable starting point.

## Boot-file size model

The model preserves every byte outside the native image's staging records,
including OF816, platform setup, manifest and final RUNAD. It replaces the
native records with the experiment archive streamed through the existing
1 KiB staging granularity. That costs 18 bytes per transport record: eight
record bytes, four XEX segment-header bytes and six INITAD segment bytes.

The sizes below **exclude new decoder code and changes to loader setup**.
They are projections, not generated bootable XEX files. They do include the
experiment archive's metadata and the modeled staging overhead.

| Image | Existing OF816 XEX | Modeled XEX, LZ4-HC12/32 KiB | Saving |
| --- | ---: | ---: | ---: |
| Current standard | 903,505 | 312,873 | 590,632 |
| Current VBXE | 947,374 | 338,098 | 609,276 |
| Preview.3 standard | 773,181 | 272,655 | 500,526 |
| Preview.3 VBXE | 817,074 | 296,956 | 520,118 |

The current cartridge wrapper stores the XEX in a fixed 1 MiB ROM. Compression
would increase its available payload space; the resulting `.bin`/`.car` file
would still have the cartridge format's fixed size. Runtime image size and
RAM consumption would remain unchanged after expansion.

## Follow-up

Start with raw LZ4 blocks produced by the high-compression host encoder. LZ4
and LZ4-HC use the same block format and decoder; the extra compression effort
happens on the development machine. See the
[LZ4 block format](https://github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md)
and [HC interface](https://github.com/lz4/lz4/blob/dev/lib/lz4hc.h).
DEFLATE saves more bytes here, but its native decoder cost and throughput have
not been evaluated by this experiment.

The next executable slice should decompress these real blocks in a focused
65816 fixture, compare every output byte, and measure CPU cycles. Keep OF816
first, use temporary upper-RAM staging and write to the existing final image
addresses. Only after that evidence should compressed records be added to the
ordinary XEX loader and reused by the cartridge wrapper.

Validation scope: host development checks and the 48 actual-image round trips.
No emulator or release qualification matrix was run. Reserved bank-zero change
for this experiment is **0 fixed bytes and 0 bytes per Task**; runtime and
loading reservations are untouched.

## Reproduce

Install liblz4, then run against the retained release build directories:

```sh
python3 tools/measure_boot_compression.py \
  --input current-standard=build/release-preview-2026-10-08-e74c2b0/standard \
  --input current-vbxe=build/release-preview-2026-10-08-e74c2b0/vbxe \
  --input preview3-standard=build/release-preview-2026-10-08-shell-without-desktop/standard \
  --input preview3-vbxe=build/release-preview-2026-10-08-shell-without-desktop/vbxe \
  --output build/boot-compression-experiment
```

Use `--lz4-library /path/to/liblz4` if automatic discovery is unavailable.
The tool needs the recorded build directories, not just the distributed ZIPs.
Compressed archives and the complete run record stay in the development output
directory; they are not demo distribution assets.
