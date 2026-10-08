# Historical records

- [Files scrolling](files-scrolling.md): cached directory rows and adaptive layout.
- [Window gadgets](window-gadgets.md): resizing and vertical scrolling.

[Documentation home](../README.md)

- [Classic GEM appearance](classic-gem-appearance.md): frame, menu and desktop
  appearance implemented through GA4, with matched costs and a tested OF816 ZIP.

These pages preserve earlier designs, completed implementation slices and
revision-specific measurements. Some use the future tense because they were
written before implementation. Start with the [current architecture](../architecture/README.md)
or [reference](../reference/README.md) when looking up today's behavior.

Recorded paths and hashes inside [development](../development/),
[qualification](../qualification/) and [experiments](../experiments/) evidence
remain tied to their original revisions. Their JSON records are not rewritten
when documentation moves. The [testing policy](../contributing/testing.md)
distinguishes that evidence from a new qualification claim.

Records made before the public repository was created refer to commits in the
private development archive. Those commits are outside the public Git history;
their recorded hashes and measurements are preserved here as historical evidence.

## Exec and project history

- [Application menu bars](application-menu-bars.md): registration, delivery,
  presenter integration and Files menu implementation evidence.

- [Desktop menu and window switching](desktop-menu-window-switching.md): active
  window menus, covered-window selection, keyboard cycling and focus restoration.

- [Control Panel session settings](control-panel-settings.md): runtime Off/Mild,
  staged Apply/Cancel, physical redraw checks and reduced Files popup stack use.

- [GEM4XE calculator port](calculator-port.md): noneditable TEDINFO, classic
  resources and a private windowed APP with Files/shell ownership and disk packaging.

- [Background console panes and primes](background-pane-primes.md): foundation
  slices, loadable command, numeric drawing, resource costs and packaged preview.

- [AES application input](aes-application-input.md): AI1–AI7 pass development checks for
  capture, routing, public input waits, interactive GEM apps, measured cost and
  the extracted OF816 demo. PI4/HY4 remain open.
- [AES window applications](aes-windows.md): WA1–WA6 complete at the development
  tier; durable GUI messages, windows, private VDI, two resident counters and an
  extracted OF816 demo. Includes coexistence timing and console repair fixes.
- [Mouse acceleration](mouse-acceleration.md): timed relative capture, interval
  and coalescing checks, queue capacity, desktop profiles and upper-memory
  accounting. MA1–MA4 are implemented; mild is the default, with loaded evidence
  and a passing extracted OF816 demo. Pre-existing caret artifacts remain open.
- [Hybrid AES refactor](aes-hybrid.md): shared endpoint lifetime, caller transport
  migration, bounded presenter/widget/text steps and measured latency tradeoffs.
- [AES service foundation](aes-server.md): private C bindings, presenter-owned messages/timers, GUI ownership, the two-client proof and latency follow-up.

- [Native interrupt replies and timer.device](interrupt-reply.md): shared port
  transactions, exact return handoff, guarded adapter returns, bounded native
  completion and Action!/C timers.

- [Hosted AES widget application](aes-widgets.md): Control Panel, loaded semantic
  input, matched updates, independent contexts, the AW6 local preview and its
  clipped-text/startup, button-feedback and separate-focus-damage follow-ups.

- [Mouse sampling and pointer batching](mouse-performance.md): MP1–MP4 implement
  about 4 kHz capture with preserved fine SIO timing, one list per pointer move,
  matched desktop measurements and a refreshed OF816 preview; remaining timing
  limits are recorded separately from correctness.
- [Desktop rendering](desktop-rendering.md): bounded damage, transactional copies
  and optional snapshots through DR7; cache eviction/fallback checks, refreshed
  OF816 preview, the obscured-scroll starvation fix and open latency limits.
- [Desktop development](desktop.md): frozen shell/mouse inputs and Task/memory
  budgets, client lifetime, framed presentation and the ST input checkpoint.
  DT0–DT7 are implemented, including the local OF816 preview. Pointer, outline,
  disk-load button and repair timing limits remain open. The sensitivity follow-up
  doubles desktop pointer travel without changing ST sampling.
- [Layers development](layers.md): bounded regions, cached visibility and
  damage transactions; raw/optimized emitted software raster and storage checks.
- [Bulk console output batching](console-output-batching.md): one multi-row
  copy/fill for bounded retained edits; cached CAT improves from 26.67 to 16.08 s,
  with unchanged bank-zero reservations and open loaded-latency goals.
- [Input registration and lifetime](input-registration-lifetime.md): checked
  admission/retirement, cheaper ordinary reads/routes, consumer race coverage
  and measured active-key CPU reductions; console latency targets remain open.
