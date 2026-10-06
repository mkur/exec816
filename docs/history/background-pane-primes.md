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

The initial six-Task idle estimate was corrected by F4: the standard shell has
four live Tasks. One background command and a two-command foreground pipeline
bring that to seven, within the eight-slot pool. Admission at capacity must
fail cleanly rather than enlarge the pools.
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

## F1 Positioned writes

`COMMAND.WriteAt` is implemented through DOS and the existing console write
FIFO. One-row ASCII validation precedes editing; the worker commits bounded
spans without moving the stream cursor. An unchanged bitmap caret outside the
dirty span is now retained instead of being restored and redrawn.

The [F1 record](../development/background-pane-primes-f1.json) contains optimized
text-console behavior, a raw mixed-argument ABI probe and final optimized bitmap
pixels/drawing. It covers ring addressing, bank-crossing source, bad coordinates,
row overflow, controls, negative/zero lengths, non-console rejection, sticky
BREAK, FIFO order, queued abort, exact replies and leak-free context retirement.
The final bitmap observer saw one five-glyph draw per update, with no fill,
copy, scrolling or label repaint. Host checks: 391 passed.

The provider adds 33 payload bytes, making the complete published manifest
1,456 bytes for 43 providers, inside its existing 1,664-byte reservation.
No new object, worker or permanent buffer is allocated. Fixed, root/kernel,
idle, loading and per-Task bank-zero reservation deltas are **0 bytes**.
Development checks do not qualify the release or physical hardware.

## F2 Height changes and owned panes

Fixed-width resize preserves the original backing capacity, endpoint, cursor
column, input route and cooked draft. One shared 80-byte upper row normalizes
circular cells; growing restores blank rows. The pane is an ordinary owned DOS
output handle whose Close/finalizer restores the parent before child retirement.
Prepared allocation failure unwinds without changing the layout.

The [F2 record](../development/background-pane-primes-f2.json) records optimized
text and bitmap checks, a raw retained-layout probe, allocation rollback, second
pane rejection and child error cleanup during an active edited Read. The draft
`ab` survives restoration, then completes as `abc`. Exact reply, domain, stack
and ownership checks pass. All 391 host checks passed.

The instance's capacity field consumes former alignment padding; the layout
association moves bitmap metadata four bytes within the existing 880-byte
reservation. Dynamic instances still round to 208 bytes. Providers use 1,490
bytes for 44 entries. Fixed, root/kernel, idle, loading and per-Task bank-zero
reservation deltas are **0 bytes**. These are development results.

## F3 Background cancellation and timer delay

Background starts keep the existing inheritance/trampoline and add a private
scope without a keyboard route or parent suspension. The Process row's four
tail bytes store flags and its published scope pointer. RequestBreak uses owned
identity lookup, latches early requests, coalesces repeats and preserves saved
completion. Foreground loans and pipeline followers also publish their scopes.
Task-side Forbid protects publication and signaling; cleanup unpublishes before
freeing. IRQ/NMI paths do not follow these pointers.

The [F3 record](../development/background-pane-primes-f3.json) records optimized
early-stop, allocation rollback, real timer waits/aborts, stale/foreign identity
rejection, completion wins and foreground restoration. Physical BREAK stops the
parent's cooked Read while the background wait continues; the parent then reads
normally and requests child cancellation. Raw probes cover new call shapes and
layouts. Exact collection, ownership and stack/domain guards pass; 391 host
checks passed.

Each background scope uses 56 requested/56 rounded upper bytes and one child
signal. The DOS context grows from 94 to 98 requested bytes, or 96 to 104
rounded bytes. Delay lazily caches a 38-byte clock/alarm request (40 rounded)
with the existing reply port and timer binding slots. The Process table remains
1,028 bytes. Providers occupy 1,521 of the reserved 1,664 bytes for 45 entries.
Fixed, root/kernel, idle, loading and per-Task bank-zero deltas are **0 bytes**.

## F4 One shell-owned background job

