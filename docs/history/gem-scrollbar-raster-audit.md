# Selected-scrollbar raster audit

[GEM plans](../plans/gem4xe/README.md) ·
[Inputs and measurements](../development/gem-scrollbar-raster-audit.json) ·
[Previous copy slice](gem-odd-edge-copy.md)

The 2026-11-17 audit implements the requested tracing and donor comparison only.
Drawing code, limits, ownership and application logic are unchanged. The concrete
next reduction is to avoid repeated row-advance calculation inside `blit_mask`;
it has **not been implemented**.

The selected-object architecture is already working: each measured vertical
slider paint acquires physical access once, traverses its subtree once and visits
only objects **9 and 10**. The dominant Task CPU cost is command construction,
not another layout pass or traversal of the complete frame.

## Capture and attribution

`tools/measure_mgview.py --slider-detail` adds passive entry/return observations
for the existing object, scratch, fill, mask, queue and upload routines. It
reuses `build/odd-edge-copy/viewer` without a build or guest instrumentation.
The existing MGVIEW down/up actions, exact viewport pixels, Process retirement,
stack/domain guards and ownership checks pass. APP, provider, native image,
document, viewport and pinned PAL/8× configuration match the previous capture.
The whole-scroll timing and pixel hashes match it exactly too.

The ready snapshot records the 16×182 vertical track at `(617,31)` and a
16×91 thumb, inside the `(0,11,633,222)` window. The work rectangle is
`(1,22,616,200)`. The track's odd edges require packed-nibble preservation when
the compact scratch image is published. One callback paints both objects;
the scratch image is published once, through three bounded command lists.

The table partitions Task CPU by the innermost observed routine. Rows are
disjoint and sum to the whole paint; interrupts and off-Task time are separate.

| Paint work, Task CPU | Down | Up |
| --- | ---: | ---: |
| Mask command construction, including row advances | 15.506 ms | 15.520 ms |
| Solid command construction | 3.640 ms | 3.625 ms |
| Object traversal/origin lookup, excluding children | 0.538 ms | 0.549 ms |
| Object preparation | 0.705 ms | 0.705 ms |
| Other object callbacks/raster/adapters | 1.504 ms | 1.509 ms |
| Command upload | 4.120 ms | 4.125 ms |
| Driver submission, excluding upload/fences | 0.412 ms | 0.404 ms |
| Fences | 1.464 ms | 1.529 ms |
| Other wrapper, ownership, queue and native work | 3.524 ms | 3.911 ms |
| **Whole frame paint** | **31.412 ms** | **31.878 ms** |

Within `widget_batch`, scratch setup costs 0.052/0.045 ms CPU, the object
callback 10.614/10.612 ms, and subsequent scratch publication plus its fence
17.751/17.829 ms. These are a second view of the same work, not costs to add to
the table. The clear's **inclusive** cost is only 0.650/0.649 ms; most of it is
already included in solid encoding. Removing it cannot recover the dominant
mask/publication work directly. That span is not an estimate of a removal's net
effect on later queue capacity or submissions.

The trace observes **101 submitted BCBs**, in lists of **22, 43 and 36** records.
There are 29 `solid_record` calls. Seven `blit_mask` calls account for 72 records:
each emits its first record, then another for each source/destination advance
pair. This inferred count reconciles exactly with submissions. These are records
inside one retained grant, not 101 ownership handoffs.

## MagiC and GEM4XE comparison

The checked MagiC pin is `28cfdd29aa16fef692cc287bad3046b44ddcce3d`:

- `AESWIN.S:2733–2796`: `ws_slide` compares/updates the selected axis and invokes
  `wind_draw` at `O_VSCROLL` or `O_HSCROLL`.
- `AESWIN.S:221–312,354–395`: `objc_wdraw` clips against visible frame rectangles,
  avoids the application work-only clip for the frame tree, and invokes the
  selected subtree drawing routine.
