# Bitmap console implementation plan

[Design note](bitmap-console-design.md) · [Implementation plans](../README.md) ·
[GEM work](README.md) · [Roadmap](../../roadmap.md)

Status: implementation started, 3 October 2026. B0–B7 have passed development checks;
B8–B9 remain unimplemented. This plan implements
the design's 80×30 bitmap backend for the existing console, improving the shared
VDI drawing path first. Each slice must leave an executable, reviewable result;
commit it with its focused development evidence before starting the next slice.

## Fixed decisions

- Use the existing 640×240 HR mode, built-in 8×8 font, logical palette and one
  visible framebuffer. The bitmap console selects opaque scanout explicitly.
- Reuse CON:/RAW:, console instances, cooked editing, input routes and shell
  code. Retain the normal 40×24 text backend in the same implementation.
- The console worker owns VBXE and calls a shared drawing library through a
  tested ordinary-call bridge. Use one existing 2,560-byte worker pool, with no
  extra rendering Task or enlargement of stacks/DPs.
- Start with one 4 KiB VRAM command arena, at most 64 records per list and a
  synchronous fence at each bounded list boundary. Preserve GEM command reply
  semantics and the inactive-interrupt hardware baseline.
- Optimize nonzero-ink text while preserving hardware-zero ink, clipping and
  outside pixels. Copy rectangles initially require even X and even widths.
- Preserve accepted-byte WRITE completion. Rendering generations and hardware
  fences are separate from source-buffer lifetime and visible scanout.
- Keep a steady underline caret. Defer mouse drawing changes, blinking, PMG,
  double buffering, hardware-text mode, overlapping windows and AES.

## Slice dependencies and outputs

| Slice | Executable result | Depends on |
| --- | --- | --- |
| B0 | Reproducible text, copy and console baseline with timing boundaries | Current tree |
| B1 | Hosted GEM drawing through bounded command lists | B0 |
| B2 | Faster glyph runs and packet preparation with unchanged pixels | B1 |
| B3 | Checked reusable bitmap copies with overlap handling | B1 |
| B4 | Worker-owned console presentation using the text backend | B0 |
| B5 | Backend geometry, retained 80×30 models and row damage | B4 |
| B6 | Bitmap console startup, checked language bridge and exact full redraw | B2, B3, B5 |
| B7 | Dirty runs, synchronized pixel scrolling and caret integration | B6 |
| B8 | Shell, pipelines, coexistence and measured responsiveness | B7 |
| B9 | Optional packaged bitmap console and current documentation | B8 |

The table records logical dependencies. Execute and commit in listed order to
keep reviews small and avoid simultaneous ABI edits. B6 is the first usable
bitmap console; B7/B8 establish whether it is fast enough.

## B0 Freeze the baseline and acceptance workloads

Promote the local text experiment under `build/gem-text-performance/` into a
maintained focused fixture. Reuse [build_gem_vdi.py](../../../tools/build_gem_vdi.py),
the [raster oracle](../../../tools/gem_render_oracle.py), console observers and
existing bridge timing facilities; do not create a general profiling framework.
Any new runner names in this plan describe planned tools, not existing commands.

Freeze the Action! pin, Calypsi tools/flags, selected GEM source, ROM, emulator,
FX core, CPU multiplier, memory, PAL raster and physical SDFS transport. Record
source and executable hashes. Use the current mouse-capable production pin when
measuring ST/SIO overhead, rather than comparing different emulators silently.

Measure single characters, 8/32/64-character runs, odd X, clipped glyphs,
zero-colour ink, full 80×30 repaint, fill, and an isolated full-width eight-pixel
scroll copy. Separately record current text-console accepted bytes, retained
scroll and presentation costs. Include blank, dense and mixed strings; avoid
using empty space as a proxy for normal text.

Collect preparation cost, MEMAC traffic, BCB count, launch-to-idle time and
end-to-end visibility. Use cycle/scanline timestamps for sub-frame measurements,
with scanout observation outside any measured execution interval it could alter.
Reuse original production hardware status reads. A transformed observer must
have its own hash and an identical-image replay without active observation.

Freeze the design's 40 ms input, 20 ms fenced scroll, following-frame scroll
visibility and 500 ms full-repaint targets. Define exact input positions, screen
patterns, request sizes, peer work and disk contents. Record input capture both
disabled and enabled; neither result predicts mouse-drawing cost. Store compact
portable evidence in `docs/development/` and bulky traces under `build/`.

