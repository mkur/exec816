# One interior copy for same-parity screen edges

[GEM plans](README.md) · [Raster contract](../../reference/gem-vdi.md#conventional-raster-copy)

Implemented on 2026-11-17 as one executable slice. The
[execution record](../../history/gem-odd-edge-copy.md) retains focused checks
and the matched measurement. MGVIEW alone is the application target.

The WG6 [capture](../../development/magic-window-geometry.json) supplies the
matched baseline: work `(1,22,616,200)`, one semantic 616×192 copy per line
scroll, 15 `VbxeOwnerCopyRect` calls and 16 display entry/leave pairs. Copy Task
CPU is 76.674/77.276 ms down/up. Geometry and application binaries stay fixed.

GEM4XE's pinned raster donor is `2bf10f6788372dcfa94f6d9416e4b957eb4ce394`.
In `src/vdi/dev_vbxe.c:1880`, `dev_copy_form` separates partial edge columns
from the byte-aligned interior and blits that interior once. Its directional
edge order protects overlap. Exec already snapshots all source edge bytes
before writes, allowing its existing overlap-safe typed copy to handle the
interior. Preserve that source capture and the current MagiC caller/UPDATE flow.

1. Keep the existing first grant: erase intersecting source overlays, capture
   complete source-edge columns into existing scratch, fence, read at most 480
   bytes into the existing upper buffer and release.
2. Reacquire the existing grant once. Erase intersecting source/destination
   overlays, reload the saved edges, and send the aligned interior through the
   existing whole-screen `VbxeOwnerCopyRect` encoder. Restore the caller's
   descriptor even on failure. Queue the masked destination-edge columns with
   the existing `blit_mask` producer; retain this grant through its bounded
   lists, final fence and overlay restoration. Remove the outer band loop.
3. Check emitted interior BCBs and mask-list construction against a whole-source
   pixel snapshot: both nibbles, one/two edges, narrow/zero-interior cases,
   full-height and screen boundaries, horizontal/vertical/diagonal overlap,
   admission and transfer/submission/fence failures. A release must allow
   scratch replacement; no source edge may rely on its old VRAM contents.
4. Recompile only the changed renderer object, relink the checked provider and
   rebuild the native loader. Reuse the unchanged MGVIEW APP. Repeat the same
   down/up pixel, CPU/elapsed, ownership, stack/guard and retirement observation.
   Run host checks and record both gains and remaining costs before committing.

The typed screen bound remains 640×240. Every mask record retains its sixteen-row
limit; raw lists retain 64 records and 8,192 estimated accesses. Neither generic
limits, other modes, different-parity copies nor cache policy changes. Keep
normal Task preemption and current device fault retention. No new API, Task,
signal, platform service, buffer, VRAM region or reserved bank-zero bytes are
needed: fixed/root/kernel/idle/per-public-Task deltas are all zero, including
guards, alignment and spare capacity. No QED, Counter, catalog, demo or release
matrix is part of this development check.