RUN uses the ordinary parser, aliases, PATH and original argument tail. It
selects NIL streams by default, rejects interactive redirection and background
pipelines, and restores the shell streams immediately after launch. JOBS collects
at command boundaries; BREAK requests cooperative stop by Process identity.
EXIT waits for cleanup and collection. Background OpenConsole requires a bound
interactive scope, so an independent job cannot borrow the shell's keyboard.

The [F4 record](../development/background-pane-primes-f4.json) covers actual
loaded commands, aliases, quoting, stream/directory inheritance, natural and
requested completion, stale identities, restart and EXIT. Two ordinary Tasks
occupy spare slots to check clean eight-Task admission failure while a foreground
command still fits. The earlier six-Task estimate was a workload peak, not an
idle worker count; panes add no worker. Persistent C: mapping storage is removed
explicitly by the fixture before its final heap comparison.

The shell reuses padding in its 128-byte state and adds a 14-byte upper job row
within the existing 4 KiB globals arena. The provider manifest remains 1,521
bytes for 45 entries. Fixed, root/kernel, idle, loading and per-Task bank-zero
reservation deltas are **0 bytes**. These are development checks.

## P1 Loadable primes and numeric fields

PRIMES uses a private bit sieve through 10,000, bounded calculation batches,
interruptible delay and one six-row output pane. Labels are written once.
Count/latest/pass use separate padded fields and are sent only when changed;
the saved values advance only after a complete, successful positioned write.
PASSES counts finite passes; omitted or zero runs continuously.

The [P1 record](../development/background-pane-primes-p1.json) covers the shared
calculation against the real resident providers, known results (1,229/9,973),
digit growth/shrink, unchanged fields, cancelled paint without advancing the
cache, foreground completion and background stop. Heap, ownership and guards
return to baseline. The production source also compiles as an o65 command;
packaged loading and bitmap drawing follow in P2.

The optimized command has 5,405 text bytes and 1,416 private BSS bytes, including
the 1,251-byte sieve. Its disk file is 6,554 bytes. The existing loader alignment
slack is recorded separately. Fixed, root/kernel, idle, loading and per-Task
bank-zero reservation deltas are **0 bytes**. These are development results.

## P2 Shared demo startup and packaged bitmap walkthrough

The optional automatic demonstration now runs `RUN PRIMES` through the shared
shell. Its resident sieve, duplicate Process lifetime and complete-frame refresh
loop are removed. The full-screen bitmap selection includes `C:PRIMES` among
its 17 commands and starts without a background job. The OF816 preview includes
matching 720 KiB system/work disks, ROM, guides, notices and checksums.

The [P2 record](../development/background-pane-primes-p2.json) covers physical
keys, actual loaded code and independent bitmap pixels: RUN/JOBS, HELLO,
foreground pipeline, COPY/CMP, rejected second job/pane, edited input, Ctrl-L,
isolated foreground BREAK, requested stop, stale identities, restart, finite
completion and EXIT with a live job. Natural completion restores the full
screen and preserves a draft while the shell remains inside cooked Read.
The separate text fixture exercises the refactored automatic startup and exit.

Two observed steady updates each issue two positioned writes and draw ten
glyphs, with no fill, scroll, copy or label redraw. The sieve's finite result is
1,229 primes and latest 9,973. The shell has four idle Tasks; the job adds one,
and a foreground two-command pipeline fits within the existing eight slots.
Guards, ownership and OS display/input restoration pass. All 391 host checks
pass; these focused runs are development evidence, not release qualification.

The command costs recorded in P1 are unchanged. Fixed, root/kernel, idle,
loading and per-Task bank-zero reservation deltas are **0 bytes** relative to
F0. The existing bitmap profile's two enlarged Task stacks remain accounted
separately from the historical text compaction baseline.
Current heap accounting uses eight-byte alignment. P2 corrects the earlier
16-byte rounded estimates for scope/context/timer and command BSS; the archived
F3/P1 records retain their original estimates and execution hashes.
