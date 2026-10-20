# Historical records

- [QED editing](qed-editing.md): incremental QE1–QE7 editing, document
  replacement, failure and stack development work; reliable saving follows.

- [QED application startup](qed-startup.md): QS1–QS5 resource, real editor
  startup, lifecycle and GUI-stack development evidence.

- [QED native feasibility](qed-native-feasibility.md): source preparation and
  focused ABI, owned-runtime, native-file, complete-layout and stack/admission
  evidence reconciled for step 2, with conditional budgets and the step 3 handoff.

- [Multiple shell sessions](shell-sessions.md): incremental SS1–SS8 evidence,
  explicit per-session state, native layout and concurrency checks, resource
  costs, desktop tabs, final latency observations and tested OF816 packages.

- [Shell TAB completion](shell-completion.md): resumable native editing,
  builtin/alias and streamed file/PATH matching, ownership/failure checks,
  accurate disk timings and the tested standard OF816 demo.

- [Native drag and queued UPDATE](native-drag-update.md): keep captured native
  outlines tracking across a periodic client's pending UPDATE; physical pixel,
  release, Escape, presenter-sleep and cleanup checks, with unchanged bank-zero
  reservations.

- [Directory batching](directory-batching.md): public ExNextBatch, compact results
  and prefix-preserving cancellation, shared Files/selector scanner, resource
  accounting and focused checks. Eight-entry batches reduce warm SYS:C scan
  532→298 ms and complete Refresh 836→594 ms; includes the OF816 demo.

- [Files enumeration analysis](files-enumeration-analysis.md): warm root/C
  scans take 193/533 ms without disk traffic or presenter CPU; repeated DOS
  transactions dominate the next opportunity, with bounded batch enumeration
  recommended before further popup micro-optimization.

- [Popup visibility rebuild analysis](popup-visibility-analysis.md): per-layer
  costs show a bounds-only filter has little benefit; an occlusion-aware
  selector could skip about 3.5 ms of existing geometry work before overhead,
  retaining the current damage-summary and transaction semantics.

- [Damage retirement](damage-retirement.md): skip scratch reconstruction for
  disjoint damage lists; saved-popup commit CPU 16.5 → 13.8 ms, complete
  keyboard CPU 60.3 → 57.6 ms, unchanged sampled feedback, focused checks and
  a refreshed OF816 demo.

- [Warm menu input](warm-menu-input.md): same-turn keyboard menu advancement
  and empty-paint selection guard; complete keyboard CPU 66 → 60 ms, cached
  opening 140 → 120 ms, focused checks and a refreshed OF816 demo. Complete
  keyboard frame feedback remains at 100 ms.

- [Warm menu bookkeeping analysis](warm-menu-bookkeeping-analysis.md): keyboard
  advancement waits for another presenter pass; empty-paint scans and the
  remaining saved-popup scene commit provide focused follow-up targets.

- [Clipped menu text](clipped-menu-text.md): vertical glyph-run clipping,
  focused pixel/list checks and refreshed demo; Desk popup CPU 114 → 64 ms,
  sampled response 241 → 180 ms, unchanged warm complete feedback.

- [Menu title and pointer response](menu-title-response.md): one-step small
  title repaints and actual heading-crossing measurements; complete keyboard
  feedback 120 → 100 ms, focused checks and a refreshed OF816 demo.

- [Layers visibility rebuild](layers-rebuild.md): nearer occluders first,
  disjoint skips and early completion for covered layers; rebuild CPU
  18.6 → 11.0 ms, unchanged sampled visible response and refreshed OF816 demo.

- [Popup replacement](popup-transition.md): one committed Layers/cache
  transaction, input/fairness checks and refreshed OF816 demo. Warm switching
  180 → 120 ms, presenter CPU 122 → 79 ms, observed copy gap 57 → 1 ms.

- [Dropdown bookkeeping](dropdown-bookkeeping.md): maintained-bit paint
  selection and bounded region subtraction; warm switch 201 → 180 ms,
  15% less presenter CPU, unchanged pointer response and refreshed demo.

- [Dropdown response analysis](dropdown-analysis.md): isolated cached menu
  transitions; visibility rebuilds, temporary damage and repeated readiness
  scans dominate the short VRAM copies.

- [New Window and initial Files drawing](window-opening-analysis.md): passive
  breakdown of the unchanged QT4 demo; warm enumeration, serial menu updates,
  duplicate layout preparation and frame/application scheduling costs.

