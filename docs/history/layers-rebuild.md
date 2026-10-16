# Layers visibility rebuild improvement

[Plan](../plans/gem4xe/layers-rebuild-plan.md) ·
[Layers contract](../reference/layers.md) ·
[PT4 baseline](popup-transition.md)

## LR1 Rebuild order and skipped work

Each layer now subtracts nearer occluders before farther ones, skips rectangles
disjoint from its bounds, and stops once no visible pixels remain. This avoids
fragmenting a fully covered lower layer before discovering its covering window.
The visible set, damage obligations, scene transaction and rebuild counter
semantics are unchanged. Rectangle partition/order may differ, as permitted by
the visibility contract. No new cache, state or public operation is introduced.

Development checks pass: 491 host tests (four historical skips) and 8,796
optimized emitted Layers checks. The existing 128 geometry cases, 40 scene
snapshots, software paint/copy fallback, saved replacement, external damage,
bank-crossing and guard/OS-return checks pass. Four new snapshots compare all
768 pixels independently for covered layers, edge-touching neighbours,
crossing overlays and exposure after hiding/moving/reordering the cover.

Artifacts: `build/layers-rebuild/lr1-layers`. No raw or qualification matrix
was run; no ABI layout or language-bridge behavior changed.

Rebuild native code grows **1,576 → 1,778 bytes** (+202); its local stack peak
falls **36 → 34 bytes**. Layers/Regions code grows 38,646 → 38,848 bytes, with
the same 56-byte maximum local stack peak and no mutable globals. Scene size
remains 9,186 bytes. Reserved bank-zero delta is **0 fixed, 0 per public Task,
0 idle bytes**, including guards, alignment and unused capacity. DP, stack,
VRAM and upper-memory reservations are unchanged.

LR2 will compare the exact OF816 desktop package with the preserved PT4
18-action trace and record end-to-end response separately from rebuild CPU.
