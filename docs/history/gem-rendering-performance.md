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

## TX2: native odd-X text

Complete odd-X text now uses the native uploader through both caller-local
VDI and the ordinary bitmap-text entry. It selects the existing shifted atlas
once per run: five source bytes per glyph row at stride 1,280, with destination
cells advancing four bytes. The glyph offset uses shifts and addition. The
even-X loop retains its four-byte geometry.

One interior fill and an AND/OR pair at each outer edge replace the paper
without changing neighbouring pixels. Glyph records follow those five
background commands; hardware-zero ink uses inverse-mask AND, and other ink
uses the nibble stencil. The optional trailing fill remains in that same
list, with its existing even-X/even-width and 3,072-access restrictions.

A full odd-X row holds 79 cells: 84 commands, 1,764 bytes and 14,616 estimated
accesses, or 85 commands / 1,785 bytes / 17,688 accesses including the largest
trailing fill. The shared conservative capacity is 86 commands / 1,806 bytes /
17,872 accesses. Generic command limits, the command arena and both font atlas
reservations remain unchanged.

The private packet grows from 25 to 26 bytes, appending the parity byte at
offset 25. The uploader uses existing call-clobbered DP `$80–$A5`; its odd
background helper adds a three-byte return address while active. Fixed
bank-zero, each public Task's reserved bank-zero storage, private idle storage,
guards, alignment, unused capacity and VRAM reservations all change by **zero
bytes**. The drawing fixture's measured root stack peak is 384 bytes, leaving
896 bytes above its floor; the VDI clients peak at 806 / 802 bytes, leaving
250 / 254 bytes above their floors. These are observed fixture peaks, not
worst-case proofs.

Development validation covers 165 native drawing checks, 187 two-client VDI
checks and 48 console checks, with independent pixel comparisons. New cases
include all 256 glyphs at odd X, nonuniform surrounding pixels, X=1 and other
odd positions, a full 79-cell row, both ink/paper zero cases, blank strings,
bottom/right edges, CPU/VRAM bank crossings and combined text/fill termination.
Launch counters require one list per complete run. The VDI fixture includes
complete odd-X 39-character text, parameter-block glyph 255 and low-byte
mapping, clipped 80-character calls, horizontal/vertical clipping, covered and
exposed windows, pointer restoration and forced preemption while shared text
scratch is in use. Partial clipping retains the existing fallback for TX3.

The native mapping test observes four NMI boundaries and preserves the C
context, underlying aperture RAM and OS display. Selected busy-timeout and
unquiesced-DMA cases retain the driver's bounded recovery and ownership rules.
Raw and optimized emitted packet layouts agree; the host suite passes 452
tests with four historical-source skips. These are development checks, not
hosted-system qualification.

Builds use the same pinned compiler revision and optimized host executable as
TX1, with unchanged guest optimization. The older display fixture's frozen
input manifest still names a previous compiler pin; its local build copy was
refreshed to the current compiler/platform pin hashes, retaining all donor and
Calypsi checks. That override is recorded with the development evidence and
does not modify the source manifest or donor checkout.

[TX2 development evidence](../development/gem-rendering-tx2.json) records the
inputs, packet layouts, checks, stack observations and packaged measurements.
The comparison below uses the same PAL, 8× 65816, VBXE FX 1.26 configuration
and pinned ROM as TX1. Idle elapsed and Task CPU are cycle-trace means;
medians are three VBI-quantized batch averages. All values are milliseconds,
TX1 → TX2.

| Workload | Idle elapsed mean | Task CPU mean | Idle median | Counter median |
| --- | ---: | ---: | ---: | ---: |
| 100×50 bar | 28.011 → 28.003 | 16.645 → 16.654 | 27.8 → 27.8 | 31.4 → 31.6 |
| 39 characters, even X | 21.655 → 21.624 | 11.479 → 11.469 | 21.6 → 21.6 | 24.0 → 23.8 |
| 39 characters, odd X | 35.048 → 22.032 | 22.783 → 11.655 | 35.0 → 22.0 | 38.6 → 24.4 |
| Clipped text | 38.322 → 38.284 | 25.230 → 25.172 | 38.2 → 38.2 | 41.2 → 43.2 |
| Five-object dialog | 144.567 → 144.547 | 93.188 → 93.180 | 144.0 → 144.0 | 157.0 → 157.0 |