- [Circular console buffer](console-circular-buffer.md): recycled retained rows,
  wrap/lifetime checks and reduced scroll preparation cost; loaded latency remains open.

- [Blitter completion IRQs](blitter-completion-irqs.md): native/emulation delivery,
  independent timeout wake and a sleeping console worker; CPU gains and remaining latency limits.
- [Console responsiveness measurements](console-responsiveness.md)

- [Drawing validation and asynchronous scrolling](drawing-validation-and-async-scroll.md): one owner check per call and one list in flight; about 31 ms isolated scrolling, with loaded input acceptance still open.
- [Minimal GEM/VDI hosting](gem-vdi.md): G0–G6 evidence, memory costs and optional artifact.
- [Hosted GEM input and events](gem-input.md): I0–I7 reusable input, interactive controls, cursor semantics, measured concurrency and the packaged demo.
- [Physical mouse development](gem-mouse.md): M0–M6 ST capture, interactive controls, bounded timing/failures and the production artifact.

- [Intrusive Lists — earlier guide](lists-reference.md)
- [Build cleanup and artifact restoration](build-cleanup.md)
- [Two cooperative tasks under AltirraOS](cooperative-tasks.md)
- [Exec816](development-overview.md)
- [Interruptible Task policy](kernel-critical-sections.md)
- [COP fast-path implementation record](kernel-fast-path-implementation.md)
- [Classic Exec list update](lists-exec-update.md)
- [Memory allocation: classic Exec design](memory-allocation-design.md)
- [Exec memory allocation implementation](memory-allocation-implementation.md)
- [Byte-level memory allocation (superseded proposal)](memory-allocation.md)
- [Messages and ports: classic Exec design](messages-ports-design.md)
- [Messages and ports implementation](messages-ports-implementation.md)
- [Initial AltirraOS platform contract](platform-contract.md)
- [Exec816 implementation roadmap](roadmap-chronology.md)
- [Serial deadlines under concurrent kernel work](signals-concurrency.md)
- [Signals and Wait: delivery-path review](signals-delivery-review.md)
- [Signals implementation record](signals-implementation.md)
- [Signals and Wait: classic Exec design](signals-wait-design.md)
- [Eight-task configuration](task-capacity.md)
- [Two larger Task stacks](larger-task-stacks.md): implemented mixed eight-Task
  layout and bounded Action!/C development evidence.
- [Task API review and migration](tasks-exec-update.md)
- [General task management](tasks.md)

## Platform and boot

- [OF816 before kernel loading](of816-first-boot.md): returning INITAD monitor,
  preserved settings/text, small progress output and the bitmap/cartridge preview.
- [XLOS boot diagnostics](../development/xlos-boot.json): cartridge interlock
  correction, the XEX Disk Boot route through D2 and bounded firmware checks.
- [Bank manager](bank-manager.md)
- [Banked loading and memory ownership](banked-loading.md)
- [Native interrupt masking in the pinned emulator](emulator-native-irq-fix.md)
- [Native Action! launch under AltirraOS](native-launch.md)
- [OF816 boot monitor](of816-boot.md)
- [AltirraOS 65816 boundary probe](os-boundary-probe.md)
- [Stack checks](stack-checks.md)
- [VBI preemption under AltirraOS](vbi-preemption.md)

## Device I/O and SIO

- [Queued device I/O and SIO](device-io-sio-design.md)
- [Queued device I/O and SIO implementation](device-io-sio-implementation.md)
- [Shared serial IRQ adapter](serial-irq-adapter.md)
- [Nominal 57.6 kbaud SIO](sio-57600.md)
- [SIO driver migration record](sio-driver-boundary-implementation.md)
- [POKEY IRQ-to-worker latency proof](sio-latency-poc.md)

## Filesystems and DOS

- [SpartaDOS request-scoped write buffering](spartados-write-buffering.md): ordered
  publication within each Write, matched COPY gains, cancellation/failure coverage
  and shared-memory costs; the [preserved design](spartados-write-buffering-design.md)
  records the original proposal.

- [COPY and filesystem write performance](write-performance.md): 16 KiB COPY,
  four-sector extension groups, retained cursors, matched physical-I/O costs and
  BREAK timing, unchanged bank-zero reservations and a recorded MyDOS transport
  timing limit.
- [Larger demo system disk](system-disk-capacity.md): 720 KiB default, 360 KiB
  option, matching mount descriptors and MyDOS extended VTOC images.
- [MyDOS and SpartaDOS write implementation](filesystem-write-implementation.md):
  lightweight mounts, file/namespace writes, bounded commit units, inherited
  writer retirement, failure outcomes, native round trips and the OF816 demo.
