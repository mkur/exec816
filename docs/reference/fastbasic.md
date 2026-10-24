# FastBasic source target

[Reference index](README.md) · [Programming guide](../guides/fastbasic.md) ·
[Integer record](../history/fastbasic-integer.md) ·
[Floating-point record](../history/fastbasic-floating-point.md) ·
[Source interpreter record](../history/fastbasic-interpreter.md)

FastBasic 4.7's source interpreters and integer/FP compilers/runtimes run in emulation mode as
ordinary Exec Processes. Build with the shared guest bridge enabled (`--sdx`);
the demo's `--fastbasic` option installs FB/FBI, FBC/FBCI and examples.
This source target has its own format and native services. The exact-binary
SDX MD5/ARC/EDX catalog remains separate.

## Source execution

`FB source` reads and runs integer/FP BASIC; `FBI source` selects the integer-only
grammar. Exactly one source path is required, with optional quotes. Bare commands
print usage and return 20/115. Source is read separately from inherited standard
input, so BASIC INPUT/GET can still consume redirected input. Native directory,
file paths, streams and BREAK apply. `.BAS` is not automatically executable.

Source translates to bytecode and runs within one Image, guest bank and Process.
Run produces no source, executable or diagnostic scratch file. Shell FB/FBI
commands retire their Process after END, failure or BREAK. BASIC.APP instead
keeps one interpreter Process and its state between runs, as described below.
Direct mode, Pause/Continue and variable inspection remain unsupported. FBC/FBCI and standalone COM
loading remain available through their existing interfaces.

Input is limited to 32,768 original bytes; CRLF counts twice. Normalize LF,
CRLF, CR and ATASCII to guest EOL, adding a final EOL when missing. Tabs count as
one byte; lines allow 255 non-EOL bytes. Other source bytes must be printable
ASCII. NUL and unsupported bytes fail with 306 before execution. Exact-cap files
are accepted at source admission when they end at EOF. Source, parser tables,
bytecode and runtime heap share the guest bank; a fitting source can still fail
allocation with 103. Source Read/Close failures never execute partial input.

The parser remains linked during execution, reducing available array/string
heap relative to standalone output. Large line counts also incur a checkpoint
per parser line. Source document capacity is not a program-allocation guarantee.

### Source-buffer attachment

The generated [C header](../../c/include/exec816/fastbasic-interpreter.h) and
[Action! records](../../lib/dos/fbinterpabi.act) follow
[fastbasic-interpreter.json](../../abi/fastbasic-interpreter.json).
Load an owned, unstarted FB/FBI Image through the ordinary cooperative loader,
call `ExecBasicAttach(image, source)`, then use StartLoaded/Break/Collect.
A zero session address selects one-shot execution.
Action! disk commands use `COMMAND.BasicAttach(image, source)`.

The version-2, 28-byte descriptor carries version/size, a 32-bit source address/count,
nonzero job identity, source generation, a 32-bit result address and an optional session address. C pointer
fields use the huge-data ABI. Native code copies the descriptor and borrows
the immutable source and writable 128-byte result until collection or final
unstarted Image release. Failure preserves an existing attachment; a valid
replacement releases its old borrow. Failed Start preserves it for retry;
successful execution consumes it. Reattach before another buffer run. Releasing
the parent's load reference after Start is supported.

Read the result only after collection. It contains version/size, matching
job/generation, source/parse/execute/complete phase, location validity, primary
and native cause, parser error, one-based line, zero-based byte column and a
bounded message. Runtime source positions are unavailable. Ordinary Process
results remain authoritative for launch/setup failure. The first fatal cause
survives cleanup; handled BASIC ERR behavior is unchanged. No extra Task, guest
slot or bank-zero reservation is added for attachment/results.

If a returned child identity fails setup before BASIC entry, collection still
ends its source/result borrow. A configured Start that returns zero retains
the attachment for retry. Neither path publishes a fabricated BASIC result.

### Persistent interpreter sessions

A nonzero `source.session` borrows an `ExecBasicSession` through Process
collection. Set its message reply port and length before Attach/Start. The
interpreter creates its own request port, publishes it in `session.port`, and
replies to the session message when ready. The initial descriptor does not
execute source; send RUN for the first program. Setup failure still uses the ordinary
Process result. Keep the Image's owner reference while using the session.

