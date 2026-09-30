# First Amiga Exec example: a message and its reply

[amiga-ports.act](../../examples/amiga-ports.act) adapts the `port1.c` / `port2.c`
exchange from the Amiga documentation's
[Exec Messages and Ports](https://wiki.amigaos.net/wiki/Exec_Messages_and_Ports#Port1.c).
It sends the pair 10,20 to a receiver, which adds 50 to both fields and replies.
The Action! implementation uses the existing Exec816 APIs and is a standalone
XEX, with no disk-command imports or kernel changes.

Expected console output:

```text
Send: 10,20
Reply: 60,70
Message returned; resources released.
Press RETURN to exit.
```

## The exchange

The root Task creates a reply port and allocates an `XYMessage`. Its first
field is the ordinary Exec `Message` header; the two numbers follow it.
The receiver Task creates its own port and publishes readiness.

The sender calls `PutMsg`, then `WaitPort` and `GetMsg` on its reply port.
The receiver also uses `WaitPort` followed by `GetMsg`, changes the payload,
and calls `ReplyMsg`. `WaitPort` does not remove a message from its queue.
Both Tasks see the same message allocation. The sender resumes using that
memory only after collecting the reply.

After the single exchange, the receiver deletes its port, then signals completion
and removes itself inside one Forbid region. The sender waits for that signal,
frees the message, and deletes its reply port.
Allocation and Task-admission failures release resources already acquired.

## Small adaptations

- Both sides live in one executable and use private ports. The original example
  uses a named public port and two separately launched programs.
- The receiver handles one request and exits; no interactive stop command is
  needed. Startup and completion use allocated signals and `Wait`; message waits use
  `WaitPort`. Failed creation never waits for a nonexistent child.
- Port and message allocation use classic `CreateMsgPort`/`DeleteMsgPort` and
  `AllocMem`/`FreeMem`. The current Amiga wiki uses the newer `AllocSysObject`
  interface, which Exec816 does not implement.
- `CreateTask` selects an existing worker pool and manages the Task record.
  Its borrowed result is never polled after retirement.
- Only root prints, using `DOS.Write` on `CON:` with C-string text and LF
  newlines. The small [output helper](../../examples/example-output.inc) waits for
  Return before closing the handle and releasing the root Task's DOS context.
  This keeps the result visible until the user is ready to restore the OS screen.

The example uses three public Task slots in the existing four-slot layout, plus
the existing idle context. Reserved bank-zero delta is **0 fixed bytes / 0 bytes
per Task**, including guards, alignment and unused capacity. Small globals use
the existing near-data arena; the message and ports use the upper heap. No stack,
direct-page domain or fixed arena reservation is added or enlarged.

## Build and run

Build using the compiler pinned in [actionc.json](../../toolchain/actionc.json):

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console \
  --source examples/amiga-ports.act --output build/amiga-ports/standalone
```

Load `build/amiga-ports/standalone/program.xex` in AltirraSDL using the dedicated
AltirraOS 65816 ROM and native CPU/upper-RAM setup described in
[banked loading](../history/banked-loading.md). This standalone image starts its own native
console; it does not need the play image's shell. Press Return to exit.
The test runner uses the exact ROM/emulator hashes
and 8x, 15-upper-bank configuration in
[altirra-shell-paced.json](../../toolchain/altirra-shell-paced.json).

Focused development checks:

```sh
python3 tools/test_amiga_ports.py --mode opt --output build/amiga-ports/opt
python3 tools/test_amiga_ports.py --mode raw --output build/amiga-ports/raw
```

Each command builds and runs the actual example once. Checks cover reply
identity, both returned numbers, exact visible output, a physical Return key,
worker retirement, signal release, heap bank ownership, stack/domain guards
and OS display/input restoration. It also checks that no ROM output call was used.
Execution is bounded. The results are written to each output's `results.json`;
the runnable image is under `program/program.xex`. `--from-build` replays a
recorded image after checking its hashes, compiler mode, example source and
shared output helper against the adjacent `results.json`.
These are development checks, not a new platform qualification.

The [native-console development record](../development/task-examples.json) covers
all three Task examples in raw and optimized modes, with artifact hashes and
the task-capacity memory accounting.

The earlier [development record](../development/amiga-ports.json) describes the
original ROM-output version and its compiler pin. Current native-console runs
write their own fresh evidence to the output directory; that historical record
does not validate the changed example.

To check all three public Task examples in one batch, use:

```sh
python3 tools/test_task_examples.py --mode opt --output build/task-examples/opt
python3 tools/test_task_examples.py --mode raw --output build/task-examples/raw
```

The C version, [messages.c](../../c/examples/messages.c), uses classic Amiga
headers and calls without platform conditionals or Exec816 extensions. The
[CreateTask record](../development/create-task.json) tracks the updated Action!
and C examples; the earlier records above describe their original revisions.
