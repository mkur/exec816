# Exec816

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../../README.md) and [history index](README.md).

Exec816 is an Exec-inspired multitasking kernel for the WDC 65C816, written in
Action! with a small assembly platform layer. Its first platform is
**AltirraOS 65816 running in Altirra**.

The core API namespace is `EXEC`. The kernel provides tasks, scheduling,
memory allocation, synchronization and message passing. A later bare-metal port
can provide another platform layer.

## Understand the system

| Guide | What it explains |
| --- | --- |
| [Exec816 overview](../architecture/overview.md) | The main parts, boot, commands and current capabilities. |
| [Tasks and execution contexts](../architecture/runtime.md) | What runs in each Task, what uses a stack/direct page, and how messages and ownership fit together. |
| [Filesystems and disk I/O](../architecture/filesystems.md) | One shared filesystem Task, per-mount ports, per-file state, caching and the separate SIO worker. |

For a hands-on introduction, use the [demo guide](../guides/demo.md).
Implementation plans live in [docs/plans](../plans/).

An initial [C binding for Calypsi](../guides/calypsi-c.md) provides classic Exec
headers and a small COP shim. Its standalone
[message example](../../c/examples/messages.c) runs a two-Task Amiga-style exchange.
The [OF816 boot monitor](../guides/boot-monitor.md) starts the standard shell/prime
image after a five-second countdown. Press a key to enter Forth, then type
`EXEC816` when ready to boot. Its bundle includes the companion SDFS disk.

The [library layout](../../lib/README.md) groups sources into `exec`, `dos`, `fs`,
`console`, `mydos`, `spartados` and `io` subsystems while retaining their Action module names.

## Status

The notes below retain individual implementation milestones and their validation
scope. Later milestones can supersede earlier limitations; the guides above
describe the current system organization.

The [general-task kernel](../guides/tasks.md) implements the classic Exec Task core:
AddTask, RemTask, FindTask, SetTaskPri, Forbid and Permit. Tasks have pointer
identity and caller-prepared records and stacks. The default profile has four user contexts,
including the initial root; a separate idle context runs when all users sleep.
VBI preemption, nested scheduling exclusion and serialized AltirraOS console
calls use the native context adapter. The scheduler uses a FIFO ready list and
ignores stored priorities for now.

The same Task kernel [implements signals](signals-implementation.md)
through AllocSignal, FreeSignal, SetSignal, Signal and Wait, with 32-bit masks,
Forbid restoration, direct Task association and an IRQ pending-wake queue.
Task and real-IRQ correctness pass. The
[shortened critical sections](kernel-critical-sections.md) let the IRQ
byte pump meet the 125 kbaud target during concurrent four-task Yield,
Signal/Wait and timed Sleep, with one signal per block. The
[allocator qualification](memory-allocation-implementation.md) also passes
four-task timing under allocation, fragmentation/query and CLEAR workloads.
The later [queued SIO qualification](device-io-sio-implementation.md)
covers eight-task timing with allocator, port and signal work. Per-byte worker
delivery has not been requalified after this change.
The [eight-task configuration](../architecture/task-capacity.md) supports eight live public
Tasks plus idle, with a compile-time kernel bank and upper-RAM bank table.
`--tasks` selects this single implementation; there is no `--task-api` choice.
Development changes require rebuilding callers. Memory allocation is complete
within its documented scope, as are the nine message/port APIs.

The [serial latency proof](sio-latency-poc.md) tests a minimal POKEY IRQ,
blocked worker and next-byte refill before the full stack. It meets the
125 kbaud target on the tested 8× PAL profile with direct native IRQ delivery,
fast ROM access and scoped SIO critical mode; the generic ROM path fails.
The integrated signal measurements above supersede that minimal experiment
for decisions about the full kernel path.

