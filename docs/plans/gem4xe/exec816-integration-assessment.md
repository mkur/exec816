# GEM4XE as the GUI layer for Exec816

[Implementation plans](../README.md) · [Earlier analysis](README.md)

**Assessment on 2026-10-01: technically plausible and worth a bounded prototype.**
GEM4XE supplies substantial reusable graphics, widgets, window management and
desktop code. Exec816 already supplies the execution and I/O foundations. The
recommended integration is an optional GEM service above Exec, reached through
client bindings and ordinary messages. The current GEM executable cannot simply
be launched as an Exec Task: its memory map, stack transitions and hardware
ownership conflict with the hosted system.

This assessment uses GEM4XE **0.9.4**, commit
`e413c39d2f8e1bec8fe16596f610b923de4a0ae9`, and Exec816 commit
`477f091e8725d22cc57c270f0673b8220fc8c0ef`. It supersedes the September 15
assessment for present feasibility; the older documents remain historical.
[Source hashes and layout calculations](../../development/gem4xe-assessment.json)
record the inspected inputs. This is source analysis, not an executed port.

## Agreed integration scope

- **VBXE is the sole GUI display backend.** The Exec port will not include an
  ANTIC framebuffer backend or fallback. ANTIC remains part of the platform's
  VBI timing and scheduling path.
- **Upper RAM capacity is expandable.** Add banks as needed for the initial
  port, updating the machine configuration and Exec's usable-bank map together.
  Image placement and allocation ownership still require validation.
- **Boot without a resident Atari DOS; plan Exec bank-zero allocation from
  `$0800`.** Retain `$0000–$07FF` for the OS and low-memory workspace. This
  has recovered `$0800–$1FFF` from the earlier conservative reservation. Exec's own
  DOS/file services remain part of the system.
- **Bank zero is the main memory constraint.** Prioritize moving eligible data
  and metadata upward, reserving a safe VBXE aperture, and budgeting the GUI
  stack and direct page with stack guards and interrupt headroom.

## What has changed since the earlier analysis

| Area | Inspected implementation | Effect on integration |
| --- | --- | --- |
| Exec foundations | Tasks, native preemption, signals, ports, memory, Process lifetime, file services and program loading exist. | Work can focus on the GUI adapter rather than implementing the kernel first. |
| C execution | The Calypsi binding runs C on Exec Task stacks and DPs, with recorded C preemption checks. | Retain C for GEM and Action! for Exec; a language rewrite is unnecessary. The existing binding is narrower than GEM needs. |
| GEM resources | AES accepts far object trees; resource loading can allocate them outside bank zero. | The old requirement to keep every resource tree near is obsolete. |
| GEM far memory | Blocks have owners and can be freed individually; GEMDOS implements `Mfree` and shrinking. | Independent far lifetimes are more tractable. The near application pool still rewinds a cursor. |
| GEM applications | Packed G4A format 5 separates code and far variables; formats 3/4 remain for larger images. | An adapter must understand the current format if G4A compatibility is selected. File extensions do not identify Exec o65 images. |
| GEM concurrency | Seven AES process records support a foreground application and up to six accessories, sharing an engine stack cooperatively. | This is not yet a server for independently preempted Exec GUI clients. |

Evidence: [Exec overview](../../architecture/overview.md),
[C binding](../../guides/calypsi-c.md), [resource loader][gem-rsrc],
[far allocator][gem-farmem], [G4A loader][gem-app] and
[AES process definitions][gem-proc]. Some GEM source comments still describe
the retired far bump allocator; the allocator and its callers take precedence.

## Recommended division of responsibility

| Layer | Responsibility |
| --- | --- |
| Exec kernel | Tasks, scheduling, signals, message ports, allocation and resource lifetime rules. |
| Exec platform and device drivers | Interrupt entry, OS transitions, SIO, keyboard/pointer capture and exclusive ownership of display hardware. |
| GEM service | AES window/widget/event semantics, VDI rendering, GUI resources, client identities and pending GUI requests. |
| GEM client binding | Preserve selected GEM source APIs, marshal their argument blocks into requests and wait for replies. |
| Desktop and applications | Run as Exec Tasks or Processes through rebuilt startup/bindings; use GEM for interaction and Exec DOS for files. |

