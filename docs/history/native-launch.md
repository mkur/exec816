# Native Action! launch under AltirraOS

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

The first hosted slice runs one compiled native Action! procedure on its own
stack and direct page, prints through AltirraOS, and reaches a controlled end.
It packages the compiler's pinned native image (currently version 3) as an Atari
XEX with an assembly launcher. The [cooperative extension](cooperative-tasks.md) adds the COP `$50`
gateway and two tasks; this page describes the original single-program mode.

## Build and run

Use a clean checkout of the compiler revision in
[toolchain/actionc.json](../../toolchain/actionc.json). For a fresh checkout:

```sh
git clone https://github.com/mkur/actionc.git build/actionc
git -C build/actionc checkout --detach 32af3e2bbe4a48e85704b57370254b1846daa458
```

Install Rust/Cargo, Python 3.9+, ca65, and ld65. Prepare the pinned ROM and
AltirraBridge distribution as described in the
[boundary-probe instructions](os-boundary-probe.md#reproduce). Then:

```sh
python3 tools/native_program.py --compiler-dir build/actionc
```

This builds the compiler with its lockfile, compiles
[examples/hello.act](../../examples/hello.act), and writes `build/hello/program.xex`.
Open that file in the qualified Altirra configuration, or run it automatically:

```sh
python3 tools/native_program.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

Expected output is `EXEC816 NATIVE ACTION OK`. The Action! program first waits
for the OS clock to change while running on its private stack, then calls the
console service. It also checks initialized data and explicitly zero-filled
globals. The terminal loop retains the displayed text while OS VBI/IRQ work
continues; this slice does not return to a DOS command prompt.

Options: `--source path.act`, `--output directory`, `--no-opt`, and `--rom path`.
An explicit `--allow-compiler-override` permits a different or dirty compiler
checkout and records that fact. Normal qualification requires the clean pin.
The builder records compiler revision, changes, executable and ABI hashes,
platform inputs, source/image/XEX hashes, and optimization mode in `build.json`.
Assembly consumes the generated ABI include from that same compiler checkout.

## Build pipeline

The [Python packager](../../tools/native_program.py) coordinates these tools for
both the single-program launcher and current Task builds:

1. **ca65** assembles the handwritten `.s` platform code: startup, interrupt
   handlers, gateways and device adapters. **ld65** links the assembly objects
   using the platform linker configuration and exports their addresses.
2. **actionc** compiles the Action! kernel policy, libraries and application
   sources directly into native machine code and data in `program.a816.json`.
   Its layout binds imported services to the assembled addresses. actionc has
   its own machine-code emitter; its output does not pass through ca65.
3. The packager validates image placement and ABI contracts, assembles again
   with the compiled entry addresses, and checks that the exported platform
   addresses remain unchanged. It packages the compiler and assembly bytes
   into `program.xex`, including the loader and manifest for banked builds.

Build settings that affect both code producers are passed to each explicitly.
For example, [stack checks](../contributing/stack-checks.md) use an actionc layout option and a
ca65 assembly define. This requires no conditional compilation in Action! source.

## Native Task console option

The Task launcher also supports `--tasks --task-capacity 8 --console` for the
native `console.device`. The build option defaults to `console` in
[config/kernel.json](../../config/kernel.json), currently false; `--no-console`
explicitly disables it. Startup completes the resident worker before calling
Main. Applications use CreateMsgPort/CreateIORequest/OpenDevice and ordinary
READ/WRITE/CLEAR requests, then collect and close them before exiting. No
application binary format or runtime loader is needed. Use the
[console platform pin](../../toolchain/altirra-console.json) for its qualified
hardware environment and the [console implementation record](console-io-implementation.md)
for scope and reproduction. The original ROM-backed `EXECOS.Write` remains
available after safe native-console shutdown and in console-disabled builds.
It returns busy while the native console owns the screen/keyboard.

## Loader contract

This launch path supports the pinned 800XL/65C816/PAL/64K configuration, BASIC
disabled, VBI enabled and DLI disabled, with the emulator's cold XEX launch.
It does not claim compatibility with arbitrary DOS layouts, resident handlers,
memory expansions, accelerated clocks, or a warm launch into another program.

The host packager validates the image identity and the platform stack contract,
checks every initialized/zero-fill range for bounds and overlap, and requires a
zero-argument procedure entry inside executable code. Imported services must
match the assembled addresses and the compiler-exported interface IDs, argument
layout and result convention. It rejects nonzero-bank allocations, writable
code, unsupported imports, arena overflow, and incompatible ABI/image versions.
External absolute aliases such as the OS clock do not allocate or clear memory.

The XEX contains exact segment bytes and explicit zero bytes for BSS. It is
published only after validation and final assembly. The machine launcher checks
`MEMLO <= $2000` and `MEMTOP >= $9000`, reserves through `$9000` in `MEMLO`,
installs its native interrupt vectors, initializes guards and the ABI domain,
and enters with E=0, M=X=0, decimal clear, DBR=0, D=`$2200`. The ordinary entry
uses a zero padding byte and JSL, so S is even at procedure entry. Compiler
stack checks and the assembly service's own check run before their reservations.

| Bank-zero allocation | Purpose |
| --- | --- |
| `$0100-$010F` | Lower OS-stack guard |
| `$0110-$01EF` | OS stack; native arrivals already in page one keep their current S |
| `$2000-$20FF` | Initialized launch state; diagnostics through `$203F`, cooperative state above it |
| `$21F0-$21FF`, `$2300-$230F` | Direct-page guards |
| `$2200-$22FF` | Native task domain; scratch, owner, kind, and stack bounds from ABI v1 |
| `$3000-$3FFF` | Launcher, native interrupt entries, console service, exit/fault adapters |
| `$41F0-$41FF`, `$4800-$480F` | Native stack guards |
| `$4200-$42FF` | Conservative native interrupt reserve below the ordinary floor |
| `$4300-$47FF` | Ordinary stack allocation; initial body S=`$47FE` |
| `$6000-$8FFF` | Native image arena; code starts at `$6000`, data at `$8000` |

The fixed domain bytes outside compiler scratch remain unchanged after launch.
The 256-byte interrupt reserve exceeds the ABI's initial 26-byte task minimum.
OS handlers use the separate page-one allocation; its lower guard is checked.
This does not establish a worst-case bound for arbitrary OS drivers or handlers.

## Console service

[lib/exec/execos.act](../../lib/exec/execos.act) declares:

```text
MODULE EXECOS
PUBLIC EXTERNAL CARD FUNC Write(BYTE POINTER buffer CARD length)
ENDMODULE
```

Call it as `EXECOS.Write(...)` after `USE EXECOS` inside a module. It writes
exact ATASCII bytes through IOCB 0/CIOV using `COP #$00`; it does not append an
end-of-line byte. It accepts 0–255 bytes. A nonempty buffer must have bank zero
and lie entirely in `$6000-$8FFF`; no pointer is silently truncated. The caller
owns the buffer and must keep it valid for the duration of the synchronous call.
A zero-length call succeeds without accessing the pointer or entering the OS.

Return values are 1 for success, the unsigned CIO error status for an OS error,
`$FF01` for invalid pointer/extent/length, and `$FF02` if another OS call is active.
The adapter implements the ordinary native ABI, including preservation of D,
DBR=0, S, and the caller's I bit. Its checked local native-stack reservation is
10 bytes. A/X/Y and arithmetic flags are ordinary call-clobbered registers.

The service sets a one-byte OS-call ownership flag, switches onto the reserved
OS stack, establishes D=0/DBR=0, and enables hardware IRQs before entering COP0.
It retrieves the CIO result, restores the native stack/domain, and releases the
flag. Calls are serialized; nested Action! calls from OS/interrupt handlers are
unsupported. Single-program mode does not switch tasks. Cooperative mode adds
the current owner's task ID and pending-yield delivery after retiring the OS
stack activation; see its [transition protocol](cooperative-tasks.md#interrupt-and-transition-protocol).

## Native interrupt protocol

Both native NMI and IRQ entries first save the complete ABI register frame.
They use long-addressed state and no interrupted direct-page scratch. After the
save, they inspect S: if outside page one, they switch to `$01EF`; if already in
page one, they keep the current S. This prevents an interrupt during COP or
another interrupt from overwriting that active OS frame.

The interrupted saved S is pushed onto the selected OS stack, private to the
current activation. A synthetic native interrupt frame chains to the saved ROM
handler. The synthetic P carries the interrupted I bit, so the ROM's VBI work
retains its normal interrupt-masking decision. On ROM return, the wrapper pops
the saved S and restores the original full register frame with RTI.

The console adapter follows the same lifetime rule: its saved native S resides
on the OS stack until the OS call and COP target word have been removed. It
consumes that word before restoring the private S. A native NMI before or after
either stack transition therefore finds a complete stack for its own saves.
An NMI in emulation mode uses the existing OS emulation vector on page one.

The supported policy is one VBI NMI activation, with no DLI; native IRQ work
runs through the existing ROM handler, and NMI may interrupt it. The wrappers
do not call Action! or schedule tasks. Arbitrary reentrant VBI/IRQ callbacks and
an OS VBI taking an entire frame remain outside this slice's qualification.

## Return and faults

Normal return checks S/D, records the boundary flags, and writes status 0.
The raw compiler stack-overflow adapter records required bytes and the unchanged
S, then writes status 1. Status 2 indicates incompatible OS memory bounds;
status 3 indicates a bad normal-return stack/domain. `$FFFF` means running.

The normal/fault exit disables interrupt delivery during restoration, switches
to the OS stack/domain, restores the saved native NMI/IRQ vectors and MEMLO,
enters emulation mode, re-enables VBI/IRQ, and parks. No corrupted task stack is
used to unwind a terminal fault. This is a controlled terminal state, not process
isolation or recovery from arbitrary memory corruption.

## Validation

Run the package-boundary checks and the actual-machine acceptance suite:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_hosted.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

The 28-case matrix covers raw/optimized NIR, both caller I states, eight real-NMI console
transition checkpoints, POKEY timer-1 IRQs through the ROM, invalid buffers,
zero-length and maximum-length writes, the arena's final byte, explicit BSS
initialization, and recursive stack overflow.
Every case checks domain/stack guards and restoration of OS vectors/MEMLO.
`--case transition-7-raw`, for example, runs one case. Test builds insert WAI at
one selected transition; the production build contains no such checkpoints.
These tests exercise real VBI/IRQ delivery, not a direct call to an ISR.

Reports and exact binaries are under `build/hosted-tests/`. The committed
[qualification record](../qualification/native-launch.json) records the accepted
run. The [cooperative extension](cooperative-tasks.md) qualifies COP `$50`,
independent contexts and locks separately; the
[preemptive extension](vbi-preemption.md) qualifies VBI scheduling. Wider
interrupt/driver coverage and an exhaustive instruction-boundary interruption
matrix remain outside these qualifications.
