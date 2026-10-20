# FastBasic 6502 migration to Exec816

Status: **FB0–FB6 functional integer and floating-point delivery implemented**,
20 October 2026. See the [integer record](../history/fastbasic-integer.md) and
[floating-point record](../history/fastbasic-floating-point.md) for actual
development checks, design adjustments and remaining qualification gates.
The [FP design](fastbasic-floating-point-design.md) and
[implementation plan](fastbasic-floating-point-implementation-plan.md) detail
FB6. The [GEM workbench design](fastbasic-workbench-design.md) defines FB7's
native editor/Run delivery and subsequent debugging/graphics gates, superseding
the original Atari editor port direction. The design below preserves the
original implementation sequence; the [current contract](../reference/fastbasic.md)
defines shipped behavior.
The [WB0–WB14 implementation plan](fastbasic-workbench-implementation-plan.md)
delivers FB7 at WB9, followed by the debugger, graphics and final workbench package.

[Plan index](README.md) · [Roadmap](../roadmap.md) ·
[Platform contract](../reference/platform.md) ·
[Testing policy](../contributing/testing.md)

## Result and scope

Port FastBasic from source, retaining its 6502 interpreter and parser, and run
it in 65816 emulation mode as an ordinary Exec Process. Native adapters provide
files, console I/O, time and cancellation. Preserve FastBasic's integer,
string, array and control-flow semantics. This is a separate application
personality using the existing guest execution bridge, rather than another
exact-binary entry in the MD5/ARC/EDX SDX catalog.

The first useful delivery is an integer programming environment in both the
text and graphical consoles:

```text
EDX HELLO.BAS
FBCI HELLO.BAS HELLO.COM
HELLO
```

These commands are available in demos built with `--fastbasic`.
The compiler must run on the Atari and produce a fresh executable that the
shell can load. A PC cross-compiler alone does not complete this milestone.
The existing exact-name-first `.COM` search needs no new shell syntax.

Start with the integer runtime and command-line compiler, using EDX for editing.
Floating point and the integrated editor follow as explicit extensions below.
Native 65816 execution, larger-than-64-KiB BASIC addressing, Atari graphics,
sound, DLI, player/missile graphics, raw SIO and FujiNet-specific statements
are outside the first delivery. Unsupported statements must fail explicitly;
initialization must also stop touching their hardware.

## Reviewed inputs

