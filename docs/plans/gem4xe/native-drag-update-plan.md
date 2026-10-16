# Native drag and queued UPDATE implementation plan

[GEM plans](README.md) · [AES contract](../../reference/aes.md) ·
[Desktop contract](../../reference/desktop.md)

ND1–ND3 are complete. See the [development results](../../history/native-drag-update.md)
for the physical regression, existing host-suite failures and memory accounting.

## Problem and intended behaviour

A Counter timer can request UPDATE while a title drag holds the mouse button.
Acquisition correctly waits for release, but the queued request makes
`MouseBlocked()` true. Input is retained, and `Suspend()` removes the outline.
The pointer moves while the drag target stays frozen. Releasing the button
eventually completes the pending repaint and move. The unchanged optimized
OF816 package reproduces this; Files alone keeps tracking.

An already captured native title or gadget gesture must keep receiving its
motion, release, Escape and loss events while an ungranted request waits.
Its outline remains visible and follows the pointer. Active UPDATE/MCTRL
ownership still excludes conflicting native work. New interactions, focus
changes and completed geometry/action commits retain the existing queue gates.
UPDATE remains pending until release; this fix does not permit application
painting during a held native gesture or change eligible-waiter ordering.

## ND1 — continuation policy

- Add a presenter-only `DESKDRAG.Continuing()` query using existing gesture
  phase and application-visual/active mouse-owner state. Include held move,
  close, size, slider and arrow gestures; exclude application file drags and
  released-button completion phases.
- Let only that captured native interaction bypass queued-request input
  deferral. Keep the normal gates for new input, widgets, menus and focus.
- Let Escape cancel that capture immediately. Keep a dirty outline runnable
  while its continuation is allowed, without making a stationary clean drag
  runnable merely because a lock is queued.
- Make outline suspension retain an eligible native continuation. Active
  ownership and the existing delegated-renderer/DMA exclusions still apply.
- Leave UPDATE eligibility, caller-local policy handoff, lock queue, geometry
  completion and physical display arbitration unchanged.

## ND2 — focused emitted-code regressions

Add a physical-mouse regression using the extracted OF816 desktop package.
Observe state and pixels without patching guest memory or injecting a timer:

1. Drag Files without a periodic client; hold and move its visible outline.
2. Drag Counter across its natural timer expiry. Prove BEGIN remains pending,
   the paint count stays unchanged, and the outline keeps tracking.
3. Release and verify final geometry, completed repaint and no leftover outline.
4. Repeat with Escape while the button is held and UPDATE is pending. Verify
   cancelled geometry and repaint resumption after release.
5. Drag Files with Counter running to cover a queued request from another
   application. Check held tracking and release.
6. Close the client and EXIT with restored resources, intact guards and no
   remaining Tasks.

Keep the failing baseline observations from the investigation. Use the same
regression on the fixed package. Run the optimized AES lock fixture for active
UPDATE/MCTRL exclusion, recursion, queue handoff and caller-local/RPC paths.
Run the host suite and relevant generated-definition checks. Raw/optimized ABI
matrices are unnecessary because public records and bridges do not change.

## ND3 — integration and accounting

Update the current AES/desktop contracts and this index with the continuation
rule. Record the actual development checks, package identity and limitations.
Build through `tools/build_demo.py --gem-desktop --release-compiler` so the
tested package includes OF816 and its five-second autoboot, matching disks,
pinned ROM, notices and checksums. Build/test output stays under `build/`.

Target reserved bank-zero growth: **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. Add no persistent state, Task,
signal, timer, VRAM surface or kernel service. Compare the actual build budgets
and report code-size changes separately. This is a development fix, not release
or real-hardware qualification.
