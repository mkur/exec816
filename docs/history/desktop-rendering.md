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
