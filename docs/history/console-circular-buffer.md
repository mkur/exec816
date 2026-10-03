# Circular console character buffer

[Historical records](README.md) · [Implementation plan](../plans/console-circular-buffer-implementation-plan.md) ·
[Console contract](../reference/console.md)

CB1–CB4 replace retained character-row copying with a circular origin. Each
scroll clears one row and advances the origin within the existing allocation.
The framebuffer remains linear and still uses one asynchronous VBXE copy/fill
list. This reduces preparation cost and isolated scrolling time; loaded input
latency remains above the desktop targets.

## Representation and lifetime

The private Instance record appends `CARD cellOrigin` at offset 198, making it
200 bytes. The origin is a byte offset aligned to the instance width. Logical
cell addressing adds it and conditionally subtracts `count`. Feed maps once per
printable run; presentation maps once per row/span. Far-address addition retains
CPU bank carry. Cursor positions, lineStart, damage rows and view indexes stay
logical; allocation, extent admission and freeing keep the original pointer.

Scroll clears the old origin row, advances the origin, marks the entire logical
model dirty and completes the existing edit quantum. This preserves the fallback
for hidden, clipped or invalidated presentation. Height one clears its only row.
FF resets the origin during the clear edit, after old cursor removal; CMD_CLEAR
continues to clear input only. No damage-array rotation or scrollback was added.

Existing instance borrowing excludes competing edits. IRQs never access the
ring, and ordinary preemption stays enabled. The committed origin and characters
remain gated while DMA is pending, while input capture and READ replies progress.
Completion never rotates a second time. Cancellation preserves accepted bytes;
PRESENTING defers adoption; destruction, Stop and faults retain the existing DMA
and storage lifetime rules. There is no new kernel operation or driver queue.

## Development checks

| Slice | Scope |
| --- | --- |
| [CB1](../development/console-circular-buffer-cb1.json) | Generated record, logical readers/writers, host snapshot decoding, nonzero-origin clipping and CPU bank crossing; raw/optimized core, text and bitmap checks. Internal bitmap helpers are excluded from application Task-entry discovery, matching the other console modules. |
| [CB2](../development/console-circular-buffer-cb2.json) | Circular edits; 192 scrolls per raw/optimized core run across six geometries. Every selected origin is visited at least three times, with an independent linear buffer and unchanged non-recycled physical bytes/guards. Both display backends and all 13 bitmap scenes pass. |
| [CB3](../development/console-circular-buffer-cb3.json) | Wrap at pending blit, unchanged origin/generation/physical cells during READ, cancellation, stale identities, hide/show, PRESENTING, last-WRITE stop/destroy/reuse, quiesced/reset-required faults and window lifetime in both modes. |
| [CB4](../development/console-circular-buffer-cb4.json) | Final isolated image and three loaded phases with identical-image unobserved replays, using saved BI5 results as the baseline. |

The host suite passes 321 tests, with four historical-source skips. These are
focused development checks with guards, native context, ownership, bounded
completion and OS restoration; they are not full release qualification.
One control variant injects input after real launch and invokes the existing
worker ReadQuantum in that turn to exercise BUSY/READ overlap in both modes.
The other control variants retain ordinary worker scheduling; production input
timing comes from CB4. No baseline workloads were rerun. CB3 changes fixtures
only, so CB2's isolated
image contains the final production implementation.

## Measured cost

The saved BI5 baseline and final images use the same PAL 65C816 ×8, 4 MiB,
VBXE FX 1.26 at `$D600`, AltirraOS 3.44 configuration. Loaded runs include eight
Tasks, physical SDFS, ST mouse on port 1, keyboard and BREAK. Action! is pinned
to `f1ff4ce0d16b4705e66d69aad00ca4a7be3e1d08`, without an override; C uses
Calypsi 5.18. The evidence records actual ROM/emulator and image hashes.

| Isolated workload | BI5 | Circular buffer |
| --- | ---: | ---: |
| Two whole scrolls, edit through final drawing chunk | 32.48 / 32.51 ms | 30.47 / 30.60 ms |
| Repeated whole scrolls | 40.45–44.60 ms | 28.60–29.55 ms |
| BitmapEdit elapsed time, including preparation | 5.23 ms | 2.72 ms |
| Initial text Cells elapsed total, 66 calls | 431.16 ms | 432.08 ms |
| Initial text Present elapsed total, 66 calls | 665.50 ms | 666.33 ms |
| Partial edit plus caret Present elapsed time | 6.61 ms | 6.65 ms |
| Full repaint request through final fence | 251.16 ms | 253.94 ms |

