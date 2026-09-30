# HELLO payload and loader breakdown

The next small optimization should be a single pass through the provider
manifest in [PROGRAMPROVIDERS.Resolve](../../lib/dos/programproviders.act).
Import resolution takes **239/268 ms** with the prime worker stopped/active.
HELLO has five imports; the resolver parses all 14 provider entries for each
import, visiting 70 entries. This is avoidable repeated parsing with a bounded
change and no format, public ABI or compiler change.

The largest elapsed component overall is the **modeled disk/device wait**:
1.62/1.53 seconds during payload reading. Serial transmission itself takes
0.475 seconds. These measurements explain why nominal 57.6 kbaud does not make
the whole load approach the file's wire time.

This follows the [sector-copy measurement](sector-copy-cost.md). It adds only
host analysis and passive PC markers; production code, the compiler pin and
the play image are unchanged. Full results and hashes are in the
[evidence record](../development/loading-breakdown.json).

## Payload read

Same S3 diagnostic XEX as the S4 measurements, Exec baseline `3d8ca49`, pinned
actionc `47cd55b`, AltirraOS 65816 ROM, PAL 8x CPU, SDFS 720×128-byte media,
GENERIC57600, accurate disk timing enabled, SIO patching/burst/random delay
disabled. The [platform pin](../../toolchain/altirra-shell-paced.json) and the
evidence record fix the actual binaries and configuration.

There are **20 transfers** inside the payload phase: file map sector 69,
then data sectors 70–88. The 2,359-byte file occupies 18 full sectors and a
55-byte tail, but the final sector is still transferred as 128 bytes. Each
transfer sends five command bytes and receives ACK, COMPLETE, 128 data bytes
and a checksum: 2,720 serial bytes in total, including the map read.

The following rows partition the whole payload phase. Times are milliseconds.

| Component | Prime stopped | Prime active |
| --- | ---: | ---: |
| Device wait: ACK end to COMPLETE start | 1,616.712 | 1,527.935 |
| Serial wire time, including command/status/checksum bytes | 474.894 | 474.894 |
| Protocol pacing and inter-byte gaps | 51.638 | 51.775 |
| Exec work/scheduling outside transactions | 351.534 | 417.018 |
| **Payload phase total** | **2,494.779** | **2,471.622** |

The last row of components separates into:

| Outside-transaction interval | Prime stopped | Prime active |
| --- | ---: | ---: |
| Phase start to first COMMAND assertion | 18.991 | 25.912 |
| Checksum end to next COMMAND assertion, 19 gaps | 320.447 | 377.673 |
| Final checksum end to phase end | 12.096 | 13.433 |

The previously reported 18 data-to-data gaps are a subset of this: they total
297.179/353.848 ms. The extra gap follows the map read. Copying is already
inside these intervals and must not be added again.

Protocol pacing includes command setup/hold, acknowledgement turnaround,
COMPLETE-to-data delay and small gaps between serial bytes. TX bytes are
contiguous. Observed bit periods are 30 base-clock ticks for TX and 31 for RX;
the analyzer uses those actual periods rather than assuming identical nominal
baud rates in both directions. Command and data checksums are checked.

The pinned emulator's `disk.cpp` implements seeking, rotational position,
sector reading and post-read processing before COMPLETE; `WarpOrDelay` retains
those delays with accurate timing enabled. `diskprofile.cpp` gives this profile
a 288 RPM disk model. Their source hashes match the platform pin. The trace
measures the aggregate ACK-to-COMPLETE wait; it does not isolate pure rotation
from seek/read/device processing. It also does not characterize a flash-backed
SIO device. Faster Exec work can change which rotational position is reached,
so removing CPU work does not imply an equal end-to-end saving.

## Loader after the read

The following is a nonoverlapping partition of the actual `PROGRAM.Load`
call, after DOS.Close and before the loaded command is started. All values are
elapsed milliseconds, including interrupts and other Tasks.

| Component | Prime stopped | Prime active |
| --- | ---: | ---: |
| Format/profile validation | 223.161 | 250.019 |
| Resolve system/library imports | 238.621 | 268.375 |
| Image record and text/data/BSS allocation | 6.139 | 6.927 |
| Check relocation placement | 60.629 | 67.123 |
| Copy text and data | 71.602 | 80.040 |
| Apply relocations | 62.222 | 96.567 |
| Release temporary validation records | 8.742 | 12.939 |
| Result publication and other caller instructions | 0.857 | 0.865 |
| **PROGRAM.Load total** | **671.972** | **782.856** |

