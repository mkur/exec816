# GEM4XE benchmark port execution record

[Plan](../plans/gem4xe/g4bench-port-implementation-plan.md) · [History](README.md)

## G4B1 — Loadable application and clock

The pinned donor is GEM4XE `fbfea9b0b1233a5d659d5ec583c63f863cceadfa`.
The first slice provides the window/event shell and an application-private
adapter over `timer.device`'s monotonic VBI clock. Import ABI 12 exposes seven
existing public Exec message-port/device-I/O calls. The matching provider and
applications rebuild together; no kernel call or timer unit was added.

[Development evidence](../development/g4bench-g4b1.json) records an optimized
emitted clock probe followed by two independently loaded benchmark lifetimes.
The probe covers low-word rollover, changed-rate/reversal rejection, eight
timer bindings, exhaustion cleanup and reuse. Physical Return reads the live
clock; Escape closes each window. Process/heap ownership returns to baseline,
and native stack/domain checks pass. This is development coverage, not release
or real-hardware qualification.

The APP is 3,867 bytes with a 65,901-byte image span and relocation verified at
62 legal bank bases. Its clock port/request use 72 upper-heap bytes. The
ordinary application slot's observed stack peak is 584 bytes, leaving 472 bytes
above its interrupt floor. Existing stack reservations remain unchanged.
Slice bank-zero delta: **0 fixed, 0 per public Task, 0 private-idle**; no new
VRAM reservation. The generic runner's historical compaction deltas include
earlier stack growth and must not be interpreted as this slice's cost.

The first build exposed an existing stack-analysis bug: the IDE scanner read
a `$22` inside a JSL address as another call. The prerequisite fix skips an
accepted call's operand bytes, retains call-map agreement and adds two host
regressions. Re-admission of the emitted image gives a 722-byte IDE worker
bound within its 1,024-byte reservation. Compiler output was unchanged.

## G4B2 — Workloads and reporting

The five rows now use the selected donor geometry and tree through public
VDI/AES calls. The text is exactly 39 bytes. UPDATE groups contain at most four
bars/strings or one tree, with event polling between groups. Calibration,
three timed samples, cancellation, geometry/focus/visibility admission and
the screen/disk reports are implemented. Unsupported donor families remain
explicitly skipped. See the [application guide](../../ports/gem4xe/apps/g4bench/README.md).

[Development evidence](../development/g4bench-g4b2.json) records independent
full-canvas pixels for all five rows, all fifteen saved samples agreeing with
the observed clock endpoints/counts, a physical title drag invalidating a run,
Escape cancellation, missing-WORK save failure, two clean loaded lifetimes,
heap ownership restoration and intact stack/domain guards. The clock probe
also repeats G4B1's rollover, zero-interval and binding-exhaustion checks.
The fixture uses the pinned emulator's 57.6 kbit/s profile for both disks.

Pixel checks exposed Calypsi 5.18 `-O2` miscompiling the new local-array
expressions `p[2]=p[0]+99` and `p[3]=p[1]+49`: emitted additions read stack
slots 11/13 instead of the initialized coordinates at 7/9. Rectangle setup now
uses named X/Y coordinates, and canvas clearing reads its model directly.
The corrected optimized emission passes the independent pixels. Neither
Action! compiler code nor the shared renderer was changed for this adaptation.

The APP is 14,777 bytes, spanning 67,931 bytes, with relocation checked at all
62 legal bank bases. Its observed ordinary-stack peak is 697 bytes, leaving
359 bytes above the interrupt floor. Slice bank-zero delta remains **0 fixed,
0 per public Task, 0 private-idle**, including guards and unused reservation;
no VRAM reservation changes. The clock still owns only 72 upper-heap bytes,
and results/workload state live in the private loaded image.

Compared with the preceding Files-redraw demo, the shared C provider's stored
segments and BSS are byte-for-byte unchanged: the seven I/O functions were
already resident. The native import-address table grows from 231 to 252 bytes
(seven three-byte addresses), within the existing upper-memory data arena.

These checks establish correctness of the selected workloads. G4B3 supplies
the normal packaged-desktop baseline; fixture measurements are not a direct
GEM4XE comparison or an input-latency result.

## G4B3 — Packaged desktop observations

The OF816 package includes `C:G4BENCH.APP`, the matching ABI-12 provider/apps,
system and writable WORK disks, pinned AltirraOS ROM, donor notices and the
updated short guide. `tools/measure_g4bench.py` boots the exact ZIP, closes
unneeded applications through the Windows menu, launches through the shell,
starts with Return and closes with Escape. It reads application-owned results;
it does not inject drawing commands or a private clock.

[Development evidence](../development/g4bench-g4b3.json) preserves image,
compiler, donor, ROM and emulator identities, raw samples, geometry, screenshots
and stack observations. Both runs use PAL, the pinned 8× 65C816 configuration,
VBXE FX 1.26, the same 480×160 canvas at (152,56), and the pointer at (630,230).
Both five-second autoboots take 249 observed PAL frames. The counter case keeps
its complete value visible above the shell and verifies that it advances.

Median approximate milliseconds per operation, from three batch averages:

| Workload | Idle shell | Visible counter and idle shell |
| --- | ---: | ---: |
| Solid bars | 28.0 | 31.4 |
| Plain text, even X | 23.8 | 26.8 |
| Plain text, odd X | 39.2 | 42.0 |
| Clipped plain text | 41.2 | 45.2 |
| Five-object dialog | 144.0 | 156.0 |

These are separate initial observations. Counts are calibrated independently
for each row/load; raw counts and VBI ticks are retained. They include UPDATE
admission, geometry/visibility checks, event polling, scheduling and drawing
completion. They exclude clearing, warmup and report saving. They establish
neither click latency nor a direct GEM4XE ratio or a regression tolerance.
Both packaged runs completed all rows without low-resolution flags; they did
not force the calibration-cap branch.

Report saving, shell use after closing (`HELLO`), normal desktop shutdown and
stack/domain guards pass in both loads. The benchmark's ordinary Task peaks
at 697 bytes idle and 703 bytes with the counter, leaving 359/353 bytes above
its interrupt floor. Slice bank-zero reservation change is **0 fixed,
0 per public Task, 0 private-idle**, with no VRAM reservation change. The APP
remains 14,777 bytes. Twelve package tests, two application-observer tests and
four C-image package tests also pass; the prerequisite stack scanner has two
focused host regressions. This is development coverage, not hosted-system or
real-hardware qualification.

Reproduce with the current pinned toolchain:

```sh
python3 tools/test_g4bench.py --output build/g4bench/check
python3 tools/build_demo.py --gem-desktop --output build/g4bench/demo
python3 tools/measure_g4bench.py --bundle build/g4bench/demo --load both
```

The distributable is `build/g4bench/demo/exec816-demo.zip`. Close one desktop
app if all windows are occupied, then use `RUN C:G4BENCH.APP`. Return runs or
repeats the benchmark; Escape stops a run or closes the report. The saved file
is `WORK:G4BENCH.TXT`. Manifests, raw observations and screenshots stay in the
development directory.
