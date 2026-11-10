# AES UPDATE snapshot reuse implementation plan

[Design](update-snapshot-reuse-design.md) · [GEM plans](README.md) ·
[UPDATE contract](../../reference/aes.md) ·
[Testing policy](../../contributing/testing.md)

Status: US0–US3 complete at the development tier. Started from `00266e28`;
runtime baseline `ac33f02b`.
See the [implementation record](../../history/update-snapshot-reuse.md) and
[matched evidence](../../development/update-snapshot-us3.json).
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

Completed: the passive capture preserves the exact guest image, all eleven
frames and timing groups. The direct metadata fixture passes 71 checks.
[US0 evidence and decision](../../development/update-snapshot-us0.json).

Selected: cache clipped work geometry using a new non-wrapping Layers
`Scene.layoutEpoch`, live window identity, frame kind, iconified mode and
source bounds. The existing rebuild counter can wrap and does not advance
before a failed rebuild, so it is unsuitable by itself. Append four bytes to
the ordinary-call Scene and regenerate/version that layout. Store eight
aligned private bytes per AES window (48 bytes for six windows); invalidate on
creation, deletion and service binding. A zero layout epoch disables reuse
after exhaustion. Keep the AES wire/view/import ABI unchanged.

Targets: at least 10% less caller CPU for the controlled fixed-layout
four-window fragmented metadata case and at least 5% less total caller CPU
for the matched fragmented Counter tick. Investigate changed-layout/control
regressions above 5%, including local/RPC admission shifts. Actual reserved
bank-zero growth in US0 is zero in every shared category.

Add a passive observer for native BEGIN, SnapshotAll/Publish, geometry/clipping,
pixel readiness, END and cache work, alongside public BEGIN/END and local/RPC
admission. Reuse the frozen optimized object-traversal image for the initial
capture; verify its guest hash, pins, normal completion and exact frames.
Keep the guest workload and archived records intact. Preserve prior observer
versions; explain and independently check any observer correction.

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

Completed on the original runtime: 137 native checks with 22 independent
visible-set observations; real cache (224), locks (181) and window (285)
assertions pass, including physical frame/geometry checks and cleanup.
[US1 evidence](../../development/update-snapshot-us1.json). Host checks pass
665 tests with four historical-source skips. Reserved bank-zero growth is
zero in every shared category. Older pending damage outside current work is
explicitly retained by the paint-readiness checks.

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

Completed: [US2 evidence](../../development/update-snapshot-us2.json).
All 22 geometry/paint/revision observations match; 137 normal and 174 epoch
checks pass. Failure, exhaustion, recovery and scene/service lifetimes are
covered. The cache, lock and physical window fixtures pass, as do 8,924 optimized
Layers checks, 126 layout/access checks in each raw/optimized mode, and the
665-test host suite (four historical-source skips).

Controlled fragmented metadata CPU falls 19.0%; changed-layout cost grows 2.6%.
Layers Scene v14 and Desktop v17 add four upper-RAM bytes per desktop Scene;
the private AES table adds 48 bytes. Publish's emitted fixed frame grows four
bytes (36 to 40), while its body shrinks 45 bytes. Complete bank-zero maps
match the previous builds: zero reservation growth in every category.

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

Completed: the original minimum-two-redraw guard rejected a valid single
bounding exposure message. An unprofiled replay passes all eleven exact
frames; the [diagnostic record](../../development/update-snapshot-us3-diagnostic.json)
records all delivered rectangles. A bounded geometry/coverage oracle now
accepts legal coalescing while rejecting missing, duplicate and unexpected
damage. The guest is unchanged, the old observer remains archived and the
new oracle accepts every recorded baseline exposure. Compare exposure repair
area and helper counts separately rather than attributing changed coalescing
to direct snapshot savings. The ABI probe now also checks the new field's
exact offset (127 checks in each mode).

The legacy 349-file manifest omits native GUI modules. The final audit adds
863 Git-recovered production inputs and freezes current sources; exactly eight
native/layout files differ. Observer changes are recorded separately.

The final capture passes all eleven exact frames, 505 fixture assertions,
67 measured operations and normal cleanup. Fragmented Counter tick caller CPU
falls 39.306 → 36.686 ms (6.7%); BEGIN falls 9.590 → 6.938 ms with unchanged
local admission, meeting the 5% target. The controlled target passes at 19.0%.
Changed-layout overhead is 2.6%; other controls have no unexplained material
regression. Exposure repair area differs with legal coalescing and is not a
direct per-rectangle speedup. The final host suite passes 668 tests, four skipped.
Complete bank-zero maps match, with zero additional reservations in all shared
categories. The development gate is complete; full qualification remains open.

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
