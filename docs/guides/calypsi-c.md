# Calypsi C binding

The initial C target is a standalone Exec816 XEX containing the native kernel,
console bootstrap and a Calypsi program. Start with
[messages.c](../../c/examples/messages.c): two Tasks exchange a message carrying
`10,20`; the receiver adds 50 and replies with `60,70`. Press Return to restore
the OS display and exit.

The example adapts the small port1/port2 exchange described in the
[Amiga RKM messages and ports chapter](https://wiki.amigaos.net/wiki/Exec_Messages_and_Ports).
It uses classic Exec calls and record names, including `CreateTask` from
`<clib/alib_protos.h>`. Both sides run in one executable. Startup and completion
use signals; there is no Exec816-specific header, Yield loop or Task-state polling
in the shared source. The C main routine prints through `Write(Output(), ...)`;
the Action! bootstrap opens the console and lends its handle as standard output. This is
source compatibility, not an Amiga binary ABI or a complete Amiga SDK.

## Build and run

Install Calypsi 65816 **5.18** with `cc65816`, `as65816` and `ln65816` on PATH.
The build uses `--code-model=large --data-model=huge`. The existing Exec816
build prerequisites and pinned actionc checkout are also needed.

```sh
python3 tools/build_calypsi.py
```

Open `build/calypsi/messages/program/program.xex` using the
[pinned hosted configuration](../../toolchain/altirra-shell-paced.json).
`build/calypsi/messages/c-image.json` records the C executable, tool versions
and hashes, runtime archive hash, source inputs and emitted layout checks.
The native build record also contains this provenance. No compiler-pin update
or play-image replacement is needed.

To build a different message-exchange example, start by editing `messages.c`.
The small builder currently expects `main` and the `Receiver` Task entry. The
development runner observes `received_x`/`received_y` and `same_message`. Add further
Task entry names explicitly to the builder's registration list; ordinary
function addresses are not automatically admitted as Task entries.

## Supported interface

Include `<exec/types.h>`, `<exec/tasks.h>`, `<exec/ports.h>`, `<exec/memory.h>`
as needed, and `<proto/exec.h>` for the function declarations.

| Area | Calls |
| --- | --- |
| Memory | `AllocMem`, `FreeMem`, `AvailMem` |
| Tasks | `CreateTask` (in `<clib/alib_protos.h>`), `AddTask`, `RemTask`, `FindTask`, `Forbid`, `Permit` |
| Signals | `AllocSignal`, `FreeSignal`, `SetSignal`, `Signal`, `Wait` |
| Messages | `CreateMsgPort`, `DeleteMsgPort`, `PutMsg`, `GetMsg`, `WaitPort`, `ReplyMsg` |
| Public ports | `AddPort`, `RemPort`, `FindPort` |
| Lists | `NewList`, `IsListEmpty` |
| DOS output (`<proto/dos.h>`) | `Output`, `Write` |
| Exec816 extension | `ExecYield` in `<exec816/runtime.h>` for low-level probes |

These retain Exec816's existing [Task](../reference/tasks.md),
[signal](../history/signals-implementation.md) and [port](../history/messages-ports-implementation.md) contracts and
restrictions. For example, `WaitPort` observes the head without removing it;
`GetMsg` removes it. A port belongs to the Task that creates it. Delete an empty,
unregistered port in its owner. Hold `Forbid` across public-port discovery and
the send, then `Permit`.

CreateTask accepts a borrowed name, signed 32-bit priority, registered entry and
unsigned 32-bit minimum stack allocation. The allocation includes interrupt
headroom and may select a larger existing pool. The kernel selects and owns the
Task record; failures return NULL. The C shim rejects pointers outside 24 bits
before narrowing them. It does not scan or reserve pools itself.

A managed result is borrowed and may already be retired when the call returns.
Do not free it or poll it after removal. Use Forbid across any initial setup that
requires a live Task. The example's final notification uses
`Forbid(); Signal(sender, done_mask); RemTask(NULL)` after cleanup, ensuring that
the sender resumes only after retirement. A normally returning entry also uses
native default self-removal. AddTask remains available for caller-owned records
and custom finalizers, whose entries must also be registered.

The constants and COP selectors are generated from `abi/*.json`:

```sh
python3 tools/generate_calypsi.py --check
```

## Representation and call boundary

`BYTE`/`UBYTE` are 8 bits, `WORD`/`UWORD` 16, and `LONG`/`ULONG` 32. Ordinary
C pointers use Calypsi's four-byte huge representation. Pointer fields shared
with Exec use `__far24`, giving the native three-byte layout. Explicit Task
padding preserves its native offsets. Node/List/Task/MsgPort/Message records and the CreateTask packet
are checked against target-emitted `sizeof`/`offsetof` values before linking.
The probe object is not included in the image. Calypsi 5.18 frontend static
assertions alone do not describe this final far24 layout.

The C wrappers form native argument packets on the caller's bank-zero stack.
Two small assembly entry points marshal Calypsi `__simple_call` arguments into
the public `COP #$50` gateway. Return values come back in A/X. All memory,
scheduling and message policy remains in the existing kernel. Caller-context
helpers handle memory clearing and port allocation, as the Action! binding does.
No Action! function is called using a C argument convention.

The DOS binding uses a separate, ordinary-call bridge. The launcher installs two
native entry addresses in six bytes of upper-bank storage, selects its open
console as standard output, and restores the previous selection after C returns.
`Output()` looks up the calling Task's current selection; the binding does not
cache a global console handle. Treat `BPTR` as an opaque 32-bit handle: Exec816
does not use Amiga's shifted BCPL address representation.

`Write(file, buffer, length)` passes full 32-bit values to a checked native
adapter. Addresses outside 24 bits return -1 and set DOS `ERROR_BAD_NUMBER`;
representable arguments go through the existing DOS implementation. It returns
the actual byte count, including partial writes, or -1 on error. A successful
zero-length write returns zero. The assembly bridge aligns the native stack,
preserves the original C stack, and leaves Calypsi's lower DP untouched across
blocking calls. No new COP service or console implementation is added.

For example:

```c
#include <proto/dos.h>

static const char greeting[] = "Hello from C!\n";
LONG written = Write(Output(), greeting, sizeof(greeting)-1);
```

The launcher owns the selected handle; C must not close it. In the shared Amiga
example, DOS output stays in `main`: a raw Amiga `CreateTask` worker has no DOS
Process context. The receiver continues to use only Exec calls.

C uses the Task's existing D page. Calypsi's `_Dp` occupies offsets `$00–$0F`
and `_Vfp` `$10–$13`: **20 of the 128 caller-workspace bytes**. These are
D-relative link addresses, not shared fixed zero-page storage. DBR remains
zero. Native entry supplies 16-bit A/X/Y and a zero-initialized Task workspace.
The kernel uses its own D page and preserves the caller's D and lower workspace
across COP calls and interrupts. The Action! bootstrap's zero-argument call to
C `main` uses the common JSL/RTL and 16-bit result boundary.

The linker places C code in bank `$0C` and data in bank `$0D`. Only actual code,
initialized data and BSS are packaged; unused link capacity is not copied or
cleared. The existing bank allocator reserves the occupied banks. The virtual
DP range and 16-byte host packaging metadata are never loaded as bank-zero
segments. Existing range, ownership and explicit Task-entry admission checks
also apply to C storage and entries.

**Bank-zero reservation delta: 0 fixed bytes, 0 bytes per Task**, including
guards, alignment and unused capacity. C consumes existing lower-DP capacity
and existing stack pools. There is no additional resident C runtime service.
The Calypsi linker selects referenced shim/runtime routines for this executable.

## Current limits and development checks

This binding does not provide C disk commands/o65, DOS calls beyond
`Output`/`Write`, device APIs, `stdio`, `malloc`, arbitrary CRT initialization or
general Action!/C callbacks.
Initialized globals and BSS are handled by the hosted loader. Pure compiler
arithmetic helpers can be linked; a general-purpose C library port is separate.
User-defined tiny/near storage is not part of this target's linker layout.

C functions do **not** have Action!'s compiler-inserted stack-overflow checks.
The platform still checks native domains/guards and the development runner
checks stack watermarks, but these are not equivalent to checking every C
function entry. Keep C examples bounded and their stacks small.

Focused development checks:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_calypsi.py --mode opt --output build/calypsi/messages --from-build build/calypsi/messages
python3 tools/test_calypsi.py --mode raw --context --output build/calypsi/context-raw
python3 tools/test_calypsi.py --mode opt --context --output build/calypsi/context-opt
```

The separate C context fixture covers signals, memory clearing/cleanup, nested
Forbid/Permit, message identity, public-port removal, Task return/self-removal,
DOS output counts, zero/negative lengths and invalid addresses,
and two live computations interrupted by actual VBI. The observer verifies
both computations against host results, C callee-saved DP registers, untouched
caller workspace and the kernel's lower DP. The runner also checks native
guards, bounded completion, console output, physical Return and OS restoration.
These are development checks on the recorded inputs, not release qualification.

The [CreateTask development record](../development/create-task.json) records
the current binding, packet checks, raw/optimized C preemption probes and
updated message example. The [original binding record](../development/calypsi-c.json)
retains measurements for the earlier ExecPrepareTask-based revision.

The [same-source Amiga guide](amiga-c.md) gives the companion vbcc build and
actual classic-Amiga runtime check for this same message example.

The [C output binding record](../development/c-dos-output.json) records the
current shared-source runs and raw/optimized DOS boundary checks. Its only new
binding state is the six-byte entry table in upper RAM; fixed and per-Task
bank-zero reservations remain unchanged, including guards and unused capacity.
