# GEM rendering performance

[History](README.md) · [Implementation plan](../plans/gem4xe/text-run-fast-path-plan.md) ·
[Drawing baseline](g4bench-drawing-traces.md)

## TX1: 80-character text batches

The private VDI chunk and native even-X uploader now accept 80 characters.
An opaque run needs one background fill followed by its glyph records. An
optional trailing fill remains in the same list and retains its 3,072-access
allowance. The maximum combined list is 82 records, 1,722 bytes and 15,872
estimated bus accesses. Generic lists retain their 64-record / 8,192-access
bounds; the console retains its own 32-character presentation step.

The workstation grows from 282 to 378 live bytes, or 288 to 384 heap-reserved
bytes: **96 extra upper-RAM bytes per open VDI workstation**. Fixed bank-zero,
each public Task's reserved bank-zero storage, private idle storage and VRAM
reservations all change by **zero bytes**, including guards and unused capacity.
The 25-byte native upload packet and its existing DP scratch are unchanged.

Build-time checks keep VDI and native batch limits equal, fit the generated
records into the existing arena, and ensure the donor's 128-word scratch can
hold the 80-word fallback. No new runtime validation was added.

Development checks exercise emitted optimized drawing code with an independent
pixel oracle. Native text covers lengths 0, 1, 31, 32, 33, 39, 64, 79 and 80,
every byte glyph, CPU-bank crossing, screen edges, colours, spaces and the
maximum combined text/fill work. Test-only launch counters verify one launch
for complete 39- and 80-character runs, including the 80-character run with a
3,072-access trailing fill. Ownership cleanup, OS restoration and stack guards
remain part of the fixture.

The two-client VDI test covers 80-word parameter-block input, bank-crossing
named strings, clipped fallback, a complete 39-character fast unit, covered
and exposed windows, and forced preemption while shared scratch is in use.
Current framed windows cannot expose a complete 640-pixel work row, so the
80-character complete-row pixel/launch check uses the native drawing entry;
the public VDI test clips its 80-character calls to the window work area.
The private VDI layout is checked from both unoptimized and optimized emitted
C objects. These are development checks, not hosted-system qualification.

The console fixture also needed two maintenance corrections: a 4 KiB upper
image-data arena for the current DOS diagnostics (formerly 2 KiB), and tracing
`DisplayOwnerEnter` at the current drawing admission point. Its CR+Z case keeps
an unchanged caret outside the dirty span, so the assertion now requires one
text launch and no caret redraw. Pixel comparisons remain independent of these
operation counts. These changes do not alter production console behavior.

The debug host compiler reached the build runner's 600-second timeout on the
console integration image. Subsequent integration and demo builds use an
optimized host build of the same pinned Action! compiler revision; guest
optimization remains enabled. This build profile is recorded in each artifact.
Re-emitting the unchanged original benchmark's native input with that host
build reproduces all 1,909 native segments and zero-fill regions exactly. The
original package also contains separately compiled C and adapter segments.

[Development evidence](../development/gem-rendering-tx1.json) records 452 host
tests (four skipped), 131 native drawing checks, 182 VDI checks and 48 console
checks, plus emitted layouts, stack usage, image hashes and pinned machine
configuration. The rebuilt OF816 package passes the idle and counter-loaded
G4BENCH scenarios and clean shutdown.

The following elapsed/CPU values are cycle-trace means per operation on the
idle desktop; the counter column is the benchmark's median of three
VBI-quantized batch averages. All numbers are milliseconds, baseline → TX1.

| Workload | Idle elapsed mean | Task CPU mean | Counter median |
| --- | ---: | ---: | ---: |
| 100×50 bar | 28.102 → 28.011 | 16.662 → 16.645 | 31.4 → 31.4 |
| 39 characters, even X | 24.011 → 21.655 | 13.277 → 11.479 | 26.8 → 24.0 |
| 39 characters, odd X | 39.349 → 35.048 | 25.850 → 22.783 | 42.0 → 38.6 |
| Clipped text | 41.618 → 38.322 | 27.682 → 25.230 | 45.2 → 41.2 |
| Five-object dialog | 144.786 → 144.567 | 93.196 → 93.188 | 156.0 → 157.0 |

Even-X text now takes one borrow, native upload and launch, down from two.
Its Task CPU cost falls 13.5%, while total elapsed time falls 9.8% because
application protocol and off-Task time remain. Odd-X and clipped text also
use one borrow but still dispatch all 39 glyphs individually. Their native
run improvements remain TX2/TX3 work. Bar and dialog command counts remain
four and ten launches respectively; this slice does not optimize their fills.
These measurements do not close the final interaction-latency gate.

The updated demo is `build/gem-rendering-tx1/demo/exec816-demo.zip` (538,799
bytes), with SHA-256
`22ccf5ce2b25b2295453bfc3b74f7b9a793de488ff61fd83b451d0d1bb904646`.
Launch it with `build/gem-rendering-tx1/demo/launch-altirra.command`.
The previous G4BENCH package remains intact as the comparison baseline.

The focused fixture entrypoints are:

```sh
python3 tools/test_gem_drawing.py --mode opt --output build/gem-rendering-tx1/drawing-opt
python3 tools/test_aes_server.py --suite vdi --mode opt --output build/gem-rendering-tx1/vdi-opt
python3 tools/test_console_bitmap.py --mode opt --observe --output build/gem-rendering-tx1/console-opt
```

For the recorded VDI/console builds, the local
`build/gem-rendering-tx1/host_release.py` wrapper runs these entrypoints with
`native_program.compiler(..., release=True)`. It does not change the compiler
pin or guest options; its checksum is in the evidence record. Console trace
assertions were then replayed against that same built image with
`--replay --observe`.
