# Two cooperative tasks under AltirraOS

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

Exec816 can launch two native Action! tasks under the pinned AltirraOS 65816
configuration. Both enter the image's zero-argument main procedure, share its
globals and code, and own separate stacks, invocation locals and direct pages.
`EXEC.TaskId()` distinguishes task 0 from task 1. Scheduling policy is written in
[Action!](../../lib/exec/execpolicy.act); assembly owns context entry, restoration and the
OS boundary. No compiler change or compiler-pin override is required.
The separate [preemptive mode](vbi-preemption.md) adds VBI scheduling; the
`--cooperative` mode documented here retains voluntary scheduling.

## Build and run

Prepare the compiler, ROM and emulator using the
[native launch instructions](native-launch.md). Build the example with:

```sh
python3 tools/native_program.py --compiler-dir build/actionc --cooperative \
  --source examples/cooperative.act --output build/cooperative
```

Open `build/cooperative/program.xex` in the pinned Altirra configuration. Add
`--bridge-dir /path/to/AltirraBridge-nightly-macos-arm64` for a headless run.
The [example](../../examples/cooperative.act) prints `A0`, `B0`, `A1`, `B1`, through
`A3`, `B3`, one per line. It yields inside recursive calls to the same routine,
then returns normally from both tasks. The display remains visible while the
OS continues running. There is no DOS return or dynamic task creation yet.

Cooperative programs use `MODULE ...` and `USE EXEC`. The module brings in the
policy implementation. The packager validates native import interfaces and
the compiled `EXECPOLICY.Dispatch(CARD saved, BYTE service)` callback before
binding their machine addresses. Single-program builds remain available
without `--cooperative`.

## Public API and COP ABI

[lib/exec/exec.act](../../lib/exec/exec.act) declares the ordinary native Action! API.
The underlying ABI is `exec816.cop.v1`, defined in
[abi/exec816-v1.json](../../abi/exec816-v1.json). Regenerate its shared assembly and
Action! constants with `python3 tools/generate_exec_abi.py`; `--check` rejects
stale generated files. The builder also checks the policy's frame offsets
against the pinned compiler's ABI JSON.

`COP #$50` selects Exec. A's low byte selects a service; Exit uses X's full
16 bits for its code. Entry is native mode on the current task's stack with
its owned D. Raw callers may use any M/X width, flags or DBR. The complete
native register frame is preserved, except for services that return A.
The ordinary Action! wrappers retain `action65816.native.v2` boundaries.

| Selector | Action! call | Result and behavior |
| --- | --- | --- |
| `$00` | `CARD EXEC.Version()` | `$0100`, major 1/minor 0 |
| `$01` | `EXEC.Yield()` | Request the next ready task; preserve raw A |
| `$02` | `EXEC.ExitTask(CARD code)` | Terminate this task and retain its exit code |
| `$03` | `CARD EXEC.TaskId()` | 0 or 1 |
| `$04` | `CARD EXEC.Lock()` | Increment the task's nested scheduling lock; return 0 |
| `$05` | `CARD EXEC.Unlock()` | Decrement the lock; deliver pending yield at depth zero; return 0 |
| `$06` | `EXEC.Poll()` | Deliver an existing pending yield at a safe point; preserve raw A |

Locks prevent scheduling; they do not disable hardware interrupts. A yield is
deferred while the interrupted P has I set, the current lock depth is nonzero,
or the OS adapter is busy. Pending requests are coalesced per task. An outer
unlock or the console adapter's return polls for delivery; code restoring I
after a masked yield must call `EXEC.Poll()` or yield again. Simply clearing a
guard does not schedule. Poll without a pending request does not switch.

Unknown selectors return `$FF10` in full A. A foreign D/stack or an entry during
a switch returns `$FF11`. Lock overflow, unlock underflow and a protected raw
Exit return `$FF12`. All preserve the other raw registers and saved flags.
The nonreturning `ExitTask` wrapper turns a refused Exit into terminal launch
fault 4. Calling a terminating service while holding a lock is therefore an
error. Arbitrary OS/interrupt callbacks into Exec are unsupported.

An ordinary main return checks the task's stack/domain and exits with code 0;
it requires the ordinary native ABI and I clear. Exiting removes the task from
rotation. A surviving task can continue yielding to itself. When both tasks
exit, the launcher restores the native COP/NMI/IRQ vectors and OS memory
reservation and parks in emulation mode with VBI/IRQ enabled. This is a trusted
kernel with shared address space, without memory protection or fault isolation.

