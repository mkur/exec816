# FastBasic floating point implementation plan

Status: **FB6a–FB6e functional delivery implemented**, 20 October 2026. See the
[execution record](../history/fastbasic-floating-point.md) for actual checks,
memory/timing costs, design adjustments and remaining qualification gates.

[Design](fastbasic-floating-point-design.md) ·
[Migration plan](fastbasic-6502-migration-plan.md) ·
[Current target contract](../reference/fastbasic.md) ·
[Testing policy](../contributing/testing.md) · [Plan index](README.md)

Deliver the full floating-point language runtime and on-machine `FBC.COM`
compiler described in the design. Keep `FBCI.COM` as the smaller integer
compiler on the same current platform ABI. Completion includes EDX editing,
compilation on Exec, independent execution of the saved program, and tested
text and graphical demo packages. A host-only cross-compiler or arithmetic
probe completes an intermediate slice, not FB6.

```text
EDX CALC.BAS
FBC CALC.BAS CALC.COM
CALC
```

The slices below retain the implementation sequence and suggested commit
boundaries. Development evidence does not qualify the general hosted platform.

## Scope and invariants

- Retain the pinned FastBasic 4.7 and mini65 inputs from
  [upstream.json](../../ports/fastbasic/upstream.json), and the native compiler
  from [actionc.json](../../toolchain/actionc.json). Record any local override.
- Adapt the pinned mini65 Altirra math source for ca65 and link it into each FP
  runtime. All numeric registers, stacks and scratch belong to the guest.
  Preserve the six-byte Atari representation and donor language semantics.
- Use the existing Process/Image lifetime, guest slots, context/IRQ/NMI
  transition protocol and native files/console. Add no kernel math service,
  Task, driver-private kernel operation or OS-ROM arithmetic call. Exec's
  gateway remains COP #$50; guest service events are not new COP signatures.
- Keep one current platform profile. Rebuild all affected FastBasic producers
  and consumers together; do not retain an old-loader compatibility branch.
  Integer and FP remain language/build variants of the maintained source port.
  Update the current reference in the slice that changes an interface or adds
  supported behavior; FB6e completes the user guide and delivery documentation.
- Target **0 added fixed, root, kernel, per-public-Task and idle reserved
  bank-zero bytes** in every slice, including guards, alignment and unused
  capacity. Reuse the existing 544-byte guarded two-slot guest D pool.
- Keep the integrated IDE, hardware statements, external user USR, IEEE types,
  native 65816 BASIC generation and larger guest addressing outside FB6.

Compiler/parser/runtime changes belong in the FastBasic source port; Exec816
owns its loading, native services and integration. Action! compiler defects
belong in actionc with focused regressions; machine-emulation defects belong
in actionc-vm. Do not compensate for either with individual Exec routine hacks.

## Slice sequence

| Slice | Executable result | Completion evidence |
| --- | --- | --- |
| FB6a | Private math probe and new native snapshot services; rebuilt integer tools still work | Source/map audit, small raw/optimized ABI and decimal-context probes, independent numeric vectors |
| FB6b | Host-built FP programs run through the ordinary loader | Complete supported numeric corpus, original controls, literal agreement, time/random and integer regressions |
| FB6c | FBC compiles new FP source on Exec and its output runs after FBC exits | Source/error/capacity cases, saved-image readback, injected write/Close faults and recovery |
| FB6d | FP runtime/compiler coexist with other guests and native Tasks | Forced IRQ/NMI, isolated state, bounded BREAK, slot/resource recovery and measured memory/timing |
| FB6e | Documented, reproducible programming environment in both demo packages | Extracted-package edit/compile/run, keyboard/redirection checks, source rebuild and complete packaging checks |

Record progress and unresolved acceptance gates per slice. Do not mark later
slices complete because their components were linked by an earlier build.

## FB6a Private math foundation and current ABI

Primary files: `abi/fastbasic.json`, `tools/generate_fastbasic.py`,
`ports/fastbasic/upstream.json`, `target/exec.cfg`, `target/header.asm`,
`patches/exec6502.patch`, `tools/build_fastbasic.py`,
`lib/dos/fbprogram.act`, `fbservice.act`, `fbstate.act`,
`tests/test_fastbasic_profile.py` and `tools/audit_fastbasic.py`.
Paths under `target/` and `patches/` are relative to `ports/fastbasic/`.

### Source and relocatable math

