# New Window and initial Files drawing

[Quiet-turn baseline](presenter-quiet-turn.md) ·
[Measurements](../development/window-opening-analysis.json) ·
[Passive observer](../../tools/trace_window_open.py)

## Finding

The next gains are in window preparation and serialized service calls. On the
unchanged QT4 demo, New Window completes its frame at **641.643 ms** and its
whole image at **1002.630 ms**. The first Files redraw starts at **793.556 ms**.
There is exactly one initial content paint, with no subsequent pixel changes.

Directory enumeration costs **270.104 ms without physical disk traffic**.
Eight active-menu enable requests then cost **98.591 ms** including their
surrounding menu preparation. Files also runs the same layout twice, at
**19.21 ms of caller CPU per pass**. These costs precede, or surround, the
actual object rendering.

## Measurement scope

One passive capture reuses `build/presenter-quiet-turn/demo`, without rebuilding
or modifying guest code. It reproduces the previous frame and whole-window
times exactly. The observer iconifies Shell, closes the existing SYS: window,
then selects Desk → New Window. SYS: contains nine entries and has already been
enumerated. This is a cold window/frame with a warm directory, not cold media.

The machine remains 800XL/PAL, 65816 x8, VBXE, 64 KiB plus 63 upper banks,
accurate generic56k media, SIO patching/burst/random delay off. The JSON records
the exact compiler, package, ROM and emulator hashes. Runtime firmware IDs
depend on the disposable emulator configuration; ROM content hashes match.

Times begin at physical input scheduling, including a button release scheduled
50.750 ms later. Thus approximately **951.88 ms** remains after scheduled
release. Pixel completion is sampled once per PAL frame; it is not a precise
last-blit timestamp. Function boundaries are passive instruction observations.
CPU charges include kernel calls, scheduler/return overhead and bus stalls;
native IRQ/NMI bodies and time running peer Tasks are separate. Nested routine
costs must not be added together.

## Opening sequence

These non-overlapping elapsed phases sum to the observed whole-window time.
Presenter frame work overlaps application enumeration/preparation; the table
does not imply that all work in a phase runs in the application.

| Phase | Interval after input | Elapsed |
| --- | ---: | ---: |
| Input handling and menu dismissal | 0–142.875 ms | 142.875 ms |
| Allocate/clear Browser | 142.875–196.081 ms | 53.206 ms |
| Create, name, preserve and open window; obtain work area | 196.081–337.586 ms | 141.506 ms |
| Lock, Examine, ExNext loop and UnLock | 337.586–607.691 ms | 270.104 ms |
| Sort, summary, layout and slider preparation | 607.691–688.427 ms | 80.736 ms |
| Update active application menu | 688.427–787.039 ms | 98.612 ms |
| Dispatch initial redraw | 787.039–793.556 ms | 6.517 ms |
| Initial content redraw, including UPDATE | 793.556–979.364 ms | 185.808 ms |
| Remainder until complete pixel sample | 979.364–1002.630 ms | 23.265 ms |

The 142.875 ms first phase includes the scheduled button hold, popup restoration
and `menu_tnormal`. The latter spans 95.215–142.862 ms, but consumes only
3.587 ms of caller CPU. It waits on the existing presenter protocol.

`desktop_new()` allocates a 4,039-byte cleared Browser. That `AllocMem` consumes
27.258 ms of caller CPU and 53.095 ms elapsed. The object tree and 28,672-byte
entry array are separate allocations without `MEMF_CLEAR`. Clearing the whole
entry array is therefore not responsible for this cost.

### Directory enumeration

The application issues Lock, Examine, ten ExNext calls (nine results and end of
directory), then UnLock: thirteen DOS calls. The successful ExNext
intervals are mostly about 20 ms each. FileScanBegin takes 47.999 ms; the final
FileScanNext includes UnLock and takes 37.798 ms.

During the 270.104 ms enumeration phase, the filesystem Task consumes
111.564 ms CPU, Desktop 41.578 ms, presenter 69.397 ms and native interrupts
47.566 ms. There is no idle-Task CPU in this phase. The serial observer records
commands and receive traffic elsewhere in the capture, but none during the
whole New Window interval. This is service processing and interleaved drawing,
not a disk timeout or a 270 ms hardware read.

The source path is `FileScanNext` → `ExNext` → `DOSCALLS.Information` →
filesystem packet handling → `FSDIRECTORY` metadata/result publication. Each
entry repeats that public transaction. This capture does not subdivide the
filesystem's 111.564 ms among validation, copying, cache lookup and metadata
handling; attributing all of it to message transport would be incorrect.

