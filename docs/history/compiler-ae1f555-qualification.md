# Compiler ae1f555 qualification

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

Status: qualified and pinned, 2026-09-22. The
[qualification record](../qualification/compiler-ae1f555.json) binds the compiler,
inputs, test results and measurements to their hashes. All 19 required hosted
groups pass; the one pre-existing host-test evidence mismatch is recorded below.

The candidate is actionc `ae1f555e77d0ae6caffbfc7453cbf06e3d098bee`, checked out
cleanly at `build/compiler-ae1f555`. The baseline is
`c2268b7c742958bd9078c4e11ef9b10f3b7a0221`. This qualification concerns the
existing Exec816 kernel, MyDOS and native console; DOS console streams remain
planned work. The developer's separate compiler working tree is untouched.

## Contract and integration changes

The physical ABI JSON and assembly definitions are byte-identical between the
two revisions. Register/argument conventions, saved context, 64-byte compiler
scratch, direct-page ownership and interrupt reserves remain unchanged.
The candidate uses image format v3. Its temporary maps distinguish stack and
direct-page homes, and different temporaries may share a stack home when their
live ranges permit it.

The hosted packager now takes an explicit compiler contract for candidate
builds and records it in build provenance. The default still uses the repository
pin. It accepts only the requested image version and independently checks v3
frame extents, incoming displacements, temporary identities/widths, permitted
direct-page homes, call restrictions and local stack accounting. Typed liveness
and instruction-selection proofs remain compiler-owned; a final image map
cannot reconstruct them. Bounds and placement checks are retained.

Candidate tests reuse the existing native fixtures and timing oracles through
`tools/qualify_compiler.py`. Console concurrency, TX and recovery runners accept
the explicitly selected toolchain. No kernel, driver, scheduling policy,
hardware deadline or stack reservation is changed to obtain a pass.

The promoted pin also builds normally without an override and produces identical
image and XEX bytes to the candidate smoke build. The historical parser-bundle
test now checks the compiler revision in its original block-I/O record.

## Compiler checks

The clean candidate passes:

- 3,379 compiler tests, with 27 ignored and no failures, including NIR snapshots.
- All 51 NIR sweep fixtures.
- All 111 native execution tests in each of debug and release, with two ignored
  optional tests per profile. The profiles produce 648 identical saved artifacts
  and identical compiler/fixture input hashes.
- Eight focused package/frame-map tests, including invalid scratch locations,
  DP values across calls, bad frame accounting and mismatched image versions.

Native execution includes arithmetic, aliasing, calls, pointer/scalar DP,
allocation pressure, frame guards and interrupted task/domain restoration.
It uses the compiler suite's pinned independent VM and status-timing patch.
These checks do not by themselves qualify AltirraOS integration.

Compact builds use `CARGO_INCREMENTAL=0`, `CARGO_PROFILE_DEV_DEBUG=0` and
`CARGO_PROFILE_TEST_DEBUG=0`. Disabling host debug information saves disk space;
both raw and optimized guest code are still tested. The qualified hosted compiler
binary is built with the debug host profile.

## Hosted matrix

All required candidate groups pass:

| Group | Modes and scope |
| --- | --- |
| OS boundary | Raw/optimized entry with IRQ enabled/disabled, all eight NMI transition checkpoints, POKEY timer IRQ, ROM console bounds and recursive stack failure on the original platform pin. |
| Kernel regressions | Raw/optimized heap, ports, queued I/O, signals, 261 created Tasks through slot reuse, named/shared Lists and bank-3 loading. |
| DOS | Raw/optimized concurrent file calls, locks/directories, two-mount lifetime and failed-mount retry. |
| Console lifetime | Raw/optimized normal close, allocation rollback, clean-input reopen, both console/SIO claim orders, combined retirement and unsafe `$FF93` retention. |
| Integrated FASTEST125 | Raw/optimized 128/256-byte media, eight simultaneously live public Tasks plus idle, physical keys and scrolling output, observed timing and identical-image unobserved replay. |
| Other placement/profile | Raw/optimized bank-3 functional concurrency and the established optimized STOCK810 regression. |
| Serial TX and recovery | Raw/optimized TX timing/replay and six real peripheral error cases with the configured console. |
| Oracle controls | Deliberately missing keyboard observation and late SERIN service must fail their existing checks. |