The [concurrent-kernel stress test](signals-concurrency.md) measures the
IRQ pump alongside Yield, Signal/Wait and timed Sleep, recording byte deadlines,
IRQ-masked intervals and identical uninstrumented replays.

The [public contract](../reference/tasks.md) and
[migration record](tasks-exec-update.md) describe the API and its development history.
The earlier [two-task preemptive](vbi-preemption.md),
[cooperative](cooperative-tasks.md), and
[single-program](native-launch.md) probes remain available for platform testing.

The [OS-boundary probe](os-boundary-probe.md) separately characterizes the
pinned ROM's native VBI, COP console calls, private-stack limitations, and actual
COP routing through 14 experiments.

Compiler and hosted qualification records apply to their recorded revisions and
PAL machine profiles. The current actionc pin includes
[compiler-supported `NULL`](compiler-null.md), checked with the shared
compiler suite and focused native/hosted tests. Current Process results are
focused development checks.

The current platform pins include a focused [native interrupt fix in the
emulator](emulator-native-irq-fix.md), found during Task qualification.
Use the recorded corrected bridge build when running the current test suites.

The [banked launcher and bank manager](banked-loading.md) add INITAD-based
loading into native upper RAM, a build-sized ownership table, and checked
whole-bank reservation/acquisition/release. The default banked profile covers
1 MiB; the original PAL/64K launches remain available.

The [memory allocation design](../reference/memory.md) follows classic
Exec's AllocMem/FreeMem, AllocVec/FreeVec and MemHeader/MemChunk model, with
ordinary bank-contained and linear allocation and explicit bank-zero requests.
It documents native deviations, IRQ-permitting serialization and preemptible
clearing. Allocation precedes message ports, queued SIO and DOS. The
[public services](../qualification/memory-exec-api.json) implement all eight
native imports, vectors and caller-side CLEAR. The [current ABI probes](../qualification/memory-exec-abi.json)
qualify classic declarations, flags and layouts. The [private free-list engine](../qualification/memory-exec-core.json)
passes raw/optimized model and fault tests. [Heap registration](../qualification/memory-exec-registration.json)
now claims upper RAM, rolls back failed startup and releases claims at shutdown.
[System policy](../qualification/memory-exec-policy.json) qualifies shared ordinary/LINEAR
placement and queries. [Concurrent qualification](memory-allocation-implementation.md)
covers shared lifetime, forced interrupt races, eight-task functional allocation
and four-task serial timing. No additional bank-zero reservation is required.
Older records describe the
[superseded prototype](memory-allocation.md). The
[implementation plan](../plans/memory-allocation-implementation-plan.md) defines six
executable slices with validation and a commit after each; all six are complete.

The [messages and ports implementation](messages-ports-implementation.md)
now provides task-context PutMsg, GetMsg, ReplyMsg and WaitPort with classic FIFO queues
and direct signal notification. The [design](../reference/ports.md)
documents storage lifetimes and the initial task-only calling contexts.
CreateMsgPort/DeleteMsgPort also provide explicit allocation and signal lifetime;
AddPort/RemPort/FindPort provide priority-ordered public discovery. See the
[named request/reply example](../../examples/messages.act). All six slices of the
[implementation plan](../plans/messages-ports-implementation-plan.md) are complete
and committed separately. Qualification covers eight live tasks with 17 ports
and four-task 125 kbaud TX under message/registry/allocator work, with zero
refill misses in raw/optimized 4,096- and 65,535-byte runs. Worker latency, RX
and turnaround have separate limits described in the implementation record.

For a small runnable introduction, see the [Amiga port1/port2 adaptation](../guides/messages.md):
two Tasks exchange one message, print the reply and release their resources.