Metadata allocation during validation belongs to validation, not the image
allocation row. File-staging allocation/free are outside this call. Relocation
checking and application are separate passes with different responsibilities;
the table is not a proposal to remove a validation pass.

Within stopped-worker validation, header/import-name parsing takes 29.718 ms,
the first relocation-stream pass 23.980 ms, exports 9.479 ms, and the native
descriptor 156.790 ms. The descriptor includes routine checks (11.561 ms),
object checks (11.159 ms), import contracts (45.784 ms) and relocation proof
checking (84.831 ms). These nested figures are already included above.

The old VBI counters still report payload 2.48/2.46 seconds and loading
0.66/0.78 seconds. The passive instruction markers give finer boundaries:
the full relocation probe phase is 672.144/783.035 ms, including probe/call
setup. Quantization to 20 ms PAL ticks explains the differences; the same-image
phase counts have not regressed. Open-to-prompt remains 3.88/4.16 seconds.

## Recommended implementation slice

Change only the resolver's traversal: parse and validate each provider entry
once, then compare it with the program's imports. For this HELLO image that
reduces provider-entry parsing from 70 visits to 14. Continue scanning the
entire manifest and preserve missing/duplicate-provider rejection, bounds,
address/extent checks and exact ABI-contract matching. No persistent provider
cache or new ABI is needed for this slice.

In the stopped run, the 70 provider-name String calls take 106.305 ms; reading
the repeated extent and contract-length fields takes another 70.841 ms. Name
matching takes 7.848 ms and the five matching contract comparisons take
10.573 ms. This points to repeated parsing as the first target. The full
239 ms resolver cost is not a promised saving.

Across the whole loader, 587 calls to `O65READ.U32` take 297.767/336.474 ms
inclusively. That is a nested diagnostic, not an additional cost. Wider scalar
reads currently decompose into smaller reads with repeated cursor checks.
Optimizing those helpers may be useful later, with explicit malformed-input
semantics and tests. It is broader than eliminating the repeated manifest scan.

After the resolver change, run focused raw/optimized provider success/error
cases and repeat this same-profile HELLO measurement. Sector copying remains
a separate follow-up; this measurement implements neither optimization.

## Validation and reproduction

The [host analyzer](../../tools/measure_loading_breakdown.py) decodes JSL call
sites from the actual retained image using the pinned compiler's decoder.
It records call and return PCs without adding guest instructions, pairs calls
in the caller's direct-page domain, and checks the expected HELLO success path.
Each hardware transaction and payload partition reconciles to its complete
elapsed interval. Nested calls are reported separately, avoiding double counts.

Two new replays run HELLO, DIR and EXIT with the prime worker stopped/active.
Both pass bounded completion, stack/domain guards and OS ownership restoration.
Their relative VBI phase ticks, transfer counts and all 20 payload transaction
timings and gaps exactly match both the earlier S4 traces and retained untraced
replays with identical inputs. No new images were compiled. The existing guest
load probes remain in all diagnostic runs; this is not a measurement of the
uninstrumented production image.

The development host suite passes **212 tests**, including six new cases for
partition reconciliation, partial/corrupt serial frames, wrong baud/overlap,
map/data selection and repeated/nested call accounting. Full release and
physical-hardware qualification were not run.

```sh
python3 tools/measure_loading_breakdown.py \
  --bundle build/development/sio-driver/s3-integration/bundle \
  --output build/development/loading-breakdown/stopped
python3 tools/measure_loading_breakdown.py \
  --bundle build/development/sio-driver/s3-integration/bundle \
  --prime-worker active --output build/development/loading-breakdown/active
```

Add `--analyze-only` to reuse a saved trace. Output includes disassembly,
markers, the original harness results and `breakdown.json`. About 11 MiB of
development artifacts were added; existing images and traces were reused.

Reserved bank-zero delta: **0 fixed bytes and 0 per Task**, including guards,
alignment and unused reserved capacity. There are no guest memory-map changes.
