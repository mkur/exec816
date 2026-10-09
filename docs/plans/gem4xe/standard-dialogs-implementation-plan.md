# Standard GEM dialogs implementation plan

[Design note](standard-dialogs-design.md) · [GEM integration](README.md)

Status: FD1 passes development checks; FD2–FD4 remain planned. See the
[execution record](../../history/standard-dialogs.md).

Implement the design's caller-local `form_do`/`form_alert` profile, including
the small `form_dial` lifecycle needed by normal GEM call sequences. Preserve
the single-window application model and existing event-driven callers. Each
slice produces executable behavior and a separate commit after its development
gate passes. No new baseline or performance project is required.

## Slices

| Slice | Working result | Development gate |
| --- | --- | --- |
| FD1 | Dialog host lifecycle, centering and `form_dial`; temporary host/workstation when needed; durable borrowed-content repair | Named/AESPB lifecycle and focused layout probes; allocation rollback, full desktop, repair/message ordering and unchanged borrowed resources |
| FD2 | `form_do` editing, buttons/radios, input feedback, exposure and interruption | Optimized emitted form scenarios, physical input, two callers, exact message preservation, focus and stack checks |
| FD3 | Bounded `form_alert` parser/layout/icons using the same session and loop | Parser boundaries, independent pixel expectations, button/default results and complete failure/cleanup checks |
| FD4 | Loadable dialog example and refreshed OF816 desktop package | Exact ZIP walkthrough beside shell/counter/panel, shutdown/heap return, measured stack headroom and current documentation |

## FD1 Dialog host and lifecycle

Add a small `aes-form.c` binding implementation and private upper-memory session
state. Keep the existing window, workstation and display APIs as the owners of
their resources. No separate server-side dialog service or general UI framework
is needed.

Implement these complete paths:

- Borrow a shown window; verify the requested form extent fits once, without
  changing application geometry, menu or workstation attributes.
- With no allocated window, open a normal temporary window and, only if absent,
  a private workstation. Use existing capacity/focus/close policies.
- Reject an allocated-but-closed host, nesting and caller-owned UPDATE/MCTRL.
  Track any missing caller lock depth on successful transitions, with no hot
  query RPC. Preserve existing recursive `wind_update` semantics.
- Extend `form_center` to calculate temporary-host placement without allocation.
  Implement START/FINISH and animation-free GROW/SHRINK. An emitted fixture must
  exercise center/start/short locked draw/finish before adding the event loop.
- Add one epoch-tagged local repair fact, independent of the existing deferred
  message. Integrate readiness/delivery/retirement with the existing message
  matcher. Test deferred-message first, repair next, later queued messages last;
  ordinary WM-shaped messages remain opaque and a full receive queue cannot
  lose repair.
- Make partial failure and `appl_exit` unwind only internally owned resources.
  Preserve storage if a consumer/grant cannot yet retire. Preserve the original
  result diagnostic unless cleanup itself fails.

Update declarations, AESPB counts/dispatch, binding manifest, component exports,
shared context layouts/generators and all affected callers together. Rebuild
GEMSYS and applications for the single current ABI. Record new donor inputs
through the existing extraction/pin mechanism; leave `~/atari/gem4xe` untouched.

Use host checks plus one small raw/optimized probe for changed C/context layout
and dispatch boundaries. Run lifecycle, message and ownership tests optimized,
including interrupts at publication/retirement boundaries where changed. Verify
no window/port/signal/grant/allocation leaks, no focus steal on borrowed finish,
and normal focus restoration when the temporary host closes.

## FD2 Form interaction

Implement named and AESPB `form_do` on FD1 sessions. Direct calls own an implicit
session; explicit START permits repeated calls until FINISH. Do not retain the
per-call busy flag across nested AES helpers, or overwrite outer AESPB inputs
with inner calls.

Reuse the extracted object/form helpers and `objc_edit`; keep the donor's global
screen ownership, polling loop and synchronous watchbox out of the binding.
The new loop uses current `evnt_multi` input/message readiness, short UPDATE
sections and the existing display grant. No timer polling or new event transport
is needed.

Implement the design's initial edit selection, control traversal, Default/Space,
radio peers, press preview, inside-release acceptance and outside/loss
cancellation. Restore pre-press state before committing. Leave the accepted
EXIT selected at the `form_do` boundary while retaining current `form_button`
behavior for Files/panel/calculator. Draw only affected objects on ordinary
input; initial/exposure repair may paint the whole form.