The 256-byte fixture verifies the complete 70,003-byte single DOS Read; the
128-byte fixture contains 777 bytes and returns a short read. Keep that
distinction when comparing throughput. Preserve the approximately 78.9423 µs
FASTEST125 byte deadline, 100 µs alarm/watchdog bound, phase limits and existing
per-case completion bounds. There is no baud downgrade or successful-I/O sleep.

## Measurements and limits

Both 128-byte integrated cases and their replays pass. Their task and platform
source inputs match the baseline; the packager differs to support image v3.

| Measurement | Baseline raw | Candidate raw | Baseline optimized | Candidate optimized |
| --- | ---: | ---: | ---: | ---: |
| Executable bytes | 691,708 | 497,535 | 644,774 | 470,247 |
| Observed reader stack bytes | 760 | 242 | 610 | 218 |
| Reader space above interrupt reserve | 8 | 526 | 158 | 550 |

Code shrinks by 28.1% raw and 27.1% optimized. The raw image releases three
whole upper-RAM banks (192 KiB) for allocation. The stack figures describe
observed complete call chains, not a proof of arbitrary application call depth.
Frame/domain guards and the 256-byte interrupt reserve remain enabled.

The complete loading/runtime bank-zero maps are identical: 57,232/61,536 bytes
including OS. Fixed reservation delta: **0 bytes**. Per-Task reservation delta:
**0 bytes**, including guards, alignment and unused capacity. Smaller generated
frames do not themselves release reserved stacks or qualify twelve/sixteen Tasks.

Both 256-byte media runs and their replays also pass, verifying all 70,003 bytes.

| Full-read observation | Raw | Optimized | Existing bound |
| --- | ---: | ---: | ---: |
| Maximum RX service | 72.74 µs | 72.18 µs | 78.94 µs |
| Maximum TX refill | 68.79 µs | 65.41 µs | 78.94 µs |
| Maximum alarm service | 74.85 µs | 68.65 µs | 100 µs |
| Maximum watchdog service | 90.15 µs | 89.02 µs | 100 µs |
| DOS Read duration | 48.755 s | 48.659 s | Existing completion bound |
| DOS Read throughput | 1,435.8 B/s | 1,438.6 B/s | No new performance threshold |

These are guest-time observations with mechanical drive timing, concurrent
Tasks and console traffic. Read timing excludes Open, payload verification and
cleanup. Neither mode has an RX/TX deadline miss or TX gap in these runs.

The full host test run reports 127 passes and one pre-existing
failure: `test_sio_sector_record.SectorTests.test_published_gate` compares the
historical sector record with today's `platform/altirraos/sio.s`. The current
source hash equals the source at Exec816 `bacfe92984fa0f36afaa675e3c393b46de700c49`
and differs from that older record. This mismatch predates the candidate and
the file is unchanged by this migration. Retain the failure explicitly; do not
rewrite old evidence or treat it as a new compiler regression.

## Reproduction

The candidate contract is the ordinary compiler pin JSON with its revision set
to the exact candidate SHA, image format set to 3 and the old local-bundle entry
removed. During qualification it lived at
`build/compiler-qualification-ae1f555/candidate.json`; it now matches
[toolchain/actionc.json](../../toolchain/actionc.json).

For example, from the Exec816 root:

```sh
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
python3 tools/qualify_compiler.py \
  --compiler-dir build/compiler-ae1f555 \
  --compiler-pin toolchain/actionc.json \
  --suite concurrent --case raw --sector-size 128 --trace \
  --output build/compiler-qualification-ae1f555/target128-raw
```

Choose a fresh output path for a repeat; the driver refuses to overwrite an
existing result. Other suites are `boundary`, `core`, `dos`, `console`, `tx` and `recovery`.
Concurrent cases also accept `--bank 3`, `--sector-size 256` and `--speed 1`
(STOCK810); bank-1 timing cases use `--trace` and include automatic replay.
Artifacts and logs remain under one qualification root. Do not publish full
emulator logs: the trace tools extract the relevant observations separately.
