# Direct-page partition implementation plan

Status: **D1–D3 implemented; development checks passed**. Scope spans
actionc and Exec816. See the [development record](../history/direct-page-partition.md).
Reserve the lower half of each execution domain's existing direct page for a
future foreign-language runtime. Move Action! scratch and domain metadata into
the upper half. Follow the [platform contract](../reference/platform.md),
[critical-section protocol](../history/kernel-critical-sections.md) and
[development testing policy](../contributing/testing.md).

No C compiler installation, C headers, wrappers, runtime integration or C demo
belongs to this plan. Use Action! and small assembly fixtures to verify the new
ownership boundary.

## Target contract

Keep D at the 256-byte-aligned base of the existing domain. Define one fixed
layout in actionc's machine-readable ABI, generating every consumer's constants.

| Offsets | Bytes | Owner and rule |
| --- | ---: | --- |
| `$00–$7F` | 128 | Caller/runtime workspace; Action! and Exec helpers preserve it. |
| `$80–$BF` | 64 | Action! compiler scratch; call-clobbered. |
| `$C0–$C2` | 3 | Execution-domain owner pointer. |
| `$C3` | 1 | Execution-domain kind. |
| `$C4–$C5` | 2 | Stack floor. |
| `$C6–$C7` | 2 | Stack ceiling. |
| `$C8–$FF` | 56 | Reserved; must remain zero. |

Pointer scratch aliases move from `$00/$03/$06` to `$80/$83/$86`. Existing
selector temporaries and scalar promotion slots move by the same `$80` within
the Action! area; their capacity and calling semantics stay unchanged.

Domain creation/reuse may clear the whole page before handing it to its new
owner. During that owner's lifetime, the lower half may contain arbitrary
nonzero data and must survive calls, waits and preemption. It is not another
reserved-zero region. No save/copy of that half is added to ordinary calls or
task switches. No cross-language calling convention is introduced yet.

Use this layout consistently for Action! task, bootstrap and kernel/interrupt
domains. The kernel keeps its separate DP. Temporary D values pointing into an
activation's stack, as used by COP decoding and fast services, retain their own
local offsets; they are not fixed compiler domains. ROM-owned DP is outside this
ABI. Do not shift D by `$80` to implement the partition.

This is a breaking native ABI change: publish `action65816.native.v2` and accept
only the current ABI in active consumers. Advance the compact command profile
to `actionc.o65.compact.v3`, descriptor `__a816_o65_compact_v3`, magic `A8C3`.
Retain the eight-byte descriptor header and four bytes per import. Update
ABI-bound entry/helper identities and checked provider contracts consistently;
recompute generated signatures. Native image container versions need not change
when their existing ABI field can identify the new layout. Old binaries must be
rejected before execution. Keep old-layout bytes only as rejection fixtures,
and preserve historical qualification records as historical evidence.

**Memory budget:** 0 additional fixed bank-zero bytes and 0 additional bytes per
task, including guards, alignment, pool stride and unused capacity. DP pages,
stacks and task capacity keep their current reservations. Record this delta for
each implementation slice.

## D1 — actionc: move the native ABI and emitted scratch

1. Replace the active native-v1 manifest with native-v2 and update
   `tools/generate_abi65816.py`, generated Rust/assembly constants and ABI docs.
   Add named offset/size constants for the lower workspace. Generate any
   additional language definitions needed by Exec816 from this same source.
2. Audit MIR65816 emission, allocation, clobber effects, copy scheduling and
   frame/home maps. Derive scratch locations from its base, including
   `emit/select.rs` temporaries and `emit/scalar.rs` promotion slots. Replace
   checks such as `offset + width <= DP_SCRATCH_SIZE` with a checked range test
   against the scratch start and end. Keep serialized DP offsets relative to D.
3. Update the native runtime bridge, startup, stack/fault paths and runtime
   helpers, including handwritten scratch such as the IRQ bridge's `$10` slot.
   Audit all DP accesses by ownership; do not mechanically add `$80` to stack
   displacements, absolute addresses or activation-local scratch.
4. Update native image validation, rich/compact o65 emission and inspection,
   ABI-tagged runtime bindings and checked library provider contracts together.
   Remove active old-ABI support; keep wire sizes unchanged.
