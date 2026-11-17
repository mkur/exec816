# MGVIEW mouse hide/show audit

[History index](README.md) · [Pre-copy audit](gem-pre-copy-audit.md) ·
[Pinned inputs and measurements](../development/gem-mouse-hide-audit.json)

The 2026-11-17 audit confirms that mouse hiding is mostly surrounding work.
`graf_mouse(M_OFF)` charges **5.904–5.928 ms viewer CPU**, while the cursor
restore routine, including command submission, charges **0.501–0.534 ms**.
The 8.016–8.034 ms elapsed call does not represent eight milliseconds of
blitter work. Runtime code and drawing limits are unchanged by this audit.

## Frozen capture

`tools/measure_mgview.py --mouse-detail --expect-copy-units 1` reuses
`build/gem-slider-noop/viewer`. Native image, provider, MGVIEW APP, document,
viewport, ROM and emulator match the preceding unchanged-slider slice. The
observer adds linked entry/return PCs only. Local renderer symbols are checked
against their emitted executable sections. Neither target builds nor guest
instrumentation are involved. Both action samples, including their observation
ticks, match the preceding capture exactly.

The pointer is parked at `(639,0)`, outside the viewer. This is a clipped cursor
fixture, not a benchmark of every pointer position or form. The observer matches
the two public mouse calls inside `set_shift`: hiding before `vro_cpyfm` and
showing after painting. Function return PCs and full Task D/S delimit calls.

The following caller stages are disjoint and reconcile elapsed, Task CPU,
interrupts and off-Task time independently:

| M_OFF stage | Down CPU | Up CPU |
| --- | ---: | ---: |
| Public binding, context lookup and dispatch | 1.068 ms | 1.067 ms |
| Native cursor policy | 0.805 ms | 0.805 ms |
| Policy return and C device bridge | 0.086 ms | 0.092 ms |
| Device apply, including physical borrow | 3.465 ms | 3.436 ms |
| Completion/wake checks and public return | 0.503 ms | 0.503 ms |
| **Whole call** | **5.928 ms** | **5.904 ms** |

Native interrupts add **1.424/1.381 ms**; other Tasks add **0.682/0.732 ms**.
Inclusive routine measurements below overlap these caller stages and must not
be added to them. CPU charges include bus stalls and gateway/scheduler return
work; the location of preemption changes which live routine receives that work.
The per-direction variation is not evidence of different hide algorithms.

## Work inside those stages

- `AESCURSOR.Call` unconditionally invokes `Select`. That resolves the current
  cursor recipient through copied hit routing even for a hide. `Select`
  costs **0.565/0.559 ms CPU**, including **0.423 ms** in
  `AESMOUSE.CursorRecipient`. This is not a full input snapshot publication.
- `draw_Mouse` copies the entire **76-byte `AESMouseForm`** into scratch under
  Forbid before comparing the kind. The built-in arrow hide therefore copies
  the 74-byte MFORM payload too. One `memcpy` call charges **1.481/1.015 ms**.
  There is no `memcmp` or form repacking in these observed hides.
- The complete public hide traverses **13 Forbid/Permit pairs**: four through
  the C gateway wrappers and nine through native Task calls. Their measured
  spans do not overlap. The exclusive coordination category charges
  **2.052/2.469 ms CPU**, including continuation work when a Permit yields.
  This is not the intrinsic cost of thirteen counter increments. Guards occur
  in lookup, nested policy/selection, device target/completion and admission.
- Physical borrowing succeeds once. Hiding submits **one BCB**, restoring the
  saved background; showing submits three records to save and draw the pointer.
  The hide's `cursor_render` is **0.501/0.534 ms CPU**, including the
  **0.220/0.253 ms** submission. Two observed fence calls charge
  **0.037/0.070 ms CPU**; those are wrapper costs, not a pure DMA timer.
- After device completion, `AESCURSOR.Wake` scans registrations and `Pending`
  checks the durable target. Together they charge about **0.44 ms CPU**.
  Neither public mouse call signals or waits in these samples. There is no
  manager RPC or UPDATE acquisition on this path. Display admission and
  completion remain synchronous in the calling Task.

Showing costs **5.294 ms CPU / 6.437 ms elapsed** in both actions. It repeats
recipient selection and the complete form copy. The physical cursor draw
routine costs **0.907 ms CPU**, including three records. Both public hide/show
calls return success.

## Pinned MagiC comparison and next slice

At MagiC revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d`, normalized
`AESMAIN.S` `gm_hide` (7201–7203) increments `ap_mhidecnt` and jumps to
`mouse_off`. `AESOBJ.S` (368–376) calls VDI only when the aggregate hide count
was zero, then increments that count. `INPUT.S` `v_hide_c` (264–274) updates
the device hide count and calls `undraw_sprite` on its first hide. These paths
do not reselect a recipient or copy/install a mouse form. MagiC's form-selection
branch is separate from the special hide/show dispatch.

Exec preserves normal Task preemption, so guarded state changes, an owned
display grant and synchronous restoration still have a concrete purpose.
The audit does not propose deleting synchronization or adding a platform
service. It identifies general form/routing work inside a visibility operation.

The next bounded candidate is a **direct visibility path for M_OFF**: keep
per-client/aggregate hide accounting and synchronous physical completion, while
avoiding recipient/form selection and copying form data solely to erase an
existing cursor. A later show must still install the correct form after real
routing/form changes. Form installation, dirty recipient selection and broad
guard/wake simplification should be reviewed separately rather than folded
into this first slice. No implementation or performance saving is claimed here.

## Development checks

Exact viewport pixels, one viewport copy and exposed-row draw per action, no
fallback repaint, three Process lifetimes, ownership/heap restoration and
stack/domain guards pass. The settled full scanout remains identical. Host
checks run **740 tests, four skipped**, including disjoint mouse-stage
attribution with peer and interrupt time and rejection of incomplete stages.

Added reserved bank-zero bytes: **0 fixed, root, kernel, idle and per public
Task**, including guards, alignment and unused capacity. Runtime storage is
unchanged. No QED, Counter, target build, demo refresh or release qualification
ran. Two clipped-cursor hide/show pairs do not establish a latency distribution
or qualify the hosted system.