**Gate:** independently checked pixels and repeatable timings, with every clock
boundary and excluded setup cost stated. Existing slow results are the baseline,
not a failure of B0. Commit the maintained fixture and baseline record.

B0 development evidence: [portable baseline](../../development/bitmap-console-b0.json).
The maintained `tools/test_gem_text.py` runs 26 pixel-checked cases with optional
passive cycle observation and identical-image replay. The text-console fixture
also passed observation/replay. Timings distinguish packet construction, requests,
and launch-to-confirmed-idle; the latter includes driver/polling/scheduling cost.
First-visible input latency, isolated Task CPU time and exact hardware occupancy
remain measurements for the subsequent integration gates; the baseline does not
claim these from tick or elapsed-driver values. Bank-zero delta is zero fixed,
root/kernel, per public Task and idle, including guards and reserved slack.

## B1 Submit bounded blitter lists

Extend [vbxe.c](../../../platform/altirraos/vbxe.c) and its
[C declarations](../../../c/include/hardware/vbxe.h) with a validated list
submission operation. The driver receives CPU-side records, validates the whole
extent and allowed operations, and constructs driver-owned VRAM records. Set
the chain bit internally. Reject oversized lists, arithmetic overflow, invalid
source/destination extents and stale ownership before any hardware mutation.

Replace the old BCB reservation in [vbxe-vram.json](../../../platform/altirraos/vbxe-vram.json)
with the design's 4 KiB arena and add its upper-RAM construction storage. Begin
with the existing positive-step operations. Keep one list in flight, real
BUSY/BCB_LOAD completion checks, interrupts enabled and the existing timeout/
STOP/quiescence recovery. MEMAC B and VBXE IRQs remain disabled.

Change [gem-vbxe.c](../../../ports/gem4xe/adapter/gem-vbxe.c) so blit callbacks
append records and flush at dependency/budget boundaries. Give `blit_pending`,
`blit_start` and `blit_run` truthful queued/completed behaviour. Fence before
CPU window reads, staged writes, font/glyph scratch reuse and cursor scratch
reuse. A full arena may flush part of a VDI command, but the service still
counts it only after the command's final successful fence. Retain fault latching.

Split lists by estimated work as well as count; a full-screen operation may
need row chunks even though it is only one BCB. Preserve dependencies and copy
direction when subdividing. Do not hold Forbid or mask interrupts for a list.

**Gate:** selected raw/optimized G3/G4 pixel, guard, mapping-interruption and
recovery cases pass with actual hardware reads in a production control. Cover
empty/oversized/malformed lists, arena exhaustion, scratch reuse, cursor drawing,
partial-command failure, timeout wrap, recoverable STOP and reset-required park.
B0 reports fewer submissions for long strings without changed pixels or GEM
completion counts. Commit the adapter and hosted backend together.

B1 development evidence: [bounded lists](../../development/bitmap-console-b1.json).
Raw/optimized drawing, maximum/invalid lists, mapping interruption, fault
recovery, cursor and a concurrent physical-SDFS workload passed. A 64-character
line drops from 480 to 185 ms without ST capture; 129 submissions become three.
Chunked full-screen copies cost more total time than the previous long command;
B3/B7/B8 retain the original latency gate. These are development measurements,
not achieved desktop responsiveness. Added reservations: bank zero 0 in every
category, upper construction storage 4,096 bytes inside the existing C bank,
and VRAM +3,840 bytes including unused command capacity.

## B2 Optimize text and request construction

Share the existing atlas and add a fast path for fully visible nonzero-ink glyphs
using one stencil command per ink glyph. Keep the exact hardware-zero path and
the clipped fallback. Fill each opaque text run once, using explicit foreground/
background values in the common drawing layer; adapt VDI's existing replacement
background rule at its boundary. Preserve baseline placement and font metrics.

Keep donor changes in the extraction/patch workflow under
[ports/gem4xe](../../../ports/gem4xe/README.md), never only in a generated build
tree. Factor reusable drawing operations out of the current service adapter so
the console can call them later without importing client IPC or cursor policy.
Keep one font, fill and clipping implementation shared by those callers.

Preinitialize BCB templates and patch changing fields. Retain full validation at
submission rather than repeat lease/extent crossings for each private glyph
helper. Skip empty ink while painting its opaque background. Keep mutable
templates private to the owning Task and immutable once submitted.

