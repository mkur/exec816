# Menu title repaint and pointer response

[Plan](../plans/gem4xe/menu-title-response-plan.md) ·
[Measurements](../development/menu-title-response.json) ·
[LR2 baseline](layers-rebuild.md)

## MT1 Complete feedback and heading crossings

The passive observer resolves coordinate stores in `DESKINPUT.Fresh` and the
pending-heading store in `DESKMENU.Heading` from emitted instructions. It
records the first normalized position inside an enabled destination heading,
then its routing. Deferred input, recrossing and loss are distinguished.
No guest code, data, breakpoints that stop execution or timers are added.

The new cohort submits one physical quadrature burst and immediately samples
each frame. The historical positioning helper advances seven frames per
coarse movement before returning; its roughly 281 ms result therefore cannot
measure early repaint completion. Historical actions remain available as a
separate cohort. Complete feedback includes the changed headings and both
popup footprints. Only the current/previous cursor footprint is masked;
keyboard checks compare all title pixels without a cursor mask.

On the unchanged LR2 archive, warm keyboard popup pixels settle near 60 ms,
but complete feedback takes **120 ms**. The three physical samples reach
complete pixels **140–161 ms after submission**, with crossing-to-visible
intervals **108–128, 106–126 and 108–128 ms**. Crossing-to-routing is 1.8–1.9 ms.
These intervals retain PAL-frame sampling uncertainty. They are a corrected
baseline, not a production speedup or a p95 estimate.

Six new host tests pass; the host suite passes 497 tests with four historical
skips. The initial capture completed all timed actions, then failed an obsolete
Counter observer assertion expecting the previous 16-row title geometry.
The corrected observer uses the current geometry constants. The affected
complete-feedback and Counter cases pass on the same archive, including
guard checks, normal EXIT and OF816 autoboot. Counter advances and visibly
repaints during 30 application and 30 native menu highlights.

Artifacts: `build/menu-title-response/baseline` and
`build/menu-title-response/baseline-complete`. The first pointer-completion
attempt used the positioning helper and is excluded from the compact record.
Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. MT1 changes only host observers/tests.
