# Compiler issues encountered by Exec816

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

Audit date: 2026-09-20; compiler migration: 2026-09-22. This records compiler
defects separately from supported language rules, backend limitations and Exec's
own memory budget. Fixes belong
in actionc; Exec routines must not compensate for incorrect generated code.

The [compiler pin](../../toolchain/actionc.json) is now `ae1f555`, with unchanged
native ABI v1 and image format v3. All three confirmed correctness defects below
remain fixed. The [migration qualification](compiler-ae1f555-qualification.md)
found no new compiler defect or need for an Exec-specific workaround.

## Correctness defects

| Issue | Effect | Fix and regression evidence |
| --- | --- | --- |
| Absolute-array address lost its native pointer type | Native indexed access could enter NIR with an integer base instead of a target-width address. | `f088ab9`: preserve the pointer type and reject integer native index bases. [Memory record](../qualification/compiler-memory-fix.json); actionc `tests/nir_absolute_arrays.rs` and native `memory` executions. |
| Named record-pointer conversion misparsed | An explicit conversion such as `Node POINTER(address)` did not produce the intended typed cast. | `e726698`: parse and validate the destination type. [Lists record](../qualification/compiler-lists-fix.json); actionc `tests/named_pointer_casts.rs` and bank-crossing pointer execution. |
| Scalar comma group followed by a contextual/named type misparsed | Valid fields or arguments such as `CARD a,b LONGCARD c` were rejected or grouped incorrectly. | `c2268b7`: disambiguate the comma from the following declaration group. [Block-I/O correction](block-io-dos-implementation.md#compiler-correction); parser and native CLI checks cover LF/CRLF and raw/optimized emission. |

### Integration audit of the parser correction

At the original audit, local actionc main revision `ea01059` contained the
first two fixes but not the comma-group correction. Exec816 then obtained that
correction from the checked [Git bundle](../../toolchain/actionc-comma-groups.bundle),
so its DOS qualification already included it. The current pin contains the
correction and no longer needs the bundle.

The native CLI regression was added to a clean worktree of `ea01059` and failed
with `expected parameter declaration`. Commit `90bd73e` restores the correction
to local actionc main, together with an additional native execution regression:
mixed CARD/LONGCARD/BYTE/LONGINT arguments are stored into a record crossing
`$12:FFFF`, and checked against independently specified bytes. It covers both
optimization modes, LF/CRLF source, IRQ enabled/disabled entry, canaries and
native context guards. Pre-existing compiler worktree changes were preserved;
that audit did not push the local commit.

## Backend limitations that shaped the implementation

These are explicit limits or optimization opportunities, not established
miscompilations. Source adaptations remain useful until the corresponding
compiler capability is implemented and qualified.

| Limitation | Exec adaptation | Compiler-side follow-up |
| --- | --- | --- |
| At most 254 bytes in an even native fixed frame; stack-relative accesses must fit offsets 1–255, including incoming arguments and call setup. | Split large predicates, ABI probes and policy routines. | Slot reuse reduces pressure within this limit. Larger frames require a different addressing strategy and checked ABI/image support; increasing the constant alone is incorrect. |
| The old emitter allocated distinct stack slots for MIR temporaries and edge copies. | Smaller helpers and explicit state reduced oversized frames and deeply nested waits. | Addressed by qualified `ae1f555`: CFG liveness-based slot reuse, edge-copy improvements and constrained pointer/scalar direct-page homes. The 254-byte frame limit and whole-call-chain budget still apply. |
| Bare absolute declarations use a shared 16-bit address resolver. The native driver rejects wide numeric bare initializers. | Access upper RAM through explicit 24-bit pointers instead of mapped globals. | Generalize address resolution through semantic analysis and NIR for the selected target, retaining legacy declaration semantics and boundary diagnostics. |
| Native multiply, divide and remainder are explicitly unsupported. | Use shifts for power-of-two geometry, typed array strides a bounded binary algorithm for SIO timeout conversion, and decimal place subtraction in the shell. | Implement generic arithmetic lowering/runtime primitives in actionc, with signedness, width and boundary execution tests; do not add Exec-specific compiler cases. |

The frame limit is a restriction of the current compiler strategy, not a claim
that the 65816 cannot address larger stack frames. Splitting procedures also
does not automatically reduce total stack use: callers remain live while
callees execute. Returning between filesystem steps keeps parsing frames off
the blocking transport call chain.

## Language rules worth distinguishing from bugs

- A bare declaration initializer can specify an absolute storage address.
  `LONGINT count=4` is not the spelling for an ordinary variable initialized to
  four; use bracketed initialized data or assign in executable code.
- Names are case-insensitive. A local name can collide with a type or routine
  name even when their capitalization differs.
- Legacy literal typing and explicit conversions matter. Use an explicitly
  unsigned representation for bounds such as `LONGCARD($ffff)`; do not assume
  every decimal literal between 32768 and 65535 is already a positive 32-bit
  quantity. Pointer/integer conversions use native `ADDRESS`/`SIZE` types.
- An initialized dynamic array has a descriptor and backing storage. Passing
  its value and taking the address of its descriptor are different operations.

## Stack pressure is also a system constraint

The earlier [DOS qualification](block-io-dos-implementation.md#observed-bank-1-results)
measured raw client use of 748 bytes in a 1,024-byte stack, leaving 20 bytes
above the protected 256-byte interrupt reserve. The largest raw filesystem
worker observation was 744 bytes, leaving 24 bytes. Compiler-generated frame
guards correctly stopped earlier, deeper call chains; those faults were not
evidence of incorrect code generation.

On the same integrated console/DOS fixture, the migration reduces observed
reader stack use from 760 to 242 bytes raw and 610 to 218 bytes optimized.
The complete fixed and per-Task bank-zero reservations are unchanged; eight
Tasks, guards and the 256-byte interrupt reserve remain. These measurements
do not establish an arbitrary whole-task stack bound or qualify more Tasks.

## Validation and compiler migration boundary

The [audit qualification record](../qualification/compiler-issue-audit.json) binds
the regression results to source, log and native-execution manifest hashes:

- Existing Exec pin: five focused pointer/index/parser checks pass.
- Current compiler fix: all 3,263 compiler tests pass, with 24 ignored tests;
  the earlier TN catalog/sample failures do not recur.
- NIR snapshots are unchanged and all 51 NIR sweep fixtures pass.
- Ten native execution tests pass, including the new eight-case mixed-width
  regression and the existing memory/ABI interop cases. Both raw and optimized
  emitted code execute on the independent VM; this is a targeted debug-host run.

The first broad build exhausted disk space while linking. Clearing only the
audit's generated compiler cache and disabling host debug symbols allowed the
complete checks to pass. Test acceptance and guest execution modes were unchanged.

The original audit did not change Exec816's compiler pin or replay the hosted
DOS/SIO matrix. The subsequent [ae1f555 qualification](compiler-ae1f555-qualification.md)
adds image-v3 packaging checks and reruns native execution plus 19 hosted groups
before advancing the pin. It also records the pre-existing host-test failure
caused by the historical SIO source-hash mismatch; no old qualification evidence
is rewritten.
