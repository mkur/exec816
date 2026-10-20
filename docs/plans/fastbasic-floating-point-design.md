# FastBasic floating point on Exec816

Status: **FB6 functional delivery implemented**, 20 October 2026. See the
[execution record](../history/fastbasic-floating-point.md) for the private-D
addressing adaptation, measured checkpoint change and actual development scope.
The [current target](../reference/fastbasic.md) defines supported behavior;
the design below records the implementation's starting decisions.

[Plan index](README.md) ·
[Implementation plan](fastbasic-floating-point-implementation-plan.md) ·
[Migration plan](fastbasic-6502-migration-plan.md) ·
[Integer execution record](../history/fastbasic-integer.md) ·
[Platform contract](../reference/platform.md)

Extend the source port with FastBasic's six-byte Atari floating-point numbers
and an on-machine `FBC.COM` compiler. Link a private, source-built math package
into each floating-point executable. Keep the existing guest bridge, ordinary
Process ownership and native console/file backend. The intended workflow is:

```text
EDX CALC.BAS
FBC CALC.BAS CALC.COM
CALC
```

Retain `FBCI` as the smaller integer compiler, built from the same maintained
port and current platform ABI. The integrated editor remains FB7. Native 65816
BASIC code generation, IEEE arithmetic, larger BASIC address spaces and Atari
graphics/sound compatibility are outside FB6.

## Numeric behavior

Preserve upstream variable types and expression rules, including `%` variables
and arrays, mixed integer/float expressions, comparisons, integer conversion,
`VAL`, `STR$`, PRINT and INPUT. Each float occupies six bytes: a sign/exponent
byte and five packed-decimal mantissa bytes. Keep this representation in
constants, variables, arrays and saved data. Do not substitute a native host
`float` or `double` representation.

Include upstream arithmetic, powers, ABS/SGN, SQR, logarithms, exponentials,
trigonometry and DEG/RAD state. Exact supported range, rounding, formatting and
domain-error behavior must be recorded from the selected math implementation
and original controls before publishing the numeric reference. Six-byte format
compatibility alone does not establish identical answers across Atari ROMs.

Preserve BASIC's error behavior. The donor's `check_fp_err` records numeric
error 3 in `IOERROR`; FP `VAL` records conversion error 18. These are observable
through BASIC `ERR()`. They are separate from the current native fatal-service
selector 3, which means allocation failure and maps to native error 103.
Do not turn a handled arithmetic error into Process failure or overwrite a
previous file failure during fatal cleanup. Freeze returned numeric values on
error against the controls as well as the error numbers.

## Source baseline and dependency inventory

Use the existing FastBasic 4.7 and mini65 revisions in
[upstream.json](../../ports/fastbasic/upstream.json). Do not update donors as
part of enabling floating point. The relevant source findings are:

| Source | Required port work |
| --- | --- |
| `src/syntax/float.syn`, `src/vars.asm`, `src/interp/atarifp/` | Enable FP grammar, six-byte allocation, handlers and the FP expression stack. Keep the restricted Exec user grammar. |
| `src/actions.asm` | Replace the parser's `read_fp = AFP` ROM dependency, including consumed-character and failure behavior. |
| `src/interp/a800/str.asm` | Supply `int_to_fp` and `fp_to_str`; the integer port currently replaces this file with a native integer formatter. |
| FP arithmetic, conversion and polynomial handlers | Replace Atari entry-point equates with private linked symbols, including load/store helpers. |
| `fp_rnd.asm`, `fp_time.asm` | Replace direct hardware RANDOM and RTCLOK reads with Process services. |
| `fp_sincos.asm`, `fp_sqrt.asm` | Replace internal math entry/constant addresses such as `FPNORM=$DC00` and `FPHALF=$DF6C`, as well as public ROM calls. |
| `src/compiler/atarifp.h` and `.cc` | Check host literal conversion against the on-machine parser; existing host conversion uses C++ double arithmetic. |

