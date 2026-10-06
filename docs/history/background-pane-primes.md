# Background console panes and primes

The [implementation plan](../plans/background-pane-primes-implementation-plan.md)
lands reusable foundations F0–F4 before the loadable command P1–P2. This page
records development checks and costs; it is not release qualification.

## F0 Baseline and interface definitions

The [baseline record](../development/background-pane-primes-f0.json) freezes
the matching bitmap shell build, source changes, compiler, ROM, emulator,
machine configuration and reservation costs. The existing timer-listing changes
are included in that build and remain separate from the pane implementation.
The ROM is AltirraOS 3.44 for 65C816, SHA-256
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`.
The compiler is the clean pin `6510ea1d148c93edea595be8a5afa9630d5a75e3`.

Freeze these Task-only signatures; publish each provider when its implementation
lands, so intermediate commits continue to build:

| Operation | Result | Arguments |
| --- | --- | --- |
| COMMAND.WriteAt | LONGINT committed count, or -1 with IoErr | BYTE POINTER handle, CARD column, CARD row, BYTE POINTER bytes, LONGINT length |
| COMMAND.OpenPane | BYTE POINTER handle, or NULL with IoErr | CARD rows |
| COMMAND.Delay | LONGINT -1 success, 0 with IoErr | LONGCARD ticks |
| PROCESS.StartBackgroundLoaded | LONGCARD identity, or 0 with IoErr | PROGRAM.Image POINTER image, BYTE POINTER arguments, CARD length |
| PROCESS.RequestBreak | BYTE 1 accepted, 0 with IoErr | LONGCARD identity |

`CONCMD_WRITE_AT=9` is a console-specific IOStdReq command, not an Exec service.
Its io_Offset contains the zero-based column in bits 0–15 and row in bits 16–31;
io_Data/io_Length carry the printable span and io_Actual the accepted count.
The definitions are machine-readable in abi/console.json. The existing 42-byte
IOStdReq, FIFO and completion protocol remain in use. F3 will assign the Process
row's four reserved tail bytes to pending cancellation (offset 124) and its
three-byte scope pointer (125), without changing the 128-byte stride.

The existing provider payload is 1,423 bytes for 42 providers. The three new
COMMAND providers need 98 bytes, leaving 143 bytes within the existing 1,664-byte
reservation. The Process table remains 1,028 bytes for eight slots. The console
metadata reservation is currently 880 bytes and the demo globals arena 4,096.
Height-capacity and pane fields will be accounted in F2 before enlargement.
Loaded command backing includes its existing 64 KiB text-alignment slack.

Six Tasks cover the shell, root and resident workers. One background command
and one foreground command fill the remaining two slots; a two-command pipeline
alongside that job must fail admission cleanly rather than enlarge the pools.
The six-row pane needs another console instance, not another worker Task.
Each background scope needs one child cancellation signal; the parent uses the
existing per-Process completion signal. Delay uses the DOS context's reply port.

The baseline reserves 25,408 runtime bank-zero bytes excluding OS ranges,
56,128 including OS ranges, and 52,592 bytes including OS during loading.
Fixed, root/kernel, idle, loading and each per-Task reservation delta in F0 is
**0 bytes**, including guards, alignment and unused capacity.

F1 uses a bounded native fixture for positioned retained cells and queued device
I/O, with row-edge rejection, cursor preservation, cancellation and ownership.
Later fixtures extend the same foundations through resize/cooked input, child
scope lifetime and shell launch, then one packaged bitmap walkthrough. Raw
checks cover small new ABI shapes; behavioral checks use optimized code.

Validation: all 391 host checks passed on the baseline. Console generation and
the F0 definitions are checked before committing this slice. No additional
emulator run is needed for these unused constants and documentation.
