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

- [Console interaction implementation plan](console-interaction-implementation-plan.md)
- [Console input/output implementation plan](console-io-implementation-plan.md)
- [Console size and drawing refactor](console-refactor-plan.md)

## Programs and shell

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
