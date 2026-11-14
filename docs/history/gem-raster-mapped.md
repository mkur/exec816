# Mapped VRAM raster copies

[History](README.md) · [Plan](../plans/gem4xe/mapped-raster-plan.md) ·
[Display contract](../reference/display.md) ·
[Foundation evidence](../development/gem-raster-mapped-foundation.json)

## Workspace and driver foundation

The foundation reserves `$4C000–$4FFFF` (16,384 bytes) from the previously
unassigned 20 KiB interval. The generated C and Action! constants agree with
the map. Total reserved VRAM is 489,984 bytes, with 34,304 unassigned (34,272
after diagnostic borrowing). The retained Shell backing is unchanged.

Private `VbxeOwnerMapPage` fences, maps one prepared page, invokes a synchronous
CPU callback and disables the aperture before return. Only the admitted
physical owner runs it. The callback cannot start graphics, remap, wait or
retain its window pointer. Normal Task preemption and interrupt delivery stay
enabled. The existing mapping assembly and asynchronous recovery protocol are
unchanged; there is no new kernel or public ABI operation.

The optimized G3 pattern, mapping-NMI and mapped-page cases pass. Each checks
32,914 mapped-page assertions, all 16 KiB including untouched bytes, four
callbacks across active VBI and a computing peer, underlying CPU aperture RAM,
exact OS screen/cursor preservation during display ownership, physical SIO,
retained native/C context, guards and normal cleanup. Four injected NMI entries
between mapping stores retain the expected hardware publication order and
saved Task frame.

The old G3 runner needed a focused refresh to execute against the current
kernel: compare its eight-Task fixture with an eight-Task reference, allow
8 KiB of upper image data, and recognize the current guarded-stack NMI
prologue. Volatile fixture rendezvous points now check OS screen preservation
after close and before the deliberate CON write. Native target assertions
still require successful console reopening, the complete write and teardown.
These changes do not alter production interrupt code or Task reservations.

The legacy GEM source manifest fingerprints an older compiler configuration.
The execution record explicitly preserves the local test override to the
current `toolchain/actionc.json` pin, revision
`05c01f39ff3beef97af0e65b0a16666f5a1bd805`. Only the host compiler build profile
changes to release; the compiler revision and optimized guest policy remain
pinned. The fixture's upper image-data allowance grows by 4,096 bytes; production
upper reservations do not change in this foundation.

Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 idle and 0 bytes per
public Task**, including guards, alignment and unused capacity. The CPU
aperture remains `$8000–$8FFF` (4 KiB). The entire 16 KiB VRAM reservation is
counted, including unused row-slot capacity. These are development checks,
not full hosted qualification or a copy-performance result.

## Screen-copy integration

Different-parity screen-to-screen S_ONLY now captures each source band with
the blitter, runs the existing generated GEM4XE shifter directly inside mapped
VRAM, and publishes through blitter copies plus masked edge operations. Source
and output are disjoint halves of 1,024-byte row slots. All source rows in a
band are captured before destination writes; downward moves consume bands
bottom first. Memory forms, other logical modes and aligned S_ONLY retain
their existing paths. APP ABI 39 and all fourteen shipped APP bytes are unchanged.

The complete raster-access estimate is `2*sourceBytes + 5*destinationBytes +
3*partialEdges` per row: source capture, native word-read/byte-write shifting
and publication. Bands retain the existing sixteen-row maximum and 8,192-access
bound. The 303-pixel sample therefore uses seven-row bands, fourteen bands for
96 rows, rather than the earlier sixteen-row fallback bands. Narrow copies
can use all sixteen slots and four mapped pages. This is a consequence of
accounting for all three phases, not a new fixed seven-row quantum. Each band
finishes DMA and repairs overlays before handing off; no scratch data is retained
between grants. Ordinary Tasks remain preemptible during mapping and shifting.

The independent host snapshot oracle checks both shifts, overlap directions,
full-width/tiny/odd copies, screen boundaries and injected transfer failures.
It checks the complete raster work bound, untouched source/padding bytes and
balanced physical ownership, and poisons the entire scratch after each release.
The raw callback probe checks 81,922 assertions (16,386 modulo 65,536) across
both shifts, one/four rows and widths 1, 2, 17, 319 and 320 bytes. The optimized
RAM probe includes the same callback and previous bank-crossing/all-mode checks:
114,603 assertions (49,067 modulo 65,536), with no hardware entry for RAM forms.
The physical VDI fixture passes 905 assertions, all copy and logical-mode pixels,
pointer restoration, forced yield, cleanup and stack/domain guards. Its minimum
spare remains 20 bytes above the separate 256-byte interrupt reserve.

The rebuilt OF816 ZIP passes its 73-file SYS/checksum audit and two exact
Raster/Counter walkthroughs, including the passive timing run. Each walkthrough
checks ten 29,184-pixel work-area images, memory round trip, timer scrolling,
exposure, physical movement, Counter progress, application collection and
normal EXIT. Autoboot remains 250 PAL frames. The host suite passes 715 tests
with four existing skips. The
[integration evidence](../development/gem-raster-mapped.json) freezes actual
inputs, results, timing observations and package hashes.

## Matched packaged observations

The previous package is `build/gem-raster-fast/demo`; the new package is
`build/gem-raster-mapped/demo`. Both use the same fourteen APP binaries, ROM,
machine profile and unmodified passive observer. The first seven work-area
pixel hashes match the baseline exactly; timed-scroll and later scenes are
checked against their independently reconstructed current row state.

| Copy | Before CPU ms | After CPU ms | Before elapsed ms | After elapsed ms | After checked scanout ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Up eight pixels, 304×88 | 19.579 | 17.708 | 40.275 | 32.796 | 83.762 |
| Down eight pixels, 304×88 | 17.830 | 18.141 | 35.947 | 35.201 | 93.554 |
| Left one pixel, 303×96, step 1 | 497.927 | 110.111 | 624.434 | 149.040 | 292.074 |
| Left one pixel, 303×96, step 2 | 498.259 | 110.071 | 624.738 | 150.412 | 292.702 |

Right advances the sample's left offset, shifting its pixels left. The two
different-parity observations improve by 4.15–4.19× elapsed and 4.52–4.53× caller
CPU. Off-Task time is 15–17 ms and native interrupts account for about 24 ms.
The aligned operations keep their direct blitter path. Four observations do
not establish a latency distribution or a MagiC-relative speed claim.

Copy completion and completed scanout remain separate: the one-pixel calls
still take about 150 ms, and checked scanout is about 293 ms after call entry,
including exposed-strip painting and frame-resolution observation. This slice
removes CPU buffer transfers from that screen-copy path; it does not optimize
the subsequent repaint or the RAM/screen transfer fallback.

The provider grows by 1,322 emitted C-image bytes, with zero-fill unchanged at
18,615 bytes. Workstation storage remains 1,056 bytes, including its 642-byte
CPU scratch. Complete bank-zero budgets, Task pools, runtime and upper
reservations match the previous package. Production reserved growth is **16 KiB
VRAM, 0 upper CPU bytes and 0 reserved bank-zero bytes**, fixed or per Task.
The exact package's smallest observed spare is 121 bytes above its separate
interrupt reserve; the broader physical fixture retains its 20-byte minimum.

Launch with
`build/gem-raster-mapped/demo/launch-altirra.command`, or distribute the generated
`build/gem-raster-mapped/demo/exec816-demo.zip`. Development logs and manifests
remain outside the ZIP. The [sample guide](../guides/gem-raster.md) contains
reproduction commands.
