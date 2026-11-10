# AES UPDATE snapshot reuse implementation plan

[Design](update-snapshot-reuse-design.md) · [GEM plans](README.md) ·
[UPDATE contract](../../reference/aes.md) ·
[Testing policy](../../contributing/testing.md)

Status: implementation starting from `00266e28`; runtime baseline `ac33f02b`.
Commit this plan first, then commit each executable slice below after its
selected checks pass. Update completion and evidence links with each slice.

## Shared constraints

Preserve conventional BEGIN/END, FIRST/NEXT, ordinary/scoped and nested UPDATE,
all owned views, local/RPC admission, waiter ordering and synchronous journals.
Keep geometry freshness separate from content revisions, paint epochs,
completeness and the public view's iterator revision. Follow the design's
invalidation table and existing gate/publication protocol.

Keep public wire/view layouts, compiler pins, renderer policy and the kernel
unchanged. No hot-path allocation, second rectangle array or long Forbid region.
Select bounded private upper-RAM metadata only after measuring its benefit.

Each slice reports reserved bank-zero deltas, including guards, alignment and
unused capacity: target **0 fixed/root/kernel bytes, 0 per public Task and
0 idle bytes**. Report code, upper-RAM and transient stack costs separately.

## US0 Attribute and select

Add a passive observer for native BEGIN, SnapshotAll/Publish, geometry/clipping,
pixel readiness, END and cache work, alongside public BEGIN/END and local/RPC
admission. Reuse the frozen optimized object-traversal image for the initial
capture; verify its guest hash, pins, normal completion and exact frames.
Keep the original measurement tool and archived records intact.

Add a small controlled emitted workload for one/multiple owned windows,
repeated fixed layout and layout changes. Hold window counts equal when
isolating clipping; record nesting and admission scope explicitly. Prefer
existing metadata primitives over a second full application scenario.

Acceptance: separate BEGIN/END and caller/presenter costs, relevant helper
counts and a frozen before artifact. Record the selected key, lifecycle,
wrap/reset/failure rules, exact storage and a numerical cost target before
changing production. If reconstruction is not a worthwhile share, implement
the measured bounded bookkeeping reduction allowed by the design instead.

Commit: profiling tools, controlled fixture and US0 evidence/decision.

## US1 Establish freshness and paint regressions

Extend focused emitted coverage on the original implementation. Use independent
visible-set expectations and existing pixel oracles rather than reproducing
the proposed cache key in the oracle.

Cover repeated BEGIN; owner move/resize and peer/native/overlay changes;
disjoint and empty visibility; hidden/iconified normal geometry; ordinary,
scoped and nested UPDATE; iterator replacement; hidden/no-draw model changes;
stale/partial/failed paint reports; close/delete/detach and slot reuse.
Use existing real-client fixtures for local/RPC and two-client behavior,
supplementing only missing cases. Record actual executed scope.

Acceptance: old behavior passes, with bounded completion, guard checks and
normal heap/ownership retirement. Retain before outputs for comparison.

Commit: regressions and US1 evidence, with production still unchanged.

## US2 Implement the selected reduction

Implement the US0 decision in small routines at the existing publication
boundary. Preserve all required paint/cache and iterator metadata on a hit;
unknown or invalid geometry follows the ordinary reconstruction path. Cover
valid empty visibility, identity retirement and the selected counter's
wrap/reset/failure behavior. Keep ordinary and scoped acquisition publication
equivalent to the original behavior.

Acceptance: US1 passes on emitted optimized code; inspect actual layout/frame
costs and complete bank-zero maps. Run the host suite. Add a focused raw probe
only if changed ABI/compiler behavior needs it. Resolve compiler defects in
the owning compiler repository rather than adding routine-specific workarounds.

Commit: production reduction, focused hit/miss/lifetime checks and US2 evidence.

## US3 Match measurements and close the gate

Repeat the controlled workload and unchanged AES baseline corpus on the final
implementation with the same compiler, ROM, emulator and machine pins.
Compare all eleven frame digests, message/damage geometry, drawing-unit counts,
source differences, total caller/presenter cost and BEGIN/END/helper breakdowns.
Attribute local/RPC phase shifts and retain all failed development attempts.

Acceptance: the US0 cost target passes, no unexplained material regression in
changed-layout or control cases, guards and cleanup pass, and resource costs
are recorded. Keep samples and raw captures under `build/`; add a current
development record and completed history page, update this plan and indexes.

Commit: matched measurements and reconciled implementation record. This closes
the development gate, not full hosted or hardware qualification. No demo build
or refresh is required; any later distribution follows the OF816 build contract.
