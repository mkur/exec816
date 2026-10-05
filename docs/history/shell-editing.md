# Small shell editor and command history

[History](README.md) · [Shell guide](../guides/shell.md#editing-and-break) ·
[Implementation plan](../plans/shell-editing-implementation-plan.md)

The existing cooked console now supports insertion, a logical cursor, bounded
horizontal scrolling and Ctrl-A/E/B/F/U/K/W editing. Ctrl-P/N and Atari cursor
chords navigate a ten-command history. It preserves the unfinished draft and
cursor and skips blank submissions and consecutive duplicates. There is no
completion, search, escape parser, persistence or new worker.

The session owns optional fixed storage, shared by inherited CON wrappers.
Native DOS ABI revision 6 adds SetConsoleHistory; COMMAND remains version 9.
The shell enables history at a prompt and disables it before parsing or dispatch.
This prevents programs reading inherited CON input from recalling commands or
recording their data. An initial allocation failure disables optional history
for that shell session, preserving editing and command results. The contract
is in [cooked input](../reference/cooked-console.md) and
[DOS history configuration](../reference/dos.md#console-history).

The [development record](../development/shell-editing.json) records pins, source
and artifact hashes, checks and memory costs. This is focused development
validation, not a release matrix or physical Atari qualification:

| Scope | Checks |
| --- | --- |
| Host and generators | 339 host tests, DOS/program generator checks and documentation links. |
| Emitted editor | 639 operations in each of raw and optimized code: movement, insertion/deletion, viewport/caret and echo bounds, narrow/36/37/255-byte lines, resizing, overflow/loss/EOF, ring wrap, duplicates, draft restoration, independent sessions and shared cleanup. |
| Native DOS and physical CON | Raw and optimized checked handles, allocation exhaustion, busy rejection, toggles during partial drains, independent filesystem progress, physical keys and OS restoration. |
| Shipped standalone shell | Optimized checked entry, updated HELP and built-ins through physical input, exact output, OS restoration and cleanup. Its documented build and fixtures use the demo's existing 4 KiB upper data arena. |
| Low-memory shell | Injected history-allocation error: one enable attempt across repeated prompts, working editing, correct command results, exact output and heap/OS cleanup. Actual allocation exhaustion is covered separately by the editor and DOS fixtures. |
| Packaged demo | Five-second OF816 autoboot into shell/prime, physical editing and history, recalled pipelines, draft cursor restoration, CAT input excluded from history, long lines, BREAK, Ctrl-D, retained/physical screen and caret, heap/ownership recovery and OS restoration. |

All four Atari cursor scan codes run through the emitted decoder. The pinned
bridge can physically press Ctrl-*, Ctrl-- and Ctrl-=, but lacks a PLUS key name.
Ctrl-+ is therefore checked using raw scan code $86; Ctrl-B exercises its common
editing path through physical input. No emulator pin or compiler override was
introduced for this limitation.

The cooked payload grows from 402 to 410 bytes: 408 to 416 after allocator
rounding. Optional history takes 2,824 bytes (ten 256-byte slots, a 256-byte draft,
eight control bytes). An enabled shell therefore adds **2,832 upper-RAM bytes**.
ShellState uses a previously reserved byte and keeps its size. The 128-byte echo
buffer is unchanged; a full 36-column redraw emits at most 111 bytes.

The demo's complete memory layout matches the preceding writable-command demo.
Reserved bank-zero change is **0 fixed bytes and 0 bytes per Task**, including
guards, alignment and unused capacity. Stack/DP pools, boot reservations, Task
slots and provider capacity are unchanged. Resident code and observed stack
costs are recorded with the exact build artifacts in the development record.
The optimized demo grows from 612,990 to 620,457 executable bytes: **7,467
additional upper-RAM code bytes**. Its 4 KiB data arena is unchanged.

The refreshed distributable is `build/shell-editing/demo/exec816-demo.zip`.
It retains OF816, the pinned ROM, the system disk with all fifteen commands,
the disposable work disk, the guide, license notices and checksums. Intermediate
builds and test records remain outside the ZIP. The source banner identifies
the committed plan plus local implementation; recorded hashes identify the
exact tested build.
