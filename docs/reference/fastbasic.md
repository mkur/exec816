# FastBasic source target

[Reference index](README.md) · [Programming guide](../guides/fastbasic.md) ·
[Integer record](../history/fastbasic-integer.md) ·
[Floating-point record](../history/fastbasic-floating-point.md)

FastBasic 4.7's 6502 integer and floating-point compilers/runtimes run in emulation mode as
ordinary Exec Processes. Build with the shared guest bridge enabled (`--sdx`);
the demo's `--fastbasic` option also installs the compiler and examples.
This source target has its own format and native services. The exact-binary
SDX MD5/ARC/EDX catalog remains separate.

## Supported language and services

The target retains signed 16-bit integer arithmetic, strings, byte/word arrays,
procedures, loops and conditional control flow. PRINT/PUT and INPUT/GET use
inherited Process streams. INPUT uses native cooked console editing; GET waits
for one translated character without requiring Return. KEY() peeks without
consuming: zero means no queued character, 1–255 identify a console character,
and 256 identifies queued NUL. It requires interactive input. These are console
character codes, not the original Atari CH scan codes.

ATASCII `$9B` is the line separator. Interactive output selects the console's
ATASCII glyph mapping for the duration of the invocation and restores native
mode on return, failure and BREAK. Retained cells use the current console mode;
inverse/graphics history may change appearance after native mode is restored.
Redirected files retain the original bytes, including `$9B`. Mode changes clear
pending input, as defined by [console.device](console.md).

Channels are 0–3. Channel zero borrows the Process streams; channels 1–3 own
native files. OPEN modes 4, 8 and 12 select old-file, new-file and read/write.
CLOSE, GET, PUT, INPUT, BGET and BPUT use the source backend's bounded CIO
operations. XIO operations outside these implemented commands fail with CIO
156. Native paths and the Process current directory apply, with up to 254 path
bytes before the terminator. `E:`, `S:` and Atari drive syntax are not general
device emulations; use native DOS paths and inherited streams.

EOF is CIO 136; short BGET updates the actual-length word in the guest IOCB.
Ordinary CIO errors remain available through ERR(). The adapter retains the
native cause for an explicit compiler failure. Successful END returns 0/0;
fatal compiler/service failures return primary 20 with IoErr holding the first
native cause. Parse errors use 306, unsupported services 307, allocation errors
103 and BREAK 304. Invalid argument quoting/length reports 115. Close and flush
errors are preserved when no earlier fatal error exists. Compilation writes
directly to the chosen output; a failed write can leave a partial file.
The compiler requires EOF within its remaining source-read buffer. An input
that fills that buffer is rejected with 20/306 (`File error: 1`); source and
compilation workspace share the guest bank. A source that fits may still exhaust
parser/runtime allocation, reported as 103. Observed boundary sizes belong to
the build's execution record rather than a general document-size guarantee.
BREAK before the guest starts can cancel shell loading with 10/304. A running
BASIC Process returns 20/304 through the ordinary child-result path.

TIME returns the low 16 bits of the public VBLANK clock. PAUSE N waits N+1
VBLANK intervals through native cancellable delay. RAND uses per-invocation
xorshift32 state, initially `$6D2B79F5`, reduced modulo the unsigned bound;
RAND(0) returns zero. The sequence differs from Atari hardware RANDOM.

FBCI rejects floating-point syntax. Both language variants reject external USR assembly calls,
Atari graphics, sound, DLI, player/missile, raw SIO and FujiNet statements at
compile time. The donor Atari editor is not included. Use EDX or the native
[GEM workbench](fastbasic-workbench.md) for editing and integrated Run. This profile is
for rebuilt programs, not existing Atari XEX or arbitrary machine-code payloads.

## Floating point

FBC accepts the donor floating-point grammar, including `%` scalars/arrays,
mixed expressions, comparisons, INT, VAL/STR$, INPUT/PRINT, powers, ABS/SGN,
SQR, LOG/LOG10, EXP/EXP10, SIN/COS/ATN and DEG/RAD. Procedure parameters retain
the donor integer convention; pass addresses to operate on floats in procedures.
Integer FBCI remains available and uses the same current platform services.