Odd-X text now takes **one borrow, one native upload and one launch**, with
zero `vdi_v_gtext` or `vbxe_glyph` calls. Task CPU falls 48.8% and idle elapsed
time falls 37.1%. It is now close to even-X text; the remaining end-to-end cost
includes the unchanged VDI/application protocol, scheduling and interrupts.

The controls' idle CPU and elapsed means are essentially unchanged. The
counter-loaded clipped-text median is worse in this run (41.2 → 43.2 ms),
despite unchanged idle rendering cost; that loaded run was not cycle-traced,
so this does not establish its cause. TX2 does not claim a clipped-text or
interaction-latency improvement. TX3 remains the next slice, and the final
interaction gate remains TX7.

Both packaged benchmark scenarios pass through normal application launch and
clean shutdown. The refreshed OF816 demo is
`build/gem-rendering-tx2/demo/exec816-demo.zip` (538,935 bytes), SHA-256
`a98487a3958103530640d6deef3f4f115bc4527fe4e67ba6fa343f92d031f5c9`.
Launch with `build/gem-rendering-tx2/demo/launch-altirra.command`.
The TX1 package remains intact for comparison.

The native drawing, VDI and console entrypoints are the same as TX1, using
`build/gem-rendering-tx2/host_release.py` and TX2 output directories. Additional
selected regressions use `tools/test_gem_display.py --mode opt --case map-nmi
--case busy-timeout --case unquiesced`, through the recorded local
`build/gem-rendering-tx2/display_current.py` manifest wrapper.

## TX3: complete cells inside horizontal clips

Caller-local VDI now skips hidden characters by cell offset and sends the
complete middle of a full-height text intersection through the native uploader.
Only the one or two partial edge cells use the existing clipped replacement
glyph routine, including its clipped paper fill. There is no separate
background pass over the whole string and no new per-glyph ownership or
validation call.

The native middle completes first; both edges are then queued together in a
single generic list. Adjacent cells preserve each other's nibbles, so this
ordering keeps correct replacement pixels while avoiding a separate launch
for each edge. The entire operation remains inside its original display borrow,
with the existing pointer/outline handling and synchronous completion. This
does not make publication atomic or close the final interaction-latency gate.

A clip exactly on cell boundaries uses only the native run. A vertical cut or
an intersection with no complete cell retains the donor path, narrowed to the
characters that actually intersect it. A one-pixel clip inside a glyph draws
that glyph once; an empty intersection never enters the renderer. The native
bitmap clipping entry is unchanged by this caller-local VDI slice.

There is no public or private packet layout change, new buffer, lookup table,
font atlas or reservation. Fixed bank-zero, each public Task's bank-zero
storage, private idle storage and VRAM reservations all change by **zero bytes**,
including guards, alignment and unused capacity. Generic list and native text
bounds are unchanged.

The optimized two-client VDI fixture passes **226 checks**, including an
independent full-screen pixel oracle over nonuniform surrounding colours.
Twelve focused cases cover left/right/both cuts, exact cell boundaries,
one-pixel and two-partial-cell clips, an empty intersection, vertical clipping,
a negative starting X, bank-crossing named input, both X parities and
hardware-zero ink. Target counters require one native run where complete cells
exist and only one or two device glyph calls for horizontal partial edges.
The vertical-cut case draws twelve clipped cells through the fallback; the
one-pixel case draws one glyph; the empty case draws none.