Handle live host redraw/topping locally. Accept movement only for the internally
owned temporary host, translating the tree after acknowledgment. Temporary
close dismisses; application-policy events preserve the exact existing deferred
message/epochs and return -1 with `AES_PENDING`. Do not continue consuming or
accept a simultaneous input action after deciding to interrupt. End editing and
clear transient feedback on every return.

The focused emitted fixture covers:

- No editable field, multiple editable fields, disabled/hidden controls,
  formatted text, maximum capacity, radios, default and repeated EXIT calls.
- Direct and START/FINISH sequences, both named and AESPB calls, including
  resource-loaded trees and two independent Tasks/contexts.
- Press then outside release, keyboard during a held press, initial held button,
  input-loss recovery, focus switching and an obscured dialog becoming visible.
- Window/menu/application-message interruption, a previously deferred message,
  retirement of stale epochs, WM-shaped ordinary messages and queue saturation.
- Borrowed close/resize returning control before mutation, temporary move/close,
  caller lock rejection, no held lock/token during a wait and peer progress.

Add physical paced and burst typing schedules with capture/routing/insertion
counts. Diagnose any mismatch; keep overflow expectations tied to the existing
bounded input contract rather than claiming unbounded paste support. Preserve
stack/domain/register checks and measure deepest ordinary-Task paths with the
128-byte headroom target. A measured stack shortage permits a documented small
pool increase; it is not grounds for a broad renderer rewrite.

## FD3 Alerts

Add named/AESPB `form_alert` and exports. Parse once into session-owned upper
storage using the design's five-line/three-button/511-byte limits and escape
rules. Enforce format, default and capacity at that boundary; do not repeat
validation in layout or painting.

Build the ten-object alert tree from supported primitives. Pin/extract the
three fixed monochrome icon assets and render precomputed fill runs using the
current clipped drawing path. Reuse the same form loop, damage handling and
cleanup. Do not add general G_IMAGE/VDI raster support, a near-bank image buffer
or a second dialog implementation.

Check icons 0–3, one/two/three buttons, each default and no default, doubled
delimiters, all string/count boundaries and failed fit without prior painting.
Compare text, borders, icons and clipped exposure against independent expected
pixels. Cover zero results for interruption/dismissal/failure and ensure no
zero result becomes an accepted button. Test concurrent alerts in separate
clients and repeated open/close for resource return. Inject failures into the
allocations and owned-resource transitions introduced by this slice.

## FD4 Application and packaged desktop

Add a small loadable example containing a compiled-in editable form and alerts.
It should demonstrate both a pre-window alert and a dialog in an existing
application window, explicit/repeated and implicit form calls, and an explicit
negative-result branch before tree indexing. On `AES_PENDING`, finish the
session, return to the application's event loop and process the retained
message. Keep Files' current event-driven dialogs and calculator integration.

Build through `tools/build_demo.py --gem-desktop`, including OF816, the
five-second autoboot, pinned ROM, matching disks, notices and guide. Launch the
example after closing a demo application when needed; do not raise the current
Task/window capacities merely to put every example on screen simultaneously.

Run the extracted `exec816-demo.zip` on its recorded configuration. Cover
editing/alerts beside shell disk work and a progressing counter, obscuring and
revealing dialogs, switching focus, window/menu interruptions, stopping the
application while waiting, repeated launch/close and final EXIT. Verify that
temporary focus restoration and borrowed-content WM_REDRAW repair both complete.
Include no-window/full-capacity failure and an ordinary Files/calculator smoke
check after the shared binding changes.

Record minimum checked stack headroom per physical slot, guards, heap/resource
return, package/source hashes and actual executed scenarios. Update the current
AES contract/application guide, roadmap and both plan indexes; add a compact
history/evidence record. Do not turn historical HY4/PI4 results into new latency
or real-hardware qualification claims.

## Common acceptance rules

Follow the [two-tier testing policy](../../contributing/testing.md): host suite
and affected generator `--check` checks for code slices, focused optimized
emitted behavior, and small raw/optimized tests for changed compiler-facing
layouts or bridges. Full release matrices are not automatic. Keep extraction
patches reproducible and use the recorded compiler/platform pins; document any
intentional pin change.

For every slice report reserved bank-zero delta as **0 fixed, 0 per public Task,
0 private idle** unless measured stack growth explicitly changes it. Count guards,
alignment and spare capacity; verify the boot arena if a pool changes. Report
actual upper-memory code/data/context/heap growth and unchanged VRAM reservations.
Keep all evidence/intermediates outside the distributed ZIP.

Commit only after the slice's behavior, cleanup and resource checks pass. Update
this plan's status with the execution record at that point; writing this plan
does not establish implementation or qualification.
