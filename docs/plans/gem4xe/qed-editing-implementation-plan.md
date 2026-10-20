# QED editing implementation plan

[GEM plans](README.md) · [Editing design](qed-editing-design.md) ·
[Strategy](qed-port-strategy.md) · [Startup baseline](../../history/qed-startup.md)

Status: strategy step 4 in progress; QE1 passes its development checks,
recorded in the [editing history](../../history/qed-editing.md). QE2–QE7 are
pending. Implement the
[editing design](qed-editing-design.md) in the following executable slices.
Each slice builds on the ordinary loaded QED APP and commits after its selected
development checks. Record a design amendment before relying on a measured
departure. Reliable saving remains strategy step 5.

| Slice | Runnable result | Depends on |
| --- | --- | --- |
| QE1 | Keyboard insertion/deletion and safe modified-document retirement | QS1–QS5 startup baseline |
| QE2 | Correct fixed-font redraw, caret and long-line navigation; transparent VDI text | QE1 |
| QE3 | Event-driven pointer/keyboard selection with visible ranges | QE2 |
| QE4 | Internal Cut/Copy/Paste and grouped Undo, with coherent failure behavior | QE3 |
| QE5 | Native cancellable dialogs and literal Find/Find Next | QE4 |
| QE6 | Checked reading and transactional single-document Open/New/launch arguments | QE5 |
| QE7 | Reconciled editing session, failure/reuse/stack evidence and step 5 handoff | QE1–QE6 |

## Rules for every slice

- Keep source pins, patch preparation and the native source-selection ledger
  reproducible. Change generated resource/ABI outputs through their inputs
  and generators. Leave historical QF/QS evidence unchanged.
- Execute changed behavior optimized through emitted code, using the real loaded
  editor when asserting an application outcome. Focused actual-source probes
  can isolate failures; they do not replace the application gate. Add raw cases
  only for changed compiler-facing boundaries or a focused defect diagnosis.
- Check text state and visible pixels independently. Preserve bounded completion,
  DP/register restoration, stack/domain guards and IRQ/NMI checks. Update the
  source frame ledger and observe newly reached deep chains in that slice;
  do not postpone stack feasibility until QE7.
- Report code/data/container/provider changes against QS5 and remaining frozen
  allowances. Report reserved bank-zero delta as fixed / per-public-Task /
  private idle, including guards, alignment and unused capacity. Target **0/0/0**;
  the user permits a measured stack increase when needed, as recorded in the design.
  charge upper-image, live heap, backing/rounding and transient peaks separately.
- Run the host suite and affected generator checks for code changes, plus the
  selected emitted regressions. Documentation-only follow-ups need content and
  local-link checks. Reuse passed results only with matching relevant inputs.
- Keep partial slices usable within their stated scope. Unsupported live entry
  points are disabled, not successful no-ops. No QED-specific kernel hooks,
  second editor implementation, production failure mode or full raw system
  matrix is selected.

## QE1 Keyboard editing and safe retirement

Audit `event.c`, `tasten.c`, `nkccinit.c`, menu dispatch and the retained editing
defaults together. Publish an explicit native key/action table. Preserve menu
shortcut precedence, handle the native cursor scans before donor Control-arrow
semantics, reject unhandled Control-letter insertion, and remove Escape's
deferred macro path. Set literal tabs, no autoindent/soft wrap/reformatting and
LF for new documents. Exercise Insert/Overwrite through the same state.

Before accepting mutations, make dirty Close/Quit/Stop and replacement entry
points safe: use Cancel-default Discard/Cancel, treat alert zero as cancellation,
disable Save/Save As and every automatic live save path. Until QE6, disable
New/Open replacement commands. Until QE3, disable document pointer selection
and detach the unsupported drag wait from the live path. Keep clipboard/Undo,
Find and donor MDIAL entry points disabled until their owning slices establish
the live behavior. As later slices land, enable each command with its actual
semantics; retain no compatibility profile.

