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
- [ReplyMsg from interrupt context](interrupt-reply-design.md): implemented native
  reply entry, shared queue transactions and controlled NMI continuations;
  [IR0–IR5 implementation plan](interrupt-reply-implementation-plan.md) covers
  the generic foundation and timer adoption gate. Development checks pass at
  nominal 57.6k; the 125k transport performance gate remains open.
- [Signals and Wait implementation plan](signals-wait-implementation-plan.md)

## Device I/O and SIO

- [Device I/O and GUI latency](io-latency-implementation-plan.md): caller-local
  CheckIO, timer exit/poll reduction and the original HY4 GUI comparisons,
  implemented in IL1–IL3. API costs fall; the GUI latency gate remains open.
- [Caller device dispatch](caller-device-dispatch-implementation-plan.md):
  implemented established resident dispatch in the caller, preserving public
  I/O semantics. [Measurements](../history/aes-hybrid.md#hy4-caller-device-dispatch)
  record 0.394/1.115 ms DoIO/SendIO medians with variable scheduling tails.
- [timer.device design](timer-device-design.md): implemented asynchronous VBI delays,
  monotonic deadlines, cancellation and normal Exec I/O replies. Reuses ordinary
  Wait without a worker. TD4/AES integration follows the
  [development record](../history/interrupt-reply.md).
- [Queued device I/O and SIO implementation plan](device-io-sio-implementation-plan.md)
- [SIO driver boundary implementation plan](sio-driver-boundary-implementation-plan.md)

## Filesystems and DOS

- [MyDOS and SpartaDOS write support](filesystem-write-implementation-plan.md):
  W0–W9 implemented with lightweight mounts, write-through file/namespace
  operations, inherited writers and shell cleanup. Both sector geometries pass
  native DOS round trips; [development record](../history/filesystem-write-implementation.md)
  and [mutation protocol](filesystem-write-protocol.md).
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

- [Bulk console output batching](console-output-batching-implementation-plan.md):
  OB1–OB5 complete; cached CAT takes 16.08 s versus 26.67 s, with 332 scroll
  launches versus 769. [Implementation and remaining latency limits](../history/console-output-batching.md).
- [Input registration and lifetime design](input-registration-lifetime-design.md):
  the [refactor plan](input-registration-lifetime-implementation-plan.md) is
  implemented through IR5. Ordinary reads/routes trust registration lifetime;
  lifecycle checks, diagnostics, IRQ queues and signals remain.
  [Measurements](../history/input-registration-lifetime.md) show about 0.95 ms
  letter service, with the 2 ms Return and broader console goals still open.
- [Circular character buffer](console-circular-buffer-implementation-plan.md):
  CB1–CB4 complete; retained row copies are replaced by a circular origin with
  logical damage/cursor coordinates. [Measurements](../history/console-circular-buffer.md)
  show 52–56% less retained-edit CPU per call; loaded latency remains open.
- [Blitter completion IRQs](blitter-irq-implementation-plan.md): BI0–BI5 complete;
  retained completion and timeout signals let the worker sleep with one list in
  flight. [Measurements](../history/blitter-completion-irqs.md) show reduced
  completion CPU cost; scroll and loaded visible-input targets remain open.
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

- [ASSIGN logical directories](assign-implementation-plan.md): implemented
  four-slot, system-wide directory assignments with bounded DOS resolution,
  a loadable command and explicit shell PATH interaction.
  [Development record](../history/assign.md).
- [Multiple-file arguments and LIST patterns](multiple-file-patterns-implementation-plan.md):
  implemented bounded `/M` results for CAT and DELETE, plus command-level
  `*`/`?` matching in read-only LIST. [Development record](../history/multiple-file-patterns.md).
- [Small shell editor and command history](shell-editing-design.md): implemented
  control-key editing, Atari cursor aliases and ten recalled commands. Optional
  history uses 2,824 upper-RAM bytes with no extra bank-zero reservation.
  [Implementation plan](shell-editing-implementation-plan.md) and
  [development record](../history/shell-editing.md).

- [Commands for writable filesystems](write-commands-implementation-plan.md):
  COPY, DELETE, RENAME, MAKEDIR and TEE implemented using the existing writable
  DOS APIs. [Development record](../history/write-commands.md) covers raw/optimized
  command bodies, both filesystems and the packaged OF816 demo.
- [Command usability](command-usability-implementation-plan.md): U1–U6 complete;
  bounded shell PATH, shared fault messages and command template help.
  [Development record](../history/command-usability.md), raw/optimized checks
  and the verified OF816 distribution.
- [First command toolbox](command-toolbox-implementation-plan.md): C1–C6 complete;
  shared arguments/streams, seven loadable commands, directory/console imports
  and the integrated OF816 demo. [Development record](../history/command-toolbox.md).
- [Layers implementation](layers-implementation-plan.md): L1–L4 complete;
  bounded regions, stacking, visibility, damage and drawing transactions.
  [Current contracts](../reference/layers.md); the first desktop presenter now uses them.
- [First desktop on Exec816](gem4xe/desktop-design.md): the
  [DT0–DT7 implementation plan](gem4xe/desktop-implementation-plan.md) covers one
  presentation worker, client/event lifetime, a framed shell, ST mouse timing
  before dragging, two independent clients, exposure repair and the optional
  preview. DT0–DT7 have development evidence and a local OF816 preview; pointer, outline, disk-load button and repair timing limits remain open.
  [Current desktop contract](../reference/desktop.md).
- [Mouse sampling and pointer batching](gem4xe/mouse-performance-implementation-plan.md):
  MP1–MP4 implemented at the development tier: about 4 kHz capture with short
  fine-timing SIO exceptions, one list per pointer move, matched measurements
  and a refreshed OF816 preview. IRQ overhead and pointer setup cost fall;
  pointer, outline and move-repair timing targets remain open. The 2× travel
  and memory reservations are unchanged.
- [Separate widget focus damage](gem4xe/widget-focus-damage-plan.md): implemented
  at the development tier; independent rectangles and underline-only focus
  repair reduce the five-press idle median from 319 to 119 ms. Release/status
  regressions and remaining timing limits are recorded.
- [VBXE command builder refactor](gem4xe/vbxe-builder-refactor-plan.md): BR1–BR4
  implemented at the development tier. Trusted geometry, generated upper-memory
  tables, sequential records and reserved glyph runs reduce maximum widget-paint
  CPU by 40–44% in the original panel samples. One additional upper RAM bank;
  zero bank-zero/VRAM growth. HY4 remains open.
- [AES widget library](gem4xe/aes-widgets-implementation-plan.md): AW0–AW6 implemented
  at the development tier;
  actual GEM4XE object/drawing/form extraction, retained widget windows, bounded
  damage, event-driven controls and a control-panel preview. Uses the existing
  presenter and Task pools. [Panel measurements and the local preview](../history/aes-widgets.md)
  pass correctness checks; feedback latency remains open. Task-bar policy and
  full AES compatibility follow.
- [Desktop rendering with pixel reuse](gem4xe/desktop-rendering-design.md):
  Amiga/GEM4XE synthesis with bounded damage, asynchronous window
  copies, fewer background passes and optional VRAM snapshots. The
  [DR0–DR7 plan](gem4xe/desktop-rendering-implementation-plan.md) is implemented
  at the development tier. The preview and correctness checks pass; latency
  acceptance remains open. One presenter is retained.
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
- [XaAES study for the GEM desktop](gem4xe/xaaes-study.md): pinned source analysis
  of multitasking AES, client waits, update locks, redraws, callbacks and cleanup;
  recommends GEM source compatibility over Exec services and a two-client proof.
- [AES server layer design](gem4xe/aes-server-design.md): proposed GEM bindings,
  bounded messages, pending events, update/mouse locks and retirement in the
  existing presenter; shared-alarm integration with the implemented timer.device,
  AS0–AS4 proof slices and pending TD4 GUI latency measurements.
- [AES server implementation plan](gem4xe/aes-server-implementation-plan.md):
  executable AS0–AS4 slices for C bindings, presenter admission, messages,
  shared timer alarms, GUI locks and the two-client latency/lifecycle proof.
- [Hybrid AES and VDI design](gem4xe/hybrid-aes-vdi-design.md): proposed caller-context
  operations and event waits, Exec message delivery, retained GUI coordination
  and a separate ownership/stack gate for direct drawing. Priorities stay inactive.
- [Hybrid AES implementation plan](gem4xe/hybrid-aes-implementation-plan.md):
  proposed HY1–HY4 commits for shared endpoint lifetime, caller-owned timers,
  atomic message/event migration and native GUI/latency validation. Keeps
  registration and GUI locks in the presenter.
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