The original 80-word parameter-block, glyph-255, multi-chunk negative-X,
covered/exposed window, two-client preemption and pointer-restoration cases
remain in that fixture. After moving the pointer away from the new clipped
scene, the restored pixels also match independently. The client stack peaks
are 826 bytes each, leaving 230 bytes above each floor; these are measured
fixture peaks, not worst-case bounds. Ownership and OS restoration pass.
There is no ABI/bridge/assembly change, so this slice uses optimized behavioral
checks without duplicating the integration scene in raw mode.

[TX3 development evidence](../development/gem-rendering-tx3.json) records the
inputs, route counters, pixel comparisons, stack observations and packaged
measurements. The compiler, guest optimization, ROM and PAL, 8× 65816, VBXE
FX 1.26 configuration match TX2. Idle elapsed and Task CPU are cycle-trace
means; medians are three VBI-quantized batch averages. Values below are
milliseconds, TX2 → TX3.

| Workload | Idle elapsed mean | Task CPU mean | Idle median | Counter median |
| --- | ---: | ---: | ---: | ---: |
| 100×50 bar | 28.003 → 28.116 | 16.654 → 16.691 | 27.8 → 28.0 | 31.6 → 31.4 |
| 39 characters, even X | 21.624 → 21.806 | 11.469 → 11.465 | 21.6 → 21.8 | 23.8 → 23.8 |
| 39 characters, odd X | 22.032 → 22.034 | 11.655 → 11.665 | 22.0 → 22.0 | 24.4 → 24.2 |
| Clipped text | 38.284 → 27.415 | 25.172 → 16.300 | 38.2 → 27.4 | 43.2 → 30.4 |
| Five-object dialog | 144.547 → 144.544 | 93.180 → 93.142 | 144.0 → 144.0 | 157.0 → 156.0 |

Clipped text uses **35.2% less Task CPU** and **28.4% less idle elapsed time**.
The unchanged workload includes 282 full-height operations and 18 vertically
clipped operations across its three samples. Each full-height operation uses
one native upload for 37 middle characters and one generic upload for the two
partial edges. Vertical cuts retain all 39 donor glyphs and two generic uploads.
Across both routes, native uploads average 0.94, generic uploads 1.06 and device
glyph calls 4.22 per operation, down from 39 glyph calls in TX2. Donor
`vdi_v_gtext` calls fall from 1 to 0.06. Every operation still uses one borrow.

Total launches increase from 1.06 to 2 per operation: the native middle and
generic edges are separate lists. The measured CPU and elapsed reductions
justify that tradeoff; this result does not depend on fewer launches. The
other workloads' Task CPU costs are essentially unchanged. TX4, small AES
object units, is next; the combined interaction-latency and flicker gate remains
TX7.

The host suite passes 452 tests with four historical-source skips. Both
packaged benchmark scenarios pass through normal application launch and clean
shutdown. These are development checks, not hosted-system qualification.
The refreshed OF816 demo is `build/gem-rendering-tx3/demo/exec816-demo.zip`
(539,224 bytes), SHA-256
`d7966959561c69d60bb9cf75dcb68012f83c08fd25f4a605fdc9a96dc4e3c7a9`.
Launch with `build/gem-rendering-tx3/demo/launch-altirra.command`.
The TX2 package remains intact for comparison.

Reproduction uses the same pinned compiler's release host executable as TX2,
through the recorded `build/gem-rendering-tx3/host_release.py` wrapper:

```sh
python3 build/gem-rendering-tx3/host_release.py tools/test_aes_server.py \
  --suite vdi --mode opt --output build/gem-rendering-tx3/vdi-clips-opt
python3 build/gem-rendering-tx3/host_release.py tools/build_demo.py \
  --gem-desktop --format sdfs --sector-bytes 256 --system-kib 720 \
  --output build/gem-rendering-tx3/demo
python3 tools/trace_g4bench.py --bundle build/gem-rendering-tx3/demo \
  --output build/gem-rendering-tx3/trace-idle --load idle
python3 tools/measure_g4bench.py --bundle build/gem-rendering-tx3/demo --load counter
```