Adapt insertion, Backspace/Delete and line split/join failures in their owning
text routines. Preserve the 1,023-byte logical-line limit, prepare required
backing/Undo state before mutation and mark dirty only on success. Establish
bounded private test observations of ring bytes, cursor, ending and dirty state;
do not let the observer insert text or bypass event dispatch.

Completion checks:

- Physical/native keys edit the actual empty document: printable bytes, Tab,
  Return, insertion and overwrite, Backspace/Delete and boundary joins. Check
  expected logical bytes, caret location, title/modified state and selected
  native pixels. A shortcut produces its action without inserting its letter.
- At the line limit and a selected backing-allocation failure, reject the
  command coherently and retain prior text. Navigation does not dirty it.
- Dirty Close, Quit and cooperative Stop support Cancel and explicit Discard;
  cancellation leaves the Process live, and consent returns through normal
  collection/unload. The supervisor must not wait for retirement after Cancel.
- Update the frame/callback ledger and observe mutation, alert and retirement
  chains. Retain focused startup/cleanup coverage without repeating every QS
  acquisition-failure case.

Commit the executable slice and its scoped development evidence.

## QE2 Redraw, viewport and transparent VDI text

Implement the design's public `MD_TRANS` behavior in named/parameter-block
VDI dispatch and the actual renderer. Keep replace as the workstation default;
invalid modes preserve the previous mode. Solid bars remain solid in both
accepted modes. Preserve user/visible clipping, damage, bounded drawing units
and caller/workstation isolation. Update the machine-readable VDI layout and
capability inputs, generated definitions and applicable component versions.
Rebuild matched provider/callers; bump the APP import ABI only if its contract
actually changes.

Refactor QED's bounded row painter to accept normal/selected foreground runs
and explicit background fills, restoring replace mode on return. Use it for
cursor repair, blink and full/partial redraw. Repair long-line arithmetic,
tab-to-byte conversion and viewport clamping. Implement native arrow,
line/page/start/end navigation and vertical gadgets, retaining horizontal
cursor-driven panning without new horizontal window gadgets.

Completion checks:

- A small raw/optimized emitted probe verifies changed record fields/layouts
  and the VDI call boundary. Optimized native pixel cases prove transparent
  glyph backgrounds, unchanged replace behavior, both accepted solid-bar modes,
  unsupported-mode rejection, two-workstation attribute isolation and clipping
  at odd X/partial glyph edges.
- Actual QED navigation reaches both ends of long and tab-expanded lines,
  including positions whose absolute pixel coordinate exceeds signed WORD.
  Confirm desired-column movement, viewport origin, byte cursor and pixels.
- Move, resize/full, scroll and overlap/expose the real document with another
  ordinary GEM window. Complete redraw and incremental repairs agree; blank
  rows and old caret pixels are cleared and other windows are preserved.
- Record current provider/private costs, deep drawing stack use and any affected
  existing VDI caller regressions. Selection commands remain disabled until QE3.

Commit after the selected checks pass.

## QE3 Selection without a nested modal wait

Replace `wi_click`'s `MU_M2`/MCTRL loop with the design's Ready, Selecting and
release-rearm states in the outer event dispatcher. Use left down/release,
`MU_M1`, normal messages/keys and a nonzero outside-work autoscroll deadline.
Rely on existing native work-area capture; hold UPDATE only during painting.
Process release coordinates before ending the gesture and handle combined bits
once. Add input-loss/cancellation handling and bounded failure exits.

Use stable byte anchors for Shift-navigation/Shift-click, normalize half-open
ranges and map tabs/newlines into the QE2 painter. Enable mouse placement,
contiguous selection and Select All. Disable donor brace/word/column and block
drag/drop paths consistently. List actual physical key limitations.

Completion checks:

- Actual physical clicks/drags select forward and backward, across tabs/blank
  lines and beyond each viewport edge. Fast press/release and release outside
  work use the retained endpoint. A held button cannot retrigger selection.