In [gem-client.c](../../../ports/gem4xe/service/gem-client.c), initialize the
submitted packet extent plus required reply/header state rather than all 2,204
bytes. Preserve zeroed reserved words, message linkage rules, exact lengths,
bad-packet rejection and one-pending-request ownership. No service ABI change is
needed merely to clear fewer unused bytes.

**Gate:** raw/optimized emitted pixels for all sixteen pens, both X parities,
spaces, clipping through each nibble, empty strings and repeated mixed commands;
packet reuse and stale-input/output regressions; service completed-prefix tests.
Record font initialization separately from repeated text cost. Commit only with
an explained B0 comparison; do not claim the hardware-only estimate as throughput.

B2 development evidence: [text and common drawing](../../development/bitmap-console-b2.json).
All sixteen pens, both parities, clipping, packet reuse, cursor and shared-library
cleanup passed focused emitted checks. At the pinned PAL ×8 configuration,
64 characters take 72.5 ms without ST capture (B0: 480 ms; B1: 185 ms), and
80×30 repaint takes 3.02 seconds (B0: 18.62; B1: 7.54). Idle ST capture raises
those to 102.5 ms and 4.22 seconds. Font initialization is outside those repeated
text intervals. The 500 ms repaint target remains unmet. Bank-zero delta is zero
in every category; 277 added upper bytes fit existing reservations; VRAM delta 0.

## B3 Add reusable bitmap copy operations

Add a common-library rectangle copy using explicit VRAM offsets, pitches and
dimensions. It is an ordinary driver/library operation, not a new COP service
or an automatically advertised VDI opcode. Freeze its generated descriptor and
document supported geometry before implementation.

Support byte-aligned rectangles in either overlap direction. Extend internal
BCB validation to signed X/Y steps using widened minimum/maximum address
calculations. Start descending copies at the last source/destination row or
column, and retain that ordering between chunks. Check the complete operation
before touching pixels. Treat empty rectangles as a no-op at the drawing layer;
never underflow the hardware minus-one dimensions.

Reject odd X, odd widths, parity changes, invalid pitches and out-of-surface
extents without mutation. The first console caller redraws unsupported geometry.
Do not use nonzero stencil transparency as a general opaque-copy substitute:
source pixels may legitimately contain zero. Reuse constant fills for new rows.

**Gate:** emitted raw/optimized copies compared to an independent memmove-style
model: up/down/left/right overlap, same rectangle, distinct surfaces, height one,
VRAM 4 KiB and 64 KiB crossings, edge rejection and guard preservation. Repeat
a chunked copy with NMI/SIO activity and test a fault between chunks. Record
fenced full-width scroll cost separately from its future console scheduling.

B3 development evidence: [checked bitmap copies](../../development/bitmap-console-b3.json).
Raw/optimized snapshot-model copies cover all overlap directions, separate
surfaces, VRAM boundaries and rejected geometry. Injected faults verify the
completed chunk prefix, recoverable STOP, tick wrap and reset-required retention.
The ordinary API validates the entire descriptor once and constructs private
bounded records. A 640×232 copy measures 28.828 ms without ST and 34.275 ms
with idle capture; identical-image replay preserves pixels and tick results.
The complete console scroll remains B7/B8, and the 20 ms target is still unmet.
Reserved bank-zero, upper-bank and VRAM deltas are all zero.

## B4 Put console presentation in its worker

Refactor [consoledisplay.act](../../../lib/console/consoledisplay.act) into a
backend boundary while preserving the current text implementation. Migrate
display mutations from [consoletiling.act](../../../lib/console/consoletiling.act)
and instance retirement to retained control transactions processed by the worker.
Use the existing public message/signal/lease facilities; no private kernel entry.

Specify the transaction states, caller/instance holds, exact acknowledgement,
busy rejection and shutdown behaviour in generated private records. Reserve
control storage before admission so hide/stop cannot depend on a new allocation.
Do not queue a worker request behind a presentation lock that prevents the
worker from servicing it. Internal worker operations must not wait on themselves.

Keep validation and owner checks for Show/Hide/Focus. Preserve focus capture
identities, hidden writes, synchronous erasure, late write presentation borrows,
and the existing rule that open instances prevent destruction/stop. No caller
may touch physical screen memory after this migration.

**Gate:** text-only raw/optimized presentation/focus, cancellation, startup and
lifetime cases pass. Exercise concurrent control calls, caller-removal holds,
destroy during pending redraw, input arriving during control completion, failed
startup and lost-wakeup boundaries. Exact OS screen restoration remains required.
Commit the ownership refactor independently of bitmap hardware bring-up.

