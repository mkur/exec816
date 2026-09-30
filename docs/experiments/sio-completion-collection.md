# Combine SIO completion checking and collection

`BLOCKWIRE.Transfer` now uses the existing `IOCORE.Collect` operation to test
completion and collect its exact reply in one kernel entry. A pending result
keeps the existing cancellation-pump, conditional abort and durable-signal wait
loop. A terminal result supplies the signed error directly; the separate
`CheckIO` and final `WaitIO` calls are gone.

The existing ownership checks and guarded reply removal remain in the kernel.
No signal is cleared between collection and waiting, and the adapter, request
and caller buffer remain retained until terminal collection. An accepted abort
still maps `IOERR_ABORTED` to `ERROR_BREAK`.

## Same-profile measurement

The [record](sio-completion-collection.json) compares this slice with the
[preceding profile](sio-hot-path-profile.md), repository baseline `fb1896f`.
Both use the same compiler pin, ROM, emulator, HELLO binary and 128-byte SDFS
media: PAL 800XL, 65C816 at 8×, GENERIC57600, accurate disk timing, SIO patching
and burst transfers disabled. Eighteen gaps separate HELLO's nineteen data
sector reads.

| Elapsed interval | Prime stopped: before → after | Prime running: before → after |
| --- | ---: | ---: |
| Mean SIO retirement entry → filesystem return from Transfer | 4.86 → 3.79 ms | 5.41 → 4.20 ms |
| Mean last serial byte → next sector command | 17.70 → 16.80 ms | 20.88 → 18.57 ms |
| HELLO payload loading | 2.46 → 2.46 s | 2.42 → 2.42 s |
| HELLO open → prompt | 4.10 → 4.10 s | 4.14 → 4.14 s |

The retirement interval falls about **22%** in both modes. Mean sector gaps
fall **5.1%** with the prime task stopped and **11.1%** with it running.
Other phase timings also shift with scheduling; these are elapsed intervals,
not exclusive CPU costs. Rotational timing remains enabled, and end-to-end
loading shows no change at the loader observer's 20-ms resolution.

Each new trace was checked against its identical image without CPU markers:
relative loader ticks, transfer counts and all eighteen hardware gap lengths
match exactly. The tracer observes actual DOS submissions; there are no
intermediate DOS read boundaries in this payload.

## Development validation

- 197 host tests pass.
- Eight emitted-code cancellation cases pass: before submission, during wire
  activity, before wire start with an accepted abort, and after terminal
  collection, each in raw and optimized mode. These also check subsequent
  successful reads, committed cursors, ownership, guards and OS restoration.
- Two optimized real-peripheral fault cases pass: checksum recovery and a short
  transfer requiring reset. Both preserve the error cause and retire software
  ownership; the latter intentionally requires reset after cleanup.
- HELLO, DIR and EXIT pass in both profiling modes and their untraced replays.

The integration trace tools now mark sector completion at the filesystem
worker's return from `BLOCKWIRE.Transfer`. A return from `Collect` alone can
mean pending and is unsuitable as a terminal marker. A host regression checks
this distinction; the marker was also verified against the emitted image.
The fault harness now passes its explicit MyDOS format to the shared observer.

These are focused development checks, not release qualification. The compiler
pin is unchanged. Reserved bank-zero delta: **0 fixed bytes, 0 per Task**,
including guards, alignment and unused capacity. Complete memory and Task
reservations match the preceding diagnostic image.

Artifacts are retained under `build/development/sio-collect`. Reproduce the
measurement with:

```sh
EXEC816_LATENCY_TRACE=1 python3 tools/measure_command_loading.py --prepare \
  --bundle build/demo --format sdfs --prime-worker stopped \
  --output build/development/sio-collect/measurement
python3 tools/trace_command_io.py --output build/development/sio-collect/profile
python3 tools/trace_command_io.py --prime-worker active \
  --output build/development/sio-collect/profile-active
EXEC816_LATENCY_TRACE=1 python3 tools/measure_command_loading.py \
  --bundle build/development/sio-collect/measurement/bundle --prime-worker active \
  --output build/development/sio-collect/measurement-active
```

Only the diagnostic demo was rebuilt for this slice. The play bundle at
`build/demo` remains the preceding image. Combining SIO worker stop/dequeue
controls and optimizing sector copying remain separate follow-ups.
