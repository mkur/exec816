# VBI preemption under AltirraOS

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

The `--preemptive` launcher runs two native Action! tasks on the
[pinned AltirraOS machine](../../toolchain/altirra.json). Both tasks can make
progress without voluntary yields. It retains the cooperative task records,
stack/domain allocations, COP `$50` ABI and Action! scheduling policy described
in [cooperative tasks](cooperative-tasks.md). No compiler change is required.

## Build and run

Prepare the pinned compiler, ROM and emulator as described in
[native launch](native-launch.md), then build:

```sh
python3 tools/native_program.py --compiler-dir build/actionc --preemptive \
  --source examples/preemptive.act --output build/preemptive
```

Open `build/preemptive/program.xex` in the pinned Altirra configuration. Add
`--bridge-dir /path/to/AltirraBridge-nightly-macos-arm64` for a headless run.
`--preemptive` implies the two-task launcher; `--cooperative` alone retains
explicit cooperative scheduling.

The [example](../../examples/preemptive.act) prints `A0` through `A3` and `B0`
through `B3`. Each task's lines remain ordered; their interleaving depends on
VBI timing. Both enter the same recursive routine with independent locals.
Its leaf publishes a round counter and waits for the peer through volatile
memory, without calling any kernel or OS service. Running that image with
cooperative scheduling stalls at the first wait. Both tasks return normally
after four rounds, leaving totals 132 and 144.

## Tick and dispatch contract

The platform hooks the OS's immediate VBI vector, `VVBLKI`, and chains to its
saved target. The pinned ROM reaches this hook in emulation mode for both a
native task's VBI and VBI during an emulation-mode COP `$00` call. The hook
records a coalesced pending tick and increments a diagnostic counter. It does
not call Action!, use any direct-page scratch, switch stacks or schedule.
The original OS VBI stages still maintain the clock, keyboard and display.
The pin disables DLI; display-list interrupts are not a source of ticks.

Native NMI/IRQ adapters first save the full 13-byte context, select or retain
the OS stack and run the saved ROM handler. After it returns, the adapter
masks IRQs, retires the complete OS activation, and restores S to the saved
native frame. Only then can it consider dispatch. Eligibility requires:

- A pending tick and no active context transition.
- No live native IRQ activation and no busy OS adapter.
- Original I clear and the current task's owned stack and D in the saved frame.

Ineligible returns restore their interrupted context without consuming the
global tick. Eligible returns use the kernel stack/domain and call the same
Action! dispatcher as COP, selecting `Poll`. The policy preserves nested task
locks, selects the other ready task when allowed, and returns a complete frame
for restoration with RTI. Raw A (including hidden B), X/Y, D, DBR, P, PC and PBR
remain part of that frame. This original qualification uses code in bank zero; the separate
[banked qualification](banked-loading.md) also exercises upper-bank code.

IRQ return can deliver a VBI tick that arrived during IRQ work. An IRQ alone
does not generate a scheduling request. Emulation-mode OS calls keep their
live stack until they return; the console adapter's existing Poll delivers
pending work after restoring its native caller context. Blocking OS calls
continue to delay both tasks.

## Asynchronous state protocol

Hardware entry keeps I set through all kernel work and partial context
restoration. SEI does not mask NMI. The transition flag and saved-frame checks
prevent a nested NMI from borrowing the kernel stack/domain or dispatching a
partially saved context. Nested interrupt adapters keep their own saved S on
the OS stack and do not touch compiler scratch. A native IRQ depth counter
also excludes its live activation from scheduling.

Only the VBI hook sets the global tick byte. A dispatcher consumes it with a
single byte-sized `TRB`, then transfers the request to the current task's
pending field. NMI cannot interrupt that instruction. A tick arriving after
the consume stays in the global byte for another safe boundary; policy cannot
overwrite it. Per-task pending fields are accessed only within serialized
dispatch.

The transition flag is set before selecting the kernel stack and cleared
after selecting the final task stack, with I still set. Main-return diagnostics
are also collected with IRQs masked to prevent task switching between their
shared writes. The captured original flags are checked before task exit.

An outer unlock, console return or explicit Poll delivers pending work when
eligible. A task that clears I or another guard without calling the kernel
can resume scheduling at the next eligible VBI return. A tick that arrives
during dispatch or restore is retained for a later boundary; clearing the
transition flag alone does not start a second dispatch.

The existing 256-byte interrupt reserves remain unchanged. The task-side
reserve covers a full 13-byte frame, a two-byte helper/temporary save and a
nested 13-byte interrupt frame. Ordinary Action! stack costs remain checked
against each domain's floor. Guards surround all task/kernel stacks, direct
pages and the supported page-one OS stack. The supported nesting remains
the pinned ROM's bounded VBI/IRQ handling; DLI, third-party callbacks and OS
handlers lasting an entire video frame remain outside this contract.

The additional state is defined in the
[generated ABI input](../../abi/exec816-v1.json):

| Address | Purpose |
| --- | --- |
| `$202E-$202F` | Saved immediate VBI vector |
| `$2030` | Global pending tick |
| `$2034-$2035` | VBI count, including ticks in emulation mode |
| `$2036-$2037` | Eligible interrupt dispatch count, including deferred IRQ returns |
| `$2038-$2039` | Native IRQ depth |

Exit/fault cleanup restores `VVBLKI` along with the native COP/NMI/IRQ vectors
and MEMLO. The launcher then parks under the OS as before. This launch mode loads code and data in bank zero. Add `--banked` for the
[INITAD loader and upper-RAM profile](banked-loading.md).

## Qualification

```sh
python3 tools/generate_exec_abi.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_preemptive.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
python3 tools/test_cooperative.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
python3 tools/test_hosted.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

The 60-case preemption matrix covers raw and optimized code: the no-yield example and
its cooperative negative control, nested locks with repeated deferred ticks,
all M/X combinations, hidden B, decimal mode, DBR/direct-page restoration,
IRQ-masked deferral and Poll delivery, COP forwarding, real POKEY timer IRQs
and injected keyboard input. Eighteen real-VBI checkpoints cover console and
kernel stack transitions, partial saves/restores, the atomic tick consume,
and VBI inside a live emulation-mode OS call. Probe-only instructions are
absent from production builds.

Positive cases must finish within 120 emulated frames and check output,
task state, guards, domain metadata, OS clock progress and vector/MEMLO
restoration. Negative controls run eight frames and check that only the first
task reached its initial wait. Reports are written to `build/preemptive-tests/`;
the accepted record is [qualification/vbi-preemption.json](../qualification/vbi-preemption.json).
