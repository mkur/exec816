# QED startup implementation plan

[GEM plans](README.md) · [Startup design](qed-startup-design.md) ·
[Strategy](qed-port-strategy.md)

Status: QS1–QS4 implemented with [development evidence](../../history/qed-startup.md).
QS5 follows. Implement strategy step 3 in the following order.
Commit this design/plan, then commit each slice after its development checks.
Preserve pinned upstream inputs and record any evidence-driven design amendment
before depending on it. Every implementation slice reports reserved bank-zero
delta, including zero, and upper-memory costs separately.

| Slice | Deliverable | Completion gate |
| --- | --- | --- |
| QS1 | Compact reproducible resource, matching identifiers and complete bounded resource support | Actual loaded emitted code acquires every retained tree/free string; extents, relocation, writable fields, failed replacement and resource reuse are checked. Host audit proves menu links/identifiers and limits. |
| QS2 | Fixed-font source adaptation and real remaining input binding | Complete retained graph links without analysis traps. Focused optimized drawing/input checks and small raw/optimized binding/layout checks pass. |
| QS3 | Runnable real QED APP and ordinary startup/close | Actual resource/menu and editor callbacks open an empty document and return after Close/Quit through normal loading and collection. All legal-base relinks pass. |
| QS4 | Failure unwind, repeat launch and full-chain stack evidence | Acquisition failures and Stop retire owners; repeated runs restore resources. Observed GUI stack, DP, guards and asynchronous context checks meet the design's budgets. |
| QS5 | Reconciled evidence, documentation and matching demo callers | One baseline supports all gates and costs; affected generators/host checks and exact-package standard/GEM smokes pass. Strategy hands off editing and saving accurately. |

## QS1 Resources and bounded ownership

Add a resource generator under tools and a reviewable selection/mapping under
ports/gem4xe/apps/qed. Prepare a separate work copy, retain necessary trees and
strings, generate a compact menu and matching qed.h, flatten decorations and
record exact counts/bytes/hashes. Patch resource initialization and menu state
updates to use only valid identifiers. Keep every initial-scope operation
reachable and every deferred operation absent or explicitly disabled.

Extend the public resource implementation and documentation for 16 trees,
64-object trees and standard R_STRING/R_FRSTR results. Keep the total-object
and menu ceilings unchanged. Check free-table extents/terminators before
relocation; relocate pointer slots once. Audit form/popup storage and traversal.
Exercise the generated resource using a real loaded C Process, including failed
replacement, bounds and repeat ownership cleanup. Run the host suite and small
raw/optimized pointer/layout cases for the new resource-access boundary.

## QS2 Fixed-font rendering and input

Patch retained QED/CFLIB callers, preserving donor notices. Remove dead menu,
3D capability, pointer hiding and cursor-shape assumptions. Implement the
fixed-font editor renderer with public clipped v_bar/v_gtext; convert top to
baseline. Use redraw cursor/scroll operations. Do not add successful dummy
bindings or keep a second editor implementation.

Implement general graf_mkstate with named/AESPB entry, synchronized snapshot
and no event consumption. Update machine-readable import inputs, generate the
current ABI and rebuild matching provider/applications. Execute a small binding
probe in raw and optimized modes, plus selected optimized pixel/input behavior.
Compile the entire selection and account for every former analysis binding.

## QS3 Executable startup

Extend build_qed.py with a real executable mode using ordinary image packing,
minimum-stack metadata and all legal-base relocation verification. Preserve
the independent analysis-artifact rejection. Record the complete source/link
closure and changed private/provider sizes against step 2 allowances.

Fix actual startup acquisition, required resource pointers, geometry, title and
window flags against native contracts. Keep CFLIB's single workstation owner.
Execute actual QED main/event callbacks with SYS:QED.RSC and an empty document;
observe installed menu, document window and drawn pixels. Close through real
application event delivery and collect/unload normally. Exercise Quit as a
separate event path. Report execution limits: this does not qualify editing or
Save.

## QS4 Failure, reuse and stack closure

Add fixture-only failures at AES/workstation, resource/menu and document/window
acquisition boundaries. Run missing/malformed resource and bounded allocation
failures. Preserve the initial error, retire every acquired borrower in reverse
order and prove no residual menu/window/context/lock/signal/image ownership.
Exercise ordinary Close, Quit, cooperative Stop, then repeated load/run/collect/
unload with real startup. Prefer existing failure mechanisms and public calls.

Use the passive stack observer on the actual QED APP and provider, with physical
pool/Process lifetime/DP attribution and after-reservation samples. Include
resource load, menu, initial redraw, Close/Quit, Stop and failure cleanup. Update
the frame ledger for adapted paths; distinguish measured chains from future
editing/dialog paths. Resolve any exceeded continuation, allowance or stack
budget at its owner before declaring the gate complete.

## QS5 Reconcile and hand off

Add concise development JSON and implementation history identifying exact
sources, tools, runtime, ROM/emulator, cases, costs and observation limits.
Update documentation indexes, strategy, source/build instructions and binding
dispositions. Preserve historical QF evidence unchanged.

Run development host checks, affected generators, content/local links and only
newly justified native checks. Rebuild the standard and GEM development demos
with matching callers via tools/build_demo.py, including OF816 and the pinned
ROM/notices. Preserve standard shell/prime autoboot and exclude private startup
fixtures/reports from ZIPs. Run standard and affected GEM launch/close smokes
on the exact packages. Mark step 3 complete only when QS1–QS4 evidence supports
the actual resource/menu/window/lifecycle gate. Hand off editing, long-line
interaction, dialogs and reliable Save to steps 4–5.

Design/plan-only reserved bank-zero delta: **0 fixed, 0 per-public-Task,
0 private idle bytes**, including guards, alignment and unused capacity.
