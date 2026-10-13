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

## Remaining slices

AV2–AV6 remain in progress. No menu-cache or window-cache performance gate is
accepted by the AV1 bookkeeping results.