Both message headers must start at even addresses, as required by Exec ports.
Align static storage explicitly and pad embedded records when needed; packed
C record types alone do not establish that address alignment.

Send one `ExecBasicRequest` at a time to that port using public Exec PutMsg.
RUN borrows its immutable source and result until ReplyMsg returns the request;
the result is complete before the reply. Its job must be nonzero and its
version, sizes, addresses and counts must follow the generated records. The
caller owns live buffers and messages; the driver does not repeatedly validate
those contracts. Wait on the reply port signal together with Process completion.
A request is 46 packed bytes; the session's 16-byte Exec Message and 24-bit port
pointer occupy 19 bytes. Source/result pointers remain 32-bit huge pointers.

END, Stop and recoverable errors finish that request while the same Process,
Image, bank, variable bindings, scalar values, strings, arrays, random sequence,
DEG/RAD mode and open channels remain. Each Run starts the current source at its
beginning with fresh expression, call and loop stacks. Statements still have
their normal effects: an assignment overwrites its old value. Parse failure
executes nothing and preserves the last committed bindings. Runtime failure or
Stop keeps effects completed so far. Break is acknowledged before the next run.

Source/parser/bytecode workspace is replaced on the next Run. Raw pointers into
that workspace, including an address of inline DATA, have that invocation's
lifetime; execute DATA declarations again to bind the new program's data.
DIM-allocated data and copied string storage live in the retained data arena.

Variable slots remain stable even when declarations move or disappear from the
source; new bindings append. A changed variable type requires RESET. Repeated
DIM of the same type and size preserves its allocation and contents; a changed
size reports 115 and requires RESET. RESET closes channels, frees symbols and
reinitializes BASIC memory and modes inside the same Process, then replies.
QUIT replies and exits; collect the Process before releasing the session, ports,
output or Image. Stop uses ordinary BreakProgram and does not terminate a session.

Session variables occupy guest `$A000–$A1FF`; its array/string allocator uses
`$A200` upward. The allocation end pointer must stay below `$E000`, allowing
at most 15,871 array/string bytes before other allocations.
Source, bytecode and temporary parser tables must fit below `$A000`, so source
admission can report 103 before the document's 32 KiB limit. This separate
workspace prevents a parse or source edit from overwriting retained data.
The symbol-name copy lives in upper native heap. Strings/arrays use the donor
bump allocator; RESET recovers accumulated allocations and bindings. One-shot
shell and standalone programs retain their dynamic workspace arrangement.

An idle session blocks on its request port while retaining one public Task,
one of the two shared SDX/FastBasic slots and their existing memory reservations.
It releases the single page-one execution lease. Other guests and Check/Build
can execute while BASIC data survives. A live invocation, including INPUT or
PAUSE, retains the lease through native waits. A second activation returns
primary 20/cause 202 before parsing or changing BASIC data. RESET and QUIT while
parked operate only on private resources and do not touch another guest's stack.
It does not poll or add a kernel operation. Reserved bank-zero changes are zero:
fixed, root/kernel, every public Task and idle, including guards and padding.

Grammar backtracking uses a 256-byte private-bank buffer with three bytes of
bookkeeping, bounded to 63 live states. The parser checks CPU state at `$01A4`
and machine actions at `$01A7` after three temporary saves; excessive syntax nesting
reports `too long` through the existing parse error result (306). Error reporting
retires the parser continuation before printing. This protects
the complete interrupt frame and the pinned ROM borrowing budget. See the
[resident guest contract](sdx-runtime.md) for headroom and ownership.

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
target `$4705` container. All words are little endian:

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
and repopulates the bank and D, so a one-shot retained-image relaunch starts fresh. Session requests reuse the live Process.
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
`$F800–F9FF` and the existing bridge intervals are reserved. No executable code
is installed in bank zero to reproduce the donor's zero-page dispatch.

## Scheduling and ownership

Dispatch and MOVE execute in private-bank code with mutable absolute JMP
operands. They avoid ordinary indirect JMP reading a pointer in bank zero.
The compiler's internal callbacks use private direct jumps; external USR is
excluded from the user grammar. Parser ROM helpers and integer conversion are
replaced at source level. Startup does not close borrowed streams or initialize
sound hardware. The command-line compiler uses `cmdmenu.asm`; FB/FBI use the
port's assembly source-run wrapper with zero relocation. The donor IDE's
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