1. Inventory every reachable FP dependency, including parser AFP, conversion
   helpers, polynomial operations, internal normalization/constants, RANDOM
   and RTCLOK. Record source paths, original addresses, replacement symbols,
   workspace and clobbers. Include the math package's own low-memory operands,
   computed transfers and decimal-mode exits.
2. Add a maintained ca65 adaptation of the pinned mini65 `asm/mathpack.s`,
   for example `target/mathpack.asm`, retaining its notices and provenance.
   Preserve the original 2 KiB layout and padding initially, relative to a
   page-aligned linked base. Export symbolic entries and constants. Translate
   origin/offset assertions so assembly fails on unintended layout growth.
3. Include the adaptation and all added sources in `port-inputs.json`,
   `port-source.json` and the build manifest. Preserve original archive/cache
   verification. Edit the checked-in port inputs, not generated source caches.
   Rebuilding from a clean patched source tree must not depend on reused tools
   or an unchecked embedded math binary.
4. Link the package inside RUNTIME before bytecode, updating linker alignment
   and runtime-size/header calculations as necessary. Verify the flat payload
   includes every math byte and padding byte without a hole to `$D800`.
   Check relocated entry and table references at two guest-bank placements;
   compare selected operations with the original fixed-origin provider.

### ABI and memory

5. Allocate the next common target identity, provisionally `$4702`, while
   keeping `FB65` envelope version 1, its 16-byte header, load `$3000` and limit
   `$E000`. Recheck that allocation against the current tree at implementation.
   Update the sole host/native admission rule and rebuild FBCI, host integer
   output and fixtures in the same slice. The previous `$4701` target must fail
   as unsupported before claiming a guest slot.
6. Generate the design's memory constants: general D allocation `$80–D3`,
   reserved math/conversion D `$D4–FF`, FP expression stack `$04D0–04FF`,
   numeric size 6, and snapshot `$0700–0703`. Limit allocatable ZP to 84 bytes
   with linker assertions. Declare existing CIX/INBUFF aliases as shared
   conversion state. Check the `$0580` input/format area and `$05E0`/`$05E6`
   math scratch for lifetime overlap; save any input or value that must remain
   live when conversion reuses that space.
7. Append services without renumbering existing entries. The provisional
   allocations below follow the current table; verify them against all shared
   bridge intervals before emitting veneers.

   | Service | Event | Veneer | Result |
   | --- | --- | --- | --- |
   | TICKS24 | 75 | `$F960` | Low 24 VBLANK ticks in little-endian `$0700–0702`, byte `$0703` zero |
   | RANDOM32 | 76 | `$F980` | One new xorshift32 word in little-endian `$0700–0703` |

   Generate service count 13 and reserve through `$F99F`. Check unique events,
   contiguous veneer generation and nonoverlap in host tests. Keep integer
   TIME/RAND meanings unchanged; share one PRNG advance helper so interleaved
   RAND/RND calls consume the same per-invocation state consistently.
8. Implement both services through existing session timer/random state and
   the normal guest transition. Set all four snapshot bytes on success,
   including the cleared high clock byte. Use no caller pointer and add no
   native session field unless evidence requires it. Preserve existing
   first-cause failure, console/file cleanup and bank/D reset on relaunch.

### Checks and completion

Add one focused runner, provisionally `tools/test_fastbasic_fp.py`, with
selectable math, ABI, runtime, compiler and context groups. Add a small emitted
fixture under `tests/programs/` and exact numeric vectors under
`tests/fastbasic/`. These names describe planned additions, not existing tools.
Reuse the current build/runner infrastructure rather than introducing another
guest launcher.

The first probe must load through PROGRAM, convert signed integers and decimal
strings, add/multiply known values, format a result, call both snapshots and
return normally. Cover byte order, D/snapshot boundaries, old-profile and
malformed-image rejection, flags/hidden B/register/stack preservation, guards
and complete heap recovery. Force at least one IRQ/NMI entry while decimal
arithmetic is live. Test this small native ABI/context surface in raw and
optimized builds; prove arithmetic by emitted 65816 execution, not host tests.
Rebuild and run focused integer compile/run and existing KEY/file smoke cases.

Extend the audit to select FBCI, the math probe and later FBC, derive D extents
from actual linker output, and classify private math calls/data references.
Remove its hard-coded integer D-use values. Source-review dynamic addressing
and parser RTS tables separately; traversal success does not prove them safe.

Acceptance: a private linked math probe and both services execute correctly,
the new integer profile works, and no new bank-zero reservation is introduced.

