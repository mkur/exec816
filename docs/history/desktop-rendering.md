# Desktop rendering development

[History index](README.md) · [Design](../plans/gem4xe/desktop-rendering-design.md) ·
[Plan](../plans/gem4xe/desktop-rendering-implementation-plan.md)

## DR0: preserve the renderer and its observations

The [baseline record](../development/desktop-rendering-dr0.json) pins the
optimized executable, toolchain, emulator, ROM, machine, maps and stack usage.
The complete executable and large pixel outputs remain in
`build/desktop-rendering/dr0/moves/`; the frozen copies must not be rebuilt for
later comparisons. `tools/record_rendering_baseline.py` checks the 15 full-frame
comparisons before recording the baseline.

The expanded presentation fixture covers console output/scroll, odd occlusion,
exposure, and a static command window moving in all four directions, between
disjoint positions and to screen edges. It uses independent retained pixels,
without reading the renderer's damage/visibility to construct expected output.
Settling samples include request processing, repair, caret and two explicit PAL
frames. They are **not** hardware DMA durations. The pinned observer exposes IRQ
and adoption boundaries, not exact hardware BUSY edges; retain this limitation
in subsequent timing reports. Mouse, widget and IRQ evidence is referenced by
hash rather than rerunning those completed matrices.

The fixture now uses an explicit 8 KiB upper-RAM globals arena, matching the
widget fixtures; its former 2 KiB arena no longer fits the merged desktop. The
demo's separate 4 KiB arena is unchanged. There is no production implementation
change in DR0. Reserved bank-zero delta is zero for fixed state, root/kernel,
each of eight public Tasks and idle, including guards, alignment and capacity.
VRAM delta is zero. Eight damage entries and candidate cache ranges
`$50000–$5FFFF`, `$60000–$6FFFF` are checked against current reservations and
diagnostic scratch; this slice does not reserve those ranges.

## DR1: bounded damage and streamed painting

Layers now retains eight damage rectangles per layer/background. Containment
and exact rectangular unions merge; a ninth unmergeable rectangle collapses all
entries to a conservative bound. The existing 96-entry visibility/work capacity
is unchanged. `AdvancePaint` streams the next nonempty damage intersection and
must return EMPTY before successful Finish. Failure preserves the complete
original damage list. Every desktop, direct-console and fixture consumer has
been migrated.

The [DR1 record](../development/desktop-rendering-dr1.json) includes optimized
geometry, independent pixel-set coverage of eight batches exceeding 96 total
fragments, 15 desktop and ten widget scenes. Small raw/optimized probes cover
far record access, eight advances, early Finish rejection and call results.
The host suite passes 352 tests with four skips. These are development checks.

A Layer grows from 792 to 850 bytes; a Scene and its enclosing desktop Service
each grow by 292 bytes in upper RAM, including alignment and spare damage slots.
No mutable Layers globals or new allocations are introduced. Reserved bank-zero
delta is zero for fixed, root/kernel, every public Task and idle; guards,
alignment and unused stack/DP capacity are unchanged. VRAM delta is zero.

## DR2: typed asynchronous copies and shared completion

`VbxeCopyStart` copies up to 640×240 even-aligned pixels in one launch, including
safe overlap direction. Synchronous CopyRect shares its geometry preparation.
Copies and copy/fill scrolling use the same operation ID, pending state, IRQ
signal, command arena and deadline. `VbxePoll` replaces ScrollPoll throughout
current code and tools. Empty/identical copies return OK with ID zero; BUSY and
invalid admission preserve the output. No caller descriptor survives launch.
The console drawing packet gains COPY_START without changing its 78-byte size.

The [DR2 evidence](../development/desktop-rendering-dr2.json) records optimized
pixel/overlap and failure cases, maximum copy, reopen/exhaustion, lost IRQ/tick
wrap, unquiesced retention, mapping NMI, batched console output and drawing
ownership/context cleanup. Small raw/optimized boundary probes cover descriptor
and native-call behavior. The copy control disables substituted status reads;
its fixture launch counters remain explicit. These are development checks.

Operation state is renamed, not duplicated: seven existing payload bytes plus
the existing four-byte sequence counter. Upper-RAM driver-state delta is zero;
VRAM delta is zero. Fixed, root/kernel, all public Task and idle reserved
bank-zero deltas are zero, including guards, alignment and unused capacity.
There is no new signal, Task, stack, DP, queue or watchdog.

## DR3: transactional window moves

Clean, aligned front windows now copy through one IRQ-completed operation.
Layers retains old/new bounds in its existing rectangle pair; it publishes new
geometry only on successful completion and damages old-minus-new exposure.
Failure after quiescence keeps old geometry and invalidates touched pixels.
Programmatic MOVE and drag release share one continuation. Replies acknowledge
geometry commit, while queued mutations remain gated during DMA. Console moves
rebase placement without replaying its circular character model.

The [DR3 record](../development/desktop-rendering-dr3.json) includes far-layout
and transaction probes in both modes, optimized service/desktop/widget scenes,
physical idle drags, screen-edge moves and cancellation/retirement checks. A
passive CPU trace verifies one asynchronous launch for each of eight eligible
moves. The small emitted probe checks old hit-test geometry during the hold,
atomic commit and failure damage. The drag oracle now waits for adoption after
gesture release. Removing a caret explicitly schedules its restoration even
when the copied move exposes no console pixels. No observer code is linked
into the production executable.

The Layers/Service records do not grow: transactions reuse the existing saved
rectangle pair. Presenter globals add ten upper-RAM bytes within the existing
arena. Reserved bank-zero and VRAM deltas are zero; fixed, root/kernel, all eight
public Tasks and idle retain their guards, alignment and full reserved capacity.
Desktop test helpers default to an 8 KiB globals arena for composed fixtures;
demo builders continue supplying their explicit 4 KiB profile.

The two idle drag samples reached 279.6 ms release-to-repair, exceeding the
250 ms target. These checks establish correctness, not timing acceptance;
DR4–DR7 retain this open target and require the larger matched sample set.

## DR4: disjoint base backgrounds

The painter fills the frame around each client intersection, then fills the
client once. Title, close gadget, clipped opaque text, widget styles and the
sixteen-scanline/four-command quanta remain unchanged. The independent optimized
desktop and widget rasters pass all 25 scenes; see the
[DR4 record](../development/desktop-rendering-dr4.json).

For a complete 528 by 184 console window this removes 40,960 bytes of duplicate
base fill; the 160 by 80 command fixture removes 4,032. These are geometry-derived
work counts, not measured DMA time. The separated side borders increase base
fill calls (22 to 32 and 9 to 14 respectively), so setup-heavy scenes can cost
more despite fewer pixels. Matched scene timings are retained without attributing
whole-scene time to the blitter. No glyph/copy replay count or exact hardware
BUSY-edge claim is made by this check.

Reserved bank-zero delta is zero for fixed state, root/kernel, each of eight
public Tasks and idle, including guards, alignment and unused capacity. Upper
RAM globals and VRAM reservations also have zero delta.