B4 development evidence: [worker presentation controls](../../development/bitmap-console-b4.json).
Raw/optimized focus, capture identities, cancellation, window lifetime and startup
rollback pass. A gated transaction checks competing calls, caller retention and
input delivery; a submission just before worker Wait checks durable notification.
The eight-byte private transaction fits a metadata reservation enlarged from
720 to 736 upper bytes, including added alignment/slack. Every bank-zero category
changes by zero. Presentation now enforces its existing scheduling-permitted
precondition by rejecting outer Forbid before admission.

## B5 Widen geometry and track row damage

Update [console.json](../../../abi/console.json),
[generate_console.py](../../../tools/generate_console.py), the core, display
records and all callers/tests together. Use one maximum model geometry of
80×30/2,400 bytes, with separate active display capabilities. Allocate actual
instance dimensions and reject overflow/bad buffers before clearing them.
Text admission and Show remain limited to 40×24.

Add `CONSOLE.ScreenWidth()` and `ScreenHeight()` with the readiness semantics
from the design. Remove fixed 40/24 assumptions from common tiling and retained
editing; leave physical text pitch 40 inside the text backend. Keep four slots
and current unit/route identities. Audit cooked-editor width calculations,
echo buffers, tab stops, immediate wrapping and height-one scrolling.

Replace the old dirty-interval representation and its observers with per-row
half-open bounds. Do not keep two competing authoritative damage models.
Track model/presentation invalidation and oldest unpresented damage. A change
arriving after a bounded redraw cannot be erased by that redraw's bookkeeping.

**Gate:** host layout checks and generator `--check`, plus raw/optimized model
fixtures for 1×1, 3-column cooked input, 40×24 and 80×30, invalid extents,
bank-crossing cells, hidden/show, sparse changes on distant rows, control bytes,
clear/scroll and cancellation. Text presentation remains an executable control;
an 80×30 retained-model test does not yet claim bitmap display support.

B5 development evidence: [geometry and row damage](../../development/bitmap-console-b5.json).
Core raw/optimized tests cover 80×30 across a CPU bank, sparse distant-row
damage, preserved age and stale-generation acknowledgements. Text display,
focus, cancellation, narrow cooked input and allocation rollback pass. Current
capability queries report 40×24 only while ready. The existing 36-character
cooked tail stays bounded by the caller's available row space; its 128-byte echo
buffer remains sufficient. Instance/presentation payload grows by 132 upper bytes
per instance, below the 256-byte allowance. The rounded default metadata grows
144 bytes to 880. Bank-zero reservation changes by zero in every category.

## B6 Bring up the bitmap backend

Link the shared C drawing library into an optional native console build using
the existing foreign-image placement/validation machinery in
[native_program.py](../../../tools/native_program.py) and the Calypsi builders.
Link console support with automatic startup deferred, so the ordinary bootstrap
can bind the drawing entry and display bridge before calling console Start.
Add a narrow checked
ordinary-call adapter and generated native/C packet definitions; do not call
C or Action! functions using the other's argument convention. Test C entry/
return with sentinel lower-DP values, full registers, odd/even stack alignment,
pointer limits and native/emulation interrupt entry before using it in CON:.

Select the console worker from an existing 2,560-byte pool in bitmap builds.
Admit it before small background workers and reject unavailable pools cleanly.
Bind the adapter and establish cold-boot authorization before readiness. Keep
code/data, construction records and row tables in upper RAM, and validate the
foreign banks against OF816/loader/runtime lifetimes and heap reservations.

Implement bitmap claim, full redraw, erase, fence and release. Install the
existing font and palette with explicitly opaque 640×240 presentation. Use the
current fixed glyphs and colours. Start with exact bounded full redraw as the
fallback, with row-damage information available for B7. All hardware entry runs
on the console worker, including presentation controls and cleanup.

Exercise a direct full-screen CON: workload and native input, without importing
the desktop or GEM application loop. Preserve WRITE completion after logical
acceptance and ensure the renderer holds no freed source buffer. On display
fault, retire or error outstanding requests and control waiters exactly once;
confirmed idle permits restoration, while unquiesced DMA requires reset.

**Gate:** raw/optimized native/C context checks, exact 80×30 pixels, unsupported
hardware and busy-display rejection, every partial startup unwind, stack/domain
guards, high-water marks and full OS/input/display cleanup. Complete a read,
write, clear, hide/show and stop cycle. Report the whole linked image and heap
cost relative to both the text demo and existing GEM build.

