# Implementation plans

[Documentation home](../README.md) · [Open roadmap](../roadmap.md)

Plans describe bounded implementation slices. This index includes completed
plans; consult each plan's status and linked implementation record before
assuming work is pending. Current behavior belongs in the
[reference](../reference/README.md), and implementation results in
[history](../history/README.md).

## Exec and project history

- [Two larger Task stacks](../history/larger-task-stacks.md): implemented; two
  2,560-byte worker stacks within the eight-Task layout, costing 3,072 bank-zero
  bytes and leaving 9,408 bytes free after startup. Raw/optimized Action! and C,
  admission/reuse, selected interrupts and the OF816 demo passed development
  checks; [implementation plan](larger-task-stacks-implementation-plan.md) and
  [evidence](../development/larger-task-stacks.json).
- [Bank zero compaction](bank-zero-compaction-plan.md): complete; one 12,480-byte
  free range in the eight-Task build, consolidated boot storage, and 240 fixed
  bytes recovered in four-Task builds;
  [development evidence](../development/bank-zero-compaction.json).
- [Direct page guard removal and compaction](dp-compaction-plan.md): complete;
  contiguous 256-byte Task DPs with separate kernel ownership and unchanged stacks.
  Saves 2,336 bytes with eight Tasks or 192 with four;
  [development evidence](../development/dp-compaction.json).
- [Bank zero relocation and boot manifest retirement](bank-zero-relocation-plan.md):
  complete; state at `$0800`, resident globals in upper RAM, and manifest
  reclamation after startup. Recovers 10 KiB while retaining existing Task pools;
  [development evidence](../development/bank-zero-relocation.json).
- [VBXE aperture reservation evidence](../development/vbxe-aperture.json):
  reserves `$8000–$8FFF`, relocates boot staging and overlapping stacks,
  and retains eight public Tasks; the [G3 adapter](../reference/display.md) now
  exercises mapped VBXE; the hosted GEM service now uses this adapter.
- [CreateTask for Action! and C](create-task-implementation-plan.md): complete;
  shared creation service, language bindings and same-source Amiga example.
- [Kernel COP fast-path refactor plan](kernel-fast-path-refactor-plan.md)
- [Lists implementation plan](lists-implementation-plan.md)
- [Loader and bank/region manager implementation plan](loader-bank-manager-plan.md)
- [Memory allocation implementation plan](memory-allocation-implementation-plan.md)
- [Messages and ports implementation plan](messages-ports-implementation-plan.md)
- [Signals and Wait implementation plan](signals-wait-implementation-plan.md)

## Device I/O and SIO

- [Queued device I/O and SIO implementation plan](device-io-sio-implementation-plan.md)
- [SIO driver boundary implementation plan](sio-driver-boundary-implementation-plan.md)

## Filesystems and DOS

- [Block I/O and MyDOS implementation plan](block-io-dos-implementation-plan.md)
- [DOS console streams implementation plan](dos-console-streams-implementation-plan.md)
- [DOS simplification](dos-simplification-plan.md)
- [Separate filesystem file and lock objects](filesystem-objects-implementation-plan.md)
- [Simplify filesystem initialization](fsinit-simplification-implementation-plan.md)
- [MyDOS simplification implementation plan](mydos-simplification-plan.md)
- [Sector cache implementation plan](sector-cache-implementation-plan.md)
- [SpartaDOS filesystem implementation plan](spartados-implementation-plan.md)
- [SYS: implementation plan](sys-volume-implementation-plan.md)

## Console and interaction

- [Blitter completion IRQs](blitter-irq-implementation-plan.md): BI0–BI4 complete; remaining
  slices replace scroll polling with a retained completion signal and independent
  timeout wake, preserving input service, one in-flight list and driver ownership.
- [Drawing validation and asynchronous scrolling](drawing-validation-implementation-plan.md):
  D0–D6 implementation and measurements recorded; isolated scrolling is about
  31 ms, while 20 ms scrolling and 40 ms visible-input acceptance remain open.
  See the [measurement record](../history/drawing-validation-and-async-scroll.md).
- [Cheap idle input checking](console-idle-input-implementation-plan.md): Q0–Q3 passed
  development checks; notification-driven workers preserve loss, BREAK and wakeups.
  Input checking fell from 52 ms to 9.7–10.0 ms; complete scrolling remains above target.
- [Bitmap console design](gem4xe/bitmap-console-design.md) and
  [implementation plan](gem4xe/bitmap-console-implementation-plan.md): functional
  80×30 VBXE preview with shared VDI batching, dirty text and blitter scrolling,
  using the existing CON: model and worker. Responsiveness acceptance remains
  open; see the [preview guide](../guides/bitmap-console.md).
- [Console interaction implementation plan](console-interaction-implementation-plan.md)
- [Console input/output implementation plan](console-io-implementation-plan.md)
- [Console size and drawing refactor](console-refactor-plan.md)

## Programs and shell

- [Physical mouse design for hosted GEM](gem4xe/physical-mouse-design.md): implemented
  ST mouse on port 1 using Altirra's existing configuration, with shared SIO
  timing, reusable capture, lifetime, memory and acceptance rules. The
  [implementation plan](gem4xe/physical-mouse-implementation-plan.md) is complete
  through M0–M6 development checks, including the optional production artifact.
  See the [execution record](../history/gem-mouse.md) and [guide](../guides/gem-vdi.md).
- [Hosted GEM input and events implementation](gem4xe/input-and-events-implementation-plan.md):
  I0–I7 complete: media recovery, shared keyboard capture, console handoff,
  interactive controls during disk I/O, serialized cursor drawing and the optional
  artifact. See [input](../reference/input.md) and the [implementation record](../history/gem-input.md),
  based on the [design note](gem4xe/input-and-events-design.md). Physical pointer
  support and AES have separate follow-on gates.
- [Minimal hosted GEM VDI subset](gem4xe/minimal-vdi-implementation-plan.md):
  G0–G6 complete, including concurrent physical-SDFS/failure checks and the
  optional artifact. See the [current contract](../reference/gem-vdi.md),
  [guide](../guides/gem-vdi.md) and [implementation record](../history/gem-vdi.md).
- [GEM4XE as the GUI layer for Exec816](gem4xe/exec816-integration-assessment.md):
  VBXE-only integration with expandable upper RAM, bank-zero and hardware
  constraints, and proposed executable slices. The
  [earlier analysis](gem4xe/README.md) is preserved.
- [Command arguments implementation](command-arguments-implementation-plan.md)
- [Command Main return-value implementation plan](command-main-implementation-plan.md)
- [CSTRING module implementation plan](cstring-implementation-plan.md)
- [Exec816 demo implementation plan](demo-implementation-plan.md)
- [Interactive console and program execution plans](interactive-programs-implementation-plan.md)
- [o65 loading and external commands implementation plan](o65-loading-implementation-plan.md)
- [Process lifetime implementation plan](process-lifetime-implementation-plan.md)
- [Resident shell implementation plan](shell-implementation-plan.md)

## Compiler and ABI

- [Native pointer loops: implementation plan](compiler-pointer-loops-plan.md)
- [Direct-page partition implementation plan](direct-page-partition-implementation-plan.md)