- Verify bytes/range endpoints and independent normal/selected/caret pixels,
  including selected tab spaces, selected newline cells and exposure repair.
- Logical Shift-navigation and reachable physical Shift/Shift-click routes
  agree. Escape, focus/geometry messages, close/Stop and a targeted native
  input-loss case retire gesture state and permit another gesture.
- A stationary outside pointer produces bounded autoscroll; an inside held
  pointer waits without polling. Another GEM client can handle events/draw.
  Verify no residual UPDATE/MCTRL ownership after cancellation or exit.

Record stack/cost evidence and commit.

## QE4 Clipboard and donor Undo

Wire selected actions to the actual text/block/clipboard routines. Copy/Cut
require a selection; remove the current-line Copy fallback. Keep clipboard
contents internal and preserve them across document replacement. Preflight
line lengths/counts and acquire clipboard/Undo/line backing before destructive
changes, including selection replacement and multi-line paste. Fix affected
failure paths in the owning routines.

Establish and document the donor's single operation-group Undo and toggle
behavior through emitted execution. Keep dirty state conservative and reset
Undo on later successful document replacement. Add no multi-level history or
external clipboard service.

Completion checks:

- Menu and shortcut Cut/Copy/Paste/Undo act on identical real selections,
  including tabs, newline-only ranges, end-of-file and multi-line content.
  Check exact logical bytes, selection/cursor and pixels after each command.
- Repeated Undo establishes the documented grouping/toggle behavior. A new
  edit invalidates stale group ownership without claiming a saved baseline.
- Failure acquiring a replacement clipboard, Undo backing or paste storage,
  and a paste/join beyond the line limit, retain coherent prior document and
  clipboard state with an error. No partially published ring survives.
- Repeated clipboard/Undo replacement and exit return owners; record transient
  heap peaks and the deepest new block/Undo chains.

Commit after these development checks.

## QE5 Native dialogs and literal Find

Replace selected donor MDIAL paths with native forms/alerts/selector adapters.
Remove signed-result masking before validation in all reachable callers,
including About and error/modified alerts. Preserve object/tree ownership,
recenter to accepted geometry and report non-fitting forms. Retire unused
MDIAL units in the selection ledger where the final call graph permits it.

Implement one bounded resumable command/draft in private upper storage. On
`AES_PENDING`, return from the retired dialog before consuming/dispatching the
exact deferred message. Resume drafts only after compatible geometry policy;
Close/Stop/replacement cancels them. Respect native selector path[128]/leaf[13]
bounds and keep its later Open integration disabled until QE6.

Generate the honest Find-only resource while preserving retained local IDs.
Implement 50-byte literal, case-sensitive, forward Find/Next without wrap;
remove ignored control entry points. Preserve the last accepted pattern on
Cancel, select/reveal a match, retain position on not-found and process
cancellation/messages between bounded search steps.

Completion checks:

- Actual QED Find field editing, keyboard focus, press/release/outside release,
  Find/Next, Cancel/Escape and not-found outcomes match text/range/pixel oracles.
  Literal metacharacters remain literal; repeated Find Next advances past the
  match. Pattern limits, line ends and long-line targets behave explicitly.
- About, error and modified alerts work through the same native lifetime rules.
  Test negative form results and alert zero without indexing/consent errors.
- Move/size/close/Stop interrupts dialogs without recursive document actions,
  duplicated messages or leaked edit associations. Another client remains
  interactive. Test too-small geometry and one dialog-allocation failure.
- Exercise the selector adapter with real native file selection/cancellation,
  path bounds and policy interruption in a focused loaded probe. Selecting a
  path at this slice does not publish another document.

Reconcile full dialog/search/alert stack chains and commit.

## QE6 Checked load and transactional replacement