B6 development evidence: [worker bitmap backend](../../development/bitmap-console-b6.json).
Raw/optimized bridge and exact scanout checks pass for both stack parities,
full registers and twenty lower-DP sentinels, with timer IRQs and native NMIs.
The 80×30 workload covers write, read, clear, hide/show and stop. Allocation,
signal, capture, display-busy and large-pool exhaustion unwind; absent and
unsupported hardware leave the OS intact. Pending reads and writes retire on a
quiesced rendering fault; unquiesced DMA retains ownership and requests for reset.
The worker uses slot 6 from the existing large pools. Its eight-byte binding fits
existing metadata slack, so metadata, alignment and every bank-zero reservation
have zero delta. The shared C image reserves 131,072 upper bytes relative to text,
with packet/workout storage inside those banks. No fast-console claim is made;
caret, pixel scrolling, loaded SDFS latency and packaging remain B7–B9.

## B7 Present dirty runs and scroll pixels

Render only dirty row spans, splitting by foreground/background, command capacity
and work budget. For now the console uses one fixed pair; the primitive remains
usable by VDI with other pens. Reconcile presented generations only after the
relevant list fences. A clean screen and unchanged caret submit nothing.

Implement the design's scroll eligibility decision before retained editing.
Remove the caret, optionally settle a small dirty span, copy/fill in safe chunks,
commit the retained edit once, then redraw the caret. Use full model redraw for
hidden, stale, invalidated or unsupported sources. Support narrow tiles without
touching neighbouring pixels. Keep continuations in retained presentation state,
validated by unit and generation at each borrow, not a borrowed stack pointer.

While a physical scroll continuation is active, defer new model writes for that
instance. Input capture/read service, control processing and other instances
continue. Hide/retirement drains an active list and retires the continuation;
show starts from full invalidation. Cancellation counts only accepted source
bytes and never rolls back a completed logical scroll or replies twice.

Add the steady focused underline caret. Restore from retained content before
moving, copying or erasing; redraw last. Test byte footprints and ensure no caret
pixels enter scroll destinations. Preserve the shared GEM renderer's cursor
save-under invariants without adding mouse optimization to this slice.

**Gate:** patterned nonblank scrolling, consecutive wraps, text-plus-newline,
clear, height one, narrow tiles, pending damage, generation changes and faults
between chunks. An eligible scroll draws no unchanged-row glyphs. Compare final
pixels against full model redraw, including the caret. Raw/optimized correctness
passes; optimized measurements record actual list/CPU budgets and all fallbacks.

B7 development evidence: [scrolling, damage and caret](../../development/bitmap-console-b7.json).
Raw/optimized scanout matches an independent retained-model oracle for full-screen,
narrow and height-one tiles, consecutive wraps, clear, hidden output and caret
movement. Continuation tests cover input service, cancellation after one accepted
byte, hide/show and stale unit/view/model identities. Faults after the first copy
chunk cover STOP recovery and reset-required retention. Passive operation counts
show only two or three glyphs for eligible full-screen scrolls, and no drawing
in any settled interval; identical-image replay preserves every scanout hash.
These intervals include fixture waits and do not establish latency acceptance.
Each borrow copies/fills at most sixteen pixel rows, with internal list work capped
at 8,192 pixels. Presentation payload grows sixteen upper bytes, fitted into
existing default metadata padding; metadata remains 880 bytes and bank-zero/VRAM
reservations have zero delta. B8 must still measure and satisfy or explicitly
revise the responsiveness gate.

## B8 Integrate the shell and meet the measured targets

Reuse the shared shell/prime session with queried display dimensions. The bitmap
layout uses 80×24 shell and 80×6 prime tiles; the text layout remains 40×18 and
40×6. Generate the separator/title from the selected width so literal forty-column
wrapping cannot corrupt the scene. Use unchanged DOS commands and cooked editing.

Run TASKS, MOUNT, CD SYS:, DIR, HELLO, TYPE, MEM, HELLO-to-WC and CAT-to-WC.
Check shell input, long lines, editing near the right edge, history, EOF, BREAK,
hidden output, focus and clean exit. Verify command results, file bytes and
ownership, not only screenshots. Prove the remaining heap and Task pools admit
the normal seven-Task pipeline; declare any eighth stress Task explicitly.

Run the frozen B0 timing workloads with input and physical SDFS active, including
an independently acquired idle/active ST source with no pointer drawing. Keep
SIO timing assertions and mouse sampling/loss bounds unchanged. Measure maximum
CPU quantum, list occupancy, source acceptance, completion fence and visibility;
include first outstanding damage when output arrives repeatedly.