Numbers occupy six bytes: sign in bit 7 of the first byte, a biased base-100
exponent in its low seven bits, followed by five packed-BCD mantissa bytes.
Normalized values have nine or ten significant decimal digits, depending on
exponent parity. Zero has exponent zero. The selected private Altirra provider
supports positive normalized values from `1E-98` through `9.999999999E97`,
and their negatives; smaller results underflow to zero. There are no IEEE
NaN/infinity values or an IEEE rounding-mode interface.

Literal conversion in both compilers and FP VAL uses the selected AFP decimal
digit rules, truncating excess input precision. For example `1.234567895`
becomes `1.23456789`. This deliberately fixes the donor host compiler's
double-based rounding disagreement with its on-machine parser. Arithmetic and
formatting follow the pinned math package; they do not promise bit identity
with every Atari ROM. INT rounds magnitude and reapplies sign (`-1.5` becomes
`-2`); converted magnitudes at least 32768 report error 3, including the
negative boundary. Arithmetic/domain/range errors record BASIC ERR 3;
invalid FP VAL records 18. These handled BASIC errors do not by themselves
fail the Process. Capture ERR() immediately: subsequent console/file I/O can
replace it. Native fatal allocation error 103 remains separate.

Transcendental and noninteger-power results are approximate. Development cases
check `4.0^0.5` against 2 with absolute tolerance `1E-7` (the selected provider
returns `2.00000002`), plus exact selected zero/one, DEG/RAD and square-root
controls. These case tolerances are not uniform accuracy bounds for all inputs.

FP RND() uses the same per-invocation xorshift32 state and seed as integer RAND,
advances it once, and divides the unsigned word by 4,294,967,296 in private FP
code. It returns a value in `[0,1)`; interleaved calls share the sequence.
`%TIME` converts one coherent public VBLANK snapshot, truncated to 24 bits.
It counts VBLANK intervals and wraps at 24 bits; integer TIME uses the low 16.
Neither operation reads Atari hardware or RTCLOK.

## Executable and memory contract

[abi/fastbasic.json](../../abi/fastbasic.json) defines the `FB65` version 1,
target `$4703` container. All words are little endian:

| Offset | Field |
| --- | --- |
| 0 | Four magic bytes `FB65` |
| 4, 6 | Version, target identity |
| 8, 10 | Load address `$3000`, exclusive initialized end |
| 12, 14 | Entry within initialized data, memory limit `$E000` |

The header is exactly 16 bytes, followed by exactly `end - $3000` initialized
bytes. This first target uses one flat segment. It admits fresh compiler output
structurally, without an executable hash allowlist. Unknown versions/targets
fail with 307; invalid/truncated layouts fail with 306 before claiming a slot.
The header is copied into private `$2FF0–2FFF` too, for the compiler's writer.
BSS/workspace is implicit zeroed memory after the initialized image.

An Image owns an immutable file snapshot, one private aligned 64-KiB bank,
native session and one of two guest slots shared with SDX. Each run clears
and repopulates the bank and D, so retained-image relaunch starts fresh.
Backing allocation requests 131,071 bytes (allocator reservation 131,072)
to ensure alignment, including unused capacity. Native session and file-image
storage are additional upper-RAM costs; timer resources are allocated on demand.
The per-instance saved page-one image and service buffers are in that session.

The linker reserves D offsets `$80–D3`; math registers and conversion state own
`$D4–FF`. FP accesses that need absolute,Y use five native-initialized long
pointers at D `$70–7E`, inside the existing full guest page. PEEK/POKE
and DPEEK/DPOKE addresses 0–255 alias the instance's relocated D; other 16-bit
addresses name its private bank. The `$FF` word boundary accesses private bank
`$0100` for the second byte. MOVE addresses refer to the private bank, so copying
the virtual D aliases with MOVE is unsupported. PEEK/POKE of nominal hardware
addresses accesses private RAM. This convention provides no memory protection.
The FP adaptation uses 65816 long-indirect instructions in emulation mode to
reach that D state; it is not an executable for a plain 6502 machine.