The Amiga precedent remains appropriate: Exec mechanisms below GUI libraries
and services. **Proposed departure:** serialize the initially non-reentrant GEM
engine in one service Task rather than immediately allowing library execution
on every application's stack. This limits renderer scratch duplication and
concentrates its deep stack requirement in one place. Measure request overhead
and support bounded batches of drawing operations; do not issue a kernel call
per pixel. QNX-style request/reply is a useful implementation pattern here, not
a reason to change Exec's public message ownership rules.

Retain the [VDIDEV boundary][gem-vdidev] and the
[pointer position/button boundary][gem-pointer]. Keep hardware queue,
cancellation and shutdown policy in drivers using public Exec primitives.
Reusable platform operations may need to be added, but GEM-specific private
kernel calls are not the integration boundary.

## Bank zero is the first feasibility gate

The [bank-zero relocation plan](../bank-zero-relocation-plan.md) is implemented:
state is at `$0800`, ordinary globals occupy upper RAM, and the manifest retires
after successful startup. The subsequent
[aperture reservation](../../development/vbxe-aperture.json) protects
`$8000–$8FFF`, and [DP compaction](../../development/dp-compaction.json) removes
DP guards and padding. These records preserve their historical layouts.

[Bank-zero compaction](../bank-zero-compaction-plan.md) now packs persistent
Exec storage into `$0800–$4F3F`: boot state at `$0900`, kernel/Task DPs at
`$0A00–$13FF`, the resident adapter at `$1400–$23FF`, and guarded stacks at
`$2400–$4F3F`. Staging, manifest and loader occupy `$5BF0–$7BFF` temporarily.
See the [development record](../../development/bank-zero-compaction.json).

The generated eight-Task layout now reserves:

| Current eight-Task reservation | Bytes |
| --- | ---: |
| OS ranges | 30,720 |
| Fixed Exec runtime, including VBXE aperture | 10,528 |
| Root Task | 1,824 |
| Seven other public Task pools | 9,184 |
| Private idle | 800 |
| Total reserved in bank zero | 53,056 |
| One unreserved range, `$4F40–$7FFF` | 12,480 |

These totals include guards and unused reserved capacity. They recover 8,480
bytes from the assessed baseline after reserving the aperture and compacting
DPs. Whole-map compaction adds no eight-Task savings; it combines the nine holes
into one 12,480-byte range. The range becomes fully reusable after
`startup_complete`, when the manifest retires. It is not yet a heap arena. The
no-resident-Atari-DOS boot contract requires the original MEMLO to be at most
`$0800`. Exec's own DOS/file services remain operational.

Each ordinary worker reserves a 1,024-byte stack, 32 stack-guard bytes and a
256-byte aligned DP reservation without external guards. The stack includes
256 bytes of interrupt reserve. The root stack is 1,536 bytes. GEM's present
engine alone reserves **2,048 stack bytes**, before adapting its call chain to
Exec. The current configurable pool generator accepts at most 1,536 stack
bytes. Passing a larger number to `CreateTask` does not allocate new space.
See [Task capacity](../../architecture/task-capacity.md) and
[pool generator](../../../tools/task_capacity.py).

GEM's [linker layout][gem-layout] reserves `$2000–$3FFF` for engine DP, data,
stack and near code, `$4000–$47FF` for additional state, and `$4800–$7FFF` for
the product near application pool: **24,576 bytes altogether**, before display
storage. These ranges overlap Exec. They are not an additive estimate of the
eventual port: removing standalone startup, moving data far and sharing Exec
services should change them substantially. A combined link map must measure
the result; adding the two existing binaries is impossible in these layouts.