- [Presenter quiet turns](presenter-quiet-turn.md): conditional signal collection,
  event-driven cache inspection and visible-damage readiness; median presenter
  CPU 4.39 → 1.76 ms, remaining tails and matched application/demo observations.

- [Presenter bookkeeping](presenter-bookkeeping.md): trusted dispatch, cheaper
  readiness/input/cache maintenance and prepared window stacking; measured
  New Window/close gains and remaining quiet-turn costs.

- [Caller-local AES UPDATE](caller-local-update.md): shared policy, presenter
  handoff, local BEGIN/END and matched application measurements.

- [AES binding cleanup](aes-binding-cleanup.md): reuse established caller
  contexts, remove reply-time identity queries and simplify direct admission;
  focused before/after CPU costs ahead of caller-local UPDATE.

- [Physical display C/Action bridge cost](display-bridge-cost.md): passive
  ownership measurements after restoring preemption; about 70 us bridge CPU
  per uncontended client pair, with C, assembly and Action costs separated.

- [Short drawing units and Task switching](drawing-preemption.md): retired
  scheduling experiment, held-display pauses, dialog costs and focused checks.

- [Dialog drawing costs and batch sizing](dialog-drawing-batches.md): current
  per-unit bookkeeping, drawing and preemption costs; four-batch starting point.

- [Rectangle overhead](rectangle-overhead.md): shorter physical display reservations,
  changed-only input publication, direct VDI bindings and cheaper ownership entry;
  matched dialog and Files observations with the refreshed OF816 demo.

- [FujiNet control](fujinet-control.md): protocol pins, FUJI reports/browsing/image changes, scripted real-frame
  integration and implementation slices.

- [Resident shell report output](shell-report-output.md): bounded row batching,
  builtin latency, formatting checks and memory costs.

- [Command loader refactor](command-loader-refactor.md): completed bulk-copy and scalar-reader
  slices, matched timings and memory costs.

- [LIST command loading](list-command-loading.md): frozen loader phase baseline,
  scalar decoding and relocation pass costs.

- [SpartaDOS listing measurements](spartados-listing-measurements.md): current
  DIR/LIST cold/warm IDE/SIO timings, first-row drawing and remaining costs.

- [Cheap directory metadata](directory-metadata.md): flags, explicit exact
  queries, caller migration and listing measurements.

- [MyDOS performance](mydos-performance.md): native copies, VTOC publication,
  retained traversal state and matched development measurements.

- [Window and menu response work](window-menu-response.md): menu request
  reduction, prompt raising and subsequent atlas/menu development evidence.

- [Window frames and desktop exposure](window-frame-exposure.md): complete frame
  sides, frame-inclusive snapshots, precise close damage and matched timings.

- [Window preservation](window-preservation.md): large client restores, explicit
  AES exposure policy, shipped-app adoption and focused packaged-image checks.

- [Compact window geometry](compact-window-geometry.md): compact title bars, gadgets and
  menus; Shell alignment, application fixes and packaged pixel checks.

- [Window iconification](window-iconification.md): presenter-owned tiles,
  normal geometry, hidden application progress and menu recovery.

- [Aligned moves and Shell backing](window-backing.md): completed AES copies,
  persistent console pixels, scrolling and matched performance evidence.

- [Shell focus without full redraw](shell-focus.md): title/caret-only focus
  changes, no-op front-window activation and physical click/pixel checks.

- [Unchanged menu backgrounds](menu-switch.md): scoped desktop updates, retained
  save-under across headings, pixel checks and matched latency measurements.

- [AES and Layers VRAM caching](aes-layers-vram.md): repaint completion,
  shared caches, incremental repairs, matched timing and memory accounting.

- [Dropdown menu latency](menu-latency.md): bounded label batching, targeted
  damage, menu precedence and matched visible-feedback measurements.

- [Loaded Process Task names](process-task-names.md): retained executable names
  in TASKS, without changing the Task API or execution domains.

- [Desktop usability](desktop-usability.md): a default 4×4 Files grid, RAM disk
  icon, compact delete confirmation, shorter Shell title and desktop spacing.

- [Files navigation and appearance](files-navigation-appearance.md): distinct
  title gadgets, compact layout and parent navigation implementation results.

- [Compact Files windows](compact-files.md): navigation glyphs, one status line,
  stable window sizes and separate keyboard focus.

- [Desktop drag and drop](desktop-drag-drop.md): captured file selections,
  one AES completion and the existing buffered copy job.

- [Exec816 desktop style](desktop-style.md): restrained palette, distinct icons,
  window decoration and a persistent focused-window menu caption.

