# Filesystem and DOS performance execution

[Plan](../plans/filesystem-dos-performance-implementation-plan.md) ·
[Historical records](README.md) · [Testing policy](../contributing/testing.md)

Development checks use the pinned compiler and AltirraOS ROM. These results
are emulator development evidence, not hardware or release qualification.
All slices retain 0 additional fixed, per-Task and idle bank-zero bytes,
including guards, alignment and unused capacity. Stack pools are unchanged.

## FP0: baseline and observers

The [retained baseline](../development/filesystem-performance-baseline.json)
records the exact compiler, ROM, emulator, BIOS and media inputs. Loaded COPY
moves 23,872 bytes through its 16 KiB buffer. Cold IDE takes 151 PAL frames
(3.02 s), 54 reads, 61 writes and 2,580 gateway calls. Warm source takes
122 frames (2.44 s), 4 reads and the same 61 writes. Both independently pass
persisted-byte and allocation audits. Timing excludes command loading and
controller initialization; observers add calls and counters, so comparisons
must use matching observers.

`measure_ide_write_performance.py --from-build DIR --warm-source` replays the
retained native image against newly generated media. The shared SIO observer
now accepts the transport-neutral IOStdReq and reads its SIO extension only
in SIO measurements. Both tools collect native gateway/Task-switch deltas.
The release-host compiler binary uses the same pinned inputs and emits the
same optimized target code; it is not a compiler override.

Reproduce the SIO baseline with a current source image containing COPY16 and
LONG.TXT:

```sh
python3 tools/measure_write_performance.py --source-image SOURCE.atr \
  --filesystem sdfs --size 256 --buffer 16384 --create-only --output DIR
```

The SIO case uses accurate Generic 57600 timing and fresh destinations for
cold/warm source runs. Large images, traces and complete build inputs remain
under `build/filesystem-performance/`. Host checks: 447 passed.

The uninterrupted SDFS copy loop takes a median 2,252.3 µs for 128 bytes,
968.0 µs for 55 bytes and 4,504.2 µs for 256 bytes in the isolated emitted
fixture. The current compiler shares its return epilogue; the observer accepts
one or two RTL exits and still verifies its single byte-loop boundary.