The current [VBXE implementation][gem-vbxe] maps a **4 KiB** CPU aperture at
`$8000–$8FFF`. Exec now reserves that entire range through loading and runtime.
The former stack and globals overlaps have been removed. The old
analysis's 8 KiB description should not be used as this aperture's size.

The agreed VBXE-only GUI uses VRAM for display storage, retaining the dedicated
AltirraOS 65816 platform. The next display slice needs an explicit VBXE machine
pin, window/register ownership and console handoff, then mapped-memory tests
under IRQ/NMI and SIO load. The address reservation alone does not implement a
VBXE driver. Eight public Tasks remain available; GEM's own near-memory and
stack requirements still need a measured combined layout. The upper global
arena is part of the checked platform contract.

Move engine tables, globals and constants far where practical; keep only real
stack/DP/entry/DMA requirements near. GEM currently uses Calypsi's small data
model, while Exec's C example uses huge data. A compiler flag change alone does
not prove correctness: audit near pointers, stack-local addresses, assembly,
structure layouts and helper arithmetic. Far resource support helps without
making the whole engine independent of bank zero.

Exec must own physical allocation. GEM's owner-aware allocator can initially
suballocate backing explicitly reserved from Exec, or its calls can be adapted
to Exec allocations with appropriate alignment and bank constraints. Never run
GEM's destructive memory probe over Exec's live images. Keep G4A page-placement
rules and GEM's bank-contained far-pointer arithmetic if those formats remain.

## Execution contexts require an explicit port

Exec's [frame validator](../../../platform/altirraos/cooperative.s) compares the
interrupted stack against the current Task's registered bounds and requires its
saved D to equal that Task's DP. GEM's [application CRT][gem-crt] switches both
S and D to the application's near region; its [COP handler][gem-abi] switches
back to the engine's stack and DP. [Cooperative contexts][gem-ctx] also copy
and replace live engine-stack contents.

Consequently, putting the existing GEM session inside one Task does **not**
automatically make it preemptible. An unrecognized frame is skipped by Exec's
interrupt scheduler; Exec calls from an invalid context encounter the gateway's
context checks. Re-enabling IRQ does not solve this, and masking IRQ does not
exclude NMI during stack transitions.

For the initial port, keep the renderer on one ordinary Exec stack/DP and
rebuild test clients for ordinary Exec Task startup. Retire GEM's standalone
stack-changing entry path in that build. Exec already preserves the lower 128
DP bytes for caller runtime state; inspect the linked GEM register/tiny-data
footprint before placing it there. The existing C example's 20 bytes are not a
measurement of the GEM engine.

Preserving unchanged G4A startup would instead require a designed, reusable
execution-domain facility covering registered alternate stacks/DPs and atomic
transitions, with guard and preemption tests. It must remain consistent with
the single public Task model. That is a substantial compatibility option, not
a prerequisite for proving GEM rendering on Exec, and not a reason to weaken
the existing validator.

The nominal GEM COP selectors `$41/$44/$56` do not collide with Exec `$50` or
AltirraOS `$00`. However, GEM now also uses **COP `$49`** in its
[interrupt-disable workaround][gem-sei], recognized by the instruction's
return address. Preserve one platform-owned dispatcher and an explicit selector
registry if any of these gates remain. Chaining the unchanged GEM dispatcher
is insufficient. Validate the workaround against Exec's pinned emulator before
deciding whether the port needs it.

## Interrupts and input need shared hardware ownership

Replace GEM's vector installation, OS shadowing, Rapidus setup and machine exit
with Exec-controlled entry and shutdown. Preserve Exec's OS VBI chain and
scheduling protocol. GUI rendering and event processing run in Task context;
interrupt capture publishes bounded state and wakes the appropriate service.

