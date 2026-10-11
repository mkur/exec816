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

## TX4: complete small-object units

`objc_draw` chooses its unit height from the complete object extent, including
outward borders, before damage or visibility clipping. Extents up to 32 rows
use one borrow per visible intersection; larger objects retain 16-row strips.
The adapter's callback ceiling is 32 rows. Generic blitter geometry, list/work
limits, presenter batches and the 640×16 scratch strip are unchanged.

[TX4 evidence](../development/gem-rendering-tx4.json) records 512 optimized
object checks and eleven independent pixel scenes, including 16/17/31/32/33-row
extents, ordinary/EXIT/DEFAULT buttons, selected/disabled wide objects, odd
coordinates, damage clipping and pointer restoration. A 33-row object uses
16/16/1; exposing only 24 rows of it still uses 16/8. A 12-row Files-style
selection remains one borrow. The wide 32-row cases complete multiple internal
lists without exceeding 64 records or 8,192 accesses per list.

The two-borrower fixture now uses 32-row callbacks beside native scroll/pointer
work. Its ownership, pixels, stack guards, quiescent timeout cleanup and
unquiesced reset-required behavior pass. Its instrumented borrow elapsed
median/p95/maximum are 5.065/18.971/19.576 ms, including fixture assertions and
two injected yields; these are not application feedback measurements. The
object fixture's root stack peaks at 941 bytes, with 339 bytes above its floor.
The host suite passes 452 tests with four historical-source skips. This is
development validation, not hosted-system qualification.

The unchanged dialog falls from ten borrows/uploads/launches to eight, with
its 64-row root still using four strips. Logical fill calls fall from 75 to 59
because the button borders are no longer reconstructed twice; their algorithm
is unchanged. TX3 → TX4 idle cycle-trace means are **144.544 → 130.516 ms**
elapsed and **93.142 → 81.805 ms** Task CPU. Bar and text controls are essentially
unchanged. The OF816 package, compiler pin, ROM, PAL 8× CPU and VBXE 1.26
configuration match the previous slice.

The matched exact-package interaction probe performs 40 Panel presses and 40
Files selection changes, comparing independently expected scanout. Its timings
include input and scheduling, with frame-granular completion polling:

| Feedback | TX3 median / p95 | TX4 median / p95 |
| --- | ---: | ---: |
| Panel button | 100.288 / 120.498 ms | 100.288 / 140.211 ms |
| Files selection | 100.289 / 160.426 ms | 100.288 / 160.411 ms |

Panel's median is unchanged and its p95 is about one PAL frame worse in this
cohort. This is an open interaction result for TX7, not evidence of improved
button latency. Combining rows reduces repeated setup but does not make
publication atomic. The final combined implementation must be compared against
this matched TX3 package before closing that gate.

Reserved bank-zero changes are **0 fixed, 0 per public Task and 0 idle bytes**,
including guards, alignment and unused capacity. VRAM reservation growth is
**0 bytes**. Resident C payload grows by 23 code bytes and zero data bytes.
The intermediate OF816 ZIP is `build/gem-rendering-tx4/demo/exec816-demo.zip`
(539,309 bytes), SHA-256
`39dc6d22ed6024c1dbad9cc9a5588fff006e0255d653efced6fc8887595b4877`.

Reproduce with the recorded release-host wrapper and `tools/test_aes_server.py
--suite objects --mode opt`, `tools/test_display_borrow.py`, and
`tools/trace_g4bench.py --load idle`. The new `tools/measure_gem_feedback.py
--bundle <demo> --output <fresh-directory>` applies the same physical input
schedule to either archived package and checks clean shutdown.

## TX5: direct, work-bounded solid fills

Solid VDI rectangles now bypass donor workstation setup. A narrow solid-fill
borrow shares the existing ownership, pointer, fence and cleanup lifecycle;
generic callbacks retain their 32-row ceiling. The trusted encoder appends one
aligned fill plus AND/OR pairs for partial bytes, at most five records per
fragment. Uniform widget fills reuse it without changing their border algorithm.
XOR, stipple, generic geometry and presenter scratch remain unchanged.

