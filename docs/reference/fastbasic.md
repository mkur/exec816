# FastBasic integer target

[Reference index](README.md) · [Programming guide](../guides/fastbasic.md) ·
[Implementation record](../history/fastbasic-integer.md)

FastBasic 4.7's 6502 integer compiler and runtime run in emulation mode as
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
BREAK before the guest starts can cancel shell loading with 10/304. A running
BASIC Process returns 20/304 through the ordinary child-result path.

TIME returns the low 16 bits of the public VBLANK clock. PAUSE N waits N+1
VBLANK intervals through native cancellable delay. RAND uses per-invocation
xorshift32 state, initially `$6D2B79F5`, reduced modulo the unsigned bound;
RAND(0) returns zero. The sequence differs from Atari hardware RANDOM.

The integer target rejects floating-point syntax, external USR assembly calls,
Atari graphics, sound, DLI, player/missile, raw SIO and FujiNet statements at
compile time. The integrated editor is not included; use EDX. This profile is
for rebuilt programs, not existing Atari XEX or arbitrary machine-code payloads.

## Executable and memory contract

[abi/fastbasic.json](../../abi/fastbasic.json) defines the `FB65` version 1,
target `$4701` container. All words are little endian:

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

The linker reserves D offsets `$80–EF`; current FBCI uses `$80–B8`. PEEK/POKE
and DPEEK/DPOKE addresses 0–255 alias the instance's relocated D; other 16-bit
addresses name its private bank. The `$FF` word boundary accesses private bank
`$0100` for the second byte. MOVE addresses refer to the private bank, so copying
the virtual D aliases with MOVE is unsupported. PEEK/POKE of nominal hardware
addresses accesses private RAM. This convention provides no memory protection.

Private low memory contains stack-variable arrays at `$0480–04CF`, numeric and
input scratch near `$057F–067F`, argument scratch at `$0800–08FF` and CIO records
at `$0340`. Programs must respect compiler/runtime-owned storage. Services at
`$F800–F95F` and the existing bridge intervals are reserved. No executable code
is installed in bank zero to reproduce the donor's zero-page dispatch.

## Scheduling and ownership

Dispatch and MOVE execute in private-bank code with mutable absolute JMP
operands. They avoid ordinary indirect JMP reading a pointer in bank zero.
The compiler's internal callbacks use private direct jumps; external USR is
excluded from the user grammar. Parser ROM helpers and integer conversion are
replaced at source level. Startup does not close borrowed streams or initialize
sound hardware. The command-line compiler uses `cmdmenu.asm`; the donor IDE's
`compile.asm` and BRKKY ownership are outside this build.

Native checkpoints occur every 64 dispatches, every 256 memory-copy/fill bytes
and per parser line. The existing guest bridge retires the guest activation
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
