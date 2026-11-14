# Mapped VRAM copy workspace

[Plan index](../README.md) · [VRAM audit](../../history/vbxe-vram-audit.md) ·
[Display contract](../../reference/display.md)

The workspace/driver foundation is implemented and passes the three optimized
driver cases; [execution record](../../history/gem-raster-mapped.md).
Renderer integration and packaged performance checks follow.

Improve different-parity screen-to-screen `S_ONLY` copies by staging through
VRAM and running the existing native nibble shifter inside the mapped page.
The measured baseline is the package in `build/gem-raster-fast/demo`:
303 × 96 copies take about 625 ms elapsed / 498 ms caller CPU. The passive
profile attributes about 391 ms to the C CPU/VRAM byte-transfer loops and
40 ms to nibble shifting. A larger CPU aperture is unnecessary for this slice.

1. Reserve 16 KiB at `$4C000–$4FFFF`, generate its constants and add private
   synchronous page composition to the driver. Check mapped callbacks through
   emitted code, real VBI/Task preemption, mapping transition injection,
   unchanged underlying CPU RAM and OS restoration. Commit this foundation.
2. Stage bounded source bands with the blitter, shift into disjoint output
   storage in the same mapped page, and publish masked edges plus complete
   bytes with the blitter. Use 1,024-byte row slots: source at +0, output at
   +512, four rows per page and sixteen slots in the reservation. Capture the
   complete band before screen writes and process downward overlap bottom
   first. Bound complete staging/shift/publication work to 8,192 raster bus
   accesses and sixteen rows. Fence before each handoff; retain no VRAM
   contents between physical grants. Keep RAM forms, other logical modes and
   same-parity direct blits on their current paths.
3. Check all parities, tiny/odd edges, page transitions, overlapping directions,
   screen boundaries, ownership/fault cleanup and stack reserves. Rebuild the
   OF816 demo with `tools/build_demo.py`, audit its ZIP and execute the exact
   Raster/Counter walkthrough. Measure the same four calls with the unchanged
   sample and passive observer. Record actual timings and memory changes, then
   commit the integrated slice.

Development tier, with focused optimized machine-code checks and a small raw
callback check. No full qualification claim. Reserved VRAM grows by 16,384 bytes;
the aperture remains `$8000–$8FFF`. Reserved bank-zero growth is zero fixed,
root/kernel, idle and per public Task, counting guards, alignment and unused
capacity. No public ABI change, renderer Task or kernel operation is needed.
