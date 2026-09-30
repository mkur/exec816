# One-pass provider resolution

`PROGRAMPROVIDERS.Resolve` now parses the provider manifest once per load and
matches each decoded entry against all imports. HELLO's five imports therefore
need **14 provider-entry parses instead of 70**. The 70 name comparisons and
five complete contract comparisons are retained.

The change follows the [loading breakdown](loading-breakdown.md). Resolver
elapsed time falls by about **72%**, with no new allocation, public ABI change,
compiler change or persistent provider state.

## Match lifetime and validation

The existing `O65TYPES.Import.address` field stores each successful match.
After accepting the manifest header, the resolver clears every import address
before matching. A second matching provider sees a nonzero address and fails;
an import still at zero after the complete scan is missing and fails. Zero is
an unambiguous sentinel because provider target address zero is rejected.

This state belongs to one Validation object. Different program loads have
separate records, and a retry clears its previous matches. Every call reads
the current manifest. There is no global cache, additional lock, generation
protocol or lifetime extending beyond the existing validation records.
`PROGRAM.Load` releases the records on both provider failure and success.
As before, a failed attempt may contain partial matches and must not be used
to publish an image.

The resolver still reads the entire manifest after finding the requested
imports. It preserves header/count limits, cursor bounds and final-length
checks, linker-name validation, target address/extent checks, rejection of
duplicate requested providers, and exact contract length/content checks.
Valid unused entries remain allowed; malformed unused entries still fail.
Zero-import loads retain their previous header-only behavior.

## Same-profile HELLO result

Times below are elapsed guest milliseconds; the prime worker is stopped or
active as indicated. The compiler, ROM, emulator, media, command bytes, mount
table and load observers match the previous measurement: pinned actionc
`47cd55b`, PAL 65816 8x, SDFS 128-byte sectors, GENERIC57600 and accurate disk
timing. The new diagnostic image includes the resolver change and refreshed
build banner. The production play image is unchanged.

| Component | Stopped before | Stopped after | Active before | Active after |
| --- | ---: | ---: | ---: | ---: |
| Resolve imports | 238.621 | 67.644 | 268.375 | 75.603 |
| Whole `PROGRAM.Load` | 671.972 | 500.910 | 782.856 | 561.620 |
| Payload-read phase | 2,494.779 | 2,494.576 | 2,471.622 | 2,476.061 |
| HELLO open to prompt, VBI resolution | 3,880 | 3,720 | 4,160 | 3,940 |

Resolver savings are 170.977/192.772 ms; open-to-prompt improves by 160/220 ms.
The end-to-end differences also include scheduling and disk timing, and are
sampled in 20 ms PAL ticks. They should not be attributed entirely to exclusive
resolver CPU work. Disk/device waits still dominate total loading time.

Both new traces are checked against replays of their identical new image with
CPU tracing disabled and hardware observation retained. Relative phase ticks,
transfer counts, and all 20 payload transaction timings and gaps match exactly.
Two further replays with all passive tracing disabled match the phase ticks and
transfer counts. The [evidence](../development/provider-resolver.json)
records before/after summaries, call counts, hashes and replay comparisons.

## Development validation

The existing [o65 execution fixture](../../tests/programs/o65_execution.act)
now adds 17 resolver attempts covering successful matching and reuse, a missing
late import with a stale address, recovery after failure, contract length/content
mismatches, a changed live provider address, duplicate requested providers,
valid unused entries, malformed unused names/addresses, truncated/trailing
manifest data, zero imports, and invalid provider counts.

These run in raw and optimized native code alongside the fixture's existing
relocation oracle at two distinct placements, six loaded Process executions,
eight allocation-failure points and exact heap reclamation. The test restores
its temporary manifest mutations before executing loaded commands. Stack/domain
guards, bounded completion and OS ownership restoration remain enabled.

The development host suite passes 212 tests. There are two HELLO traces, two
hardware-only replays and two fully unobserved replays. Three guest images were compiled: the
raw/optimized execution fixture and one diagnostic demo. No release matrix or
compiler qualification was run.

```sh
python3 tools/test_o65_execution.py --case raw \
  --output build/development/provider-resolver/raw
python3 tools/test_o65_execution.py --case opt \
  --output build/development/provider-resolver/opt
python3 tools/measure_loading_breakdown.py \
  --bundle build/development/provider-resolver/measurement/bundle \
  --output build/development/provider-resolver/profile-stopped
python3 tools/measure_loading_breakdown.py \
  --bundle build/development/provider-resolver/measurement/bundle \
  --prime-worker active --output build/development/provider-resolver/profile-active
```

Prepare the diagnostic bundle with `measure_command_loading.prepare` from the
retained play bundle, as in the preceding measurements. Use
`tools/measure_command_loading.py` without `--cpu-trace` for replays. Set
`EXEC816_LATENCY_TRACE=1` to retain hardware observations; leave the PC and mask
selectors unset. Unset all three for fully unobserved replays.

## Memory cost

Reserved bank-zero delta is **0 fixed bytes and 0 per Task**, including guards,
alignment and unused reserved capacity. The complete diagnostic memory maps
are equal; upper reservations and heap allocations are unchanged. The match
state uses existing fields in the allocated import records.

Optimized resolver code grows from 3,041 to 3,365 bytes in upper RAM. Its fixed
frame shrinks from 74 to 66 bytes and its local stack peak from 90 to 82 bytes;
these are active usage figures, not reductions in reserved Task stack capacity.
The expanded fixture uses the existing upper snapshot workspace and adds no
test image reservation.