Suggested commit: `Add private FastBasic math foundation and snapshot services`.

## FB6b Complete runtime and host FP target

Primary files: the port patch and target sources, `tools/build_fastbasic.py`,
`tools/test_fastbasic_controls.py`, `tools/audit_fastbasic.py`, the new focused
runner/corpus and the donor grammar/compiler sources through the port patch.

1. Add explicit restricted FP user and compiler-bootstrap target files next
   to `target/atari-int-compiler.tgt`. Combine `float.syn` with the existing
   allowed statements. Keep internal callbacks exclusive to bootstrap targets;
   do not inherit FujiNet or hardware syntax from upstream `atari-fp.tgt`.
2. Build the FP runtime library and add an explicit integer/FP selection to
   `compile_program` and the host CLI, defaulting to the existing integer mode.
   Select matching grammar, generated token tables, header object and library
   together. Record target/language mode and all output hashes in build records.
3. Restore `int_to_fp` and `fp_to_str` for FP builds, including signed-16-bit
   conversion and counted strings. Retain the smaller native integer formatter
   for integer builds. Replace all FP public/internal ROM addresses with
   package symbols, including FPNORM, FPHALF, load/store and polynomial helpers.
4. Enable six-byte scalar/array allocation, FP expression stack initialization,
   handlers and per-run DEG/RAD defaults. Preserve the donor error 3/18
   behavior in BASIC IOERROR/ERR and keep it distinct from native fatal error
   selectors. Exercise a successful operation after each handled error.
5. Replace FP RND with one RANDOM32 snapshot and unsigned conversion/division
   by 4,294,967,296 in private math. Replace `%TIME` with one TICKS24 snapshot
   and unsigned conversion. Cover values above signed-16-bit range explicitly;
   do not reuse a signed conversion helper for unsigned high words unchanged.
   Remove the hardware rejection loop and private RTCLOK reads.
6. Establish independent six-byte vectors and selected original FP controls
   before accepting port results. Extend the existing control runner to build
   unmodified FBC and use upstream FP fixtures such as `fp-fun`, `fpcomp`,
   `fp-array`, `fp-input`, `fpint` and `floatadr`. Keep simulated-OS and actual
   pinned AltirraOS controls identified separately, including provider hashes.
7. Compare host literal encoding with selected AFP conversion and original
   controls at decimal/exponent/rounding boundaries. If the existing C++ double
   conversion disagrees, fix conversion in the FastBasic port with a defined
   decimal rule and focused vectors. Ensure the host compiler is then built
   from the patched sources; copying the unmodified donor host binary cannot
   exercise such a fix. Keep original control binaries unmodified.

Runtime coverage must include each supported FP operator/function, integer/FP
mixing and precedence, nested expressions, scalar/array/procedure storage,
array stride, comparisons and DEG/RAD. Check exact representation and simple
arithmetic with exact vectors; specify absolute/relative tolerances for
approximate functions. Cover INT around negative, half-way and signed-word
boundaries, invalid VAL, division by zero, domain errors, underflow/overflow,
formatting boundaries and INPUT/STR$/VAL round trips. Record error numbers and
returned values, not just printed success markers.

Use known snapshots/seeds for clock wrap, RND endpoints and mixed RAND/RND
sequence checks. Assert `0 <= RND() < 1` after decimal rounding. Test maximum
supported expression/array/string capacity and explicit failure at one past
the supported boundary without weakening guards. Preserve exact binary and
ATASCII fixtures; normalize host text endings before parsing expected records.

Acceptance: fresh host-built FP executables run all supported numeric features
with reviewed differences from controls, integer behavior remains intact, and
no reachable math path calls live OS ROM or reads hardware aliases.

Suggested commit: `Enable the FastBasic floating point runtime and host target`.

## FB6c On-machine floating point compiler

Primary files: `target/cmdline.bas`, `target/header.asm`, the donor
`actions.asm`/parser/build rules through the port patch,
`tools/build_fastbasic.py`, `tools/test_fastbasic.py`,
`tools/test_fastbasic_faults.py`, `tests/programs/fastbasic.act`,
`fbfault.act` and the new FP runner/corpus.

1. Build `FBC.COM` from the same maintained frontend and FP bootstrap target.
   Replace parser `read_fp = AFP` with its linked private entry and audit all
   parser/helper clobbers, consumed-character offsets and failure paths.
   Preserve EOL normalization, Process arguments, no-argument prompts,
   diagnostics, internal callbacks and checked output/Close.