- [Block I/O and DOS with MyDOS filesystems](block-io-dos-design.md)
- [Block I/O and MyDOS implementation](block-io-dos-implementation.md)
- [DOS console streams](dos-console-streams-design.md)
- [DOS console streams implementation](dos-console-streams-implementation.md)
- [Single large-read throughput](dos-read-throughput.md)
- [DOS simplification development record](dos-simplification-implementation.md)
- [Filesystem CPU-step consolidation](filesystem-cpu-steps.md)
- [One owner for length metadata](filesystem-length.md)
- [Separate file handles and locks](filesystem-objects.md)
- [Shared filesystem progress](filesystem-progress.md)
- [Shared filesystem helpers](filesystem-shared-helpers.md)
- [Filesystem initialization simplification](fsinit-simplification.md)
- [MyDOS simplification implementation record](mydos-simplification.md)
- [Sector read cache](sector-cache.md)
- [SpartaDOS implementation record](spartados-implementation.md)

## Console and interaction

- [Whole rectangle scroll benchmark](whole-rectangle-scroll-benchmark.md): test-only
  copy/fill batching reduces full-screen scrolling from about 122 ms to 29.6 ms.
- [Console interaction implementation record](console-interaction-implementation.md)
- [Console input/output](console-io-design.md)
- [Native console implementation](console-io-implementation.md)
- [Console refactor development record](console-refactor-implementation.md)
- [Idle console scrolling](console-scrolling.md)
- [Console instances and windows](console-windows-design.md)
- [Cooked console contract](cooked-console-design.md)

## Programs and shell

- [Shell startup scripts](shell-startup.md): S: naming, optional STARTUP/USER,
  sequential execution before the prompt, compatibility and memory costs.
- [Shell EXECUTE](shell-execute.md): bounded scripts through ordinary dispatch,
  separate source/input ownership, inherited streams and stop/cleanup rules.
- [TAIL and FIND utilities](tail-find.md): bounded suffix buffering and recursive
  filename traversal through the existing command services.
- [Shell append redirection](shell-append-redirection.md): `>>` preserves file
  contents, seeks to EOF and uses the existing stream cleanup on success,
  BREAK and errors, with no additional bank-zero reservations.
- [System command directory](system-command-directory.md): SYS:C command
  storage, the boot C: assignment and CurrentDir-then-C: default PATH.
- [Bounded shell command aliases](shell-aliases.md): eight session-local
  definitions, one-pass expansion and normal pipeline/redirection parsing.
- [ASSIGN logical directories](assign.md): four boot-lifetime logical directory
  names, DOS-wide resolution, a loadable command and symbolic shell PATH.
- [Multiple-file arguments and LIST patterns](multiple-file-patterns.md):
  bounded `/M` results, ordered exact CAT/DELETE operands and final-component
  LIST matching on both packaged filesystem variants.
- [Small shell editor and history](shell-editing.md): cursor editing, ten commands,
  prompt-only history and unchanged bank-zero reservations.

- [Command usability](command-usability.md): bounded shell PATH, shared fault
  text and template help for all ten commands.

- [Commands for writable filesystems](write-commands.md): COPY, TEE, DELETE,
  RENAME and MAKEDIR; bounded binary transfers, cleanup, disk persistence and
  the OF816 demo, with no additional bank-zero reservations.
- [First command toolbox](command-toolbox.md): seven loadable commands, shared
  arguments/streams and foreground-console access; raw/optimized development
  checks and the refreshed OF816 distribution.
- [Resident shell — earlier guide](shell-guide.md)
- [HELLO and CAT size analysis](command-size-analysis.md)
- [Compact o65 metadata](compact-o65-implementation.md)
- [C-string literals and CSTRING](cstrings-design.md)
- [Demo implementation record](demo-implementation.md)
- [Native o65 implementation record](o65-loading-implementation.md)
- [Resident shell and DOS current directory](shell-design.md)
- [Resident shell implementation](shell-implementation.md)

## Compiler and ABI

- [Compiler ae1f555 qualification](compiler-ae1f555-qualification.md)
- [Compiler issues encountered by Exec816](compiler-issues.md)
- [Compiler refresh and Exec816 size comparison](compiler-main-refresh.md)
- [Compiler-supported NULL](compiler-null.md)
- [Native pointer-loop implementation results](compiler-pointer-loops-results.md)
- [Compiler upstream merge](compiler-upstream-merge.md)
- [Native word-address selection](compiler-word-addresses-results.md)
- [Native direct-page partition](direct-page-partition.md)