These fixed workloads include the mapping overhead. Initial text and the partial
edit/caret show small added elapsed costs, while scroll preparation improves.
Elapsed routine intervals include interrupts/preemption and are not exclusive
CPU or a standalone caret benchmark. Pixel checks pass for all scenes and the
unobserved replay. Each isolated scroll retains one completion query and one
Wait, without a completion-polling Yield loop.

Loaded retained-edit CPU is measured separately from cursor and drawing work:

| Input phase after observed BUSY | Mean retained edit CPU, BI5 → ring | Raw glyph visible, BI5 → ring | Cooked glyph/caret visible, BI5 → ring | Maximum ring worker-turn CPU |
| --- | ---: | ---: | ---: | ---: |
| Immediate | 4.92 → 2.15 ms | 127.16 → 117.04 ms | 101.92 → 136.58 ms | 20.94 ms |
| About 2 ms | 4.79 → 2.25 ms | 127.16 → 112.92 ms | 101.92 → 100.57 ms | 21.36 ms |
| About 8 ms | 4.91 → 2.36 ms | 138.99 → 108.81 ms | 97.84 → 148.44 ms | 23.40 ms |

Retained-edit mean CPU falls 52–56%, including the unchanged damage bookkeeping.
The before/after totals are 43.11–44.25 ms across nine calls and 23.70–25.99 ms
across eleven calls within complete measured worker turns. The workload stops
production in response to interactive progress: the new image completes 35 flood
rows and 12 lists, versus 33 rows and 10 lists in BI5. These are not equal-work
aggregate totals or a measurement of the memory copy alone.

Mean charged Feed cost rises from 0.95–0.96 to 0.99–1.01 ms (77 versus 81 calls);
Cells rises from 4.61–4.67 to 5.01–5.05 ms (82 versus 86 calls). Their span sizes,
batching and interrupt phases differ, so these figures do not isolate the
mapping cost. The fixed isolated workloads above provide the corresponding
text/redraw comparison. No total loaded-CPU improvement is claimed.

All loaded lists retain one completion query, an IRQ and at least one Wait.
SIO limits pass, with no RX/TX deadline misses; watchdog service peaks at
76.05 µs against the unchanged 100 µs limit. ST sampling gaps peak at 270.66 µs.
Same-image unobserved replays pass at all three phases. All final loaded phases
use XEX SHA-256
`4f550bec54114de1ec3209a5d1a304f4c8a2ff6abcd3dd253c085e5552be53dc`.

Raw visible input improves in these samples. Cooked input regresses in two
phases; every phase still observes an incorrect frame after 40 ms. These are
frame-sampled upper bounds, not exact pixel timestamps or worst-case guarantees.
The 4 ms worker-turn, 20 ms whole-scroll and 40 ms visible-input targets remain
open. Remaining work includes scheduling delay, damage bookkeeping and bounding
the other work between input checks.

## Memory and reproduction

Every slice adds **zero reserved bank-zero bytes**: fixed, root/kernel, each
public Task and private idle, including guards, alignment and unused capacity.
Runtime reservation remains 25,408 bytes excluding OS reservations, 56,128 with
them; loading remains 21,872/52,592 bytes. No stack, DP, bank or Task is added.

Instance payload grows two bytes in upper RAM. The default record still fits
inside the existing 880-byte console reservation. Dynamic instances were already
rounded from 198 to 200 bytes by the allocator, so their allocation charge is
unchanged. Character storage remains exactly width × height; there is no spare
row or second production buffer. The control fixture's temporary snapshot is
allocated and freed by the fixture only.

Optimized CONSOLECORE code grows from 4,931 to 5,052 bytes; CONSOLEDISPLAY grows
from 14,534 to 14,658 bytes: 245 bytes total in existing upper-code capacity.
Final isolated/loaded console stack peaks remain 444 bytes. Loaded kernel peak
is 289 bytes and idle peak 54; no kernel interrupt reserve bytes are touched.

Representative commands:

```sh
python3 tools/test_console_core.py --case opt --paced --output build/console-circular/cb2-core-opt
python3 tools/test_console_bitmap_scroll.py --mode opt --output build/console-circular/cb2-bitmap-opt --observe --performance
python3 tools/test_console_bitmap_scroll.py --mode opt --output build/console-circular/cb2-bitmap-opt --replay
python3 tools/measure_async_scroll.py --output build/console-circular/cb4-loaded-0 --profile-turns
python3 tools/measure_async_scroll.py --output build/console-circular/cb4-loaded-0 --profile-turns --replay
python3 tools/record_console_circular.py
```

Loaded phases are 0, 3547 and 14188 base cycles. The latter two reuse the same
built program/drawing/selected directories and C image via `--reuse`, followed
by `--replay`. The recorder reads the saved BI5 and final results; it does not
execute the baseline. No demo refresh or release package is part of these slices.