2. Produce FBCI and FBC together with separate compiler hashes/layouts in the
   manifest. Keep the existing build entry usable by its callers while
   updating them for two compiler artifacts. Record each heap start, D use
   and selected runtime/token identity; do not infer FBC capacity from FBCI.
3. Verify the on-machine writer copies the complete FP runtime, math package,
   constants, padding and bytecode. Read the saved file back independently,
   validate its envelope/extents and execute it only after the compiler has
   retired. No compiler-resident address may be required by the saved program.
4. Compare host and on-machine compilation of the same numeric sources using
   final values, exact six-byte storage and defined tolerances. Include nested
   runtime/parser conversion and repeated compile/run to expose shared-scratch
   clobbers. Bytecode files may differ because runtime selection and
   optimization differ; their behavior and target contract must agree.
5. Run the frontend with arguments and prompts; empty, LF, CRLF, CR, ATASCII
   and missing-final-EOL sources; malformed literals and located syntax errors;
   quoted paths; missing/read-only files; source/output capacity and allocation
   failures. Derive exact boundaries from the actual FBC link map and emitted
   behavior. A failed compilation must permit a later successful compilation.
6. Parameterize the existing fault runner for FBCI/FBC. Exercise short writes,
   fatal writes, late Close failure and combined write/Close failure against
   real owned files. Check the first cause, handle retirement and heap/slot
   recovery. Preserve the documented possibility of a partial output file.

Acceptance: the shell runs FBC on a newly edited FP source, FBC exits, and the
shell independently loads and runs its saved output, with correct diagnostics
and recovery on every selected failure path.

Suggested commit: `Port the on-machine FastBasic floating point compiler`.

## FB6d Coexistence, decimal context and bounded progress

Primary files: `tools/test_fastbasic_lifetime.py`,
`tests/programs/fastbasic_lifetime.act`, the FP fixtures, port checkpoint code
and existing platform probe hooks where a new measured boundary requires them.
Read [platform.md](../reference/platform.md) before changing platform code.

1. Run two FP guests with different live FR0/FR1, FP stack, DEG/RAD and random
   state, plus a progressing native peer. Separately run FP alongside FBC/FBCI
   and MD5 within the same two-slot limit. Reject a third guest and prove slot
   reuse after completion, failure and cancellation. Reuse a retained Image
   with changed inputs and verify fresh bank/D/math/session state each run.
2. Add targeted forced interrupt cases during SED arithmetic, conversion,
   parser AFP, formatter execution, guest/native service entry, page-one
   exchange and native return. Include existing native-return probe coverage
   where applicable. Verify decimal carry/status results, restored P/hidden B,
   D/DBR/registers and untouched native/OS arithmetic context. IRQ masking alone
   must not substitute for the SWITCHING/OS_BUSY protocol.
3. Measure worst-case supported arithmetic, power, transcendental and
   conversion loops at the pinned clock. Use a no-I/O workload to require
   BREAK observation within two PAL VBLANK frames and prove native peer
   progress. Measure parser/save cancellation and I/O/cleanup retirement
   separately; a timeout or unvisited injection point is a failed case.
4. If a path exceeds the bound, add a bounded continuation/checkpoint at a
   documented decimal-clear point, preserving live numeric scratch/registers
   and carry. Re-run numeric vectors plus the failing context/latency case.
   Keep Forbid/OS_BUSY scopes unchanged. If checkpoint code changes the initial
   2 KiB package layout, update assertions, map and symbolic-call review and
   report the actual growth; do not silently overflow fixed-origin padding.
5. Combine a focused compiler workload with native disk/pointer activity and
   console focus changes on the pinned graphical profile. Assert output/file
   correctness, guards, owned requests/endpoints, heap recovery and final OS
   restoration. This is targeted coexistence evidence, not a platform matrix.
6. Report FBC/FBCI/runtime file sizes, initialized spans and padding, D use
   versus reserved capacity, FP stack and snapshot bytes, native code/session
   costs, upper allocation peaks, remaining guest heap and measured latency.
   Include all allocator rounding and bank-alignment capacity. Report bank-zero
   changes separately for fixed, root/kernel, public Tasks and idle; each
   remains zero relative to the enabled integer/SDX build.

Acceptance: independent state and complete restoration under the selected
interrupt boundaries, bounded cancellation/peer progress, unchanged resource
ownership and measured memory cost. Outstanding required cases remain gates;
do not treat linking or selected compiler controls as completion evidence.

