# Exec816 contributor instructions

## Ownership

- This repository owns Exec kernel policy, the AltirraOS platform adapter,
  startup/loading, platform ABI definitions and system integration tests.
- actionc owns language semantics, compiler IR, code generation, the native
  compiler ABI and reusable compiler runtime primitives.
- actionc-vm owns CPU/machine emulation and emulator correctness tests.
- Fix compiler defects in actionc with focused regressions. Do not work around
  them with special cases for individual Exec routines.

## Architecture

- Use classic Amiga Exec as the default model for Tasks, messages, signals,
  device I/O and driver responsibilities. Consider QNX and BeOS as references
  for specific improvements; document the chosen semantics and the reason for
  departing from the Amiga model.
- Keep device-specific queue, active-request, cancellation and lifecycle policy
  in the driver, using general public kernel primitives for coordination.
- Treat correct API use and live application-owned pointers/handles as caller
  responsibilities on this single-user system without memory protection. Keep
  validation minimal: establish resources at creation/open, report normal
  operational errors, and preserve synchronization and state transitions.
  Do not revalidate the same request through wrappers, dispatch and drivers.
  Stack/domain guards and IRQ/NMI coordination are separate requirements.
- If a new combined kernel operation is justified, define a reusable public
  ABI operation usable by other drivers and ordinary Tasks subject to resource
  ownership rules. Do not add driver-specific private kernel services solely
  to reduce gateway crossings. Internal helpers implementing public operations
  remain implementation details.
- Evaluate these choices against the 65816 memory budget, IRQ/NMI safety and
  measured cost. Existing private driver protocols require explicit migration;
  this direction does not claim that they have already been replaced.

## Initial platform

- Read `docs/reference/platform.md` before changing platform code.
- Conserve bank-zero memory according to the
  [bank-zero memory budget](docs/reference/platform.md#bank-zero-memory-budget).
  Justify new or enlarged bank-zero reservations. For implementation slices,
  report the change in reserved bank-zero bytes (including zero change),
  counting guards, alignment and unused reserved capacity, with per-task costs
  identified separately.
- Target the dedicated AltirraOS 65816 build first. Pin the actual ROM and
  emulator configuration before making executable compatibility claims.
- Use `COP #$50` for the Exec gateway. Preserve the OS's `$00` service and
  leave WDC-reserved `$80-$FF` signatures unused by Exec.
- The current compiler bridge uses `$00` for yielding and non-switching NMI.
  Do not install it unchanged into the AltirraOS environment.
- VBI-driven preemption remains unqualified until the platform tests pass.
  IRQ masking does not mask NMI. Protect task switching and shared state with
  a documented protocol that covers asynchronous entry and stack transitions.
- Preserve the complete native context and each task's direct-page ownership.
  Do not assume an OS service or interrupt handler is reentrant.

## Implementation and validation

- Always include OF816 in demo builds and refreshes. Use `tools/build_demo.py`,
  which packages the boot XEX, matching system disk and pinned AltirraOS ROM
  with upstream license notices in the demo's `of816/` directory.
  Keep the five-second autoboot into the standard shell/prime demo.
- Distribute the generated `exec816-demo.zip`, containing only boot files,
  a short user guide, license notices and checksums. Keep build intermediates,
  manifests and test output in the development directory.
- Follow the [code style guide](docs/contributing/style.md) for handwritten Action!
  code. Apply it to new code and routines being changed; keep unrelated
  formatting separate and edit generated code through its generator.
- Maintain one current Task API and implementation. During active development,
  update callers and tests together; do not retain compatibility profiles or
  obsolete implementations. Rebuild programs when the ABI changes. Git keeps
  historical source and qualification records.
- Work in small executable slices following `docs/roadmap.md`.
- Keep public interfaces and platform contracts separate from implementation
  notes. Record unsupported behavior explicitly. Follow the
  [documentation organization](docs/contributing/README.md#maintaining-the-documentation)
  and update the relevant index when adding or moving a page.
- Keep ABI constants machine-readable and generate shared language/assembly
  definitions when the gateway is implemented.
- Use compiler and ABI inputs from the revision recorded in
  `toolchain/actionc.json`; document and record local overrides.
- Test changed behavior through emitted machine code. Use optimized builds for
  routine functional, failure, integration and performance checks. Cover raw and
  optimized NIR with small focused tests when validating compiler-facing behavior
  such as ABI layouts, language bridges or code generation; also use raw builds
  to diagnose suspected compiler/optimizer defects. Do not duplicate full system
  scenarios in raw mode by default. Preserve stack/domain guards, register
  restoration, OS coexistence and bounded completion where relevant.
- Follow the [two-tier testing policy](docs/contributing/testing.md). Development checks are
  the default for ordinary changes: host checks and focused emitted-code tests
  for the affected behavior. Documentation-only edits require content and link
  checks. Full qualification matrices run for releases, explicit qualification
  claims or an explicit request, not automatically after every edit or commit.
  Use targeted deeper cases earlier when interrupt, scheduling, transport or
  ownership changes require them. Report the tier and actual execution scope;
  development checks alone do not qualify the hosted system.
- Normalize host text line endings before newline-sensitive fixture parsing.
  Preserve exact bytes for binaries and ATASCII fixtures.
- Do not claim the hosted system is qualified solely because compiler tests pass.