The pinned [FP grammar](https://raw.githubusercontent.com/dmsc/fastbasic/55dc52f74fcfcf3e8afd29bb5b984ee1dc9b6a6f/src/syntax/float.syn)
defines the language extension. Enabling `FASTBASIC_FP` alone does not supply
the missing formatter, math dependencies or Exec compiler target.

## Private math implementation

Select the Altirra decimal math source already present in the pinned mini65
dependency as the initial provider:
[asm/mathpack.s](https://raw.githubusercontent.com/dmsc/mini65-sim/30b85d1ee940b546ca7b5737be371ff6c7f99ed1/asm/mathpack.s).
Build an auditable ca65 adaptation from that source. Record original source
hashes, the adaptation and resulting code hashes in the existing port build
manifest. Preserve its file-specific Avery Lee copyright and permission notice;
include the modified source and build instructions in the source delivery.
The rest of the FastBasic port retains its existing donor notices and runtime
linking exception.

The provider's original layout occupies `$D800–DFFF`. Relocate it into the
executable's initialized runtime, using symbolic calls and data references.
Translate fixed-origin assertions and padding into offsets relative to an
aligned package base. Keep the original 2 KiB layout initially, including its
padding, to make the adaptation reviewable. Replace every caller's fixed
entry-point or constant address; moving only JSR targets is insufficient.

Use ordinary same-bank calls with PBR/DBR naming the guest's private bank.
Audit addressing modes in the emitted code: direct-page operands must use the
guest D, absolute operands must address the private bank, and computed transfers
must obey the existing 65816 bank rules. An unmodified ROM binary copied to a
different address is not the implementation.

Arithmetic stays inside the guest. There is no new kernel math operation,
shared native FP workspace or OS-ROM activation. Compared with a marshalled ROM
service, this avoids repeated copying of numeric registers, pointers and
scratch state, and avoids serializing unrelated guests on the OS math package.
Compared with an IEEE implementation, it retains the donor's representation
and math algorithms. The cost is additional runtime code and reduced BASIC
heap space in each 64-KiB guest.

## State and memory layout

Reserve the following ranges explicitly in generated target definitions and
the linker map. Addresses below `$0100` are guest D offsets; the other ranges
are offsets in its private bank.

| Range | Proposed ownership |
| --- | --- |
| D `$80–D3` | Allocatable interpreter/parser state, including FP stack pointer and DEG/RAD flag: 84 bytes of capacity. |
| D `$D4–FF` | Math registers, temporaries, pointers and shared parser conversion state: 44 bytes, excluded from general ZP allocation. |
| `$0480–04CF` | Existing 80-byte integer expression stack. |
| `$04D0–04FF` | Donor eight-entry, six-byte FP expression stack: 48 bytes. |
| `$057F–067F` | Existing conversion/input area; account explicitly for the math package's `$0580` buffer and `$05E0`/`$05E6` scratch. |
| `$0700–0703` | New four-byte native snapshot result, shared sequentially by time and random services. |
| `$0800–08FF` | Existing argument string area. |
| `$2FF0–2FFF` | Existing executable header copy. |
| `$3000` to initialized end | Dispatch table, runtime including math package, data and bytecode. |
| After initialized/BSS data, below `$E000` | Compiler/runtime heap according to the linked target. |

The integer linker's current `$80–EF` allocation range would overlap math state.
Cap general allocation at `$D3` for the current port and fail the build on
overflow. Current FBCI uses 57 bytes there; the available 84 bytes are a design
capacity, not a measured FBC link result. Existing parser `CIX`/`INBUFF` aliases
in the upper D range must be declared as shared conversion workspace, not
treated as spare storage.

Initialize the full D page, FP stack, registers and scratch on every run through
the existing bank-reset path. A retained Image relaunch starts fresh, including
DEG/RAD, errors, random state and service scratch. Parser conversion and runtime
conversion use the same guest-owned math state. Audit their clobber contracts
and save live values around internal calls; there is no interrupt-time FP use
or simultaneous execution within one guest.

The implementation budget is **0 additional fixed, root, kernel, per-Task and
idle reserved bank-zero bytes** relative to the enabled SDX/integer build,
including guards, alignment and unused capacity. The two guarded guest D slots
remain the existing 544-byte fixed reservation; FP uses more of an already
reserved page, without adding a slot or enlarging it. This documentation change
itself reserves zero bytes.

Per Image, keep the existing aligned-bank allocation, whose allocator
reservation is 131,072 upper bytes including unused alignment capacity. Math
code, the 48-byte FP stack and four-byte snapshot fit inside that bank. Added
initialized code also enlarges the retained file snapshot, rounded by the
allocator. Keep the native session layout unchanged if the new services need
only its existing timer and PRNG state. Report actual FBC/FBCI file sizes,
linker padding, D use, heap start/capacity, session size, native code/static
capacity and transient compiler peak in the implementation evidence. Reuse
existing allocation checks; insufficient workspace is an ordinary failure.

## Native time and random services

Append two explicit service definitions to
[abi/fastbasic.json](../../abi/fastbasic.json), generating the Action! and
assembly bindings together. Each writes a four-byte little-endian result at
private `$0700`; it accepts no application pointer. Do not change the existing
integer TIME/RAND service meanings.

- `TICKS24` obtains one coherent public VBLANK-clock snapshot, returns its low
  24 bits and clears the fourth byte. `%TIME` converts that unsigned value to
  FP in private code. It counts VBLANK intervals and wraps at 24 bits; it does
  not access Atari RTCLOK or imply milliseconds. Its low 16 bits agree with
  integer TIME when sampled at the same tick.
- `RANDOM32` advances the existing per-invocation xorshift32 once and returns
  the complete word. FP `RND()` converts it to a six-byte number and divides
  by 4,294,967,296 using private math. This gives a bounded construction in
  `[0,1)` with one service crossing. Integer RAND and FP RND share that state;
  their sequence is deterministic for a fixed call order and existing seed,
  and differs from Atari hardware RANDOM. Verify the upper endpoint after
  decimal rounding explicitly.

The snapshot is copied into guest-owned math temporaries before another
service can reuse it. Remove the donor's hardware rejection loop rather than
reading a private RAM alias of RANDOM. Clock failures follow existing native
first-cause cleanup. Console, paths, channels and file bytes retain the
[current backend contract](../reference/fastbasic.md#supported-language-and-services).

## Executable and compiler integration

Keep the 16-byte `FB65` version-1 envelope and flat initialized payload. Link the
math package inside the runtime bytes copied by both compiler writers, before
user bytecode; include alignment and padding in runtime size and initialized
end. Avoid a new segment or a payload padded up to the old `$D800` ROM address.
A compiled program contains its own selected runtime and needs neither a live
compiler nor a separately loaded math library.

Allocate a new common target identity in the machine-readable ABI for the
completed FB6 port. Rebuild FBCI, FBC, host targets and examples together, and
reject the previous target identity through the existing unsupported-profile
path. Keep one current service/layout contract rather than an old-loader
compatibility branch. Integer and FP language variants can share this target
identity because they use the same platform services and memory rules; each
payload carries its matching token table and runtime. Runtime selection is a
build responsibility, not a per-instruction loader check.

Add restricted FP user and compiler-bootstrap targets alongside their integer
counterparts. Include `float.syn` without reintroducing FujiNet, graphics,
sound or user USR. Use the existing frontend for source normalization, Process
arguments, diagnostics, checked writes/Close and output prompts. The compiler's
parser must use the same private math provider as generated programs. Restore
the FP conversion helpers while retaining the smaller native integer STR path
in the integer build.

Check literal encoding from both compilers against independent six-byte test
vectors and the selected AFP implementation. Host double-based conversion may
disagree at decimal boundaries; resolve such differences in the FastBasic port,
using a shared decimal conversion rule where needed. Compare complete programs
semantically rather than requiring identical optimized bytecode files.

## Interrupts and bounded execution

Use the existing guest SWITCHING/OS_BUSY and page-one exchange protocol.
Preserve P, hidden B, D, DBR, S and the complete interrupted context. The CPU
decimal flag is distinct from the direct-page register D: the math code uses
SED/CLD, and an IRQ/NMI or native service can arrive while decimal arithmetic
is live. Native arithmetic must run with its required flags and guest return
must restore the interrupted flags exactly. SEI does not provide NMI exclusion.

Exercise actual emitted decimal ADC/SBC and carry/status behavior on the pinned
65816 profile. Test forced entry during decimal math, after flags are saved,
during page-one/context transfer and on native return. Use two guests holding
different FP registers and DEG/RAD modes, plus a progressing native peer.
Include parser AFP and formatter calls, not only interpreter dispatch.

Retain the dispatch interval of 64 bytecodes and parser/copy checkpoints. One
transcendental operation can take substantially longer than one integer
opcode, so bytecode count alone is insufficient evidence of cancellation
latency. Measure the longest supported math and conversion paths and require
no-I/O BREAK observation within the existing two-PAL-frame target. Add internal
checkpoints only at documented safe points with decimal mode clear, preserving
live registers, carry and private scratch. If a path exceeds the bound, split
it before delivery; do not hold OS_BUSY or Forbid across a whole calculation.
Measure cleanup/I/O completion separately.

## Executable slices and acceptance

Follow the [development testing tier](../contributing/testing.md). Run focused
optimized emitted-code cases per slice and small raw/optimized probes for new
service layouts, flag preservation and bridge boundaries. Full hosted-system
qualification remains a separate activity.

| Slice | Deliverable and acceptance |
| --- | --- |
| FB6a | Pin/hash the selected math inputs and ca65 adaptation; generate the disjoint D map and new service/profile definitions. Link a small guest that converts, adds and formats known six-byte values. Prove workspace boundaries, addressing modes, decimal flags and full context restoration. |
| FB6b | Enable the restricted host FP target and complete math handlers. Run constants, mixed expressions, scalar/array/procedure storage, nested expressions, comparisons, conversions, error recovery and DEG/RAD functions. Verify integer output and unsupported-statement rejection still work. |
| FB6c | Build FBC on Exec. EDX edits a decimal program; FBC compiles it; the compiler exits; the shell loads the fresh output. Cover prompts, CR/LF/ATASCII sources, parser location/error recovery, boundary/OOM cases and injected save/Close failures. |
| FB6d | Exercise two FP guests, FP plus FBCI/MD5, retained-image relaunch, third-slot rejection/recovery, forced IRQ/NMI during math/parser calls, no-I/O BREAK, native peer progress and full resource/OS restoration. Record actual memory and timing costs. |
| FB6e | Publish the numeric reference and guide, rebuild matching programs and package the workflow for both consoles. Test the actual extracted packages with physical keyboard input, redirected input/output and independent saved results. |

Use the pinned original FastBasic FP compiler/runtime and mini65 math provider
as controls, recording which math pack is selected. Also run selected controls
on the actual pinned AltirraOS ROM/emulator configuration. Original Atari ROM
math may differ; enumerate differences rather than merging incompatible
expected outputs. Controls based on mini65 do not qualify Exec interrupt or
console behavior.

The corpus must include exact byte vectors for zero/signs, decimal and exponent
boundaries, carry propagation, cancellation, array stride and conversions;
division by zero, domain/range errors, invalid VAL and subsequent recovery;
and published absolute/relative tolerances for approximate transcendental
results. Check INT near negative and signed-16-bit boundaries against donor
behavior. Test parser literal, VAL, INPUT and STR$ round trips independently.
Time/random tests use known snapshots and seeds, clock wrap, isolation and
RND endpoint cases rather than expecting Atari hardware sequences.

Keep manifests, inputs, test counts, measured costs and unresolved gates in a
new FB6 development record without rewriting the integer evidence. Reuse
`tools/build_demo.py` for delivery, with OF816 and its five-second standard
shell/prime autoboot, matching disks, pinned ROM/notices and matching XEX,
old/new Atarimax CAR and raw 1 MiB BIN. Refresh the corresponding source ZIP
with the math source, adaptation and build instructions. Boot ZIPs contain
only boot files, the short guide, notices and checksums.

FB6 is complete when the on-machine FP workflow and these development gates
pass and the supported numeric behavior is documented. That result does not
close the existing general guest interrupt or physical-hardware qualification
gates.