Require the design's optimized acceptance targets on the declared workloads.
Tune source/drawing budgets and ordinary library code only from measurements.
If scheduler delay or code size prevents acceptance, retain the failing evidence
and revise the design explicitly before adding a general kernel feature. Do not
mark the milestone fast on the strength of a standalone blitter benchmark.

**Gate:** full-screen and tiled pixel oracles, focused eight-Task fairness,
context/stack checks, SIO/cancellation/cleanup, and the measured latency targets
pass. Replay the final production image without active observers. Record exactly
which raw and optimized cases ran; broader hardware qualification remains open.

## B9 Package and document the result

Add an explicit optional bitmap-console selection to
[build_demo.py](../../../tools/build_demo.py), with a separately selected boot XEX
and its matching system disk. Keep the standard OF816 image, pinned ROM, upstream
notices and five-second normal shell/prime autoboot. Do not silently switch the
existing default artifact to a graphics-required profile. Record actual new
command-line options only once implemented.

Generate `exec816-demo.zip` with boot files, concise setup instructions, notices
and checksums only. Keep intermediary images, manifests and reports in `build/`.
Document the explicit bitmap XEX selection and required VBXE/native-65816 setup;
do not imply that a direct bitmap XEX has an OF816 handoff unless that route is
also built and executed. Use an executed production screenshot with provenance.

Test the extracted ZIP's bitmap boot, shell commands/pipeline, keyboard/BREAK,
wrong/missing disk handling and exit. Also run standard OF816 autoboot and manual
Forth-to-shell controls with ordinary disk use. Verify archive whitelist, exact
checksums, notices and matching-media instructions.

Publish implemented geometry, presentation ownership, completion, fault and
memory semantics in the console/display references; update guides and indexes.
Move the completed design discussion to history according to repository policy,
retaining links and evidence.

**Gate:** the extracted archive, production scene, standard OF816 controls,
current contracts and fresh evidence agree. Mark B0–B9 complete only after all
executable gates pass. Commit the artifact tooling/docs and execution record;
publication of a GitHub release is a separate action.

## Validation and memory reporting

Use the [two-tier testing policy](../../contributing/testing.md). Documentation
preparation needs content/link checks only. For implementation, run host tests,
affected generators and focused emitted-code checks after each coherent slice.
Do not run complete release matrices after every commit or replace focused
interrupt/lifetime cases with host mocks.

Select/extend existing runners for the changed boundary: `test_gem_display.py`,
`test_gem_render.py`, `test_gem_service.py`, `test_gem_cursor.py`,
`test_console_core.py`, `test_console_display.py`, `test_console_scroll.py`,
`test_console_windows.py`, `test_console_focus.py`, `test_console_device.py`,
`test_console_cancel.py`, `test_console_lifetime.py`, `test_console_startup.py`,
`test_console_fairness.py`, `test_console_dos.py` and `test_of816.py` in `tools/`.
Add dedicated bitmap/bridge measurement fixtures where these cannot express the
new assertions. Record real CLI and execution scope when each runner is added.

Use raw/optimized Action! and C builds for changed compiler-facing behaviour;
performance acceptance applies to the optimized production profile. Preserve
exact binary/ATASCII fixtures and normalize host text before newline parsing.
Compiler defects belong in actionc with focused regressions, not renderer-specific
workarounds. Compiler-only passes do not qualify the hosted system.

Every slice reports bank-zero reservation deltas separately: fixed, root/kernel,
each of eight public Tasks and private idle, counting all guards, alignment and
unused capacity. The target is zero in every category. Selecting an already
reserved large pool changes occupancy, not reserved bytes. Report that occupancy
and its stack high-water mark explicitly.

Account for actual cell allocations, per-instance damage/continuation metadata,
control request storage, the 4 KiB construction buffer, row tables, original
staging/snapshots, whole C banks and remaining heap. Do not exceed the design's
provisional allowances silently. B1's VRAM change is +3,840 reserved bytes;
subsequent slices must show whether they fit that map or require a reviewed
revision. No second screen, PMG buffer or new CPU aperture is planned.

Each record includes source/compiler/ROM/emulator hashes, case list, failures
exercised, bounds and measured maxima, pixels, guards, exact cleanup, stack and
memory totals, and observer/replay scope. Full release qualification and physical
hardware validation remain separate gates. These documentation changes alone
reserve **zero runtime bytes** and establish no new executable claim.