A generated 325-byte row-capacity table bounds fragments by 8,192 accesses,
including odd edges. Work is computed after choosing the height. The lookup
payload is now 37,457 bytes inside its existing bank reservation.
[TX5 evidence](../development/gem-rendering-tx5.json) records raw/optimized
table probes, exhaustive host interval/capacity checks, optimized public VDI,
object and 36 primitive/widget pixel scenes. They cover partial-byte widths,
colour zero, screen edges, budget boundaries, full-screen fills, clipping,
preemption, pointer restoration, scratch publication and failure/reopen.
Two borrowers now mix a 50-row solid fill and a 32-row generic callback;
ownership, stack guards, clean exit and both timeout cleanup variants pass.
The host suite passes 452 tests with four historical-source skips.

| Idle cycle-trace mean | TX4 elapsed / CPU | TX5 elapsed / CPU |
| --- | ---: | ---: |
| 100×50 bar | 28.125 / 16.722 ms | 19.664 / 9.494 ms |
| Five-object dialog | 130.516 / 81.805 ms | 118.758 / 71.591 ms |

The bar uses one borrow, upload and launch instead of four. Its alternating
positions average three records (one aligned or five with two partial edges).
The dialog still has 59 logical fills and eight borrows/uploads/launches;
recording `GemSolidFill` prevents mistaking renamed routines for eliminated work.
Text controls are essentially unchanged.

Matched 40-sample Panel feedback median/p95 improves from 100.288/140.211 to
80.331/100.289 ms. Files selection remains 100.289/160.411 ms. These measure
physical input to independently matched scanout with frame-granular polling.
Repeated-fill competition and the final combined interaction gate are measured
in TX7; these idle application results alone do not close that gate.

Reservation changes are **0 fixed, 0 per public Task and 0 idle bank-zero bytes**,
including guards, alignment and unused capacity; VRAM growth is **0 bytes**.
Resident C payload adds 1,031 code and 325 data bytes. The unchanged compiler
pin uses its release host executable and optimized guest code. This is
development validation, not hosted-system or real-hardware qualification.

The intermediate OF816 ZIP is `build/gem-rendering-tx5/demo/exec816-demo.zip`
(540,260 bytes), SHA-256
`37554362f59cd5c6b6d2b06e5a607f00fa6c5ccbf0c9c9efc7388a920cb4084b`.
Reproduce with the recorded release-host wrapper, `test_vbxe_tables.py` in
raw/opt, `test_widget_pixels.py`, `test_aes_server.py --suite vdi` and
`--suite objects`, and `test_display_borrow.py`. Matched application probes use
`trace_g4bench.py --load idle` and `measure_gem_feedback.py` with fresh outputs.

## TX6: two-fill opaque boxes and buttons

The maintained AES extraction patch replaces uniform `G_BOX`/`G_BUTTON`
border loops with an outer border-colour fill and an interior fill. It derives
both from the original geometry before clipping. Zero thickness emits only
the interior; negative thickness expands the outer rectangle. Hollow still
means the hosted white interior. Transparent frames, patterns, TEDINFO and
degenerate interiors retain their existing paths. Labels, selected XOR,
disabled stipple and focus decoration retain their order. The donor checkout
is unchanged; retained widgets and caller-local objects use the same patch.

[TX6 evidence](../development/gem-rendering-tx6.json) records 822 optimized
object assertions, eleven object-unit scenes and 21 additional independent
border/state scenes. Coverage includes inward/outward/zero borders, positive,
zero and negative interior sizes, odd coordinates, colour zero, every clipped
edge, two disjoint visible regions, 33-row strip boundaries, overlapping
children and pointer restoration. The existing hosted empty-interior and
white-stipple behavior is preserved; these cases do not claim broader donor
VDI compatibility. TEDINFO/editing and all 36 primitive/retained-widget scenes
also pass. The host suite passes 452 tests with four historical-source skips.
The object fixture peaks at 952 stack bytes, leaving 328 above its floor.

