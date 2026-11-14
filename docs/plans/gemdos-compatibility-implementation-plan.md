# GEMDOS compatibility implementation plan

[Plan index](README.md) · [Design](gemdos-compatibility-design.md)

Implement the design in four executable slices, committing each after its
development checks. The source library reuses the common C runtime; native
open-handle metadata belongs in public DOS. The complete MGVIEW GUI and SDX
FILELENG migration remain separate application work.

## GC1: shared wrappers and QED migration

- Define machine-readable calls, constants and the native XATTR record. Generate
  the public C header and a target-emitted layout probe.
- Add opt-in APP builder selection for `c/compat/gemdos`. Extract QED's generic
  file/allocation adapters, add runtime-aware Pterm/Pterm0, and keep QED's
  editor/save diagnostics private. Migrate every Malloc declaration together.
- Publish one native-to-GEMDOS error translator, preserving full IoErr and the
  existing runtime descriptor, pending-transfer and consumed-close rules.
- Check header generation, raw/optimized C layout/returns, optimized allocation,
  LONG transfers and file cleanup. Rebuild QED against the shared sources.

## GC2: native open-handle metadata

- Add public `ExamineFH` and generated bindings/imports. Reuse existing owned
  handle requests and filesystem metadata/measurement paths; preserve cursor
  state on success, failure and cancellation. Reject unsupported streams.
- Rebuild providers and callers with the current ABI. Add a private common CRT
  descriptor helper without exposing the native handle or consuming pending I/O.
- Execute focused optimized RAM, MyDOS and SDFS queries, including exact empty
  and nonempty lengths, shared positions, failures and resource retirement.
  Use small raw/optimized ABI coverage for the new call.

## GC3: Fcntl(FSTAT)

- Compose the common descriptor helper with temporary upper-memory FIB scratch.
  Publish a complete initialized XATTR only after exact regular-file metadata
  succeeds. Advertise size/type-only support and preserve the output on failure.
- Exercise valid/empty files, bad descriptors, unsupported commands/streams,
  scratch failure, pending transfer errors and unchanged cursor/output.

## GC4: consumer acceptance and current contract

- Execute an MGVIEW-style document loader and line-index model through the
  shared interfaces: ordinary, maximum-admitted and oversized inputs; CR/LF
  data, short reads, unwind, two Images and repeated execution.
- Retain focused QED file/save regressions. Check real disk bytes independently
  and record compiler, ROM/emulator inputs and emitted memory costs.
- Publish the supported source contract, index it, and update this plan and
  the roadmap with actual results. A demo refresh, if needed, uses build_demo.py
  with OF816 and the standard distribution checks.

## Validation and memory

Use the development tier: host suite, affected generators with `--check`,
focused emitted-code checks and selected consumer integration. Raw runs cover
small compiler/ABI boundaries; behavioral cases use optimized native builds.
Do not claim full hosted qualification from these results.

Each slice must add **0 reserved bank-zero bytes**, separately for fixed,
root/kernel, idle and each public Task, including guards, alignment and unused
capacity. Reuse existing descriptor/heap bookkeeping; charge selected APP code
and transient FIB storage to upper RAM. Record actual build and stack costs.

GC1 implemented, 2026-11-14. [Development evidence](../development/gemdos-compatibility-gc1.json)
records the raw C ABI probe, four optimized SDFS/RAM loaded executions, two
Images, repeated execution and heap/guard restoration. The optimized QED APP
rebuild uses the shared wrappers. Host checks: 715 tests, four historical skips.
The selected Process observations leave at least 480 bytes above the application
stack floor; they are samples, not a worst-case bound. No descriptor table,
allocation prefix or reserved bank-zero pool grows.

GC2 implemented. [Native metadata evidence](../development/gemdos-compatibility-gc2.json)
records four executions each for optimized SDFS/RAM, optimized MyDOS/RAM and a
small raw C call probe on the same optimized provider, plus cancellation during
measurement and before publication (277 assertions each). Output, cursor,
ownership, guards and OS restoration pass. DOS revision 16 / APP ABI 40 expose
ExamineFH to resident native Tasks and C APPs. The native COMMAND import and SDX
FILELENG migration are explicitly deferred; no native provider-table reservation
is enlarged.

GC3 implemented. [FSTAT evidence](../development/gemdos-compatibility-gc3.json)
records four optimized failure/ownership executions and four small raw C call
executions on the same optimized provider. Exact/empty size, initialized fields,
unsupported streams/commands, invalid descriptors, scratch failure, rejected
bounded/unknown/type metadata and pending transfer errors pass. The
[supported source contract](../reference/gemdos-compatibility.md) records the
280-byte temporary upper backing and 52-byte local result. Reserved bank-zero
cost remains zero in every category.

GC4 implemented. [Consumer evidence](../development/gemdos-compatibility-gc4.json)
records exact-read loader/model limits and unwind, independent ATR bytes and
the QED migration acceptance run. The final graphical check uses only Counter:
two private instances tick, close, restart and stop before entry (five collected
executions). Its APP is byte-identical to the rebuilt ABI 40 distribution.
The [delivery record](../history/gemdos-compatibility.md) records package checks,
the unchanged production bank-zero maps and the broader menu-observer limit.
All four implementation slices are complete at the development tier.

For routine follow-up changes, prefer the small GEMDOS probes and Counter.
Repeat QED scenarios when editor-specific behavior or file/save changes need
them; the initial migration does not make QED a mandatory test for every slice.
