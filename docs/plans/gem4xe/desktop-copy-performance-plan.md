# Desktop copy performance

DC1 and DC2 are implemented. The [execution record](../../history/desktop-copy-performance.md)
documents the 2.83x throughput gain, the selected 16 KiB default, the shell
reference and the measured cancellation/feedback tradeoffs.

Compare the desktop's 512-byte copy chunk with 1 KiB, 2 KiB and the shell
COPY's 16 KiB. Measure before changing the production default. The desktop
executes one synchronous Read/Write pair per event-loop pass; a larger chunk
can delay its own Cancel even when another application's buttons remain fast.

## DC1 — matched measurement

- Reuse the current optimized resident system, pinned ROM, emulator and
  accurate 57.6k SIO configuration. Build desktop application variants differing
  only in their copy-buffer size. Keep experimental media separate from the
  packaged OF816 distribution and record hashes and source provenance.
- Copy the same binary file, including a partial final chunk, within a fresh
  writable WORK volume. Record transfer completion and bytes/second, then
  independently extract the disk and compare every byte.
- Measure the existing shell COPY with its 16 KiB buffer on the same machine
  and media geometry. Separate executable loading from the timed transfer.
- Collect 40 physical Control Panel presses at idle and during a larger
  desktop copy. Record median/p95 time to matching scanout. Check that the copy
  remains active throughout the loaded sample batch.
- Inject Escape during the first active data read and data write. Record
  cancellation completion, including closing and removing the temporary file.
  Report individual phase-controlled samples, not a percentile from two trials.

Observe packet and application state at bank-zero IRQ checkpoints. The pinned
bridge's PC-breakpoint API cannot target upper-bank C routines. Label these as
sampled wall-clock measurements, not instruction-exact API-entry timings.

## DC2 — decision and focused validation

Optimize primarily for throughput: most copies run to completion. Treat the
16 KiB desktop variant as a production candidate, not just a reference. Report
Cancel delay as a tradeoff rather than a small-buffer acceptance gate; still
check that other applications remain responsive. Choose a larger buffer when
it materially improves throughput. Record whether a separate copy Process is
worth pursuing after batching. Do not add a worker protocol, runtime tuning
settings or new validation layers to this experiment.

If the production size changes, update the emitted layout probe's expected
size and run focused desktop copying/cancellation checks, including final
partial chunks and independent disk readback. Refresh the OF816 demo through
`tools/build_demo.py` only after accepting a production change.

Record results and limitations in a history page linked here and from the
documentation index. This is development measurement, not hosted-system or
real-hardware qualification. Reserved bank-zero change: **0 bytes fixed,
0 bytes per public Task, 0 bytes idle**. Any buffer increase is upper-memory
heap space for the single active desktop copy job.
