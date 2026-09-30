# Interactive console and program execution plans

Status: console implementation through W3 complete, 2026-09-24; full window
release qualification remains pending. See its
[implementation record](../history/console-interaction-implementation.md) for completed
slices and qualification. Process P1–P3 is implemented with
[development checks](../development/process-p23.json); its general release matrix
remains pending. Loading L1–L4 is implemented, with the scoped
[integrated loader qualification](../history/o65-loading-implementation.md#l4-integrated-lifetime-and-transport-qualification)
passing on 2026-09-25. Baseline: `407df9d`, including the
[scrolling optimization](../history/console-scrolling.md).

The work is split into three implementation plans. Each owns its slice details,
acceptance checks, integration points and upper-memory budgets.

| Plan | Scope | Slices |
| --- | --- | --- |
| [Console interaction](console-interaction-implementation-plan.md) | SIO evidence maintenance, cooked CON:, foreground cancellation and windows | S0, C1–C3, B1–B5, W1–W3 |
| [Process lifetime](process-lifetime-implementation-plan.md) | Resident child execution, inheritance, cleanup and retirement | P1–P3 |
| [o65 loading and external commands](o65-loading-implementation-plan.md) | Native validation/relocation, providers, disk loading and shell integration | L1–L4 |

Console windows W1–W3 are implemented and development-tested using current Task fixtures.
Process P1–P3 depends on B5 and feeds loading L1–L4; it can start before window
completion. P2 development checks cover Process foreground handoff. Design
and compiler capability inspection can happen earlier.
Each slice must work, clean up failures and pass the relevant development checks
before dependent implementation starts. Follow the [two-tier testing policy](../contributing/testing.md):
ordinary commits use focused development checks; complete acceptance matrices
gate release qualification. Record pending qualification explicitly and do not
treat a development pass as satisfaction of a timing/platform gate. Slice IDs
identify dependencies across the three plans.

## Baseline, ownership and delivery rules

- Use [toolchain/actionc.json](../../toolchain/actionc.json), currently
  `47cd55b2dac510922949832332b7a2c3220885be`, ABI
  `action65816.native.v1`, JSON image v3. The clean `build/actionc` checkout
  also contains the experimental o65 writer and reference relocator. Record
  compiler overrides and qualify a new pin before relying on changed behavior.
  Qualification of this pin is deferred; existing W1–W3 development records
  retain their original `2d73c03` compiler input.
- Use the [paced shell pin](../../toolchain/altirra-shell-paced.json), its exact
  AltirraOS ROM, PAL 8× configuration, SIO patch/burst settings and immutable
  [MyDOS fixtures](../../tests/fixtures/mydos/manifest.json). Record actual binary,
  source, image, map, media and observer hashes. Compiler VM qualification does
  not qualify the hosted loader or devices.
- Read and preserve the [platform contract](../reference/platform.md),
  [critical-section protocol](../history/kernel-critical-sections.md),
  [Task contract](../reference/tasks.md) and [device contract](../reference/device-io.md).
  IRQ/NMI capture stays bounded; DOS work, allocation, parsing and rendering
  stay in task context. IRQ masking does not exclude NMI.
- Exec816 owns these services, loading, task admission and hosted integration.
  actionc owns the native ABI, o65 producer/profile, compiler correctness and
  reusable compiler runtime primitives. actionc-vm owns CPU emulation. Fix
  defects in their owning repositories, with focused regressions.
- Maintain one current Task/DOS implementation. Generate shared interfaces
  from machine-readable inputs and rebuild callers when layouts change.
- Keep public contracts separate from implementation notes; each plan names
  its proposed design documents. Settle exact layouts, imports and error numbers
  in the owning slice before publishing interfaces. Do not add success stubs.
- Use a separate commit and artifact directory per slice. Record development
  checks and pending qualification in the implementation record; publish
  qualification JSON when the deeper gates pass. Update the owning plan, the
  roadmap and relevant public contracts together. Historical records retain
  their measured inputs and scope.

## Memory gates

Public constants/layouts belong in `abi/dos.json`, `abi/console.json` and any
new Process/program schema, with generated Action!/assembly definitions as
needed. Ordinary library helpers use ordinary calls; COP #$50 remains the Exec
gateway, preserving AltirraOS #$00 and reserved signatures.

The eight-slot baseline reserves 57,232 bank-zero bytes during loading and
61,536 at runtime including the OS. **Target delta for every slice: zero fixed
and zero per-Task reserved bank-zero bytes.** Retain guards, alignment, unused
capacity and the protected 256-byte interrupt reserves in the accounting.
The shell, console, filesystem and SIO workers use four public slots; one
foreground child uses a fifth. Loading runs in the caller. Cooked sessions,
break delivery and windows add no workers. Eight-task acceptance must count
simultaneously live Tasks, including services.

Each plan records its proposed upper-memory budgets; they are not allocated or
qualified layouts. Any overrun needs an explicit map and tradeoff before dependent
implementation. Do not enlarge
stacks, consume interrupt reserves, reduce task capacity, or double-claim heap
banks to pass tests. Frame maps are local costs, not bounds on arbitrary call
depth. Measure complete blocking/cleanup paths after each API layer is added.

## Common acceptance and completion record

Every runtime-behavior slice executes emitted raw and optimized code with
bounded host and guest completion limits. Cover full context/DP restoration,
stack/domain guards, exact request identities, failure cleanup, OS coexistence
and allocation/ownership recovery where relevant. Use deterministic interruption
at publication, handoff, completion and retirement boundaries. Preserve existing
serial byte/alarm/Forbid limits and observer-free replay for timing claims.

Keep functional bank-3 coverage distinct from measured bank-1 timing, and
128-byte fixture reads distinct from complete 70,003-byte 256-media reads.
Separate keyboard capture, break delivery, command completion and actual screen
visibility in records. Do not infer any of them solely from the same signal bit.

The final implementation record must link every completed slice, its commit,
commands, limits, source/compiler/ROM/emulator/media hashes, native results,
negative controls, memory map and unsupported behavior. The three plans deliver
cooked input, safe cooperative foreground cancellation, owned child
execution of disk-loaded o65 programs and independently usable tiled consoles.
Filesystem writes, pipelines/scripts/background shell jobs, general forced
process termination, twelve/sixteen-task capacity and physical-hardware
qualification remain separate milestones.