The unchanged dialog now makes **14 logical fills**, as planned, versus TX5's
59 and the original 75. Fixed fill records fall from 145 to 42; borrows,
uploads and launches remain eight. There is no extra internal-drain cost in
this workload. TX5 → TX6 cycle-trace means are **118.758 → 90.292 ms elapsed**
and **71.591 → 49.155 ms Task CPU**. The bar and text controls are essentially
unchanged.

Forty matched Panel presses give median/p95 **100.288/120.496 ms**, compared
with TX5's 80.331/100.289 ms. This returns to the matched TX3 baseline rather
than preserving TX5's isolated feedback gain. Files selection remains
100.288/160.411 ms. These frame-granular input-to-scanout results include
application waits and scheduling; lower drawing CPU does not establish lower
feedback latency. TX7 records the combined comparison and repeated-load gate.

Reservation changes are **0 fixed, 0 per public Task and 0 idle bank-zero bytes**,
including guards, alignment and unused capacity; VRAM growth is **0 bytes**.
Resident C payload adds 272 code bytes and zero data bytes; the existing local
rectangle is reused. This is development validation, not hosted-system or
real-hardware qualification.

The intermediate OF816 ZIP is `build/gem-rendering-tx6/demo/exec816-demo.zip`
(540,150 bytes), SHA-256
`0a61d096bfd5b01ba65828d873ba02ff45dccb775d58ba55e95558e81926e833`.
Reproduce with the release-host wrapper, `test_aes_server.py --suite objects
--mode opt`, `test_widget_pixels.py --mode opt`, `trace_g4bench.py --load idle`
and `measure_gem_feedback.py`. Build the demo using the standard `build_demo.py`
GEM desktop/SDFS/256-byte/720-KiB profile.

## TX7: combined measurements and packaged desktop

[TX7 evidence](../development/gem-rendering-tx7.json) compares the unchanged
G4BENCH against the original trace, with the same Action! compiler revision
`81dd7dc53377c772602cc09992bdf2a694b4a43b`, release host executable, optimized
guest, Calypsi 5.18, pinned AltirraOS ROM and PAL 8×/VBXE 1.26 emulator profile.
The original packages and intermediate slice results remain intact.

| Workload | Original elapsed / Task CPU mean | Final elapsed / Task CPU mean | Original → final counter median |
| --- | ---: | ---: | ---: |
| 100×50 bar | 28.102 / 16.662 ms | 19.628 / 9.491 ms | 31.4 → 20.6 ms |
| 39 characters, even X | 24.011 / 13.277 ms | 21.798 / 11.480 ms | 26.8 → 24.0 ms |
| 39 characters, odd X | 39.349 / 25.850 ms | 22.083 / 11.665 ms | 42.0 → 24.6 ms |
| Clipped text | 41.618 / 27.682 ms | 27.503 / 16.370 ms | 45.2 → 30.4 ms |
| Five-object dialog | 144.786 / 93.196 ms | 90.292 / 49.155 ms | 156.0 → 101.0 ms |

Elapsed/CPU means come from passive cycle traces of the idle workload. The
counter column contains untraced medians of three VBI-quantized batch averages;
these are separate from individual-call p95 measurements. Final untraced idle
medians are 19.6, 21.8, 22.0, 27.4 and 90.0 ms respectively.

The complete benchmark text uses one borrow/upload/launch at either parity.
The bar does likewise, with one aligned or five odd-edge records. The dialog
uses eight borrows/uploads/launches and 14 logical fills, versus the original
ten and 75. The lower fill count preserves exact pixels and does not add
internal drains in this workload. Vertically clipped text still uses its
existing fallback, which accounts for the longest clipped-text work units.

