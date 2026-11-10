# END_UPDATE cache completion implementation plan

[Design addendum](update-snapshot-reuse-design.md#end_update-cache-completion-addendum) ·
[GEM plans](README.md) · [Completed snapshot work](../../history/update-snapshot-reuse.md) ·
[UPDATE contract](../../reference/aes.md) · [Testing policy](../../contributing/testing.md)

Status: proposed; implementation has not started. Runtime baseline `34f1a1a1`
contains geometry reuse and the corrected exposure-coverage observer.
Execute EC0–EC2 in order and commit each slice after its selected checks pass.
Keep the completed US0–US3 evidence and its original hashes intact.

## Scope and gates

Add an identity-only miss return at the start of `DESKCACHE.EndChange`.
No slot match skips only cache-specific preparation. Any identity match keeps
the current body and completion of all matching slots, independent of validity,
pinning, revision or dimensions. Do not substitute the pixel-reuse lookup.

Keep `AESWINDOWSTATE.EndUpdate`, the common local/RPC policy, journals,
pending repaint obligations, final epoch/readiness publication and wake behavior
unchanged. Preserve ordinary/scoped and nested updates, hidden changes,
ownership and all public layouts/compiler pins. Add no persistent state,
allocation, region storage, Task, kernel operation or new synchronization.

The measured baseline has 36.686 ms caller CPU per fragmented Counter tick,
11.302 ms in END and 2.375 ms in cache completion. The acceptance gate is a
measured net reduction in the controlled no-slot END workload and a lower
matched Counter tick median, with local/RPC and caller/presenter work accounted
for. Investigate any match-path or control regression above 5% before accepting
the change; small differences require enough samples to distinguish phase
variation. Report actual savings without treating all 2.375 ms as removable.

## EC0 Establish slot-completion regressions and freeze the baseline

Extend the focused native metadata fixture, or a small companion fixture,
to execute the actual `DESKCACHE.EndChange` on live window/layer records.
Keep setup and observation outside timed calls. Include both direct helper
calls and integration through the ordinary END policy.

Cover no matching identity with empty slots and with unrelated valid/invalid
or pinned slots. Compare complete slot and repair records plus relevant
window/layer state before and after: a miss must be a shared-state no-op.

Cover a match in either slot and in both slots. Preserve the existing
`LAYERCACHE` contract for valid, temporarily invalid, pinned and zero-revision
matches; held/ready/no-repair states; empty/nonempty changes; odd horizontal
edges; partial completion and failure. Construct states through real lifecycle
operations where possible, rather than expecting a new result for invented
states. Include eviction/replacement between updates, a hidden/iconified owner,
ordinary/scoped and nested END, and deletion/retirement. Never evict a pinned
slot illegally to create a test case.

Reuse the existing cache/pixel and lock fixtures for retained pixels, local/RPC
combinations, scheduled peers and inherited Forbid behavior. Add only missing
coverage. Observe state/geometry independently of the proposed early guard.

Freeze the before image, compiler/runtime/ROM/emulator settings, observer,
source inventory and helper counts. Use the US3 production inventory as a
starting point; its older 349-file predecessor omits native GUI sources.
Separate controlled misses from matches and record how many slots actually
match in the application workload. Preserve the guest workload and exposure
coverage oracle when comparing the recorded US3 corpus.

Acceptance: optimized emitted checks pass on the unmodified helper, with
bounded completion, guards and restored heap/ownership. Record the exact
executed cases, baseline timings and complete reservation maps.

Commit: focused fixtures/observations and EC0 baseline evidence.

## EC1 Add the miss return and verify equivalence

Place the guard before layer lookup, client bounds/readiness work and local
rectangle conversion. Prefer a small direct check of the existing slot
identities followed by the unchanged completion body. Preserve its all-match
loop; do not assume identity uniqueness or skip invalid/pinned matches.

Run EC0 again. Add passive helper observations to demonstrate that misses
skip the cache helper's preparation, while matches keep the required work.
At the full END boundary, prove journals, repaint obligations, candidate hints
and final readiness still execute for windows without cache slots. Observe
the helper and its caller separately so skipped work is attributed correctly.

Run the focused optimized metadata/cache/lock checks and host suite. Use raw
probes only if an actual compiler/ABI concern arises; no layout change is
planned. Inspect emitted code/frame changes and compare complete bank-zero
maps. Resolve any compiler defect in its owning repository.

Acceptance: identical visible pixels, slot/repair results, paint obligations,
epoch/readiness and retirement for the selected cases; no shared-state writes
introduced on a miss. Record miss/match cost separately.

Commit: the bounded helper change and EC1 development evidence.

## EC2 Compare the matched workload and close the development gate

Repeat the controlled cohorts and the unchanged guest AES corpus using the
same pins and exposure oracle. Preserve the ordinary eight measured calls
after two warmups and the three exposure samples. Compare all eleven frame
digests, slot/repair observations, drawing-unit counts, source differences and
complete resource maps against EC0 and the US3 record.

Report public END, cache helper, total caller and presenter CPU, elapsed time
and local/RPC paths. Attribute phase shifts separately. Record delivered
exposure rectangles, repair area and number of UPDATE scopes; valid coalescing
can change their workload, so its timing is not a per-rectangle speedup.

Acceptance: the net miss-path and matched Counter gates pass, matching-cache
behavior is preserved, and material control regressions are explained or
resolved. Record code, data and stack costs, ownership/heap restoration and
guard results. Archive raw captures under `build/`, add a development evidence
record and history entry, and update the plan and indexes.

Commit: EC2 matched results and reconciled completion status. These checks do
not qualify the whole hosted system or physical hardware.

## Resource and execution budget

This documentation change reserves **0 fixed/root/kernel bank-zero bytes,
0 bytes per public Task and 0 idle bytes**, including guards, alignment and
unused capacity. Implementation targets the same zero growth, with no added
upper-RAM record storage or allocation. Report actual emitted local-frame and
observed stack use separately from reservations.

Use the development testing tier. Full qualification, disjoint redraw-region
changes, renderer batching, compiler migration and a demo refresh are outside
these slices. Any later refresh uses `tools/build_demo.py` with OF816 and the
existing packaging contract.