### Menu and layout work

After `folder_open`, `desktop_menu` re-enables eight genuinely changed menu
items using eight separate synchronous `menu_ienable` calls. Its 98.591 ms
contains 23.896 ms caller CPU and 69.657 ms off-caller time. `view_checks` sends
no requests here; the existing unchanged-bit optimization works. No whole
application-menu paint occurs inside this interval: hidden dropdown state
changes still incur individual service exchanges.

`refresh_path` constructs the object layout at 642.259–685.591 ms, consuming
19.209 ms CPU. `redraw` repeats it at 806.269–837.760 ms, consuming 19.217 ms.
The second pass is redundant for this unchanged geometry/model. Other redraws
can follow real geometry changes, so removing all redraw-time layout blindly
would be wrong. A small explicit layout-dirty state is sufficient.

The actual `objc_draw` takes 130.604 ms elapsed and **107.649 ms CPU**, with no
peer-Task time inside it. The surrounding redraw adds layout, UPDATE admission,
paint publication and completion. It uses one `objc_draw`, not duplicate
whole-window rendering. Initial BEGIN falls back to the existing server path
in this trace; END uses the caller-local path.

### Frame drawing and scheduling

| Frame fragment | Start–return | Presenter CPU | Off-presenter time |
| --- | ---: | ---: | ---: |
| Title | 327.209–347.233 ms | 12.457 ms | 4.866 ms |
| Bottom | 395.533–433.161 ms | 6.342 ms | 29.733 ms |
| Left | 476.267–513.968 ms | 6.392 ms | 29.708 ms |
| Right/scrollbar | 554.658–622.843 ms | 17.248 ms | 47.032 ms |

The four calls total **42.438 ms presenter CPU**, 163.537 ms elapsed and
111.339 ms off-presenter time. Their elapsed sum excludes gaps between calls.
Native interrupts charged to the presenter account for the remaining 9.760 ms.
The off-presenter portions include filesystem and application execution; they
are not measurements of blitter busy-waiting.

Between fragments, the presenter consumes another 38.282 ms CPU in paint
continuation, controls, input/readiness and related work. Filesystem and Desktop
also run in those gaps. The worker already continues ready painting without an
unconditional voluntary yield between every strip. Neither a fixed per-strip
timer nor a slow rectangle fill explains the 642 ms frame-completion time.

## Recommended next work

1. **Reuse prepared Files layout.** Rebuild it only after model, view or geometry
   changes. This removes one measured ~19.2 ms CPU pass from initial opening,
   and may help ordinary redraws. Preserve slider and hit-test geometry.
2. **Publish related menu state together.** Keep ordinary GEM setters, but give
   this active-menu transition one bounded publication instead of eight serial
   exchanges. Retain menu ownership and popup invalidation. The observed
   98.6 ms is the opportunity, not a promised saving; the real mutations and
   some presenter work remain.
3. **Profile cached directory processing next.** Separate DOS transport from
   the filesystem's per-entry work before choosing a change. A bounded public
   bulk-enumeration operation is a possible follow-up if repeated transactions
   dominate. Do not bypass filesystem ownership or create a private GUI-only
   kernel operation. Measure a larger directory as well as this nine-item root.
4. **Then shorten native frame continuations.** Keep adjacent ready fragments
   together where possible and avoid repeated preparation between them, while
   preserving input boundaries, ownership and normal preemption. The current
   42.4 ms frame CPU places the hardware-rendering opportunity in perspective.

The 4 KiB Browser clear and sort scratch allocation are secondary candidates.
Do not replace required initialization with uninitialized storage. There is no
evidence here requiring priorities, suppressed preemption, a new timer or more
VRAM caching. Reordering work may improve first-visible-frame latency without
reducing total work; measure both frame and complete-content time.

## Validation and limitations

Development analysis only: one matched optimized packaged capture, one initial
paint, unchanged settled pixels, one explicit Refresh paint, unrelated desktop
icons unchanged on warmup close, and normal EXIT through the existing demo
runner. The host suite passes **490 tests with four historical skips**. No raw
build, full qualification matrix or hardware claim; no p95 or cold-media claim.

Only the observer and documentation change. Reserved bank-zero delta: fixed
**0 bytes**, each public Task **0 bytes**, idle Task **0 bytes**, including
guards, alignment and unused capacity. Guest code, upper RAM, VRAM and stack/DP
reservations are unchanged. Capture files remain under
`build/window-opening-analysis-capture`; shared measurements omit raw bridge logs.