The [queued device I/O and SIO implementation](device-io-sio-implementation.md)
provides the ten classic I/O calls and ordinary `sio.device` registration. One
worker owns the bus; native IRQs move bytes and advance the transaction while
clients wait and other tasks run. All eight [implementation slices](../plans/device-io-sio-implementation-plan.md)
are complete. Raw and optimized four/eight-task tests cover 125-kbaud and stock
READ/PUT transactions on the pinned emulator, cancellation, error recovery,
resource cleanup, and unchanged-image timing replay. The Happy profile supports
no-data commands only. See the read-only [device example](../../examples/device-io.act).
Broader peripheral profiles and physical-hardware qualification remain separate.

The [block I/O and DOS implementation](block-io-dos-implementation.md)
provides an AmigaDOS-style, read-only MyDOS API: Open, Read, Seek, Close, IoErr,
Lock, UnLock, Examine and ExNext, plus explicit ReleaseContext. It reads nested
8.3 paths, ten-/sixteen-bit sector links and 128/256-byte data sectors with three
short boot sectors. One filesystem worker serves all explicitly configured
mounts through the existing SIO worker. Ordinary Task builds support the
[read](../../examples/dos-read.act) and [directory](../../examples/dos-directory.act) examples;
[empty mount configuration](../../config/dos-mounts.json) creates no filesystem task.
FASTEST125 supports both sector sizes; STOCK810 supports 128 bytes. Filesystem
writes, automatic media changes, disk command loading and physical hardware are
outside this milestone. The [design](../reference/dos.md) documents native
API differences and media restrictions. All ten slices of the
[implementation plan](../plans/block-io-dos-implementation-plan.md) are complete.

Read-only [SpartaDOS filesystem support](../reference/spartados.md) now provides
SDFS 2.0/2.1 alongside MyDOS through the same DOS API and worker. New shell/demo
bundles default to SDFS; an explicit MyDOS build option remains available.
Stored lengths make seeking independent of disk I/O, and directory listing
uses metadata without reading ordinary-file contents. The six
[implementation slices](spartados-implementation.md) include independent
fixtures, mixed mounts, cancellation and a measured play image. Writes,
512-byte sectors, release qualification and real hardware remain separate.