Use [FastBasic 4.7](https://github.com/dmsc/fastbasic/releases/tag/v4.7), commit
`55dc52f74fcfcf3e8afd29bb5b984ee1dc9b6a6f`, as the initial source baseline.
The release includes the integer command-line compiler, FBCI. The earlier
feasibility discussion inspected development sources; this plan selects the
release and reviews its relevant files directly.

FB0 will record source archive and selected-file hashes, bundled assembler and
linker identities, build commands, and the complete dependency set. Its Git
submodule pins are `mkatr` at `7d02bcb17d419ecb1bc53bb0460109595cd047ce` and
`testsuite/mini65` at `30b85d1ee940b546ca7b5737be371ff6c7f99ed1`. Fetch only the
dependencies needed for the selected builds and controls.

Keep upstream language/parser/runtime changes in a reproducible FastBasic
port under `ports/fastbasic/`, with source selection, patches and a dedicated
Exec target. Exec816 owns its loading, platform adapter and integration tests.
Action! compiler defects belong in actionc; emulator defects belong in
actionc-vm. Neither repository needs a new BASIC front end for this port.

Preserve FastBasic's GPL-2.0-or-later notices and file-specific runtime linking
exception from the [upstream license description](https://github.com/dmsc/fastbasic/blob/v4.7/README.md#license).
Keep imported and modified donor code identified separately from Exec-authored
interfaces. Record the selection and distribution requirements in
[LICENSING.md](../../LICENSING.md) when code is added.

## Source findings that determine the order

| Finding in the release sources | Consequence |
| --- | --- |
| [Interpreter](https://github.com/dmsc/fastbasic/blob/v4.7/src/interpreter.asm) executes mutable dispatch and MOVE code in zero page. The [linker configuration](https://github.com/dmsc/fastbasic/blob/v4.7/compiler/fastbasic.cfg) places `INTERP` at `$0080`, reserving `$1C` bytes. | A private D register relocates direct-page data access, not instruction fetch or absolute operands. Rework these routines before attempting the full runtime. |
| Dispatch uses absolute-indirect JMP; [USR](https://github.com/dmsc/fastbasic/blob/v4.7/src/interp/usr.asm) also uses an indirect target at `$0100`. | Audit every computed transfer. On the 65816, ordinary JMP (absolute) reads its pointer in bank zero; private-bank pointers cannot be used unchanged. |
| [Runtime startup](https://github.com/dmsc/fastbasic/blob/v4.7/src/interpreter.asm) closes CIO channels and calls SOUND_OFF; [keyboard](https://github.com/dmsc/fastbasic/blob/v4.7/src/interp/a800/getkey.asm) and [output](https://github.com/dmsc/fastbasic/blob/v4.7/src/interp/a800/putchar.asm) call OS handler vectors directly. | Replace these entry points at source level. Running PRINT through CIO would conflict with native console ownership. |
| The integer [parser](https://github.com/dmsc/fastbasic/blob/v4.7/src/parse.asm) calls OS helpers at `$DA51` and `$DBA1`. | Integer-only operation still needs ROM dependency removal; omitting floating point is insufficient. |
| [Compiler support](https://github.com/dmsc/fastbasic/blob/v4.7/src/compile.asm) installs BRKKY, and [cmdline.bas](https://github.com/dmsc/fastbasic/blob/v4.7/src/cmdline.bas) probes SpartaDOS memory and calls its argument parser. | Replace vector ownership and command parsing with Process-owned cancellation and arguments. |
| [Compiled headers](https://github.com/dmsc/fastbasic/blob/v4.7/src/comp_header.asm) and command-line save code emit Atari XEX segments, including zero page and RUNAD. | Adapt both the producer and Exec loader. Copying FBCI.COM to the utility disk cannot make its outputs executable under Exec. |

These are source findings, not execution results or a complete instruction
audit. FB0 extends the inventory to allocation, numeric conversion, timer/random
access, errors, self-modifying operands, compiler-generated tables and reachable
assembly callbacks. It must distinguish direct-page operands from ordinary
absolute addresses, including accesses to the same nominal OS variable.

## Execution and service design

Reuse the existing [guest bridge](../development/sdx-runtime.md) and
[Process/Image ownership](../reference/program-loading.md). Extract shared
bridge or lifetime helpers only as needed by a tested second caller; keep the
SDX service dispatcher and FastBasic services distinct. Preserve the one current
Task implementation and the existing MD5/ARC/EDX admission rules.

Each running instance owns its private bank, aligned guest D, saved page-one
image, interpreter state, file handles and native Process streams. Guest code
runs with `E=1`, eight-bit registers and the recorded PBR/DBR. Services detach
the guest using the established native transition before blocking; they resume
through a guest-bank trampoline. Preserve hidden B, flags, D, DBR, S and PC.
Page one remains a serialized physical resource with per-guest saved images.
No live ROM, kernel or native I/O activation may be suspended as a guest frame.

Move executable dispatch/MOVE routines into ordinary private-bank code and
separate their mutable operands from D-relative state. Use a 6502-compatible
same-bank dispatch sequence that does not fetch a private pointer from bank
zero; prove its A/X/Y/status and return-stack contract with emitted code.
Likewise replace internal USR/computed-call sequences. Reserve the bridge's
transition PC intervals in the FastBasic link map, including low-address code.
Do not allocate executable trampolines in scarce bank-zero memory to preserve
the old layout.

The first target supplies source-level backend routines rather than a general
Atari CIO implementation:

| FastBasic operation | Exec binding and policy |
| --- | --- |
| PRINT/PUT, INPUT, GET and KEY | Inherited Process streams; cooked line input for INPUT and qualified single-key input where required. Define blocking versus polling behavior explicitly. Reuse public console requests and DOS ownership. Translate ATASCII EOL at console boundaries; preserve exact bytes in files. |
| OPEN/CLOSE, BGET/BPUT and supported file operations | Owned native DOS handles, including short transfers, EOF, late Close errors and cancellation. Bare names use the Process current directory; mounted-volume paths use native DOS resolution. Remove unconditional `D:` insertion in the compiler. |
| Runtime END, parse/runtime errors and BREAK | Ordinary Process result/IoErr, preserving the first cause through cleanup. Specify the mapping in the FastBasic ABI; do not import SDX nonlocal error semantics accidentally. |
| TIME, supported waits and RAND | Public timer services and per-instance software random state. Waits must permit cancellation. Document any timing/random-sequence difference from the Atari hardware implementation. |
| Compiler argument acquisition and internal callbacks | Process argument buffers and explicit port-owned entry points; no SpartaDOS signature probe, DOSVEC call or global BRKKY replacement. |

Keep native file paths distinct from optional Atari device spellings. FB0
freezes the supported statement/device matrix, channel limit, path/argument
limits and error mapping; FB2 implements it and publishes the reference.
Channels for console input/output borrow their Process streams and must not
close the shell's endpoints. Other handles belong to that invocation.
The initial compiler path must work without screen positioning or a full E:
screen-editor emulation.

Keep PEEK/POKE-style memory operations confined by convention to the private
16-bit guest address space; this is not memory protection. Real Atari register
addresses name private RAM there and do not provide hardware compatibility.
The initial documented program subset excludes hardware-dependent uses and
arbitrary external machine-code USR routines. Port-owned callbacks remain
available to the compiler. Do not add per-instruction pointer validation.

Add a bounded native cancellation checkpoint in dispatch and in long compiler,
allocation and memory-copy loops. Start by measuring a checkpoint every 64
bytecode dispatches and every 256 copied bytes, then record the selected bounds
and cost. The no-I/O loop target is cancellation observation within two PAL VBI
frames on the pinned machine; I/O settlement and cleanup have separate measured
bounds. A native peer must progress during a BASIC loop that never calls I/O.

IRQ/NMI entry, page-one exchange, service suspension and return use the existing
SWITCHING/OS_BUSY protocol. SEI alone is insufficient. Add no FastBasic-specific
COP service or private kernel operation; the Exec gateway remains COP #$50.
Existing guest development evidence does not close the outstanding general
interrupt qualification gates. FB1 must exercise the changed execution paths
before later stages rely on them.

## Loading compiler output

Use a dedicated, versioned FastBasic executable profile recognized by
`PROGRAM.Load`. The proposed representation is a small identifying header plus
a bounded virtual-segment body derived from the existing XEX writer. It carries
the FastBasic target/ABI identity, entry point, initialized spans, zero-fill and
workspace requirements. Runtime code and bytecode travel together, allowing a
compiled program to run after FBCI exits. It remains a FastBasic profile, not
the actionc native o65 ABI or a general Atari XEX loader.

FB0 freezes the exact machine-readable layout, segment caps and link map before
loader implementation. Put the contract in `abi/fastbasic.json` and generate
shared assembly/Action! constants. The host and on-machine compilers must emit
the same profile. Their runtime/token-table identity must match even where
the generated bytecode is not byte-for-byte identical.

Distinguish guest-D initialization from private-bank segments explicitly.
An old `$0080` XEX segment must not become an instruction write to physical
bank zero. Treat RUNAD/INITAD as unsupported input records, using only the
profile's declared entry and initialization instead. D-relative state and
ordinary absolute data references need the distinct placements established
by the source port.

Validate header/version, file extents, entry, workspace, overlaps and reserved
bridge ranges once at admission, then publish an ordinary Image. Permit newly
compiled program contents; an exact-file hash allowlist cannot support this
workflow. Record source/runtime hashes for provenance, without treating a
self-declared identity as a security boundary. Plain Atari XEX files and
unknown profiles remain unsupported.

Fresh launches clear BSS and initialize mutable runtime state. Unload, failed
start, normal exit, runtime failure and BREAK release the same owned resources.
Use ordinary shell Load/StartLoaded/wait/collect and `.COM` fallback for the
compiler and its outputs. Test retained-Image relaunch and final unload.
Compiler output is valid only after successful write and Close; report a failed
save and do not advertise a partial file as runnable. Atomic replacement is a
separate filesystem feature, not an implied compiler guarantee.

## Memory budget

Relative to the existing SDX-enabled build, target **0 additional fixed, root,
kernel, per-native-Task and private-idle reserved bank-zero bytes** in every
slice. Planning changes themselves add zero. Reuse the existing guarded guest
DP pool and page-one protocol. The enabled personality currently reserves 544
fixed bank-zero bytes for two guest pages and their outer guards; FastBasic and
SDX must share those two slots rather than allocate another pool.

| Resource | Budget and ownership rule |
| --- | --- |
| Guest CPU address space | One usable 64 KiB upper bank per loaded Image; code, private OS-like variables, data, bytecode, heap and service veneers must have disjoint spans. Use the generated map, not Atari MEMTOP or screen-memory guesses. |
| Aligned bank backing | Account for the existing allocation strategy's full backing: 131,071 requested bytes, rounded to 131,072, per Image. Do not report only its 64 KiB aligned payload. |
| Bridge and guest D | Reuse the existing resident bridge reservation and two guest D pages. Report any increase in upper code/data occupancy and all unused reserved capacity. |
| Guest CPU stack | Reuse the saved page-one images and established stack limits. Measure compiler/parser, callbacks, error unwinding and interrupt headroom before claiming they fit. |
| Native adapter state | Upper-heap, invocation-owned records and buffers. Measure peak native stack use through blocking and cleanup paths; preserve existing native guards and interrupt reserves. |
| Console | Inherited streams for the first delivery. If an editor cell cache is later needed, charge width×height plus damage state to upper RAM and release it on every exit. |

FB0/FB1 must publish the complete virtual map and maximum D usage, including
parser and interpreter overlap. Source text, bytecode, variables and strings
compete for the remaining bank; supported maximum source/program sizes follow
from measured layouts and boundary tests. Do not claim a larger document or
array capacity from the machine's total RAM.

Compilation and execution are sequential shell commands, so they do not require
a third guest slot. A two-guest test must count all live native Tasks within the
existing pool. If the compiler cannot fit the current guest stack or D page,
first reduce its port-specific use; any reservation change needs a revised map
and explicit byte accounting before dependent slices.

## Executable slices

Each slice records its evidence and remaining limits before the next begins.
The first working integer delivery is FB0–FB5; FB6 and FB7 are follow-on work.

| Slice | Changes | Acceptance |
| --- | --- | --- |
| FB0 — Reproducible baseline and contract | Pin/select source and tools; build original integer compiler and reference programs; finish the instruction/ROM/hardware inventory; freeze virtual map, executable schema, service and feature matrix. | Original-machine controls compile/run arithmetic, arrays/strings, file I/O and an error case. Record hashes and exact bytes/results. Explain every selected ROM/vector dependency and identify its replacement. No Exec compatibility claim yet. |
| FB1 — Interpreter in a private guest bank | Rework dispatch, MOVE and internal computed calls; use the shared bridge, private D/state and bounded checkpoints; add a minimal entry/return path. | Emitted integer/control-flow/string/array programs run without console dependencies. Two distinct D pages, page-boundary dispatch, complete register/status restoration, guest/native guards, no-I/O BREAK, a progressing native peer, and targeted forced IRQ/NMI entry/return cases pass. Report memory and checkpoint cost. |
| FB2 — Console and file backend | Implement the agreed channels over native DOS/console services, clock/random and errors; remove startup hardware writes. | Physical-key PRINT/INPUT/GET/KEY in text and graphical shells, redirected input/output, exact ATASCII files, short I/O, EOF, missing/read-only destinations, injected write/Close errors, cancellation and complete handle/endpoint recovery pass. |
| FB3 — Host-built runnable programs | Add FastBasic image recognition/loading and the Exec cross-compiler target; emit the frozen profile. | A freshly cross-compiled HELLO.COM loads from a mounted disk and runs through the ordinary shell. Cover malformed/old profiles, overlaps, truncation, resource exhaustion, retained-Image relaunch, unload and heap recovery. Native o65 and pinned SDX behavior remain intact. |
| FB4 — On-machine integer compiler | Port FBCI and parser helpers, argument acquisition, memory allocation, diagnostics and output writer. Replace ROM helpers even in the integer build. | EDX edits a new source; FBCI compiles it on Exec; after FBCI retires, the shell loads and runs its output. Compare selected programs with original FastBasic and the host target; cover empty/boundary files, syntax errors with location, out-of-memory, failed save, BREAK during parsing/output and a subsequent successful compilation. |
| FB5 — Coexistence and useful demo | Run the final compiler/runtime alongside existing applications; package the integer workflow and its documentation. | Repeated edit/compile/run, a BASIC busy loop beside MD5 or EDX, two guest slots plus rejection/recovery of a third load, SIO/pointer activity, console focus changes, cleanup and OS return pass on the pinned profile. Cold-boot and test the actual packaged text and desktop artifacts. |
| FB6 — Floating point | Inventory every FP/math-package call and its workspace. Supply a private implementation or an explicitly marshalled native service; do not jump into shared ROM using guest pointers. Extend compiler, runtime and image identity together. | Compare six-byte Atari numeric representation, conversion, arithmetic, rounding, range/error behavior and nested parser/runtime use with the original. Verify independent state for two guests and all bridge guards. Publish the supported numeric contract before packaging FB/FBC. |
| FB7 — GEM editor and Run | Build a loadable native 65816 GEM application around FBC/FBCI, following the [workbench design](fastbasic-workbench-design.md). Reuse public Process/console services and add the general C stream, console-window and event-wait interfaces required for interactive children. | Physical-key edit/load/save and unsaved-buffer compile/run/return work on the GEM desktop, with structured diagnostics, exact source bytes, INPUT/GET/KEY, Stop, focus, exposure and complete child/mode/endpoint retirement. Shell compilation remains available in both consoles. |

FB6 and FB7 both depend on FB5; an integer-only IDE can take FB7 first.
Source debugging and native graphics follow the explicit gates in the workbench
design; FB7 editor/Run acceptance does not complete them. Graphics implementation,
sound/network and external machine-code libraries require their own plans and
public device ownership contracts.

## Validation and delivery records

Follow the [development tier](../contributing/testing.md#development-checks):
host checks, affected generators and focused optimized emitted-code checks per
slice. New native bridge/layout/ABI behavior gets small raw and optimized probes;
do not duplicate whole application workflows in raw mode. Normalize host source
line endings for reference comparisons, preserving binaries and ATASCII fixtures.

Freeze each test's compiler, FastBasic source/target, runtime image, actual
AltirraOS ROM, effective guest ROM shadow, emulator bridge, machine speed,
memory map and disk images. Use [actionc.json](../../toolchain/actionc.json) for
native wrappers and the existing platform pins selected by the runner; record
effective settings rather than inferring them from a historical pin's name.
The [EDX record](../development/sdx-edx.json) provides the previous console/guest
baseline, not evidence that FastBasic works.

Use independent expected integer/string/file results and original FastBasic
controls. Compare host and Atari compiler outputs semantically, because their
optimization and runtime selection can differ. Put bounded timeouts and
per-stage assertions around tests so a parser or interpreter hang cannot appear
as successful cancellation. Exercise maximum and one-past-boundary resource
cases without weakening guards or treating compiler tests as platform proof.

Keep build outputs and test logs under `build/fastbasic/`. Retain source
selection and patches under `ports/fastbasic/`, and record measured results in
`docs/development/fastbasic-6502.json` with an accompanying implementation note.
Publish actual supported behavior in reference and user instructions in guides
only after the corresponding stage passes. Update this plan, the indexes and
roadmap as slices complete; preserve historical evidence and hashes.

FB5 uses `tools/build_demo.py`, with OF816, the five-second standard shell/prime
autoboot, matching system disk and pinned ROM. Deliver `exec816-demo.zip` with
only boot files, a short guide, notices and checksums; include matching XEX,
old/new Atarimax CAR and raw 1 MiB BIN. Put the compiler, examples and writable
workspace on the matching system/work disk and verify execution from the
extracted package. Retain donor license notices and provide corresponding
modified source/build instructions as required in a separately identified source
delivery; keep build intermediates and test evidence out of the boot ZIP.

Full hosted-system qualification is a separate release activity. No code,
executable tests or demo rebuild is part of preparing this plan.