The development-only `gem_render_load.c` app exercises public 64/80-character
even-X and 64/79-character odd-X requests plus even/odd 100×50 fills. It runs
beside Panel, Files and the shell, replacing Counter. Only its mode word is
controlled by the observer. The immutable boot/SYS/ROM files come from each
ZIP; a separate WORK fixture contains the diagnostic app. The app binary is
identical in all comparisons. Independent scanout checks cover every load.
Each measured call includes its own UPDATE pair, while G4BENCH amortizes that
pair over groups. Application timer waits between calls are excluded.

A framed work area exposes 624 pixels. The 80-character request at X=8 draws
78 complete cells; the 79-character request at X=9 draws 77 complete cells and
one partial edge. The latter needs the native upload plus its edge submission.
Both 64-cell calls retain a single borrow/upload/launch. TX1/TX2's native tests
cover complete 80-/79-cell screen rows. The covered-window fill diagnostic has
two visible intersections, and therefore two direct-fill borrows; its earlier
16-row implementation used four. The unobscured G4BENCH bar checks the
single-intersection case.

Forty steady calls per load give the following cycle-observed distributions.
Borrow includes admission waiting; held time starts after `DisplayEnter` and
ends before `DisplayLeave`, including any preemption during that interval.
The maximum columns cover all captured calls, including physical-input cohorts.
All values are milliseconds.

| Request | TX3 completion median / p95 | Final completion median / p95 | Final borrow median / p95 | Maximum borrow / held |
| --- | ---: | ---: | ---: | ---: |
| even64 | 43.564 / 43.935 | 43.549 / 43.978 | 5.903 / 5.928 | 9.101 / 4.793 |
| even80 | 45.071 / 45.418 | 45.002 / 47.514 | 6.813 / 9.543 | 69.508 / 26.501 |
| odd64 | 43.811 / 46.424 | 43.752 / 44.184 | 6.088 / 6.124 | 9.127 / 5.006 |
| odd79 | 60.048 / 60.064 | 60.025 / 60.086 | 11.976 / 12.064 | 71.812 / 27.008 |
| even-bar | 45.801 / 48.928 | 56.086 / 56.547 | 2.034 / 2.117 | 4.769 / 0.952 |
| odd-bar | 50.189 / 50.526 | 41.567 / 41.930 | 2.778 / 2.861 | 37.206 / 16.070 |

The even-bar diagnostic illustrates the remaining scheduling cost: median
Task CPU falls from 18.041 to 13.596 ms, while off-Task time rises from 24.006
to 39.668 ms. Its individual UPDATE envelope therefore completes later despite
cheaper drawing. The unchanged G4BENCH bar improves both elapsed and CPU time.
Large borrow maxima during input include waiting for admission; they must not
be interpreted as uninterrupted renderer CPU or uninterrupted hardware ownership.
The maximum observed admitted hold is 27.008 ms in these captures.

Matched physical input uses 40 samples per cohort and independent scanout
comparison. Completion polling is once per frame. TX3 → final idle Panel
median/p95 is 100.288/120.498 → 100.288/120.496 ms; Files selection is
100.289/160.426 → 100.288/160.411 ms. TX4's intermediate one-frame Panel p95
increase is absent in the combined implementation, while TX5's unusually low
idle Panel median is not retained.

| Repeated load | Panel median: TX3 → final | Panel p95: TX3 → final |
| --- | ---: | ---: |
| even80 | 140.202 → 120.245 ms | 140.455 → 140.211 ms |
| odd79 | 140.202 → 100.288 ms | 140.458 → 120.245 ms |
| odd-bar | 120.498 → 100.288 ms | 140.467 → 140.455 ms |

The TX4 → TX5 repeated odd-fill comparison separately improves Panel p95
from 140.455 to 120.498 ms. Its completion median falls from 50.132 to
41.936 ms; its two visible intersections use two uploads instead of four.

