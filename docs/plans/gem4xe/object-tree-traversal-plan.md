# Incremental object tree traversal implementation plan

[GEM plans](README.md) · [Implementation plans](../README.md) ·
[Captured baseline](../../development/magic-aes-baseline.json) ·
[AES application contract](../../reference/aes.md)

Status: ready for implementation. Complete the correctness, implementation and
matched-measurement slices below before marking the work complete.

Replace repeated absolute-coordinate lookup in the application `objc_draw`
walker with incremental coordinates. Ordinary GEM application source, object
records, drawing order, clipping and update ownership retain their current
behavior. The change belongs in `c/calypsi/aes-objects.c`; the extracted donor
code and the Exec kernel remain separate inputs.

## Starting evidence

Baseline commit `e44a7384` records optimized Calypsi 5.18 and the pinned
PAL/8x 65816/VBXE configuration. The measured source includes conventional
Counter redraws from `64d2719a`. Use its source hashes and execution artifacts
when comparing results; do not rewrite that historical record.

| Object workload | Median caller CPU | Inclusive coordinate lookup CPU |
| --- | ---: | ---: |
| Five objects | 44.524 ms | 0.802 ms |
| 33 objects with 32 siblings | 123.997 ms | 19.589 ms |
| Nine nested objects | 171.267 ms | 3.357 ms |

`ExecAESDraw` currently calls the donor `ob_offset` for each drawable object.
Finding a parent can walk later siblings, so a wide tree repeats substantial
work. MagiC's [coordinate-carrying walker][magic-walker] and the already
extracted GEM4XE `everyobj` demonstrate the applicable traversal technique.
Keep Exec's existing synchronous strip callbacks and error publication.

The lookup share is a cost budget, not an achieved speedup. The wide workload
is the principal performance gate; small and nested workloads also expose the
cost of maintaining coordinates and must be measured.

## Algorithm and invariants

- Resolve the start object's absolute coordinates once for a non-root start.
  A root start can read its own coordinates directly. Empty draws and hidden
  starting subtrees do not require an ancestor walk.
- Keep current X/Y as caller-local scalars. Before descending, save the parent's
  absolute X/Y at the current relative depth. On ascent restore them; on a
  sibling transition combine that parent's origin with the sibling's relative
  coordinates. Use the existing head, tail and next relationships.
- Bound saved parent origins by `MAX_DEPTH`: eight X/Y pairs require 32 bytes
  of private stack storage. Report actual emitted frame growth, including
  compiler temporaries, rather than assuming this is the complete stack delta.
- Depth remains relative to the requested start. Preserve zero and negative
  depth, the existing upper clamp, non-root starts with ancestors, and stopping
  at the requested subtree boundary. Valid trees and live pointers remain the
  caller's responsibility.
- Preserve preorder, `HIDETREE` suppression and descendants outside their
  parent's rectangle. A clipped parent does not justify skipping its children.
  Read object positions for the current call; do not retain a geometry cache
  across calls or change application-owned objects.
- Keep border expansion, declared damage, hidden-window model changes,
  visibility intersection, strip capacities, callback ownership, display grants
  and failure cleanup unchanged. Calls may be preempted; no walker state is
  shared between Tasks and no new `Forbid` region is introduced.
- Keep public `objc_offset` and donor extraction unchanged. No ABI generation,
  compiler migration, kernel operation or renderer batching change is required.

## Executable slices

### OT1 Establish traversal regression coverage

Extend the existing emitted AES object fixture and its host pixel oracle with
focused trees and draw requests. Keep case setup outside measured workloads.
Check root and non-root starts, a single leaf, broad siblings, cousin/ascent
transitions, the depth limit, depth zero/negative/above the limit, hidden roots
and descendants, and children extending outside clipped parents. Include a
non-root start whose ancestors lie outside the requested relative depth.

Use the pinned unmodified donor object model for visible pixels and an
independent parent-based interpretation where the requested-subtree boundary
needs additional assertions. Cover nonzero/negative origins, partial/empty
damage, two disjoint visible clips and an entirely covered owner. Preserve the
existing TEDINFO, editable text, icon, border and bounded-strip checks.

Exercise two independently scheduled callers with different trees and origins,
then verify final pixels and normal retirement. Add a bounded test-only borrow
failure after traversal has descended; verify busy/failure state, matching END
and a subsequent successful draw. These fixtures must not add production
instrumentation or mutate the archived performance workload.

Acceptance: focused optimized emitted-code checks pass on the original walker
before replacement, with independent expected geometry, bounded completion,
guard checks and restored ownership. Record any pre-existing donor difference
explicitly instead of silently changing the expected traversal.

### OT2 Carry coordinates in the production walker

Implement the algorithm in `ExecAESDraw` and run OT1 again. Keep the existing
paint loop and common failure/changed-region exit together. Inspect emitted
code and measure the local frame. Root-start traversal should make no
`ob_offset` calls; a drawable non-root start should make at most one per draw.

Acceptance: identical eligible-object order, positions, pixels, damage and
drawing-unit bounds. No new allocation or persistent state. All existing
display/update/epoch and pointer-lifetime contracts remain authoritative.

### OT3 Compare the matched optimized baseline

Run `tools/measure_magic_aes.py` with the same workload, toolchain, ROM,
emulator and machine settings. Preserve eight measured calls after two warmups
for ordinary cases and three exposure samples. Compare all eleven frame
digests, display-admission/submission counts, source differences, code size,
stack observations and complete bank-zero reservation maps.

The wide-tree caller CPU must improve, with a target of roughly ten percent
or better. Report actual small/nested results and investigate a material
regression before accepting the change. Counter, exposure, move and timer rows
are control workloads; timing changes there require attribution rather than
being counted as traversal gains. Small samples do not establish tail latency.

Write a new development evidence record and update this plan and its indexes
with the completed scope and measurements. Keep raw captures and intermediates
in `build/`. Commit the implementation and evidence after development checks
pass; retain the original baseline record and its hashes.

## Validation and resource budget

Use the development tier: host suite, the focused optimized object fixture and
the matched optimized baseline. Run a small raw/optimized reproducer if emitted
behavior indicates a compiler defect; unchanged public layouts do not require
duplicating full GUI scenarios in raw mode. Compiler defects belong in their
own compiler repository with focused evidence.

Target reserved bank-zero growth is **0 fixed/root/kernel bytes, 0 bytes per
public Task and 0 idle bytes**, including guards, alignment and unused reserved
capacity. Parent-origin arrays use the current caller's stack; existing
reservations must accommodate their measured cost. Report code-size changes
and observed stack headroom without treating watermarks as worst-case bounds.

The scope is application object traversal. A demo refresh, full hosted
qualification, hardware testing, UPDATE optimization and clipping-cache work
are separate activities. Any later demo refresh follows `tools/build_demo.py`
and the OF816 packaging contract.

[magic-walker]: https://github.com/th-otto/MagicMac/blob/90ae7dcc28c9dc45c3d1986a796ba7f71c2188d8/kernel/aes/aesobj.s#L7961
