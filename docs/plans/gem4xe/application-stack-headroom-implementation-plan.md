# GEM application stack headroom implementation plan

[GEM integration](README.md) · [Roadmap](../../roadmap.md) ·
[Stack checks](../../contributing/stack-checks.md) ·
[Task capacity](../../architecture/task-capacity.md)

Status: SH1 and SH2 complete at the development tier; SH3 is pending. This follows the completed editable-dialog
milestone; the existing stack and Task contracts are sufficient for this work.

The user explicitly permits larger stacks and prefers them to a major refactor.
SH2 enlarges the five ordinary pools to 1,280 bytes and repack the temporary
boot arena. A small renderer experiment saved 96 nested frame bytes; it is not
retained. Existing renderer ownership and allocation remain unchanged. See the
[execution record](../../history/gem-application-stack-headroom.md).

## Goal and baseline

Give ordinary application Tasks **at least 128 bytes of measured headroom above
the existing checked floor** throughout the selected desktop scenarios. Preserve
the 256-byte interrupt reserve, guards, Task capacity and caller-owned state.
This is a development gate for those scenarios, not a universal stack bound.

Reuse the [ED3 evidence](../../development/editable-dialogs-ed3.json) and its
recorded OF816 ZIP, compiler inputs and emulator configuration as the baseline.
The narrowest recorded 1,024-byte worker stacks were:

| Walkthrough | Physical slot | Touched depth | Remaining above floor |
| --- | --- | ---: | ---: |
| Files | 3 | 740 bytes | 28 bytes |
| Files | 5 | 751 bytes | 17 bytes |
| Calculator | 3 | 719 bytes | 49 bytes |
| Calculator | 4 | 707 bytes | 61 bytes |
| Calculator | 5 | 695 bytes | 73 bytes |

These are cumulative slot watermarks, including previous occupants. The
17-byte result does not yet identify a particular Files call or even prove
that Files caused it. Boot-fill scans detect written bytes; unwritten reserved
frames and bytes equal to the fill pattern can hide deeper use. Attribution
and emitted-frame inspection therefore precede changes.

With the current 1,024-byte pool, the target permits at most 640 bytes of
application depth before the reserve. The largest observed touched depth needs
at least 111 bytes of improvement; SH1 may reveal a larger requirement.

## Implementation slices

Commit each passing slice, with its actual development checks and memory costs.

| Slice | Work | Completion gate |
| --- | --- | --- |
| SH1 | Attribute the low margins to Task lifetimes and call paths | Identify a deep path and its Task lifetime; choose a measured reduction or budgeted growth |
| SH2 | Budget and enlarge ordinary stack pools without changing the renderer | Reach the 128-byte target in focused reproductions, with correct behavior and ownership |
| SH3 | Validate the integrated desktop and distribution | Both walkthroughs pass on the same final OF816 package; record margins and costs |

### SH1 — attribute stack use

Extend the existing stack/desktop observers only as needed. Record Task slot,
Process identity and lifetime, application, operation, stack bounds and minimum
S alongside the fill watermark. Use loaded application symbols and the
existing Process observer to distinguish startup, execution, collection and
slot reuse. Take snapshots before debugger helpers reuse retired stack space;
never refill a live stack.

Replay the relevant Files editing/redraw/DOS operations and calculator paths
with targeted emulator observations. Correlate new watermark depths with live
owners; use isolated runs or direct S observations when a previous occupant
already established a deeper watermark. Inspect emitted Calypsi listings and
Action! frames for the candidate call chains, including bridge and interrupt
boundaries. Sparse samples alone do not establish maximum depth. Avoid adding
logging calls to the measured application path, and replay without intrusive
instrumentation before accepting a result.

Produce a short table of deepest call chains, frame sizes, nested runtime
costs and proposed savings. Keep application, kernel and interrupt depth
separate. Start with Files dialog/redraw paths, `aes-edit.c`, `aes-objects.c`
and any drawing or DOS bridge reached by the trace. These are candidates,
not established causes. Files already keeps its large model outside the stack
and allocates the second Rename path in upper RAM.

Bank-zero reservation delta: **0 fixed, 0 per public Task, 0 private idle**.

### SH2 — enlarge ordinary pools and repack boot storage

Increase the five ordinary eight-Task pools from 1,024 to 1,280 bytes. Preserve
root/kernel/large-worker/idle sizes, 16-byte guards on either side, 256-byte
interrupt reserves, generic pool admission and the current Task API. Keep the
renderer unchanged; the measured small reduction would leave too little margin.

This adds **256 bytes per ordinary pool**, totaling 1,280 reserved bank-zero
bytes, with zero fixed-runtime or idle growth. The ED3 guarded stacks end at
`$5B40`, only 176 bytes below staging. Move staging to `$60F0–$64FF` and the
manifest to `$6500–$6CFF`. Reserve `$6D00–$78FF` for the loader (3 KiB, down from
5 KiB); its current 1,874-byte payload leaves 1,198 bytes of spare capacity.
The enlarged guarded stacks end at `$6040`, retaining the 176-byte gap.

Validate every phase through the generated memory map, including guards,
alignment and unused capacity. Derive diagnostic borrowed buffers from that
map so they do not overwrite live stacks. Rebuild callers and check OF816
loading/return, checked-floor rejection and physical I/O with preemption.
No Process stack-size ABI or application-specific slot reservation is needed.

Report the actual delta from the **ED3 layout**, separately for fixed storage,
each public Task and private idle, including unused reserved capacity. Also
record upper-memory/image/heap costs and cleanup. Do not mistake the older
compaction baseline used by `stack_budget.py` for this slice's before-state.
If the target remains unmet, record the remaining deficit and keep the gate open.

### SH3 — integrated validation and package

Use development checks under the [testing policy](../../contributing/testing.md):

- Run host checks and the affected optimized object/edit, drawing or DOS
  fixtures through emitted machine code. Use a small raw/optimized context or
  bridge probe only if its ABI, layout or restoration behavior changes.
- Exercise supported maximum-length editing, invalid/default/cancel actions,
  overlap/exposure, shrink/grow, directory refresh, successful and failed Path,
  New Folder and Rename, child collection, close and relaunch/slot reuse.
  Include calculator interaction beside the shell and counter.
- Require correct pixels, heap return, ownership release, intact guards and OS
  return. Record all participating Task, kernel and idle margins so a local
  saving cannot hide moving the problem elsewhere. Cover real SIO and selected
  VBI/IRQ boundaries when they occur in the measured deep paths.

Build the final desktop with `tools/build_demo.py --gem-desktop`, retaining
OF816, five-second autoboot, matching disks/ROM, notices and checksums. Run
`tools/test_gem_desktop_boot.py --files-only` and
`tools/test_calculator_desktop.py` against that same package, using separate
working directories. Keep observers and intermediates outside the ZIP.

Store detailed development output under `build/gem-stack-headroom/`. Add a
compact `docs/development/gem-application-stack-headroom.json` record and
`docs/history/gem-application-stack-headroom.md`, updating their indexes.
Record exact source/compiler/package inputs, attributed paths, old/new frames
and margins, bank-zero and upper-memory deltas, observer limits and executed
test scope. Update current stack contracts only if they changed. SH3 adds
**0 fixed, 0 per-public-Task and 0 private-idle reserved bank-zero bytes**.

Completion requires the 128-byte application target in the selected scenarios
and no new stack, ownership or visible behavior regression. This work does not
close HY4/PI4, qualify real hardware or require a full qualification matrix.