A fixed 15-frame inter-motion schedule initially moves even80's pointer median
from 120.245 to 140.453 ms, with p95 unchanged near 140.454 ms. The planned
ambiguous-case repeat cycles waits through 11–20 frames identically on both
images. Both then measure 100.289 ms median and 140.454 ms p95. Odd79 likewise
matches at 100.289/120.497 ms. The initial median increase is phase-sensitive
and does not reproduce across that sweep. Both cohorts remain in the evidence.
These pointer values include the positioning helper's scheduled 70,000-cycle
(39.47 ms) delay; they compare progress under matched load, rather than measuring
bare mouse-driver latency. Rendering continues throughout every input cohort.

The measured development performance gates pass: primitive CPU/elapsed gains,
expected counts, pixels, ownership/failure cleanup and matched feedback without
a reproducible median/p95 regression. Individual call completion remains
sensitive to UPDATE/scheduling phase, as the even-bar diagnostic shows. Drawing
still publishes directly, so occasional flicker can remain.

The exact refreshed ZIP passes the full dialog/selector/TEXT walkthrough with
Files launch integration, Panel keyboard input, calculator/native launches,
covered-window and close/exposure repair, cancellation, parent/child cleanup,
heap return and clean shutdown. OF816 waits five seconds before autoboot.
The smallest observed ordinary-Task headroom is 132 bytes (slot 5); guards and
the 128-byte walkthrough threshold pass. Targeted emitted pixel, budget,
ownership and fault tests are recorded separately in TX4–TX6. The final host
suite passes 452 tests with four historical-source skips. These are development
checks, not hosted-system or physical-hardware qualification.

TX7 adds no production reservation or payload. Across TX4–TX7, bank-zero
reservation growth is **0 fixed, 0 per public Task and 0 idle bytes**, including
guards, alignment and unused capacity. VRAM reservation growth is **0 bytes**.
Resident C payload grows by 1,326 code bytes and 325 table bytes relative to
TX3, within existing upper-memory reservations. No stack reservation grows.

The final OF816 ZIP is `build/gem-rendering-tx7/demo/exec816-demo.zip`
(540,148 bytes), SHA-256
`9972bf1c730100cddbde241d5e072be6e43e3656ec7d1bb74f6590b9265a567a`.
It contains boot files, matching disks/ROM, a short guide, checksums and license
notices. Development apps, build intermediates and traces remain outside it.
Launch with `build/gem-rendering-tx7/demo/launch-altirra.command`.

Reproduce the final checks with the recorded release-host build wrapper:

```sh
python3 build/gem-rendering-tx7/host_release.py tools/build_demo.py \
  --gem-desktop --format sdfs --sector-bytes 256 --system-kib 720 \
  --output build/gem-rendering-tx7/demo
python3 tools/trace_g4bench.py --bundle build/gem-rendering-tx7/demo \
  --output <fresh-trace-directory> --load idle
python3 tools/measure_g4bench.py --bundle <separate-demo-copy> --load both
python3 tools/measure_rendering_load.py --bundle <archived-demo> \
  --output <fresh-load-directory>
python3 tools/measure_rendering_load.py --bundle <archived-demo> \
  --output <fresh-phase-directory> --modes 2,4 \
  --pointer-waits 11,12,13,14,15,16,17,18,19,20
python3 tools/test_text_viewer_demo.py --bundle build/gem-rendering-tx7/demo --files
```

Use the same diagnostic binary and schedules with the archived TX3 and final
packages, and `--modes 6` with TX4/TX5 for the isolated fill comparison.
`measure_rendering_load.py --output <capture> --analyze` reuses saved CPU
observations. Its analyzer aligns the debugger's 32-bit sample clock with the
extended trace clock; initial capture-analysis failures and their correction
are retained in the evidence. They required no guest change or recapture.
