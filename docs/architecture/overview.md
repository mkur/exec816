# Exec816 overview

Exec816 is a small, Exec-inspired multitasking system for the WDC 65C816.
Its kernel supplies Tasks, scheduling, signals, message ports, device I/O and
memory allocation. DOS, filesystems, the console, program loading and the shell
build on those services. Most code is Action!, with assembly at the native
machine boundary.

This guide describes the current organization. Start here, then read
[Tasks and execution contexts](runtime.md) and
[Filesystems and disk I/O](filesystems.md). API contracts and
implementation records are linked where more detail is useful.

## The main parts

| Part | Responsibility |
| --- | --- |
| **Exec kernel** | Schedule Tasks, preserve their CPU contexts, allocate memory and coordinate signals, messages and device requests. |
| **DOS library** | Give each caller files, streams, a current directory and error state; route operations to their owner. |
| **Process and loader** | Run commands in child Tasks, prepare arguments and inherited resources, load and relocate executable images, and collect results. |
| **Filesystem service** | One `dos.filesystem` Task serves all configured MyDOS and SpartaDOS mounts and their open files. |
| **SIO service** | One worker owns serial bus transactions; native interrupt code handles time-sensitive byte movement. |
| **Console service** | One worker handles the text console and its independent instances, output and keyboard routing. |
| **Shell and applications** | Use these services to run commands, display output and perform useful work. |

These parts share one address space. Much of their code is packaged together in
the resident system image, but it executes in different contexts. DOS library
code can run in its caller; filesystem code runs in its worker; kernel service
code runs through the Exec gateway. Packaging code in the system image does not
make every call a kernel entry.

## Tasks carry execution; objects carry state

A Task is an independently scheduled execution context with a stack, direct
page and saved CPU state. A Process adds command lifetime and DOS resources to
a Task. Service workers are Tasks too and consume the same public Task capacity.

Files, mounts, message ports, pipes and console instances are objects managed by
those Tasks. Creating another such object generally adds state in upper RAM,
without adding a stack or direct page. For example, a second mounted filesystem
has its own request port and volume state but shares the filesystem worker.
The first use of a service may need to start its shared worker.

This matters on the 65816: stacks and direct pages use scarce bank-zero memory.
Keeping ordinary objects separate from execution contexts makes multiple files,
volumes and text windows practical. See the
[runtime model](runtime.md#what-creates-another-task).

## From boot to a command

The initial target is the dedicated AltirraOS 65816 ROM under the pinned AltirraSDL
configuration. The [demo bundle](../guides/demo.md) contains the boot XEX, system disk and
matching ROM. Its OF816 monitor waits five seconds before starting Exec, or
accepts Forth commands if a key interrupts the countdown.

The XEX contains the resident system image. The system disk supplies files and
external commands; Exec does not need to load a second kernel from that disk.
Boot settings select the system drive and sector-cache capacity before handoff.
`SYS:` identifies the selected system volume, independently of where the XEX
was loaded from. See [OF816 boot](../guides/boot-monitor.md) and [SYS:](../reference/sys-volume.md).

The shell executes built-in commands in its own Task. For an external command,
it reads an o65 file, validates and relocates it, resolves its imports against
resident providers, and starts a child Process. The child inherits selected
streams and the current directory, returns a status, and has its DOS resources
cleaned up before the parent collects it. Loaded-image ownership is released
after use. Loading is library work in the caller's context; it has no dedicated
loader Task.

The [program-loading contract](../reference/program-loading.md) describes the supported
o65 profile and imports. Disk commands use the small `COMMAND` interface;
resident applications can use the wider Exec and DOS APIs.

## The current user-facing system

- **Disk access:** MyDOS and SpartaDOS with explicit writable mounts, directories,
  file reads/seeks and `SYS:`. One shared sector cache reduces repeated SIO reads.
- **Text console:** independent retained console instances tiled on one 40×24
  display, with focus and foreground input routing. Instances share one worker.
- **Commands:** resident shell commands, disk-loaded commands, input redirection
  and a foreground pipeline of two external commands. Anonymous pipes use a
  shared memory buffer and need no pipe worker.
- **Languages:** Action! is the main implementation language. An initial
  [Calypsi C binding](../guides/calypsi-c.md) supports standalone Exec examples.

Filesystem writes, a RAM filesystem, general volume assignments, longer shell
pipelines and background shell syntax remain outside the current implementation.
Tasks have no memory isolation: guards and ownership checks detect particular
errors, but cannot make arbitrary code safe. Scheduling is currently FIFO;
stored Task priorities do not yet influence selection.

## Where to go next

| To understand… | Read |
| --- | --- |
| Which code runs where, Task capacity and resource lifetime | [Tasks and execution contexts](runtime.md) |
| Mounts, handles, request queues, caching and SIO | [Filesystems and disk I/O](filesystems.md) |
| How to try the system | [Demo guide](../guides/demo.md) and [shell guide](../guides/shell.md) |
| A small message-passing application | [Amiga message example](../guides/messages.md) |
| Public Task and Process semantics | [Task API](../reference/tasks.md) and [Process API](../reference/process.md) |
| Machine limits and memory placement | [Platform contract](../reference/platform.md) |
| Where the source lives | [Library layout](../../lib/README.md) |

Implementation and qualification records apply to their recorded revisions and
machine profiles. This architectural description is not a new release or
physical-hardware qualification; see the [testing policy](../contributing/testing.md).
