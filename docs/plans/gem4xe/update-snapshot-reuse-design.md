# AES UPDATE snapshot reuse

[GEM plans](README.md) · [UPDATE contract](../../reference/aes.md) ·
[Caller-local UPDATE](caller-local-update-plan.md) ·
[Latest measurements](../../history/object-tree-traversal.md)

Status: proposed design, inspected against `ac33f02b`. Profiling is the first
implementation slice; the reuse mechanism and its storage remain to be chosen.
This note changes no implementation or public contract.

## Purpose and measured opportunity

Reduce repeated geometry and visibility work inside conventional
`wind_update(BEG_UPDATE)` / `wind_update(END_UPDATE)`. Application source,
window enumeration, update ownership and repaint obligations keep their
current behavior.

The optimized capture after incremental object traversal records a fragmented
Counter tick at **39.306 ms caller CPU**, including **20.654 ms in UPDATE**
and **1.061 ms inside drawing borrows**. These are inclusive helper costs;
they do not partition the whole operation or establish how much can be saved.
The timing artifact is
`build/object-tree-traversal/measurement/timings.json`, whose hash is recorded
in the [development evidence](../../development/object-tree-traversal.json).

Use that capture and commit as the next comparison baseline. Uncovered and
fragmented Counter cases own different numbers of windows, so their difference
does not isolate visibility cost. The exposure control also took different
local/RPC UPDATE paths between captures. Measure bookkeeping separately from
admission, waiting and work moved between caller and presenter.

## Existing work and distinct lifetimes

[`AESLOCKS`](../../../lib/aes/aeslocks.act) owns the common local/RPC policy.
On outer BEGIN, [`AESWINDOWSTATE.BeginUpdate`](../../../lib/aes/aeswindowstate.act)
resets the paint/invalidation journals and failure state, clears scoped change
tracking, calls `LAYERS.Touch` and `DESKCACHE.BeginChange`, then snapshots every
owned window. Nested transitions update depth without repeating outer BEGIN.

`Publish` derives work geometry, clips the layer's visible region to it, checks
pixel readiness and publishes the view. Owner mutations also call this path;
`Moved` preserves the special handling of a completed copied move. Final END
consumes the journals, retains repaint obligations, completes cache accounting
and publishes the final paint epoch and pixel readiness.

Keep these identities separate:

| State | Meaning for reuse |
| --- | --- |
| Scene layout / work geometry | Determines bounds and visible work rectangles. Reuse is considered only here. |
| `contentRevision` | `LAYERS.Touch` advances content state and invalidates snapshots even without visible drawing. It does not prove geometry changed. |
| `paintEpoch`, pending damage and `pixelsReady` | Describe repaint identity and completeness. They may change while geometry stays fixed and must remain fresh. |
| `WindowView.revision` | Guards FIRST/NEXT enumeration against replacement. Preserve its publication behavior; do not repurpose it as a geometry cache tag. |

## Reuse rules and invalidation

A hit may skip reconstructing or copying unchanged bounds/work/visible
rectangles. It must still establish the same observable view and perform all
required BEGIN/END, revision, depth, content/cache and paint-state transitions.
In particular, neither unchanged geometry nor an empty visible list proves
that an application made no hidden model changes or completed its repaint.

Freshness belongs to a live window/layer/view identity. Valid empty visibility
is reusable; an uninitialized or invalid entry must remain distinguishable.
Creation, deletion, detach and slot reuse retire the previous identity. Ordinary
and window-scoped BEGIN retain the existing publication of every owned window;
the scope still controls change tracking and repaint/cache holds.

| Trigger | Required handling |
| --- | --- |
| Owner move/resize, frame/work-inset change, or changed iconified normal bounds | Refresh affected geometry; preserve resize invalidation, copied-move handling and iterator replacement. |
| Any peer/native window or overlay moves, opens/closes, shows/hides, changes stacking or changes bounds | Invalidate every potentially affected view, even if its own bounds are unchanged. Include menus, dialogs and saved-overlay replacement. |
| Iconify/restore or hidden/covered transitions | Publish the current logical work area, shown state and empty/nonempty visibility as appropriate. |
| Content touch, damage, completion, cache capture/eviction or paint failure with fixed layout | Keep geometry eligible only if its own proof remains valid; refresh paint/cache facts through the existing protocol. |
| Scene reset, identity reuse, freshness-counter wrap or failed visibility reconstruction | Retire affected reuse entries. A partial region must never authorize drawing. |