5. Add focused raw/optimized emitted-code regressions. Seed the lower half with
   a nonzero pattern, exercise pointer operations, scalar DP promotion, calls,
   indirect returns, copy/fill and arithmetic helpers, then verify preservation,
   stack bounds, metadata and reserved-zero bytes. Include multiple aligned D
   bases and the existing targeted IRQ/NMI scratch-restoration coverage.

Validation: ABI generator check, affected MIR65816 unit/package tests and the
relevant native runtime targets. Reject old native/compact artifacts and check
exact compact metadata size. Stay within the 65816 backend; broaden only for
actual shared-contract changes or failures. Batch these checks after the
coherent slice, following actionc's current contributor instructions.

Exit: the compiler and its native harness run the new layout independently of
Exec816. Commit in actionc: `Move native 65816 scratch into the upper DP half`.

## D2 — Exec816: adopt the layout and prove preservation

1. Pin the tested D1 compiler revision in `toolchain/actionc.json`, including
   its native-v2 manifest/include paths. Update package ABI checks and all
   generated consumers together. A local compiler override during iteration
   must be recorded; the completed slice uses the committed pin.
2. Update task/domain construction and metadata validation. In particular,
   replace `taskpolicy.act`'s `$40/$44/$46` offsets with generated constants.
   Cover root, ordinary tasks, idle, kernel, bootstrap and reused domains.
3. Audit native helpers that operate on the caller's DP, including `heap.s`,
   `ports.s`, adapters, imports and resident library entry paths. Move fixed
   compiler-domain scratch to generated upper-half aliases. Preserve the
   activation-local layout of gateway/IRQ code and the existing NMI protocol.
4. Update `tools/native_program.py`, frame-map checks and fixtures to validate
   metadata and reserved bytes separately. Its current check of `$40–$FF` as a
   single metadata/zero block must be removed. Do not require the lower half
   to be zero after execution. Retain all outer guards and stride-padding checks.
5. Update the o65 loader, `abi/program.json`, generated providers, fixture
   builders and documentation for the new native/compact ABI. Reject old
   commands before calling them, with existing error/cleanup behavior.
6. Add a bounded Action!/assembly integration fixture with distinct lower-half
   patterns in two tasks. Exercise caller-context allocation/clearing and
   resident routines, full COP dispatch, fast Forbid/Permit/GetMsg paths,
   message/signal blocking and VBI preemption. Verify both patterns, D/register
   restoration, metadata, guards and OS restoration. Exercise task removal and
   slot reuse separately to check initialization for a new owner.

Validation: affected generators, Exec host tests, the new fixture in raw and
optimized modes, and selected existing interrupt-transition/stack-fault cases.
Use a targeted IRQ/NMI case that interrupts a live kernel activation; it must
not overwrite either task or kernel scratch. Reuse existing checkpoint support.
No full timing, baud-rate, filesystem or capacity matrix is required here.

Exit: Exec816 runs entirely on native-v2 and preserves the lower workspace
without new copying or reservations. Commit in Exec816:
`Adopt the partitioned native direct-page ABI`.

## D3 — Exec816: rebuild programs and close the migration

1. Rebuild the resident kernel/libraries, standalone examples and shipped disk
   commands with the same pin. Produce a play image containing only rebuilt
   programs; do not reuse old native images, provider binaries or o65 commands.
2. Run one focused raw/optimized loaded-command case that crosses into COMMAND
   and CSTRING while preserving a seeded lower-half pattern. Confirm that an
   old compact-v2 command is rejected without entering it or leaking ownership.
   Reuse the D2 loader rejection result when its inputs and coverage match.
3. Smoke the optimized play image through shell startup, a loaded HELLO and a
   bounded CAT/WC operation. Record compiler/ROM/emulator/configuration hashes,
   rebuilt artifact hashes, selected test scope and zero bank-zero delta.
4. Update current contracts and the roadmap. Put results in a development
   record and explicitly leave release qualification pending. Do not rewrite
   historical results or claim compatibility with either C compiler yet.

Reuse matching build outputs and passing checks; rerun only when inputs change
or an unresolved concern requires it. Commit the integration record and current
documentation in Exec816: `Record the native DP migration and rebuilt image`.

Completion means a single current ABI across both repositories, an unchanged
256-byte domain reservation, preserved lower-half contents during execution,
and a coherent rebuilt system. C integration can start later against this
documented workspace contract.