Implement detached candidate ownership in QED's reading/controller paths.
Fix buffer-allocation cleanup, negative versus short/EOF reads, terminal Close,
uniform LF/CRLF detection across 4 KiB read boundaries, NUL/CR-only/mixed-ending
rejection, line limits and checked counts. Keep newline-free/empty input and
final-newline representation byte-preserving. No create, write, backup, metadata
mutation or binary-extension auto-mode belongs in Open.

Route zero/one launch argument, menu Open and New through the single-document
controller. Remove the donor multi-file callback. Prepare every fallible
candidate allocation/metadata operation before the modified decision and ring
transfer. Commit into the existing document/window, repair sentinel links,
reset Undo/selection/viewport and preserve the clipboard. On Cancel/failure
free only the candidate. Enable New/Open when this sequence works.

Completion checks:

- Actual QED opens fixtures on RAM, MyDOS and SpartaDOS via native paths,
  including a relative path. Use a focused read-only fixture set, not the
  step 5 write/geometry/transport qualification matrix. Check exact logical
  bytes, ending/final-line state, title, clean state, viewport and pixels.
- Cover empty, LF/CRLF, final unterminated line, tabs, a 1,023-byte line and
  multi-bank text storage. Include CR/LF pairs split at the read boundary;
  reject NUL, mixed/CR-only and 1,024-byte logical lines without conversion.
- Negative/short reads, terminal Close failure, missing file and representative
  candidate/buffer/line-allocation failures retain the old document, Undo,
  cursor, selection and viewport. Check original native causes across cleanup,
  descriptor retirement and no residual candidate blocks.
- Dirty New/Open cover Discard, Cancel, selector Cancel, interruption during
  reading/decision and failed candidate preparation. Require exactly one
  document/window before and after each result. A failed launch path leaves
  an error plus empty document; extra arguments are reported.
- Observe read/selector/decision/commit/unwind chains and double-document peak
  memory. Verify representational limits and record concrete tested byte/line
  sizes. Repeated Open/New is reusable without accumulation.

Commit the checked replacement slice.

## QE7 Reconcile the editing gate and hand off saving

Extend the baseline audit/observers to bind editing fixtures, resource bytes,
source/runtime/provider inputs, current ABI and stack attribution to one
ordinary executable. Record a concise editing development JSON and history
page; link the actual artifacts rather than copying build sizes into contracts.
Preserve all earlier evidence with its original scope.

Run a combined real editing session: launch, Open a long tabbed document,
navigate/pan, mutate, select, Copy/Cut/Paste/Undo, Find/Next, overlap/expose,
cancel a replacement, commit another, then dirty Close/Stop Cancel and Discard.
Use exact state and pixel checkpoints. Pair it with selected operational
failure/reuse cases, full-chain stack samples and ordinary collection/unload.
Reconcile source bounds and the continuation allowance for the newly executed
workflows; leave future Save chains explicitly conditional.

Run affected host/generator/content/link checks. Refresh standard/GEM demos
only for affected shared provider/caller changes, using tools/build_demo.py
with OF816, pinned ROM/licenses and the five-second standard autoboot. Smoke
the exact packages and verify that private QED artifacts remain absent.
Do not rebuild or rerun unchanged passing packages solely for the final
documentation commit; retain their matching identities and evidence.

Update strategy/indexes/port instructions and the supported/unsupported table.
Mark step 4 complete only when QE1–QE6 and the combined session support the
real editing/replacement outcome. Hand step 5 a working editor, retained file
format properties, explicit Discard/Cancel restriction and known failure/stack
budgets. Save/Save As, existing-file confirmation, backups, finalization and
persisted-byte recovery remain unimplemented acceptance work.

Commit the reconciled evidence and documentation. These are development
checks, not hosted-system or release qualification.

Design/plan-only reserved bank-zero delta: **0 fixed, 0 per-public-Task,
0 private idle bytes**, including guards, alignment and unused capacity.
No executable or demo is changed by preparing these documents.
