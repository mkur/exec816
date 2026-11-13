# GEM4XE raster-copy implementation plan

[GEM plans](README.md) · [Plan index](../README.md) ·
[Current VDI contract](../../reference/gem-vdi.md) ·
[Display ownership](../../reference/display.md) ·
[Platform budget](../../reference/platform.md#bank-zero-memory-budget) ·
[Testing policy](../../contributing/testing.md)

Status: approved for implementation, 14 November 2026. Commit this plan and
each passing executable slice separately. The starting Exec source is
`a0f756f9bc6f6851dee24ec234f261e409e0750c`, APP ABI 38, VDI-client version 4.

Deliver conventional `vro_cpyfm` through the resident application VDI, using
selected GEM4XE algorithms behind Exec's existing ownership and hardware
services. RC0–RC2 deliver the screen-copy operation needed by MGVIEW.
RC3–RC6 complete the supported raster profile: device-format memory forms,
all sixteen logical modes, acceleration and packaged development acceptance.
This plan does not port MGVIEW itself.

## Source and reuse boundary

The current [renderer pin](../../../ports/gem4xe/inputs.json) selects GEM4XE
0.9.4 at `e413c39d2f8e1bec8fe16596f610b923de4a0ae9`. It already contains
`vdi_vro_cpyfm` and `dev_copy_form`; the
[selection](../../../ports/gem4xe/selection.json) omits them.
Use raster algorithms from the assessed GEM4XE 0.15 revision
[`2bf10f6788372dcfa94f6d9416e4b957eb4ce394`](https://github.com/slaapliedje/gem4xe/tree/2bf10f6788372dcfa94f6d9416e4b957eb4ce394).
Its relevant changes are
[all logical modes](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/docs/phase142.md),
[form support](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/docs/phase143.md)
and [blitter recipes](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/docs/phase147.md).

Add an independent raster input/selection manifest rather than advancing the
whole renderer, AES, application kit or their line-range patches. Pin exact
source bytes, extraction ranges, adaptations and notices. Derive a small
internal raster unit from `vdi.c`, `vdidev.h` and `dev_vbxe.c`: rectangle
ordering and paired clipping, row-copy direction and nibble merging, `rop4`
and the hardware-mode recipes. Keep its operation descriptor explicit;
replace the donor's implicit `cr_op` with caller state. Reproduce selected
source through a generator/extractor; do not hand-edit generated copies.

Adapt MFDB decoding, widened arithmetic, memory I/O and hardware submission.
Do not import donor COP/startup/context switching, its allocators, fixed near
addresses, direct-page statics, workstation registry or raw MEMAC ownership.
The nibble formula can start in portable C. Any later assembly optimization
needs a separately checked huge-data ABI and bank-crossing behavior.
Keep derived GPL implementation under `ports/gem4xe/`; the public declarations
and generated record layouts remain in Exec's interface directories with
their established provenance and licences.

The exploratory 96,000-case host probe supports this selection but substitutes
memory I/O, assembly and the blitter. It is not emitted-code, preemption,
hardware, timing or hosted-system qualification. RC0 makes the useful oracle
and source record reproducible in the repository.

## Public behavior to deliver

Expose the ordinary source interface in `<gem.h>`:

```c
void vro_cpyfm(WORD handle, WORD mode, const WORD *pxy,
              const MFDB *source, const MFDB *destination);
```

Generate the 20-byte MFDB record: a four-byte `fd_addr`, then eight signed
16-bit fields (`fd_w`, `fd_h`, `fd_wdwidth`, `fd_stand`, `fd_nplanes`, and
`fd_r1`–`fd_r3`). Use a native huge pointer for the public address field;
verify offsets, size and alignment from compiler-emitted objects. Reconcile
port-local MFDB declarations and generated QED compatibility declarations.
Do not expose the donor's tagged VRAM addresses to applications.

Named calls and VDI parameter-block opcode 109 share one implementation.
The PB takes four point pairs, one input word and no outputs; source and
destination MFDB pointers occupy `contrl[7..8]` and `[9..10]`. Define native
little-endian low-word-first pointer packing in the machine-readable ABI.
Use explicit packing, not an unaligned cast. A null MFDB pointer, or an MFDB
whose address is null, denotes the screen; ignore other fields for that case.

The eight coordinates are inclusive corners. Normalize each rectangle,
compute extents in LONG arithmetic, and use the source dimensions at the
destination's normalized origin, as GEM4XE does. Destination width/height do
not request scaling. Reject the scaling flag and modes outside 0–15 as
`AES_UNSUPPORTED` before writing. Unsupported valid modes in an intermediate
slice also fail explicitly; never copy as replacement for a requested mode.
The operation is independent of `vswr_mode` and text/fill attributes.

The final profile supports the fixed 640×240 packed four-bit screen and
caller-owned device-format four-plane memory forms (`fd_stand=0`,
`fd_nplanes=4`, positive dimensions and a sufficient word stride).
The memory pitch is `fd_wdwidth * 2 * fd_nplanes` bytes. Check the layout
once at the API boundary using widened arithmetic. Allow linear upper-memory
buffers crossing CPU banks; retain their pointers only until synchronous
return. Same-form overlapping copies with the same base and pitch have
snapshot semantics. Distinct memory forms must be disjoint; overlapping
aliases described by different bases/pitches are outside this profile and
remain a caller responsibility.

Clip the destination to its form, and translate that clipping into the
source. Clip the source to its form and translate the loss back into the
destination. Screen destinations additionally intersect the owning window's
work/visible region and user clip. A screen source means actual framebuffer
pixels, including any occluding content; there is no backing-store recovery
or settled-content test. The caller must choose source pixels appropriate to
its application, normally by the classic visible-rectangle walk. Empty clips
are successful no-ops. D_ONLY (5) is a no-op; an identical rectangle is a
no-op only for S_ONLY (3), not for XOR, inversion or the other logical modes.

Screen participation requires the current AES window UPDATE, valid private
workstation and its display grant. Memory-to-memory calls need a workstation
but no window UPDATE or display grant. Screen reads erase source overlays;
screen writes also erase destination overlays. Record destination damage,
never source damage or automatic paint completion. Screen-to-memory reads
do not dirty a window. On operational failure, retain partial damage and mark
the UPDATE failed. Report void-call errors through `ExecAESDiagnostic()`.
Keep `ExecVDICopyRect`'s current optional-copy admission and results intact.

## Ownership, clipping and memory

Normalize/validate through caller-local state before physical admission.
Use existing DisplayEnter/Leave, driver transfers and prepared blitter lists;
add no kernel selector, private gateway, Task or signal. Normal Tasks remain
preemptible while one drawing owner retains physical access. No shared
scratch or pending DMA survives a release. Preserve the current IRQ/NMI,
stack-transition, quiescent recovery and reset-required ownership protocols.
Do not hold Forbid or disable interrupts across a raster copy.

Retain existing drawing limits: at most sixteen rows and 8,192 estimated bus
accesses per physical unit, charging actual read/write/combine passes and
edge work. Do not introduce a universal smaller row quantum or acquire once
per pixel/chunk. Keep the common single-visible-rectangle path direct.

For fragmented destinations, partition the clipped region into row bands at
visibility edges. Within each band, order visible spans in the horizontal
overlap direction; order bands in the vertical overlap direction. The row
fallback reads source data before writes and preserves outside nibbles.
Visibility-list order must not determine results. Cover staggered and nested
rectangle edges in the independent snapshot oracle. Do not allocate a full
screen snapshot to implement overlap.

Reuse workstation upper scratch where possible. Any additional caller scratch
is heap allocated at workstation open and freed at close; include rollback,
allocation failure and automatic appl_exit cleanup. Keep descriptor lifetimes
and scratch ownership explicit. Report live and rounded upper allocation,
resident image growth and transient stack peaks after each relevant slice.
Target **0 added fixed, root/kernel, idle and per-public-Task reserved bank-zero
bytes**, including guards, alignment and spare reserved capacity. The existing
stack pools and 256-byte interrupt reserves remain; measure the 1,312-byte
application path and do not enlarge pools merely to accommodate donor locals.
No new persistent VRAM reservation is needed for this profile.

## RC0 Pin and extract the reusable raster core

Add immutable input hashes, deterministic extraction/adaptation and the small
internal descriptor/geometry/row-logic unit. Keep the existing renderer pin
and application behavior unchanged. Turn the exploratory pixel oracle into
host checks against production extracted code, including all sixteen modes,
parities, one-pixel/byte/chunk boundaries and four overlap directions.
Use explicit operation definitions in the oracle rather than the donor's
truth-table arithmetic. Add a focused optimized emitted-code probe of the
selected geometry and nibble logic, with unchanged stack/domain guards.

Exit: reproducible extraction, correct portable pixels and emitted execution;
source provenance and zero reserved bank-zero delta recorded. Commit RC0.

## RC1 Publish screen-to-screen S_ONLY

Add generated MFDB/mode/PB definitions and the named import; advance APP ABI
once (38→39 at this baseline), VDI-client capability version and generated
outputs. Do not shift existing import ordinals. Integrate the reusable
geometry and row fallback with the current even-displacement blitter path.
Handle either source/destination parity, clipping, reversed corners and
overlap without requiring `pixelsReady` or caller paint acknowledgements.
Initially require the nonempty effective destination to fit one current
visible rectangle; reject a fragmented case before mutation and document
this intermediate restriction. All other modes and memory forms remain
explicitly unsupported until their slices.

Exit: named and PB calls produce identical physical pixels; no-UPDATE,
unsupported-input and display failures behave correctly. Run small raw/opt
layout, full pointer-word packing and call probes, plus optimized screen
pixels with a pointer inside source/destination, display ownership and
restoration. Rebuild all APP/provider artifacts used by tests together;
previous ABI artifacts must be rejected. Commit RC1.

## RC2 Complete visible-region clipping

Implement the band/span ordering above for multiple visible rectangles,
including destination-only user clipping and translated source bounds.
Remove RC1's fragmentation restriction. Report actual destination writes and
preserve hidden/occluded pixels. Add clipped, hidden and partially covered
cases, scrambled rectangle ordering, overlapping shifts across band edges
and a screen source not contained in the user clip.

Exit: the screen-copy MGVIEW prerequisite is delivered for S_ONLY at both
parities, with snapshot-correct visible destinations and unchanged native
ExecVDICopyRect regressions. Commit RC2.

## RC3 Add device-format memory forms

Support S_ONLY for screen→memory, memory→screen and memory→memory through
the same admitted descriptor. Adapt the donor's span I/O to huge pointers
and existing driver transfers. Memory-only work uses no hardware ownership.
Screen paths keep bounded units and fences; prefer contiguous row transfers
and scratch reuse over bank-zero-only direct-copy shortcuts. Do not borrow
or overwrite a caller byte beyond the declared form while shifting nibbles.

Exit: emitted bank-crossing buffers, padding and outside nibbles are exact;
same-form overlap is correct; screen readback leaves no pointer pixels;
memory-only calls work without a window; allocation/close paths leak nothing.
Use focused raw/opt pointer/layout checks only where the bridge changes;
ordinary behavior runs optimized. Commit RC3.

## RC4 Implement all sixteen logical modes

Enable the extracted truth-table combiner on bounded CPU row paths for every
supported form pair. Keep S_ONLY's existing fast route. Validate all source
and destination bit combinations, identical rectangles, overlapping moves,
partial bytes and every mode against the independent snapshot model.
Ensure mode 5 and empty clips do no hardware work. Preserve attribute state
and enforce pre-mutation rejection of unsupported formats/modes.

Exit: all sixteen modes execute correctly through named/PB APIs in emitted
code and real screen cases, including upper memory; inquiry data describes
only this implemented profile. Commit RC4.

## RC5 Accelerate screen logical modes

Reuse the donor `rop_code` recipes for same-parity screen copies, with
direction-aware prepared blits through existing device submission. Modes
2/11 invert the destination first: overlapping copies use the correct row
fallback. Modes 8/14 invert afterwards; preserve the source across the full
operation, not merely within one submitted list. Keep edges and all passes
inside the admitted unit and its work budget. Retain CPU fallback for
different parity and memory forms.

Exit: accelerated and fallback pixels match for all modes; forced Task
preemption during shared scratch use cannot mix operations; a competing
drawer waits while a computing peer progresses. Exercise faults before the
first write and after a completed band, correct failure/damage, quiescent
cleanup and reset-required retention. Commit RC5.

## RC6 Deliver the rebuilt demo and measured record

Use a small conventional-GEM scrolling raster workload, independent of
MGVIEW's file loader and editor port. Copy its viewport and draw only the
exposed strip alongside Counter, then cover/uncover and move the window.
Use matched patterns/geometry for correctness and timing. Separate aligned
and different-parity copies, call CPU time, elapsed completion and visible
scanout; assert pixel correctness before accepting a timing observation.
Timing is characterization, not a new promised latency or a MagiC speed claim.

Rebuild the provider and shipped applications for the one current ABI through
[build_demo.py](../../../tools/build_demo.py), including OF816, the matching
writable SYS/WORK disk, pinned ROM and notices, five-second standard autoboot
and the normal ZIP contents/checksums. Execute that exact package for boot,
sample, coexistence, cleanup and EXIT checks. Audit reserved bank-zero totals,
stack peaks, upper allocations and unchanged persistent VRAM reservations.
Update the public VDI contract, usage example and indexed development record;
preserve historical records. Commit RC6.

## Validation scope and completion

Use the development tier per slice. Extend the existing
[copy ABI probe](../../../tools/test_vdi_copy_abi.py),
[copy pixel checks](../../../tests/test_vdi_copy.py) and
[VDI physical fixture](../../../tools/test_vdi_client.py), or add a smaller
dedicated raster runner when that avoids rerunning unrelated desktop cases.
Freeze source/compiler/ROM/emulator/configuration for each recorded result.
Use optimized machine code for functional, fault, preemption and timing cases.
Keep raw/opt checks focused on new records, pointer transport and calling ABI.
Documentation changes need content and local-link checks. Do not run the
full release matrix after every commit or claim hosted qualification from
host models, compiler checks or these focused development results.

Complete when all supported form pairs and sixteen modes have synchronous,
overlap-correct named/PB behavior; visible clipping and overlays are exact;
failures preserve ownership and repair obligations; memory/bank budgets are
recorded; and the rebuilt OF816 demo and current public contract agree.

Deferred: `vrt_cpyfm`, `vr_trnfm`, standard planar forms, scaling, other
depths, application-visible VRAM MFDBs and bitmap workstations, new fonts,
MGVIEW's remaining API/file-port work, scheduler changes and drawing-limit
retuning. In particular, donor bitmap slots collide with Exec's menu/snapshot
reservations; adding those requires a separate VRAM ownership design.