The pointer conflict is concrete. [GEM's interrupt setup][gem-irq] configures
POKEY timer 1, `AUDCTL`, `SKCTL`, `STIMER` and IRQ masks for its quadrature
sampler. [Exec SIO](../../../platform/altirraos/sio.s) rejects an existing timer
owner during startup, takes timer vectors and programs POKEY's audio/serial
state for transactions. The two implementations cannot independently own this
hardware. Restoring the mouse settings after each disk call is not a solution
for concurrent SIO and input.

Start with injected pointer events to prove the GUI independently of this
conflict. Then implement coordinated native input and measure missed motion,
event latency and SIO completion together. Frame-based absolute/counter devices
may reduce the timer requirement, but their POT timing and device support still
need tests; they do not establish compatibility for quadrature mice.

The text console also owns keyboard capture and presentation. Design an explicit
display/input handoff, including the ROM's video shadow state. Hiding console
tiles alone does not release hardware. A terminal window should eventually
consume the console's retained cells through a defined rendering boundary;
the present non-overlapping text tiles are not GEM windows.

## Files and applications

Implement a GEMDOS compatibility adapter over [Exec DOS](../../reference/dos.md),
covering resource reads, file open/read/seek/close, directory enumeration,
paths, handles, DTA searches and error translation. Map GEM paths such as
`A:\DIR\FILE` to an explicitly chosen Exec mount such as `D1:DIR/FILE`;
do not mix this mapping with `SYS:` policy. Exec `Seek` returns the old position;
the adapter must return the new position expected by GEMDOS.

The existing C DOS binding provides only `Output` and `Write`, so these operations
need checked C bridges. In a server design, file handles belong to the Exec Task
that opens them; clients receive GEM handle identities, not foreign DOS pointers.
Maintain per-client directories, search state and cleanup above that ownership
boundary, using explicit paths where one server serves multiple clients.

Exec's mounted filesystems are currently read-only. A first desktop can browse,
read resources and launch supported programs, but saving documents/settings,
copying files, rename, delete and directory creation require further filesystem
work. Return explicit errors and reflect capabilities in the GUI. Using GEM's
old CIO backend to obtain writes would reintroduce a competing firmware and
disk-cache owner. Cartridge storage, PBI/SIDE access and SDX command execution
do not transfer to Exec merely because upstream GEM supports them.

There are two distinct application goals:

| Goal | Required work |
| --- | --- |
| Rebuilt GEM applications on Exec | C startup, client bindings, request ownership, supported GEM APIs and Exec program admission. Recommended first. |
| Existing G4A binaries | Formats 3/4/5, old CRT and stack/DP behavior, COP compatibility, near-pool lifetimes, Pexec and module callbacks. Separate compatibility project. |

Exec's compact o65 loader accepts its checked Action! ABI and a restricted set
of command providers. It does not presently load arbitrary C/G4A programs or
publish arbitrary GUI callbacks. Initially package selected foreign C entries
with the system using the existing C-image mechanism. Dynamic GUI application
loading is a later public loader/ABI milestone. Reuse GEM source compatibility;
this does not imply running Atari ST 68000 binaries.

Keep GEM's compiler dialect and binary layouts separate from Exec's headers.
GEM FAR pointers occupy four bytes; Exec native data pointers occupy three,
and the C binding explicitly checks those record layouts. Marshal at the
boundary. Preserve upstream source and runtime notices; the existing public C
bindings provide a suitable boundary without copying kernel implementation
into GEM.

## AES is the main semantic work after platform bringup

The current event loops can suspend inside `evnt_multi`, dialogs and gestures.
A single server must not block its entire request loop while client A waits for
an event that client B will produce. Initially expose a small nonblocking draw
and input subset; then represent pending waits with per-client request state
and complete replies when events arrive. Any retained continuations must obey
Exec's registered execution-context rules.

Current AES has window owner IDs, but [redraw routing][gem-wind] still targets
`proc_app` in relevant paths; `wm_update` maintains a counter rather than an
owner-aware exclusion protocol. [The shell][gem-shell] still runs and unloads
the foreground program before restoring the desktop. Far ownership improvements
do not fix near-pool rewind lifetime or shared renderer/global session state.

Multiple independent GUI clients therefore require event routing, update-lock
ownership, per-client resources, cancellation/disconnection and independent
near lifetimes. Preserve live buffers until each request or registered callback
retires. A desktop resident alongside applications is a deliberate shell
adaptation. Exec preemption alone supplies none of these GUI semantics.

## Proposed executable slices

| Slice | Concrete result | Acceptance evidence |
| --- | --- | --- |
| 1 Memory and C boundary | Minimal hosted GEM drawing subset, explicit larger GUI stack and upper-data placement; no old CRT or hardware takeover. | Combined linker map, full bank-zero accounting, emitted C layout checks, and raw/optimized bridge tests under VBI with a computing peer. |
| 2 Display and input | VBXE drawing and cursor on a reserved aperture, explicit console handoff, injected then native input. | Pixel comparisons from GEM fixtures; IRQ/NMI at mapping/entry transitions; input plus SIO load; normal stop restores text presentation. |
| 3 GEM resources and read-only desktop subset | Exec DOS adapter, resource loading and a rebuilt UI/client with basic browse behavior. | Exact reads, seek translation, directory/error cases, repeated startup/shutdown without resource leaks, explicit write rejection. |
| 4 Independent GUI clients | Pending AES event replies, owner-aware window routing and one application beside the desktop. | A waits while B sends its event; both draw and read files; either exits first; native non-GUI work continues. |
| 5 Broader desktop compatibility | Selected application loading, accessories/modules and writable filesystem operations. | Per-feature lifetime and malformed-image tests, real applications and the chosen device/ROM matrix. G4A compatibility is included only if selected. |

Stages 1 and 2 are the go/no-go investment: prove that the memory arrangement
and ordinary Exec execution survive real asynchronous entry before porting the
whole desktop. Do not start with six accessories. The standard demo already
uses five public Tasks and reaches seven with a pipeline; GUI/service/client
admission must fit the eight slots or use a separately budgeted configuration.
More windows should primarily add upper-memory objects, not more service Tasks.

Keep the five-second OF816 shell/prime boot as the standard demo. A future GUI
build should be a separately selected profile until its platform and lifetime
checks pass, and any demo refresh must still use the normal OF816 packaging.

## Validation scope and decision

Performed for this assessment: source inspection, fresh host generation of the
eight-Task reservation layout, overlap/hole calculations and comparison with
the existing demo layout. Documentation links, anchors, source pins and hashes
are checked. No GEM/Exec combined executable, fresh GEM baseline build, emitted
integration regression, emulator run or physical-machine qualification was
performed. Upstream test descriptions are references for future work, not new
results.

Use the pinned [AltirraOS and emulator inputs](../../../toolchain/altirra-shell-paced.json)
as the starting point. VBXE and any additional upper RAM require an explicit configuration pin;
Rapidus and other real boards remain separate qualification targets. Compiler
defects discovered by the Action! bridge belong in actionc with focused tests.
Ordinary slices use the development testing tier; full qualification follows
only for the selected release/platform claim.

**Reservation change from this assessment: 0 fixed bank-zero bytes and 0 bytes
per Task**, including guards, alignment and unused capacity. The proposed port
has no accepted memory budget yet.

Proceed with the first two slices if the aim is a native Exec desktop using
GEM's UI implementation. Treat unchanged GEM binary compatibility as a separate
scope decision. A useful read-only GUI is a credible intermediate target;
a desktop with independent applications and saving is a larger staged project.

[gem-layout]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/gem4xe.scm
[gem-rsrc]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/rsrc.c
[gem-farmem]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/farmem.c
[gem-app]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/app.c
[gem-proc]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/proc.h
[gem-vdidev]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/vdidev.h
[gem-pointer]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/pointer.h
[gem-vbxe]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vbxe/vbxe.h
[gem-crt]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/app/crt_gemapp.s
[gem-abi]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/abi.s
[gem-ctx]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/ctx.s
[gem-sei]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/sei.s
[gem-irq]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/irq.c
[gem-wind]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/wind.c
[gem-shell]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/shel.c
