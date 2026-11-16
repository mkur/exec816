# One interior blit for odd screen edges

[Plan](../plans/gem4xe/odd-edge-screen-copy-plan.md) ·
[Raster contract](../reference/gem-vdi.md#conventional-raster-copy) ·
[Inputs and evidence](../development/gem-odd-edge-copy.json)

On 2026-11-17, `GemDrawingCopyBorrow` separates its same-parity aligned interior
from the masked source/destination columns. Previously, edge handling limited
the entire MGVIEW copy to roughly thirteen-row bands: fifteen interior copies
and sixteen display entry/leave pairs for one line scroll.

The outline follows GEM4XE `dev_copy_form`, at revision
`2bf10f6788372dcfa94f6d9416e4b957eb4ce394`, `src/vdi/dev_vbxe.c:1880–1926`:
blit the aligned middle separately from edge columns. Exec retains its existing
complete source-edge capture before any writes, rather than changing the
established overlap protection. The first grant captures at most 480 bytes into
the existing upper buffer. A second grant reloads those bytes, runs one typed
overlap-safe interior copy and restores edge columns through `blit_mask`.
The caller's descriptor is restored immediately after the interior call,
including its failure return. MagiC's caller/UPDATE structure is unchanged.

The mask producer still bounds records to sixteen rows and lists to 64 records/
8,192 estimated accesses. At the 240-row maximum, two source columns need 30
records/960 accesses; both destination columns need 60 records/2,880 accesses.
Those limits no longer divide or readmit the aligned interior. The existing
640×240 typed-screen bound, driver fences, timeout/fault retention, and normal
Task preemption remain in force. Other raster modes, different-parity copies,
cache policy and general drawing limits are unchanged.

## Focused validation

The optimized emitted probe executes the real typed copy encoder, adapter
routine and mask-list producer. Its hardware boundaries record BCBs, VRAM
read/write positions and releases. The host replays them against an independent
whole-source nibble snapshot, checking all 512 KiB apart from the existing
transient scratch. A simulated peer replaces that scratch on every release;
saved source edges must survive in the caller's upper buffer.

All **41 cases pass**: matched MGVIEW up/down, both partial-edge nibbles,
one/two columns, one/two-pixel copies without an interior, full-height and
screen-edge cases, horizontal/vertical/diagonal overlap, unchanged/empty
rectangles, denied first/second admission, capture submission/read, scratch
write, interior/edge submission and final-fence failure. The original non-screen
driver fallback remains covered. Every case checks descriptor preservation,
balanced successful admissions and edge-buffer canaries. Mask-list count/work
and record-row limits are checked at submission. Guards and ownership pass.

The host suite passes **722 tests, four skipped**, including existing packed
pixel/raster-mode overlap and failure checks. The additional formerly skipped
raster-source check now runs because the exact pinned donor was fetched and
verified. The display-borrow observation hooks were updated and checked against
the changed routine. Only the drawing adapter object was recompiled; verified
provider objects were relinked, the native loader rebuilt, and MGVIEW reused.
No APP was rebuilt. No QED, Counter, catalog, demo or release matrix was built
or run.

## Matched MGVIEW observation

The baseline is WG6's `build/window-geometry/wg6-scroll`. APP and document hashes,
font, `(1,22,616,200)` work rectangle, physical down/up keys, parked pointer,
pinned ROM and PAL/8× machine configuration match. The observer adds no guest
instrumentation and performs no build. Each action still executes one semantic
616×192 viewport copy and one exposed text-row draw; complete pixel hashes
match the baseline exactly.

| Per scroll | Down before → after | Up before → after |
| --- | ---: | ---: |
| `vro_cpyfm` Task CPU | 76.674 → **42.333 ms** | 77.276 → **42.381 ms** |
| `vro_cpyfm` elapsed | 97.045 → **53.750 ms** | 97.698 → **53.861 ms** |
| Interior owned-copy calls | 15 → **1** | 15 → **1** |
| Display entry/leave pairs inside copy | 16 → **2** | 16 → **2** |
| Fence calls inside copy | 110 → **12** | 110 → **12** |
| Whole `set_shift`, Task CPU | 162.589 → **128.530 ms** | 164.171 → **128.890 ms** |
| Whole `set_shift`, elapsed | 214.357 → **171.391 ms** | 218.682 → **171.853 ms** |
| Key offered → complete viewport observed | 223.586 → **180.841 ms** | 240.731 → **200.908 ms** |

Copy Task CPU falls 44.8%/45.2% in these matched samples. Inclusive call costs
must not be added together. Complete-viewport polling brackets are
163.996–180.841 ms down and 180.587–200.908 ms up. These are one action per
direction sampled at PAL/COP boundaries, not percentiles or a physical-hardware
latency guarantee.

Each copy has two successful physical ownership intervals. The second retains
the grant for about 34.2 ms elapsed, including 1.42 ms off the viewer Task and
5.87/5.92 ms of viewer-context native interrupts. Thus peer execution and
interrupt delivery occur while the grant remains held. Competing drawing waits
for the complete interior/edge operation. The typed copy still completes
synchronously without an observed completion IRQ; no new IRQ protocol is added.

Three Process lifetimes finish, heap baselines and ownership restore, and all
stack/domain guards pass. MGVIEW touches 1,274 bytes in its existing 2,560-byte
pool, leaving 1,030 above its ordinary floor. The generated bank-zero budget,
root/kernel reservations and every Task pool match WG6 exactly: **0 added fixed,
root, kernel, idle and per-public-Task reserved bytes**, including guards,
alignment and unused capacity. No upper buffer, VRAM extent, Task, signal, API
or platform service is added. These are development results.

The copy still costs about 42 ms of Task CPU. Source-edge staging/transfer and
masked restoration remain, and selected-scrollbar raster work is still separate.
This slice completes the proposed interior-copy change without claiming those
remaining costs are solved.

```sh
python3 tools/test_screen_copy.py --output build/odd-edge-copy/encoding
python3 tools/measure_mgview.py --cache build/odd-edge-copy/viewer \
  --output build/odd-edge-copy/scroll --slider --expect-copy-units 1
```