- [Sixteen-colour GEM icons](colour-icons.md): standard CICON resources,
  prepared VBXE pixels, the desktop disk artwork and Files' VRAM icon cache.

- [Desktop selection and batch operations](desktop-selection-batch.md):
  implementation progress, focused checks and memory accounting.

- [Desktop copy throughput](desktop-copy-performance.md): buffer comparison,
  shell COPY reference, cancellation and concurrent button feedback.

- [G4BENCH port](g4bench-port.md): loadable benchmark slices and measurements.
- [G4BENCH drawing traces](g4bench-drawing-traces.md): caller, renderer, blitter
  and scheduling costs in the unchanged packaged desktop.
- [GEM rendering performance](gem-rendering-performance.md): implementation
  slices and measurements following those traces.
- [Bounded IDE read ranges](ide-read-ranges.md): device, cache and filesystem
  grouping, memory costs and matched development measurements.

- [Filesystem and DOS performance](filesystem-dos-performance.md): shared
  SIO/IDE optimizations, matched measurements and memory costs.

- [AES UPDATE admission latency](update-admission-latency.md): logical lock,
  presenter painting and physical display handoff attribution, rejected renderer
  experiments and frozen input/cancellation comparisons.

- [GEM text viewer performance](text-viewer-performance.md): VDI text costs and measured tuning.

- [GEM text viewer](text-viewer.md): bounded document loading and application evidence.

- [Standard GEM file selector](file-selector.md): shared directory helpers and
  the file-selector implementation's development evidence.

- [Standard GEM dialogs](standard-dialogs.md): host lifecycle and development
  evidence for synchronous forms and alerts.

- [GEM application stack headroom](gem-application-stack-headroom.md): attribution,
  ordinary stack growth and packaged desktop checks.

- [Editable dialogs](editable-dialogs.md): caller-local TEDINFO and Files dialogs.
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

- [IDE diagnostics](ide-diagnostics.md): retained controller, APT and mount failure evidence.
- [IDE Plus block driver](ideplus-block-driver.md): transport separation and native ATA development evidence.
- [IDE-only demo](ide-only-demo.md): IDE system-volume selection and separate-profile development evidence.
- [IDE 512-byte sector refactor](ide-512-sector-refactor.md): independent media,
  reads/writes, shared cache, matched COPY measurements and real BIOS handoff.

- [RAM filesystem](ram-filesystem.md): shared-worker backend, dynamic storage,
  allocation failures, command integration and memory costs.

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

- [Compressed kernel loader](loader-compression.md): streaming LZ4 implementation,
  actual standard/VBXE XEX sizes, emitted decoder speed and boot checks; the
  [64 KiB follow-up](loader-compression.md#64-kib-follow-up) measures the larger default.
- [Boot image compression experiment](boot-compression.md): bank-bounded LZ4,
  LZ4-HC and DEFLATE measurements, exact-byte round trips and modeled XEX sizes.
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

- [MyDOS verified-write timeout](mydos-write-timeout.md): a two-second mechanical
  allowance for Generic verified WRITE, bounded failure checks and accurate
  256-byte MyDOS COPY regression.
- [Queued device I/O and SIO](device-io-sio-design.md)
- [Queued device I/O and SIO implementation](device-io-sio-implementation.md)
- [Shared serial IRQ adapter](serial-irq-adapter.md)
- [Nominal 57.6 kbaud SIO](sio-57600.md)
- [SIO driver migration record](sio-driver-boundary-implementation.md)
- [POKEY IRQ-to-worker latency proof](sio-latency-poc.md)

## Filesystems and DOS

- [User mounted SIO filesystems](user-sio-mounts.md): completed UM0–UM5,
  bounded automatic geometry, named mounts, busy/cancellation semantics,
  audited writes, disk swaps and public ABI checks.
  [Completed design](user-sio-mounts-design.md).
- [Directory listing performance](directory-listing-performance.md): DL0–DL6,
  matched warm root/SYS:C gains, one Write per row, exact extent caching,
  invalidation/lifetime checks and upper-RAM costs.
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
  writer retirement, failure outcomes, native round trips and the OF816 demo;
  [normal write completion](filesystem-write-implementation.md#normal-write-completion)
  removes mandatory SIO/IDE readback verification.
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

- [INFO command](info-command.md): copied DOS volume queries and the incremental
  implementation of loadable volume statistics.
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
  the OF816 demo, plus COPY directory destinations and bounded COPY/DELETE
  patterns, with no additional bank-zero reservations.
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