Private low memory contains integer stack-variable arrays at `$0480–04CF`,
an eight-entry FP expression stack at `$04D0–04FF`, numeric and
input scratch near `$057F–067F`, argument scratch at `$0800–08FF` and CIO records
at `$0340`. Time/random snapshots use four bytes at `$0700–0703`. Programs must
respect compiler/runtime-owned storage. Services at
`$F800–F9BF` and the existing bridge intervals are reserved. No executable code
is installed in bank zero to reproduce the donor's zero-page dispatch.

## Scheduling and ownership

Dispatch and MOVE execute in private-bank code with mutable absolute JMP
operands. They avoid ordinary indirect JMP reading a pointer in bank zero.
The compiler's internal callbacks use private direct jumps; external USR is
excluded from the user grammar. Parser ROM helpers and integer conversion are
replaced at source level. Startup does not close borrowed streams or initialize
sound hardware. The command-line compiler uses `cmdmenu.asm`; the donor IDE's
`compile.asm` and BRKKY ownership are outside this build.

Native checkpoints occur every 64 dispatches, every 256 memory-copy/fill bytes,
per parser line and every two completed FP math operations. The latter preserve
carry/registers and run with decimal mode clear. The existing guest bridge retires the guest activation
before native blocking I/O or scheduling. Its SWITCHING/OS_BUSY protocol,
complete saved context and IRQ/NMI rules remain authoritative. No new kernel
gateway or driver-private service is added; Exec still uses COP #$50.

Relative to the enabled SDX build, fixed, per-Task and idle reserved bank-zero
changes are **0 bytes**, including guards/alignment/unused capacity. The shared
profile already reserves 544 fixed bytes for two guest D pages and guards;
FastBasic consumes slots from that pool rather than enlarging it.
Development checks exercise selected interrupt boundaries and coexistence;
general guest interrupt qualification and physical hardware qualification remain
open. See the linked implementation record for actual execution scope.

## Compiler diagnostic file

The optional command tail is `source output diagnostics eight-hex-digit-job`.
The first two filenames retain their ordinary CLI and interactive behavior.
Diagnostic jobs require all four arguments, a nonzero 32-bit hexadecimal job
and source/diagnostic paths of at most 127 bytes. Registering invalid identities
fails before source or command I/O. The supplied source names an immutable
ATASCII snapshot owned by the controller through compiler retirement.

[The machine-readable record](../../abi/fastbasic-diagnostics.json) generates
the native writer constants and C header. Its 224 little-endian bytes contain
`FBD1`, version/size, job, stage, BASIC error, signed native cause, one-based
logical line, zero-based source byte column, exact source path and a bounded
message. Line zero means unavailable. Tabs are skipped between tokens without expanding the source bytes; columns
precede tab expansion. Lines over 255 bytes and unsupported source characters
are rejected before the donor parser, with BASIC diagnostic codes 257 and 256. Source
and message capacities include their NUL bytes (128 and 64). Reserved bytes
are zero. Stages are source, parse, output and complete.

The compiler records parser failure before printing its human-readable message.
The native adapter emits the record after guest channels and console mode
retire, with checked Write/Close. A requested diagnostic failure fails an
otherwise successful job; an earlier parser or I/O cause wins. A controller
must require successful Process results, a complete diagnostic with matching
job/source/generation and a fresh validated COM. File existence alone is not
success. Diagnostics do not extend the compiler's source or guest memory limits.

The registration is borrowed until Run retires. It adds six requested upper
bytes to the native Session (2,304 → 2,310 requested, 2,304 → 2,312
allocator bytes) and a transient 224-byte upper allocation when
writing. The fixed guest pool, Tasks and reserved bank-zero sizes are unchanged.
