# G4BENCH for Exec816

Pinned donor inputs and adaptation sources for the loadable benchmark.
See the [implementation plan](../../../../docs/plans/gem4xe/g4bench-port-implementation-plan.md).

`tools/build_g4bench.py --output DIR` prepares inputs below `DIR/source` and
builds a normal private C image. The donor checkout is never modified.
The app measures five rows from three donor families: solid bars, plain text
at even and odd X, clipped text, and a five-object dialog. It uses the public
VDI/AES calls, a 480×160 canvas and the existing `timer.device` VBI clock.

Close an existing desktop app if all four windows are occupied, then run
`RUN C:G4BENCH.APP` or open it from Files. Return starts or repeats the run;
Escape stops a running benchmark and closes an idle report. Keep its canvas
uncovered and leave the pointer outside it. Moving or covering the window
invalidates the active row. Results survive exposure and are also written to
`WORK:G4BENCH.TXT`; a write failure leaves the screen report available.

Each row warms up, calibrates complete donor passes toward two seconds, then
records three equal-count samples. The report shows median approximate ms/op
and saves raw ticks, operation counts, clock endpoints, geometry and adaptations.
UPDATE ownership, visibility checks, event polls, scheduling and completed
drawing are measured. Canvas clears, warmup, formatting and disk writes are
excluded. This is application throughput, not button latency or a direct
GEM4XE speed ratio. Calibration is capped at 4,096 operations; short samples
are labelled low resolution.

The donor text contains 39 bytes. Its transparent text becomes replacement
text in Exec's fixed 8×8 font; `vr_recfl` becomes `v_bar` and the unsupported
dialog `OUTLINED` state is removed. Odd-X and clipped text are additional
Exec variants. The other fifteen donor tests remain explicitly skipped;
missing VDI features and a second application window are not emulated.

The donor application and its adaptations retain GPL-2.0-or-later and the
pinned `COPYING`, `COPYING.LIB` and `docs/licence.md` notices. The Exec MIT
interface/example grant does not relicense this application.