- `AESOBJ.S:7896–8058`: `_objc_draw`/`draw_obj_tree` walks the selected objects.
  Its object routine issues the object's border/interior drawing; it does not
  first clear the whole requested frame clip.
- `AESOBJ.S:6390–6418,666–790`: box interiors use replacement drawing through
  `drawbox`/VDI, with current fill attributes cached.

GEM4XE's checked AES/rendering pin is
`e413c39d2f8e1bec8fe16596f610b923de4a0ae9`. Its `objc.c` subtree traversal and
`just_draw` object decoding/border/fill structure are the quarry used here.
`graf.c:656–670` requests replacement fills for object interiors. Its
`src/vbxe/vbxe.c:531–542` `blit_mask` builds a hardware record through
`bcb_new`/`bcb_common`; it has no equivalent loop recalculating row advances.
That donor producer also does not enforce Exec's current bounded-list protocol,
so copying it wholesale would change the accepted device contract.

Exec now follows the same selected-subtree/visible-clip flow. The extra work is
in its graphics adaptation: prepared objects draw into compact scratch, followed
by bounded masked publication to the screen. The 16-row command producer is an
Exec implementation detail, not a MagiC operation boundary. This audit does not
propose replacing the ownership or drawing-limit contract.

The pre-clear is also an adaptation detail, but is **not proven redundant**.
Exec's current patterned `GemWidgetFill` routes to the transparent disabled-
stipple helper; it does not implement the donor's general opaque replacement
pattern fill. The clear establishes neutral paper before that operation.
Deleting it alone could publish stale scratch pixels. This existing graphics
semantic difference remains for explicit review; changing it is outside this
audit and the proposed row-advance reduction.

## One concrete reduction to implement next

`blit_mask` calls `row_step(ss,n)` and `row_step(ds,n)` after each non-final
record. In this capture that happens **130 times**, costing **5.803/5.766 ms
CPU**. The strides are unchanged throughout each mask call:

| Stride | Calls per paint | Down CPU | Up CPU |
| --- | ---: | ---: | ---: |
| 0 | 32 | 0.950 ms | 0.968 ms |
| 16 | 33 | 1.680 ms | 1.701 ms |
| 32 | 10 | 0.522 ms | 0.493 ms |
| 320 | 55 | 2.652 ms | 2.604 ms |

The source establishes a stronger invariant: `limit` is constant during a
`blit_mask` call, and an iteration has more rows afterward only if its `n` was
exactly `limit`. Therefore every advance uses the same two products.

The proposed change is to calculate those source/destination advances once,
only when the initial height exceeds `limit`, and reuse them for every
non-final record. The observed calls would fall from **130 to 14**. This removes
116 repeated calculations while preserving record contents, order, row/list
bounds, capacity drains, fences and grant boundaries. The current cost of that
repeated work suggests roughly **5 ms CPU of opportunity** before hoisting and
compiler overhead; it is not a measured or guaranteed net saving.

Keep this as one focused producer change, followed by the existing emitted
descriptor/pixel/overlap/failure probe, a selected-frame pixel check covering
compact strides, and the same cached MGVIEW observation.
No implementation or performance gain is claimed by this audit.

## Validation scope

Two small host tests check disjoint nested CPU accounting across peer execution
and native interrupts, plus separation of clear/object/publication phases. The
host suite and local link/content checks accompany the evidence record. Actual
MGVIEW machine code executes unchanged with intact guards and cleanup. No APP,
provider, native loader, QED, Counter, catalog, demo or release build was run.
Reserved bank-zero changes are **0 fixed, root, kernel, idle and per-public-Task
bytes**, including guards, alignment and spare capacity. No target memory or
resource is added; these are development observations.

```sh
python3 tools/measure_mgview.py --cache build/odd-edge-copy/viewer \
  --output build/scrollbar-audit --slider-detail --expect-copy-units 1
python3 tools/measure_mgview.py --cache build/odd-edge-copy/viewer \
  --output build/scrollbar-audit --analyze-only
```
