# Hosted VBXE adapter

[Public display contract](../../docs/reference/display.md) ·
[VRAM map](vbxe-vram.json)

`vbxe.c` and `vbxe-map.s` implement the G3 adapter for the pinned inactive FX 1.26
baseline. They do not link the donor startup or its unbounded low-level waits.
The [G4 backend](../../ports/gem4xe/adapter/README.md) connects the selected GEM
dispatcher/device to this driver.

The C launcher binds `c/calypsi/display-bridge.inc` before admitting workers and
calls the private `DISPLAYBOOT.Authorize()` only when its pinned cold-boot
precondition is established. The standard text launcher leaves authorization
clear. The bridge checks full huge addresses, preserves D and aligns its temporary
native frame. The 20-byte native lease layout is checked through emitted C
constants. Shared state occupies the existing upper image-data reservation.

All adapter operations run on the retained owner Task. `VbxeOpen` acquires the
shared display resource, verifies authorization and exact hardware identity,
snapshots SDLST/SDMCTL, disables ANTIC display DMA and activates the lease.
ANTIC VBI remains enabled. `VbxePresent` installs a 640×240, 4-bpp XDL with a
16-entry grayscale overlay palette. This is an adapter pattern, not a GEM
workstation palette or VDI capability claim. `VbxePalette` installs 16 RGB
entries in overlay palette 1; `VbxeShow` enables the fixed XDL while preserving
that palette. G4 uses these two operations for GEM colours.

`VbxeFill` builds one 21-byte constant-source BCB on the caller's stack and fences
before upload and after start. VRAM transfers validate full extents, fence, map
one page at a time and unmap on return. They accept valid caller-stack or upper
CPU buffers, but reject overlap with the aperture. Actual buffer ownership is
part of the shared-address-space caller contract. VCOUNT waits observe wrap;
a sixteen-tick deadline permits scheduling of the other public Tasks. A narrow
VCOUNT-equals-zero loop and a two-tick deadline proved unsuitable with OS VBI
and a computing peer.

Only this adapter writes MEMAC A, XDL, overlay palette 1 and blitter registers.
MEMAC B, VBXE IRQs, collision and priority registers stay at their known inactive
baseline. The mapping assembly publishes hardware stores in disable/bank/control
order before committing the four-byte software map shadow. It uses only the
owning Task's upper DP scratch and existing stack; it restores S and leaves D
unchanged. Console, native NMI/IRQ,
SIO, loader and ROM paths use no MEMAC or VRAM addresses. The loader and Task
pools exclude the full CPU window. Other Tasks may run while a map is partially
published; they cannot consume that map or shadow.

Recovery writes STOP, then checks BUSY/BCB_LOAD with its own bounded deadline.
Only a confirmed idle engine permits disabling XDL and mappings, resetting the
tracked control pointers/indices, restoring SDLST/SDMCTL and releasing the lease.
Palette contents and VRAM are private to the inactive graphics baseline and are
not restored for an unknown previous graphics owner. An engine still busy after
STOP leaves the lease FAULTED and enters reset-required park. The launcher also
parks on any normal/fault exit with VBXE ownership still live, including a
rejected attempt to remove its retained Task; it cannot reclaim DMA storage.

The current VRAM assignments reserve 107,008 bytes, including 7,416 bytes beyond
payload capacity. Screen capacity is 76,800 bytes in an 81,920-byte reservation;
XDL uses 12 of 256 bytes; BCB capacity is 252 of 256 bytes (12 × 21, not 1 KiB).
The G3 fill uses only the first BCB, leaving another 231 capacity bytes unused.
G4 assigns 20,480 bytes to both font-mask strips (18,432 bytes used), plus one
4,096-byte clipped-glyph scratch page. The remaining 417,280 bytes are unassigned
within the exclusively owned 512 KiB. The
32-byte cross-page test at `$3FFF0` is diagnostic borrowing, not a production
reservation. CPU and VRAM address spaces are accounted separately.

Run `tools/test_gem_display.py --mode raw|opt --output DIR`. The probe build
substitutes status reads only for explicit timeout cases and adds four assembly
stall points for real NMI entry between mapping stores. Other cases read actual
hardware. The reports record these source transformations; they are absent from
the production adapter. Pattern checks read every screen byte through MEMAC,
check VRAM slack guards and underlying CPU RAM, run a C computing peer and real
physical SIO, and return to CON. Hardware absence, unsupported identity, unknown
baseline, recovery, tick rollover and reset-required cases are distinct runs.

Use `--production-control` with a separate output directory to run the same
pattern, SIO, context and restoration checks with the original uninstrumented
C and assembly adapter. Both raw and optimized controls are recorded alongside
the fault-injection runs.

`VbxeBlit` accepts one positive-step rectangular BCB: 1–512 bytes per row,
1–256 rows, source/destination row steps 0–4095 (the nonnegative signed 13-bit range), and modes 0–6. It checks
complete source/destination VRAM extents before mutation; the retained caller
owns those regions. No chaining, IRQ or negative steps are exposed. The call
fences before upload and after execution. G4 currently uses replace, AND, OR
and nibble stencil through the selected upstream algorithms.
