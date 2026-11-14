# MGVIEW drawing and window foundations

[History index](README.md) · [Implementation plan](../plans/gem4xe/mgview-foundation-plan.md) ·
[VDI contract](../reference/gem-vdi.md) · [AES contract](../reference/aes.md)

## MV1: VDI bindings

Adds named/PB alignment, text attributes and solid rectangle fill. The origin
arithmetic is reproducibly extracted from pinned GEM4XE 0.9.4; its state is
explicit and coordinates are widened. Bindings use the existing per-Task
workstation and drawing grant. Baseline remains the default; alignment applies
before streaming. No drawing-unit limits change.

The private workstation structure grows by four bytes; eight-byte heap rounding
increases its allocation by eight bytes. Reserved bank-zero
growth is zero for fixed storage, root, kernel, idle and every public Task,
including guards, alignment and unused capacity. Loaded C ABI 41 adds the
three imports; source clients and resident providers must be rebuilt together.

[Development evidence](../development/mgview-foundations-mv1.json) records the
executed layout/API probes, physical pixel check and host suite. This is
development coverage, not hosted-system release qualification. The original
MGVIEW application and its mouse calls remain separate work.

## MV2: full and previous geometry

The shared view retains the creation full rectangle and previous normal
geometry. Publication captures the old bounds only when committed normal
bounds change; open initializes previous geometry to the accepted rectangle.
This also covers hidden/iconified changes and copied system moves without
duplicating mutation policy in the C wrapper.

The view grows by sixteen upper-heap bytes per live window. Fixed, root,
kernel, idle and per-public-Task bank-zero reservations grow by zero, including
guards, alignment and spare capacity. Loaded C ABI 42 and AES protocol 21
require rebuilt consumers. [Window provenance](../../ports/gem4xe/window-reference.json)
records the donor behavior and source hashes.

[MV2 development evidence](../development/mgview-foundations-mv2.json) records
the raw/optimized layout access, optimized geometry, physical lifecycle and
host checks. These checks do not establish release qualification.

The unchanged MV1 worktree reproduces the old window fixture's capacity
assertion and reset-required exit. The fixture now reserves all six slots
before expecting exhaustion and drains pending frame/directory work before
asserting idle. The corrected geometry/window fixtures complete with their
original pixel, deferred-input, guard, heap and OS-restoration checks enabled.
Creation also retains the original first-publication path: initializing
previous geometry must not suppress initial external-area publication.

## MV3: horizontal scrollbars

Adds horizontal arrows, page clicks, slider size/position and thumb dragging
through the native frame and message path. Both axes share cached thumb
arithmetic. Copied pointer routes retain horizontal geometry, and application
acknowledgement remains separate from physical gesture capture. Private
borderless/iconified bits move above the conventional GEM gadget mask.

[MV3 development evidence](../development/mgview-foundations-mv3.json) records
369 window assertions with exact vertical/horizontal pixels and cancellation,
185 frame assertions, both-mode C/native and desktop layouts, and two loaded
Counters ticking independently, physical close, restart and stop-before-main
(five collected executions, 29 assertions). The 715 host checks pass with five
historical/environment skips. Guards, heap ownership and OS restoration remain
enabled. No QED execution is required by these development checks.

The view grows by four structure bytes, the native window by twelve (including
eight for the extra GUI notice kind), and the private frame packet by four.
Copied route records grow by four bytes each, using 100 additional upper static
bytes across both publications and captured state. Four native client GUI
records add 32 upper-heap bytes. The arrow atlas uses 3,456 of its existing
4,096 VRAM bytes. Fixed, root, kernel, idle and every public Task reserve zero
additional bank-zero bytes, including guards, alignment and spare capacity.

C APP ABI 43, AES protocol 22, desktop records 20 and private frame packet 14
replace their predecessors. The generated QED declarations defer to the new
public bindings. Release qualification and the original MGVIEW port remain
separate.

## Production delivery

[Delivery evidence](../development/mgview-foundations-delivery.json) records
the package built from implementation commit `a9f29be1`. All fourteen C APPs
and the resident provider use ABI 43. The SYS Counter is byte-identical to the
one used for the five-execution lifetime check. The ZIP/SYS audit matches all
74 system files and thirteen disk APPs, preserves the separate QED disk, and
checks OF816, ROM notices and checksums.

Production bank-zero reservations, twelve Task pools and complete budgets are
identical to the previous GEMDOS demo, including guards and spare capacity.
The pinned AltirraOS/AltirraSDL cold ATR boot waits 249 PAL frames in OF816,
reads 640,534 source bytes, verifies the complete expanded payload, and reaches
native handoff at frame 22,676. Reader guards and firmware context are intact.
This transport check stops at native entry; the separate small window, frame
and loaded Counter fixtures cover graphical behavior and shutdown.

Artifacts are `build/mgview-foundation/demo/exec816-demo.zip` and
`build/mgview-foundation/demo/launch-altirra.command`. The five-second standard
autoboot and writable combined SYS/WORK disk remain in place.