The resident [Process API](../reference/process.md) now runs registered commands
in child Tasks with copied arguments, inherited streams/current directory,
independent DOS contexts, foreground handoff, automatic DOS-object cleanup and
safe result collection. P1–P3 passed focused raw/optimized development checks;
full release qualification and disk-loaded commands remain pending. The public
Task ABI and bank-zero reservations are unchanged.
The earlier [integrated qualification](block-io-dos-implementation.md#slice-10-concurrent-filesystem-qualification)
covers raw/optimized builds, four/eight live tasks, kernel banks 1/3 and both
sector sizes. Observed bank-1 runs meet the 125-kbaud wire deadline and replay
identically without tracing. The handler serializes whole operations: large-file
workloads expose queue waits up to 54 seconds despite passing wire timing.
The separate [single large-read probe](dos-read-throughput.md) verifies one
70,003-byte Read with three live tasks. Removing the successful-transfer sleep
raises throughput from 2,521 to 4,193 bytes/s with mechanical disk timing
disabled. Accurate floppy timing remains limited by the emulated interleave.
Errors retain their recovery delay and uncertain transfers leave the bus offline.

The native [console](../reference/console.md) now supports keyboard input and
40×24 text output through ordinary `console.device` READ/WRITE/CLEAR requests.
Enable it with `--console` and try the [resident DOS example](../guides/console-example.md).
One worker uses an existing task slot; retained cells and input state live in
upper RAM, with no added bank-zero reservation. All eight
[implementation slices](console-io-implementation.md) are complete.
[Eight-task qualification](../qualification/console-concurrency.json) passes
raw/optimized code, real MyDOS reads, physical input, scrolling output and
125 kbaud SIO, including identical-image replays. Heavy scrolling can delay
visible echo by about one second. Multiple independent text windows and focus
remain the required [follow-up](../plans/console-io-implementation-plan.md#required-multiwindow-follow-up),
using the existing separation of console state and presentation.
The subsequent [idle-scrolling optimization](console-scrolling.md) reduces
optimized full-screen scrolling from about 319 to 98 ms per line without I/O,
with unchanged bank-zero reservations and bounded worker quanta.

The [DOS console streams](../reference/streams.md) provide task-owned
`RAW:`/`NIL:` handles, `Write`, and task-local Input/Output selection. All seven
[implementation slices](dos-console-streams-implementation.md) are complete.
Caller-side adapters use the existing console worker and bypass the filesystem
queue, adding no Task or bank-zero reservation. Try the
[resident streams example](../guides/streams-example.md), including file/NIL
redirection and disk progress during a pending keyboard Read.
[Eight-task stream qualification](../qualification/dos-streams-concurrency.json)
covers raw/optimized code, a complete 70,003-byte read, physical input/output and
125 kbaud SIO with identical-image replays. FIFO scrolling can delay visible echo
up to 1.7 seconds in this historical workload. [Cooked `CON:`](../reference/cooked-console.md)
now supplies bounded editing, partial line reads and EOF over the shared endpoint.
[Physical qualification](console-interaction-implementation.md#c2-physical-con-backend)
passes in raw/optimized code. [Foreground break delivery](../reference/foreground-break.md)
now supports polling scopes and retained capture identities, interruptible waits
and shell command cancellation. Processes inherit handles; independent windows
have development coverage, with window release qualification still pending.

The [resident shell](../guides/shell.md) provides HELP/ECHO/CD/DIR/TYPE/MEM/EXIT,
bounded CON: editing, current-directory navigation and per-command redirection.
All eight [implementation slices](shell-implementation.md) are complete,
including eight-task concurrency, complete 70,003-byte reads and 125 kbaud SIO
qualification in raw and optimized code. It runs in the root Task with three
existing services, adding no bank-zero reservation. Built-ins remain synchronous;
shared scrolling can delay the next prompt. The
[native program loader](../reference/program-loading.md) now runs exact-path
o65 commands with inherited streams, a private argument tail and safe Image
retirement. Its [integrated qualification](o65-loading-implementation.md#l4-integrated-lifetime-and-transport-qualification)
covers raw/optimized lifetime, failures, multi-bank code and serial timing with
replay. Window release qualification remains separate.

The [text-console demo](../guides/demo.md) combines a 40×18 shell with a 40×6 prime
search, disk-loaded HELLO/CAT/WC commands and two-stage pipes.
The file to share is `build/demo/exec816-demo.zip`, containing only the boot
files, a short guide, license notices and checksums.
`python3 tools/build_demo.py` always includes OF816: boot
`build/demo/of816/of816-exec.xex` with its matching `sdfs.atr` and bundled
`altirraos-816.rom`. Upstream license notices are included. BREAK cancels both pipeline
stages while the prime search continues; EXIT collects the worker and restores
the OS. It uses seven of eight Task slots at peak and adds no reserved bank-zero
memory. See the [demo implementation record](demo-implementation.md) for
focused development evidence; full release qualification remains separate.

Implementation and remaining qualification are tracked in the plans for
[console interaction](../plans/console-interaction-implementation-plan.md),
[Process lifetime](../plans/process-lifetime-implementation-plan.md), and
[o65 loading and external commands](../plans/o65-loading-implementation-plan.md).
The [plan index](../plans/interactive-programs-implementation-plan.md) records their
dependencies and shared validation and memory requirements.

The [Lists library](../reference/lists.md) follows classic Exec sentinel lists, with
MinList/MinNode and full List/Node records, priority insertion and name lookup.
It uses native 24-bit links and caller-managed synchronization. Headers and nodes need
no allocator and can occupy separate banks. The general-task scheduler uses
these primitives for its ready queue.

## Initial design

- Use `action65816.native.v2` with the [partitioned direct page](direct-page-partition.md).
- Reserve `COP #$50` as the Exec gateway, with a separate service selector.
  Preserve AltirraOS's `COP #$00` service and WDC's `$80-$FF` reservation.
- Use vertical-blank NMI as the preemption tick, with explicit deferral during
  protected operations and OS calls, and scheduling after OS interrupt return.
- Access AltirraOS services through a serialized adapter that establishes and
  restores the required stack, CPU mode and register conventions.
- Keep compiler behavior and generic compiler qualification in actionc;
  keep kernel policy, platform integration and system tests here.

See the [platform contract](../reference/platform.md),
[implementation roadmap](../roadmap.md) and
[contributor instructions](../../AGENTS.md).
The [code style guide](../contributing/style.md) records the conventions for readable
Action! commands, libraries and kernel code.
The [testing policy](../contributing/testing.md) separates routine development checks from
full release qualification.

## Compiler dependency

The build uses actionc to emit 65816 machine code and data for Action! sources.
**ca65** assembles the handwritten platform code, including startup, interrupt
handlers, gateways and device adapters; **ld65** links those assembly objects.
The Python [packager](../../tools/native_program.py) supplies the assembled service
addresses to actionc and combines both outputs into the final XEX. See the
[build pipeline](native-launch.md#build-pipeline) for details.

[toolchain/actionc.json](../../toolchain/actionc.json) pins the compiler:

- Repository: <https://github.com/mkur/actionc>
- Revision: `c384bc8da9e62a280ecb4998e4d275bc6e45935f`
- Target: `wdc-65816-native`
- ABI: `action65816.native.v2`
- Native image format: version 3

This pin includes local compiler commits that have not been pushed. The
[DP migration record](direct-page-partition.md) links the retained patches.
Use a clean checkout containing that revision, such as this workspace’s
`build/actionc`:

```sh
git -C build/actionc checkout --detach c384bc8da9e62a280ecb4998e4d275bc6e45935f
cargo build --locked --manifest-path build/actionc/Cargo.toml --bin actionc-65816
```

This builds the compiler only. Follow the [general-task instructions](../guides/tasks.md),
[banked loading instructions](banked-loading.md),
or the [preemptive example instructions](vbi-preemption.md#build-and-run),
[cooperative example instructions](cooperative-tasks.md#build-and-run)
or [single-program instructions](native-launch.md) to package and run an example. Build tooling accepts an explicit compiler
checkout, requires the clean pin by default, and records explicit local overrides.

See [build cleanup and artifact restoration](build-cleanup.md) for the local
historical-run archive and commands to restore earlier qualification outputs.

ABI JSON and assembly constants must come from the same compiler revision.
The [compiler issue audit](compiler-issues.md) distinguishes corrected
defects from the backend and stack limits that shape Exec816 code.
The [compiler migration qualification](compiler-ae1f555-qualification.md)
covers image-v3 validation, native execution and the hosted kernel/DOS/console
matrix, with unchanged bank-zero reservations. The subsequent
[stack-check setting qualification](../contributing/stack-checks.md) covers `2d73c03`
and its checked/unchecked builds. On 2026-09-24 the pin advanced to actionc
main at `32af3e2b`; compiler qualification is deferred. Existing execution
records retain their original compiler revisions and do not qualify this pin.
The pinned compiler's
[emission contract](../../build/actionc/docs/MIR65816_EMISSION_CONTRACT.md)
and [migration record](../../build/actionc/docs/NATIVE_DP_PARTITION.md)
describe its supported subset and limits.

The [compiler memory-fix record](../qualification/compiler-memory-fix.json)
describes the native absolute-array correction, focused execution checks and
two pre-existing TN sample failures reproduced at the previous compiler pin.
The [Lists compiler-fix record](../qualification/compiler-lists-fix.json)
covers named record-pointer casts, their native execution checks, and the same
two TN failures at that earlier pin. The correction is published on
`fix/65816-record-pointer-casts` in actionc.
