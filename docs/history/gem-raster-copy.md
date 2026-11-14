# GEM4XE raster-copy delivery

[History](README.md) · [Current VDI contract](../reference/gem-vdi.md#conventional-raster-copy) ·
[Sample](../guides/gem-raster.md) · [Plan](../plans/gem4xe/vro-cpyfm-plan.md) ·
[Development evidence](../development/gem-raster-copy.json)

## Reuse and delivered boundary

RC0–RC6 deliver the supported raster profile using algorithms from GEM4XE 0.15 commit
`2bf10f6788372dcfa94f6d9416e4b957eb4ce394`. The
[independent manifest](../../ports/gem4xe/raster/inputs.json) pins three source
files by SHA-256. The generator reproduces the logical row merger and blitter
recipes; widened normalization/clipping and visible-fragment traversal remain
explicit adaptations. The older renderer/AES pin stays unchanged. Derived
implementation remains under the GEM4XE port with its upstream GPL notices.

APP ABI 39 appends `vro_cpyfm` without changing existing import ordinals.
Named calls and PB opcode 109 share the same implementation, with generated
20-byte MFDB declarations and explicit low-word-first pointer transport.
Supported forms are the 640×240 four-bit screen and caller-owned packed device
forms with four planes. All sixteen logical modes support either X parity and
same-form overlap. Memory-only operations need no UPDATE or display grant.
Conventional screen copies use actual framebuffer pixels and do not depend on
Exec's optional settled-copy/paint journal. `ExecVDICopyRect` keeps its existing
optional-copy behavior.

Fragmented visible destinations are traversed in ordered Y bands and X spans,
independent of their enumeration order. Private row buffers preserve source and
destination nibbles across different parity and bank boundaries. Same-parity
screen logical operations use selected one/two-pass VBXE recipes. Inversion
before combining falls back for overlapping modes 2 and 11; inversion after
combining remains safe in modes 8 and 14. New row/combining units retain the sixteen-row
and 8,192 estimated raster-access bounds, including partial edges and both
passes. Existing display access, fences, overlays, failure/damage handling and
Task preemption provide coordination; no new kernel operation is introduced.
S_ONLY retains its existing auxiliary whole-source edge capture (at most 480
bytes) before the bounded copy strips. It does not impose a smaller quantum on
that read-only staging pass or change the older optional-copy operation.

## Executed development checks

| Boundary | Executed coverage |
| --- | --- |
| Selected algorithms | Independent host truth-table/pixel oracle, optimized emitted core and widened geometry, scrambled visible fragments in all overlap directions |
| Public ABI | Focused raw/optimized MFDB/layout and named/PB pointer/admission probes; existing native-copy regression |
| RAM backend | Optimized production row path, all sixteen modes, same-form overlap, CPU-bank crossings, untouched padding, exact heap return and no hardware entry |
| Physical display | 22 copy scenes and ATASCII, plus 32 logical transfers across all modes and both parities, exact scanout, pointer restoration and normal shutdown |
| Ownership/failure | Host work-budget and before/after-transfer failure cases; physical forced yield with packed record/scratch live; existing emitted display arbitration, fault recovery and cleanup fixture |
| Record packing | Small raw packing probe and optimized packing/RAM probe compare every byte of the actual 21-byte submission |

The accelerated physical fixture passes 905 guest assertions and observes 18
logical blitter submissions. Its yield hook calls the ordinary `ExecYield`
before the first submission while the caller retains physical access. The
separate ownership fixture observes 48 borrowed units, 120 native units and
zero overlapping owners. Instrumentation belongs to fixture copies, not the
production renderer. The native packing check caught reserved bytes that the
C compiler left uninitialized with an aggregate zero initializer; the encoder
now assigns every field explicitly.

The frozen result files and their hashes are retained in the evidence record.
These selected development runs do not qualify the hosted system or establish
MagiC-relative speed. The host suite passes 715 tests with four existing
pre-publication-history skips.

## Packaged sample and memory

RC6 adds the conventional-GEM [Raster application](../../examples/gem-raster/main.c)
and rebuilds all shipped applications with the provider for ABI 39. It starts
paused, scrolls by copying its visible viewport and repainting exposed strips,
shifts one pixel through the different-parity path, and copies screen/memory
forms in both directions. Its independent row model is also the full redraw
model. Counter runs as a distinct Process through a second shell session;
the existing shell permits one background job per session.

The OF816 package includes the combined writable SYS/WORK disk, five-second
autoboot, pinned AltirraOS ROM and upstream notices. The distribution ZIP
contains boot files, a short guide, licences and checksums. Development files
and result logs stay outside it. The package audit matches 73 system files.
All fourteen APPs, including the boot-created Desktop, use ABI 39. The exact
ZIP passes ten 29,184-pixel work-area checkpoints: initial drawing, two vertical
steps, two rightward one-pixel steps, memory round trip, timed scrolling,
exposure and physical movement. Both applications retire and their shells
collect their images; Counter continues after Raster closes. The second shell
and final EXIT return normally with ownership and stack/domain guards intact.
OF816 hands off after exactly 250 PAL frames.

The pinned bridge lacks a PLUS raw-key alias, so the automated sample uses two
rightward shifts. Lower-level snapshot probes cover leftward overlap. This
does not change the sample's ordinary Left key or the emulator configuration.

## RC6 timing characterization

The same optimized package and patterns provide these four observations.
Copy dimensions are recorded separately; this is not an equal-area throughput
ratio or a latency distribution. Calls are observed passively in their loaded
image. Charged CPU includes kernel calls and bus stalls, with native IRQ/NMI and
time assigned to peers separated. Checked scanout is the subsequent exact
frame observation, including exposed-strip painting and observer granularity.

| Copy | Pixels | Caller CPU ms | Call elapsed ms | Call to checked scanout ms |
| --- | --- | ---: | ---: | ---: |
| Up eight pixels | 304×88 | 20.092 | 40.791 | 105.338 |
| Down eight pixels | 304×88 | 17.838 | 36.014 | 103.124 |
| Left one pixel, step 1 | 303×96 | 1,895.705 | 2,336.807 | 2,469.715 |
| Left one pixel, step 2 | 303×96 | 1,895.470 | 2,332.014 | 2,480.277 |

Right advances the sample's left offset, shifting its pixels left. The aligned
operations use the existing blitter copy; different parity uses the C row
combiner. The latter spends only 24–29 ms off Task and about 412 ms in native
interrupts. Its large CPU charge identifies the fallback as remaining work;
this delivery makes no claim that arbitrary one-pixel scrolling is fast.

The guest walkthrough completed normally before CPU postprocessing. Attribution
was recomputed from the saved trace after correcting the 32-bit host clock
epoch and limiting observation to the measured scene; PROFILE_STOP leaves
passive history active. The result preserves its original result hash/error
and reanalysis metadata. Future runs use the corrected observer. No guest code,
test limits or frozen package bytes changed for that correction.

## RC6 reservation and stack audit

Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 idle and 0 bytes per
public Task**, including guards, alignment and unused capacity. Complete
`bank_zero_budget`, `runtime_reservations` and Task pools match the earlier
Widget demo. Workstation scratch grows 480→642 bytes: **162 live / 160 rounded
heap bytes added per workstation**, with 1,056 bytes now allocated overall.
No persistent VRAM extent grows. Raster allocates a 14,592-byte memory form
through its ordinary C runtime and frees it on exit.

The stress fixture's smallest 1,312-byte Task stack has 20 bytes left above the
separate 256-byte interrupt reserve. That is a measured limit for this fixture,
not evidence of arbitrary application stack headroom. Task pool reservations
are unchanged.

Deferred behavior remains standard-planar conversion, scaling, other depths,
`vrt_cpyfm`, `vr_trnfm`, application-visible VRAM forms, bitmap workstations and
MGVIEW's remaining API/file-port work. The donor bitmap addresses collide with
Exec's menu and snapshot storage and have not been imported.

## S_ONLY plain-copy follow-up

The follow-up reuses the dedicated plain-copy branch already present in the
same pinned GEM4XE revision. Equal parity copies bytes directly; different
parity uses its `nib_shift` word-load/XBA/four-shift loop. The generator now
reproduces both `core.h` and `shift.s`. The additional source is pinned by
SHA-256 in the raster manifest, preserving the donor licence and provenance.

The assembly adaptation accepts huge pointers through the existing Calypsi
argument workspace and uses long-indexed data access. It allocates no direct
page storage, changes neither D nor DBR, restores 16-bit accumulator width and
returns synchronously. Partial destination bytes are read and preserved at the
edges; complete bytes need no destination read. One spare byte in the existing
source buffer supplies the final shift without reading form padding. Row and
chunk overlap order, physical grants, fences and current drawing bounds remain
unchanged. Other logical modes retain their existing paths.

The raw helper probe passes 8,989 assertions, including zero count with null
pointers, 16-bit indexing and word reads crossing CPU banks. The optimized
production RAM probe passes 32,681 assertions: the same helper ABI, all sixteen
modes, both overlap directions, all pixel parities, one-pixel edges and
699-pixel copies spanning multiple private chunks. The optimized core oracle
passes with 9,477 checks modulo 65,536. The physical fixture still passes all
905 assertions, exact pixels and pointer restoration, with the same 20-byte
minimum spare above its separate interrupt reserve. The host suite passes
715 tests with four existing skips.

[Follow-up evidence](../development/gem-raster-s-only-fast.json) retains the
new package and the RC6 baseline separately. All fourteen comparison APPs are
byte-identical and use ABI 39; the benchmark observer is unchanged. Its marker
profile reuses only the unchanged sample's call addresses and verifies the
actual loaded relocation and call instruction before measurement.

The exact new ZIP passes the same ten 29,184-pixel checkpoints, application
collection, Counter progress, guards and EXIT, with the same 250-frame autoboot.
Seven checkpoints before timed scrolling have byte-identical pixels to RC6;
later scenes are checked against their own independently reconstructed model.

| Matched copy | Before CPU ms | After CPU ms | Before elapsed ms | After elapsed ms | After checked scanout ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Up eight pixels, 304×88 | 20.092 | 19.579 | 40.791 | 40.275 | 104.724 |
| Down eight pixels, 304×88 | 17.838 | 17.830 | 36.014 | 35.947 | 82.934 |
| Left one pixel, 303×96, step 1 | 1,895.705 | 497.927 | 2,336.807 | 624.434 | 773.522 |
| Left one pixel, 303×96, step 2 | 1,895.470 | 498.259 | 2,332.014 | 624.738 | 757.692 |

The two different-parity observations improve by 3.73–3.74× elapsed and about
74% caller CPU. Their remaining 625 ms call time includes approximately 498 ms
of caller CPU, 18 ms off Task and 108 ms in native interrupts. The copy is still
visibly slow; the result does not establish interactive one-pixel scrolling.
The aligned blitter observations remain close to their original costs. These
are four observations with checked pixels, not a percentile or latency promise.
Checked scanout retains the RC6 frame-resolution upper-bound definition.

The provider adds 567 emitted C-image bytes and no zero-fill bytes. Complete
bank-zero budgets, Task pools, runtime and upper reservations match RC6.
Reserved growth is **0 fixed, 0 root/kernel, 0 idle and 0 bytes per public
Task**, including DP, guards, alignment and unused capacity. Workstation
storage remains 1,056 bytes with 642 bytes of copy scratch; heap and persistent
VRAM reservations do not grow. These are development checks, not hosted
release qualification.
