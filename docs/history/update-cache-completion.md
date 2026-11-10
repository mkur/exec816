# END_UPDATE cache completion

[GEM plans](../plans/gem4xe/README.md) ·
[Plan](../plans/gem4xe/update-cache-completion-plan.md) ·
[Design](../plans/gem4xe/update-snapshot-reuse-design.md#end_update-cache-completion-addendum) ·
[Previous UPDATE work](update-snapshot-reuse.md)

## EC0 Baseline and regressions

The [EC0 evidence](../development/update-cache-completion-ec0.json) records
738 native assertions, restored heap/ownership and intact guards.

The native snapshot fixture now calls the real `DESKCACHE.EndChange` in fifteen
controlled cohorts, with two warmups and eight measured calls each. It covers
empty and unrelated valid/invalid/pinned slots; either slot and both matching;
held, ready and absent repairs; empty and odd-edged changes; discarded bases,
missing pixels, failed completion and accumulated repairs. Setup uses the cache
lifecycle operations and releases simulated DMA before replacement.

Misses compare every byte of the desktop service, including the scene, windows,
both slots and repairs, and check the discard counter. Matching cases check
transitions and exact expanded repair bounds. The fixture also checks scoped
END for a hidden/iconified owner and verifies that a successful no-slot paint
still publishes readiness, consumes reports and sets a capture candidate.
The existing freshness oracle continues to check all 22 geometry observations.

The real-client cache and lock fixtures cover retained pixels, eviction,
ordinary/scoped/nested UPDATE, local/RPC admission, scheduled peers, inherited
Forbid and cleanup. Their baseline runs reuse the frozen current-runtime images
from the previous UPDATE slice: 224 and 181 C assertions, respectively, plus
four native assertions each. The host suite runs 668 tests, with four expected
historical-source skips.

The unchanged guest corpus is observed with additional native entries at
`DESKCACHE.ClientBounds` and `LAYERCACHE.EndChange`. The latter counts actual
matching slots during each UPDATE, including invalid or pinned matches.
Complete slot and repair bytes are also captured at untimed settled frame
checkpoints. The guest and exposure coverage oracle remain unchanged.

The baseline reproduces all eleven US3 frame digests exactly. Fragmented
Counter tick costs 36.686 ms caller CPU, including 11.302 ms in public END and
2.375 ms across four cache-completion calls. There are **zero matching slots**
in every measured application UPDATE; matching-path cost is therefore checked
in the controlled cohorts and behavior in the retained-pixel fixture.

All 863 production inputs match the final US3 inventory; frozen sources, builds,
observers and raw captures live under `build/update-cache-completion/`.
The older 349-file inventory is not used to establish native GUI provenance.
These are optimized emitted-code development checks, not hosted-system or
hardware qualification. No demo is refreshed.

EC0 reserves **0 additional fixed/root/kernel bank-zero bytes, 0 per public
Task and 0 idle bytes**, including guards, alignment and unused capacity.
Its added records and comparison buffer belong only to the test fixture.
