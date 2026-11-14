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

Status: planned, 2026-11-14. Implementation results will be recorded per slice.
