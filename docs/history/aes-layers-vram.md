# AES and Layers VRAM caching

[Plan](../plans/gem4xe/aes-layers-vram-plan.md) ·
[Design](../plans/gem4xe/aes-layers-vram-design.md) ·
[Layers contract](../reference/layers.md) · [AES contract](../reference/aes.md)

Implementation in progress. Development checks below do not qualify a release
matrix or real hardware. The compiler pin is unchanged.

## AV1: external repaint bookkeeping

External layers retain pending client repaint independently of presenter
damage. A successful handoff retires only presenter work. Explicit completion
subtracts the reported rectangle for its observed generation; stale reports,
failure and excess fragments retain pending repair. No application wait holds
a scene transaction or causes repeated redraw delivery.

The existing outer UPDATE exchange publishes eight caller-local completion
records. Drawing accumulates changed bounds before visibility clipping; later
overlapping writes revoke earlier claims. Failure remains sticky across later
successful calls. Nested UPDATE preserves the journal. Snapshot publication
after a title/geometry call does not erase accumulated changes. Counter and
Files/desktop call the optional helper after successful reconstruction.

AES wire version 15 and C-program import ABI 16 require rebuilding clients.
Ordinary GEM clients without the helper continue on the existing redraw path.
No cache or copy admission changes in this slice.

Memory: Scene grows from 8,496 to 9,162 bytes (+666 fixed upper-RAM bytes).
Request/context grows by 114 bytes per registered client; each published
window view grows by 14 bytes, at most 84 for six owned windows. Combined
caller growth is at most 198 bytes. VRAM remains 243,200 bytes. Reserved
bank zero changes by **0 fixed / 0 per public Task / 0 idle bytes**, including
guards, alignment and unused reserved capacity.

Development checks: 459 host tests (455 pass, four existing skips); optimized
Layers regression (60,070 checks); raw/optimized far-record Layers probes;
raw/optimized C/Action! context/layout probes; optimized VDI pixel/ownership
regression including nested journals, bounded overflow, superseded completion
and sticky failure. Both exact OF816 packages pass the timing walkthrough and clean EXIT. Baseline
ZIP SHA-256 is `81c339570194b9041be0407fa85c096d79d596236bc133795c23ccfc3d95b2a2`;
AV1 is `ee2ce02ca941399f025cf8314cee3bf838b08468f0e89f3980394d870aeb7d63`.
The packaged bank-zero budget, runtime reservations and Task pools match.

Twenty samples per interaction, median/p95 milliseconds:

| Interaction | Baseline | AV1 |
| --- | ---: | ---: |
| File opens | 401.2 / 401.2 | 401.2 / 401.2 |
| File highlight | 80.3 / 80.3 | 80.3 / 80.3 |
| File to View | 782.1 / 782.3 | 802.3 / 802.3 |
| View closes / Files finishes | 401.2 / 401.2 | 421.1 / 421.4 |
| Windows opens | 180.6 / 180.6 | 180.6 / 200.6 |
| Windows highlight | 80.3 / 100.3 | 100.3 / 100.3 |
| Windows next row | 100.3 / 100.3 | 100.3 / 100.3 |
| Windows closes, visible pixels | 501.4 / 501.4 | 521.4 / 521.7 |
| Windows closes, Files finishes | 501.4 / 501.4 | 541.6 / 541.6 |

The overhead gate remains open: dismissal approaches/exceeds its one-frame
allowance, and final Files completion after Windows dismissal adds two frames.
Raw samples, source hashes and check artifacts are in the
[machine-readable record](../development/aes-layers-vram.json). No loaded or
cold-cache latency acceptance is claimed by this idle comparison.

## AV2: shared cache policy and menu backgrounds

Layers now owns a single saved-scene rectangle and shared two-slot identity,
revision and pinning policy. Native client snapshots use that policy too. A
menu captures only completed visible contributions. Its own drawing is exempt
from invalidation; underlying content, console damage and geometry changes
invalidate intersecting saves. Unsupported alignment and incomplete source
paint use ordinary rendering without waiting for an application.

The coordinated hide/restore transaction pins its storage through display
completion. Successful restoration subtracts only that footprint from manager
damage. AES exposure is retained and published after the selected menu heading
has been repaired, so an application UPDATE cannot delay that repair. Failed
or unquiesced transfers cannot publish a valid save or release a live pin.

Scene gains 22 bytes (9,184 total); cache records replace the old native
metadata without increasing their size. Adapter state adds 26 bytes, plus the
one-byte pending-show state. VRAM gains 76,800 bytes, for 320,000 total.
Reserved bank zero changes by **0 fixed / 0 per public Task / 0 idle bytes**.

Development checks: 459 host tests (four skips), 60,136 optimized Layers checks,
raw/optimized far-record probes (105 each), the AES menu fixture and twelve
native cache scenes. The native fixture also opens and dismisses a real Windows
menu whose saved background spans several owners, then compares every pixel
against an independent oracle. Identity reuse, native eviction, odd exposure,
geometry, failure and external pending-paint cases remain covered.

An intermediate exact demo showed real saves/restores: Windows dismissal fell
from 501.4 to 240.7 ms (median/p95), while final Files repaint was 361.0 ms.
This predates the repaired menu-heading/exposure ordering and is not acceptance
evidence for the final slice. The 100 ms gate remains open until remeasurement.

## Remaining slices

AV3–AV6 remain in progress. Numeric performance gates remain separate from
functional completion; no acceptance is inferred from correct cached pixels.