All other COP signatures chain to the saved `VCOPN` dispatcher. In particular,
the console adapter's COP `$00` still reaches the ROM. Qualification also covers
`$01` and `$7F` forwarding to this ROM's existing COP0 route. Exec never allocates
or probes the WDC-reserved `$80-$FF` signatures.

## Memory and saved contexts

The [single-program map](native-launch.md#loader-contract) remains the base.
Cooperative images keep the `$6000-$8FFF` arena, with data starting at `$8800`
to accommodate policy code. Additional fixed allocations are:

| Allocation | Purpose |
| --- | --- |
| `$2020-$2033` | Saved COP vector, current task, transition flag, counters and OS owner |
| `$2040-$204F`, `$2050-$205F` | Task 0 and task 1 records |
| `$2060` | Kernel domain owner identity |
| `$2080-$20BF` | Qualification snapshots; unused by production tasks |
| `$2400-$24FF` | Task 1 direct page, owner `$2050`, task domain |
| `$2600-$26FF` | Kernel direct page, owner `$2060`, IRQ/dispatch domain |
| `$4A00-$4AFF` | Kernel interrupt reserve |
| `$4B00-$4FFF` | Kernel ordinary stack, initial S=`$4FFE` |
| `$5200-$52FF` | Task 1 interrupt reserve |
| `$5300-$57FF` | Task 1 ordinary stack, initial S=`$57FE` |

Task 0 retains D=`$2200`, ordinary floor `$4300`, initial S=`$47FE`, and now
uses owner `$2040`. Each new direct page and stack has 16-byte guards before
and after its allocation. Fixed domain metadata and reserved bytes are checked
after every run. Stack floors leave 256 bytes below ordinary reservations;
this covers the 28-byte task-side peak of COP save, frame validation and a
nested full native NMI save. OS handlers run on the separate page-one stack.
These bounds exclude third-party drivers and arbitrary interrupt nesting.

The generated 16-byte task record contains saved S, state, ID, 16-bit lock
depth, pending flag and 16-bit exit code. The compiler ABI defines the full
13-byte frame at saved S: DBR, D, Y, X, full A, P, PC and PBR. Task 1 starts
from a fabricated full frame above a normal zero-argument native call frame;
task 0 uses an actual JSL. Both reach the same return continuation.

## Interrupt and transition protocol

COP hardware sets I. The gateway saves all registers before using them,
normalizes decimal mode/DBR, and uses the dedicated kernel direct page for
signature lookup. Task scratch is untouched. It checks ownership, marks the
transition active and changes to the kernel stack. Dispatch runs with I set,
updates the task records and selects a complete saved frame. The gateway
validates that frame, selects its stack, clears the transition flag while I
is still set, then restores registers and RTIs to the original P/PC/PBR.

SEI does not mask NMI. The existing passive NMI/IRQ adapters remain active
throughout these steps. They save the interrupted state on whichever stack
is physically selected, keep their saved S on the OS stack, and restore that
exact state. They never access task/kernel scratch, call Action! policy, or
change the current task. The supported interrupt configuration is one VBI
activation, DLI disabled, with VBI permitted during native IRQ processing.
An entire-frame OS handler or reentrant third-party handler is unsupported.

The console adapter marks OS ownership with the current task ID. Its live
saved S and COP target stay on the OS stack until the ROM call returns. Only
after retiring that activation and restoring the private stack does it clear
busy/owner state and poll for a pending yield, preserving the CIO result.
This prevents a suspended task from retaining the shared OS stack. Blocking
OS I/O still delays both tasks.

VBI advances OS services but **does not preempt tasks in cooperative mode**.
The [preemptive mode](vbi-preemption.md) has its own eligibility protocol and
qualification, including pending ticks during emulation-mode OS calls.

## Qualification

```sh
python3 tools/generate_exec_abi.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_cooperative.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
python3 tools/test_hosted.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

The cooperative suite covers raw and optimized output: shared recursion and
local isolation, output order, normal/explicit exits and a sole survivor,
nested locks, overflow/underflow, deferred OS-return delivery, every M/X
combination including hidden B and nonzero DBR, IRQ-masked yield and Poll,
unknown/foreign-context/protected-exit errors, COP forwarding, twelve real-NMI
transition checkpoints, and real POKEY timer IRQs. Gateway NMI probes also use
the narrow-register context test. WAI checkpoints and register probes emit no
production instructions. All cases have bounded completion and check guards,
domain metadata, task state and restoration of OS vectors/MEMLO.

Run one case with `--case registers-f9-opt`, for example. Reports and binaries
are in `build/cooperative-tests/`; the accepted result is recorded in
[qualification/cooperative-tasks.json](../qualification/cooperative-tasks.json).
This qualifies the pinned cold-launch, PAL/64K console configuration only.