Unknown freshness takes the existing reconstruction path. Preserve its existing
failure behavior. An owner mutation during UPDATE must still invalidate an
outstanding NEXT walk; callers restart with FIRST. Equal final bounds do not
erase an intervening mutation.

The measurement slice must choose among these bounded approaches:

- An existing scene-layout stamp plus window identity and local geometry inputs.
  `Scene.rebuilds` is a conservative candidate, not yet a proven cache key:
  audit all mutation/failure paths, initialization and wrap before relying on it.
- Private per-window invalidation, if the audit demonstrates complete coverage
  and a worthwhile benefit over the conservative scene stamp.
- Retain reconstruction and reduce other measured bookkeeping if clipping and
  copying are a small share. A reuse cache is conditional on that evidence.

Prefer private AES upper-RAM metadata if new state is needed. Keep the public
view/wire layouts and language bindings unchanged for the initial slice; record
the selected key, validity representation, lifecycle and exact storage before
implementing reuse. Reuse existing bounded rectangle storage rather than adding
a second region array or allocations in BEGIN/END.

## Ownership and publication

Make the reuse decision and update its metadata under the existing exclusive
AES policy ownership, identically for local admission and presenter RPC.
Publish coherent view fields before BEGIN returns; preserve synchronous END
journal consumption and final epoch/completeness publication. The application
continues to read its snapshot rather than live Layers storage.

Keep the current gate, short publication guards, normal preemption, pending
waiter order, recursive ownership, TRY behavior, MCTRL path and outer scope.
IRQ masking alone is not an NMI protocol. Add no long Forbid section, drawing
under the policy gate, retained scene token, private kernel operation or new
validation of already admitted caller pointers.

## Executable order and acceptance

1. **US0 — attribute the cost.** Add passive entry/return observations for
   BEGIN, SnapshotAll/Publish, geometry clipping/readiness, END and cache work.
   Preserve the guest workload; distinguish caller CPU, presenter CPU, waiting,
   nesting and local/RPC paths. Use controlled one/multiple-owned-window and
   unchanged/changed-layout cases with equal window counts when isolating
   clipping. Freeze inputs and record the selected mechanism and cost target
   before the first production change.
2. **US1 — establish freshness regressions.** Check current behavior before
   replacement: exact visible sets/pixels; repeat BEGIN with unchanged layout;
   owner and peer mutations; disjoint/empty visibility; iconify/restore;
   ordinary/scoped and nested UPDATE; iterator invalidation; hidden/no-draw
   model changes; stale/partial/failed paint reports; deletion and slot reuse.
   Exercise both admission paths and two scheduled clients with normal cleanup.
3. **US2 — implement the selected reduction.** Preserve the common policy and
   public ABI. Test hits, misses, identity retirement and the chosen counter's
   wrap/reset/failure rules through optimized emitted code. Keep geometry reuse
   independent of current paint readiness and completion.
4. **US3 — compare and record.** Repeat the unchanged matched AES corpus and
   targeted UPDATE cases. Require exact geometry, messages, damage and pixels,
   intact guards, restored ownership/heap and bounded completion. Report BEGIN
   and END separately and total caller/presenter cost; attribute any admission
   shift. Accept only a measured net benefit on the targeted repeated-layout
   workload, with no unexplained material regression in changed-layout or
   control workloads. Record code, data, stack and reservation costs.

Use the [development testing tier](../../contributing/testing.md): host checks
and focused optimized emitted-code fixtures. Raw probes are for an actual
compiler/ABI concern. Full qualification and physical-hardware claims require
their own evidence. Disjoint redraw coalescing, renderer batching and compiler
migration remain separate work.

This documentation change reserves **0 additional fixed/root/kernel bank-zero
bytes, 0 per public Task and 0 idle bytes**, including guards, alignment and
unused capacity. Implementation targets the same zero reservation growth;
measure transient stack use and any bounded upper-RAM metadata separately.
No demo refresh is required for the profiling/design slices. Any later refresh
uses `tools/build_demo.py` with OF816 and the existing packaging contract.