Suggested commit: `Validate and bound FastBasic floating point coexistence`.

## FB6e Documentation, reproducibility and demo delivery

Primary files: `tools/build_demo.py`, `tools/test_fastbasic_demo.py`,
`tools/package_fastbasic_source.py`, `examples/fastbasic/`,
`ports/fastbasic/README.md`, `ports/fastbasic/NOTICE.txt`, `LICENSING.md`,
`docs/reference/fastbasic.md`, `docs/guides/fastbasic.md` and
`docs/fastbasic-distribution.txt`.

1. Publish the supported numeric contract: representation, literal rules,
   measured range/rounding/conversion/formatting behavior, function tolerances,
   error/ERR behavior, limits and provider-specific differences. Document FBC
   versus FBCI, the shared current image identity, RND/time semantics and the
   unsupported features. Add a decimal example with independently known results.
2. Install both compilers with `--fastbasic`, retain EDX/MD5/ARC and add FP
   sources on the writable work disk. Update build records, checksum/readback
   checks, notices and the short user guide for both compiler artifacts.
3. Build full matching native demos after the ABI change. Make
   `--refresh-fastbasic` verify the resident target/service ABI before disk
   mutation; reject a mismatched old native build with a rebuild instruction.
   On a matching build, refresh both compiler files and their manifest hashes,
   disk verification, guides, notices and checksums together.
4. Build and test the text and graphical variants through `tools/build_demo.py`.
   Always include OF816, its five-second autoboot, matching disks and pinned
   ROM/notices; retain the standard text shell/prime startup. Preserve the
   graphical variant's documented startup selection. Include matching XEX,
   old/new Atarimax CAR and raw 1 MiB BIN, using `--cartridge-from` as needed
   after refresh. Check capacity and correspondence to the final XEX.
5. Extend the packaged-demo runner to operate on clean extracted ZIPs. Use
   physical keyboard events to edit decimal source in EDX, save, invoke FBC
   by arguments and prompts, and launch output by bare name and `.COM`.
   Exercise decimal INPUT/PRINT and exact redirected file bytes, numeric errors
   with recovery, BREAK, an FBCI integer compile/run, and ARC/MD5/native-command
   smoke. Verify persisted source/output readback, guards and normal EXIT.
6. Refresh the corresponding source ZIP with the full modified FastBasic,
   math adaptation/original notices, Exec adapters, pins and offline build
   instructions. Rebuild both compilers and a sample FP program from a clean
   extracted patched source tree, with no reused binaries. Compare artifact
   hashes under fixed inputs and investigate differences before delivery.
7. Write `docs/development/fastbasic-floating-point.json` and an execution
   record under `docs/history/`, recording actual scope/results and unresolved
   qualification gates. Preserve the existing integer evidence. Update design,
   plan, roadmap and relevant indexes with actual completion status. Keep
   manifests/logs/intermediates outside the boot ZIPs, which contain only boot
   files, the short guide, notices and checksums.

Acceptance: both extracted packages support the complete FP edit/compile/run
workflow, the clean source delivery reproduces it, and the numeric reference
matches recorded execution evidence. Report final artifact paths/checksums and
launch commands without claiming general hosted-system or hardware qualification.

Suggested commit: `Package the FastBasic floating point programming environment`.

## Validation and evidence rules

Use development checks by default: affected host checks/generators, focused
optimized emitted-code behavior and the targeted context/lifetime cases above.
Pair raw/optimized only for the small new ABI/context probes and diagnosed
compiler-facing changes. Do not repeat complete application scenarios in raw
mode or run full release qualification after each slice or commit.

Keep ordinary build/test output under `build/fastbasic/` with distinct FP slice
directories. Record source/tool hashes, actual ROM and effective shadow,
emulator/bridge identity, clock/speed, memory map, media, native wrapper mode,
observed case/injection counts and explicit deadlines. No result is a pass
until its runner completed and checked the expected output and cleanup.

Keep exact expectations independent of the implementation under test. Separate
original simulated controls, original pinned-machine controls and Exec runs.
Reuse passing evidence only while all relevant inputs match; retain original
hashes and scope for historical integer/SDX records. Use narrow diagnostic
hooks only in test builds and keep them out of published packages.

This plan changes documentation only and adds **0 reserved bank-zero bytes**.
Its preparation requires content/link checks, not compiler or emulator runs.
Implementation completion requires all FB6a–FB6e delivery gates; full release
qualification and physical-hardware qualification remain separate work.
