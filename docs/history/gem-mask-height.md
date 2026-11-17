# Full-height GEM mask records

[GEM plans](../plans/gem4xe/README.md) ·
[Inputs and measurements](../development/gem-mask-height.json) ·
[Previous raster audit](gem-scrollbar-raster-audit.md) ·
[Current display contract](../reference/display.md)

The generic GEM mask builder now emits records up to 256 rows, limited by
width and mode work instead of a fixed sixteen-row ceiling. Each raw list still
has at most 64 records and 8,192 estimated accesses. In the matched MGVIEW
down/up samples, scrollbar painting falls from 31–32 to about 14 ms Task CPU,
and observed key-to-complete latency falls from 181/201 to 140/140 ms.

## Implementation and donor flow

The 2026-11-17 user decision replaces the previous proposal to optimize repeated
row advances while retaining sixteen-row records. The
[pinned MagiC/GEM4XE audit](gem-scrollbar-raster-audit.md#magic-and-gem4xe-comparison)
found that this limit is an Exec encoder detail, not a MagiC operation boundary.
GEM4XE's donor `blit_mask` emits one hardware record. Exec now does the same
when the complete operation fits its retained raw-list work budget; otherwise
it emits ordered budget-sized fragments. Caller drawing, UPDATE, display
admission, scratch reconstruction/publication and Task preemption retain their
existing boundaries. No platform service is missing or added for this change.

`GemRowLimit2/3` now contain unsigned words so 256 is representable. They select
`min(256, floor(8192 / (bytes * factor)))`, with factor two for copy and three
for other hardware modes. The builder charges bounded `rows * rowWork` before
appending each record. It calculates source/destination advances once only if
another record is necessary, using wide products to preserve VRAM bank carries.
It still drains before exceeding count/work capacity and stops after a failed
drain. The record height remains encoded as `rows - 1`.

The old row-advance helper, factor-two work table and four stride tables are
removed. Glyph runs retain their existing small-height factor-three table.
Generated table payload falls from **37,457 to 21,961 bytes**, within the same
reserved 64 KiB upper read-only bank. This does not free that bank reservation.
The driver's public generic rectangle chunk policy is unchanged; the change
is confined to the private GEM mask producer. Wide operations still split by
work. The compact scrollbar scratch already accommodates its full height;
no scratch allocation grows.

## Focused development checks

The optimized emitted screen-copy fixture passes **59 cases**. The existing
41 cases retain whole-source snapshot, nibble-edge, overlap, descriptor,
admission, transfer, submission and fence-failure coverage. Eighteen added mask
cases check 256-row height encoding, compact 16/32-byte source/destination
pitches, full-height nibble AND/OR, replace/AND/OR/XOR modes, exact work and
record-capacity drains, tail fragments, multi-bank source/destination advances,
and a failed second list. Actual emitted records are replayed against an
independent byte/pixel model, including untouched VRAM. The hardware boundary
is captured in this fixture; real loaded MGVIEW exercises the production DMA
path separately.

Small raw and optimized emitted table probes check the changed word loads,
the value 256, every width's work-derived height, remaining glyph tables,
upper-bank placement/readback and guards. Both pass. These are table/layout
checks, not duplicate application scenarios. The host suite passes **724 tests,
four skipped**.

Only `gem-vbxe.c` was recompiled for the viewer provider, using regenerated
tables; verified unchanged provider objects were relinked and the native loader
rebuilt. The MGVIEW APP was reused. No Counter, QED, catalog, demo, release
build or qualification matrix ran. These are development checks.

## Matched MGVIEW results

The unchanged application, document, font, `(1,22,616,200)` work rectangle,
pointer placement, ROM and PAL/8× configuration match the previous raster
audit. One down and one up action still execute one semantic viewport copy
and one exposed-row text draw, with two copy grants and one typed interior
copy. Each scrollbar paint still acquires physical access once and visits only
objects 9 and 10 in one subtree traversal.

| Per scroll | Down before → after | Up before → after |
| --- | ---: | ---: |
| Scrollbar paint Task CPU | 31.412 → **14.396 ms** | 31.878 → **14.300 ms** |
| Mask construction Task CPU | 15.506 → **1.168 ms** | 15.520 → **1.186 ms** |
| Command upload Task CPU | 4.120 → **1.481 ms** | 4.125 → **1.475 ms** |
| `vro_cpyfm` Task CPU | 42.333 → **27.045 ms** | 42.381 → **28.083 ms** |
| Whole `set_shift` Task CPU | 128.530 → **96.927 ms** | 128.890 → **98.044 ms** |
| Whole `set_shift` elapsed | 171.391 → **134.019 ms** | 171.853 → **135.329 ms** |
| Key offered → complete viewport observed | 180.841 → **140.112 ms** | 200.908 → **140.339 ms** |

Paint/mask/upload rows are nested views and must not be added. The same producer
also reduces source-edge capture and destination-edge restoration in the copy
path; the improvement is not confined to scrollbar publication.

Each scrollbar submits **36 records instead of 101**: 29 solid records and seven
remaining records, matching the seven nonempty mask operations. The old two
stipple operations emitted 12 records and the five publication operations 60;
each now fits one record. There are still three lists, now **19/12/5** rather
than 22/43/36. Record construction and upload fall without claiming fewer
ownership handoffs or list submissions. The passive observer reports submitted
records minus observed solid records; it no longer infers fragment counts from
the removed row-advance helper.

Both viewport hashes match the baseline. The final up-state complete window,
including its frame and scrollbar, also matches exactly: **140,526 pixels**.
The BGRA comparison uses the bridge's 672×240 scanout, 2,688-byte stride and
16-pixel horizontal border. Before/after full-window hashes and source captures
are recorded in the evidence JSON.

The complete-viewport polling brackets are **122.433–140.112 ms down** and
**122.005–140.339 ms up**. These are two action observations at PAL/COP
boundaries, not percentiles or physical-machine latency guarantees. Normal
peer execution and native interrupts remain visible during owned drawing.

Three Process lifetimes complete, ownership/heap baselines restore and guards
pass. MGVIEW's measured stack peak is 1,298 bytes in its existing 2,560-byte
pool, leaving 1,006 above the ordinary floor. The generated bank-zero budget,
runtime reservations and every Task pool exactly match the previous build:
**0 added fixed, root, kernel, idle and per-public-Task reserved bytes**, including
guards, alignment and unused capacity. No VRAM, Task, signal, API or heap buffer
is added.
