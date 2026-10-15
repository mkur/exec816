# One scene transition for popup replacement

Status: proposed design; not implemented.

[Dropdown analysis](../../history/dropdown-analysis.md) ·
[Bookkeeping results](../../history/dropdown-bookkeeping.md) ·
[Implementation plan](popup-transition-plan.md) ·
[AES/Layers cache design](aes-layers-vram-design.md) ·
[Current Layers contract](../../reference/layers.md)

Replace one application's open dropdown with another heading using one Layers
transaction and one final visibility rebuild. Retain the saved background and
the two existing popup-image slots. On a popup cache hit, restore the old
background and copy the new popup before publishing the new scene geometry.

This is item #3 following the completed dropdown bookkeeping work. It changes
the presenter/Layers transition, with no application API or kernel change.

## Why this is the next step

After DB1–DB3, a warm File → View switch has a median elapsed time of 180.4 ms
and presenter CPU time of 121.5 ms. The representative switch spends 46.0 ms
CPU in two `Show` calls, including 29.6 ms in their visibility rebuilds.
Saved-background retirement takes another 6.5 ms; the two whole-image copy
submissions together take 4.0 ms. These are nested measurements, not costs
that can all be added together.

Today `BeginRestore` hides the old popup, damages intersecting layers and
rebuilds visibility. After the copy, `FinishSave` subtracts successfully
restored damage. `DESKMENU.Advance` changes the hidden popup's bounds and shows
it again, causing another damage pass and rebuild. The painter then finds
the new popup and restores its cached image. Background retirement to the
next copy still takes 48.2 ms in this sample.

The intermediate scene without a popup is unnecessary for a heading switch.
Keep the old scene committed until the replacement is ready. The final
visibility rebuild remains necessary; the full 29.6 ms is not removable.
The expected benefit is less CPU bookkeeping and a shorter gap between the
existing copies. The design sets no unmeasured response-time promise.

## Eligibility and responsibilities

Use the combined path when an open GEM menu changes heading within the same
current application/menu lifetime, and the retained background covers both
popup rectangles. The popup keeps its layer identity and stacking position.
Its opaque content must fit the existing aligned cache-transfer path. A new
popup image is optional: a miss still permits one geometry commit followed
by normal painting.

First opening, dismissal, native menus, owner changes and an invalid saved
background retain their existing paths. Do not expand this into a general
scene transaction framework or enlarge the popup cache.

- Layers owns the scene token, staged rectangles, background validity,
  damage retirement and final visibility publication.
- `DESKMENUCACHE` owns image-key matching, cache pins, asynchronous copies and
  completion. Freeze the target key and bounds for the admitted transition.
- `DESKMENU` and `DESKAPPMENU` own interaction state, title damage and the
  committed paint snapshot. They adopt the completed transition together.

The frozen key retains the existing owner, lifetime, menu revision, heading,
selection and kind fields. Check currency and transfer eligibility once at
admission, then check whether the borrowed state was invalidated at completion.
Do not revalidate the application object tree at each phase.

## One token, two possible copies

Add a small Layers begin/finish pair for saved-overlay replacement, alongside
the existing save/restore operations. Exact routine names belong in the
implementation plan. Add an update-kind constant through the machine-readable
Layers definitions; reuse `Scene.copySource` for the old rectangle and
`Scene.copyTarget` for the replacement rectangle.

1. Admit while the existing native policy gate is closed to competing scene
   changes. Check the retained save and claim a scene token **before changing
   any scene state**. BUSY, exhausted tokens or an unusable save leave the
   committed scene and output token unchanged. Pin the background and, on a
   hit, the selected popup image.
2. Copy the old popup's background from the retained union save. Use the old
   rectangle's offset into that save, not the new target rectangle. Keep the
   popup shown at its old bounds and keep existing visibility authoritative.
3. On notified completion, check the save is still current. On a popup hit,
   immediately submit the complete new image at the staged target rectangle.
   Do not hide/show, rebuild, hand off exposure or admit an unrelated scene
   operation between these copies. On a miss, proceed directly to the dirty
   commit described below.
4. After the final transfer is quiescent, commit final geometry and damage,
   rebuild visibility once, adopt the menu paint snapshot, release pins and
   retire the token. A dirty commit then enters the ordinary popup painter.

The image-copy helper must accept staged geometry: the live layer still has
the old bounds during both copies. Existing ordinary popup restoration can
continue using its paint token outside this replacement path.

This follows the existing copied-move rule: scene geometry changes on
completion. It is not an atomic screen flip. Scanout may briefly show restored
background before the new image arrives; removing the bookkeeping gap reduces
that interval without allocating another screen buffer.

## Commit and damage rules

Retire manager damage only inside the **successfully restored old rectangle**.
This is still required: the initial ordinary popup `Show` may already have
marked underlying layers dirty. Reuse bounded `SubtractDamage`; if its result
cannot fit, retain the damage conservatively. Leave external application
`pending` repaint obligations untouched.

Set the popup's final bounds without intermediate `Show(0)`/`Show(1)` calls or
`DamageAll` solely for the temporary coverage change. A current complete popup
image satisfies its captured paint obligation. A cache miss or failed popup
copy leaves the new popup dirty. Never clear damage from a newer menu revision
using the frozen image.

Perform damage edits first, then one `Rebuild` to publish final visibility and
the visible-damage summary. Avoid calculating summary bits for a hidden scene
which would immediately be replaced. Keep existing conservative region-overflow
behavior; a failed rebuild must not certify a clean completed transition.

Adopt the frozen heading/selection/open state in `DESKAPPMENU` without running
the ordinary full-popup invalidation again. Damage only the old and new title
segments in the bar. Update the menu's observed scene revision so its own
commit is not mistaken for an unrelated scene change. Pending newer input or
menu changes remain work for the next boundary.

Remember successful restored exposure using the existing interaction record.
Its bounding union is suitable for conservative notification, never proof that
all pixels inside the union were restored. Conventional GEM owners continue
to receive exposure notifications at interaction end after bar repair;
preservation-contract owners keep their existing behavior. No new application
repaint or Files refresh is generated between successful heading switches.

## Input, ownership and scheduling

An admitted target is fixed until completion. Defer menu clicks, keys and
heading changes while it is in flight, using existing bounded input storage:
the pointer deferral queue and the keyboard capture queue. Gate keyboard
dequeue before consuming the event; the pointer queue is not a keyboard queue.
Keep the existing ordering within each input stream and loss/cancellation
rules. No second input queue or mid-transfer retargeting is introduced.

Pointer capture continues to update the latest position, and pointer display
uses existing safe transfer boundaries. Button edges must survive deferral;
clicks must not fall through to the window beneath a transitioning menu.
Escape, Return and queued selection act at the first completed transition
boundary. Menu-owner/lifetime checks still govern durable `MN_SELECTED`
delivery; an old pending choice cannot activate a replacement menu.

Hold the scene token and existing AES policy exclusion through both copies,
including the brief transfer-free continuation. This does not require holding
physical blitter ownership while doing bookkeeping. Use the existing notified
`MenuContinuation` path to retire the first copy and launch the second before
unrelated controls. Do not poll hardware or count deferred, currently
ineligible input as runnable work while waiting for completion.

Normal Task preemption remains enabled. A combined replacement consumes one
preferred menu transaction; retain the existing two-transaction fairness limit
and offer ordinary work/input a boundary after completion. The second copy
does not renew a worker budget. There are no priority changes, new signals,
timers or kernel services.

## Failure and cancellation

The finish operation needs explicit outcomes, not one boolean conflating
background restoration with popup-image success:

| Outcome after quiescence | Scene result |
| --- | --- |
| Background and current popup image complete | Commit the new popup clean; retire only proven restored damage. |
| Background complete; popup cache miss or popup copy failed | Commit the new popup dirty and paint normally; discard a failed image. |
| Background failed/became stale, or menu lifetime changed | Keep old committed geometry, damage both possibly touched rectangles and use ordinary repair/cancellation; do not certify restored exposure. |

Check retained-background currency at final completion as well as before the
second copy. If it became invalid, the successful-background outcome no longer
applies. Discard affected cache entries and preserve newer repaint obligations.
A failed operation may have changed pixels even though its geometry never
committed; marking both rectangles prevents an apparent metadata rollback
from leaving corrupted pixels behind.

Cancellation does not release a source still used by hardware. If quiescence
cannot be established, retain the token and pins for existing display recovery.
Only matching live tokens may finish; stale completion must not release a
new transaction. A recoverable popup-only failure does not discard a still
valid background save unnecessarily.

## Memory and implementation boundary

Reuse the existing scene rectangles, scratch region and fixed VRAM slots.
Only a frozen popup key and a few presenter phase/slot fields should be needed;
target at most 32 additional bytes of fixed upper-memory state, accounting for
actual layout. Do not add per-window, per-client or per-Task records. Record
the emitted code/data and stack impact during implementation.

Reserved bank-zero delta: **0 fixed bytes, 0 per public Task and 0 for idle**,
including guards, alignment and unused capacity. DP/stack reservations and VRAM
reservations remain unchanged. The Layers update-kind addition does not change
the Exec gateway or GEM API; regenerate shared definitions and rebuild callers
when implementing it. Keep the current reference contract unchanged until then.

## Evidence required when implemented

Extend focused emitted Layers/presenter cases for old geometry while busy,
one final rebuild, correct damage and exact background/popup pixels. Cover
overlapping and disjoint old/new rectangles, different popup sizes, existing
underlying damage, pending application repaint, cache misses, stale saves and
owner revisions, transfer failures and token/pin retention until quiescence.
Exercise rapid pointer/key input, button edges, Escape and lifetime changes
without adding an exhaustive qualification matrix.

Repeat the existing 18-action menu trace on the same pinned platform, with the
DB3 package as baseline. For an eligible cached switch, require one visibility
rebuild, two whole-image copies, no transient hide/show damage pass, correct
final pixels and zero Files paints. Measure presenter CPU, background-retirement
to-popup-submission gap and elapsed response separately. Include the existing
three-heading cache-miss case and ordinary open/dismiss behavior to expose
regressions. Report the small cohorts as minimum/median/maximum, with the
one-frame sampling limitation, rather than claiming p95.

These are development checks under the [testing policy](../../contributing/testing.md).
This note itself requires only content and link checks. It makes no new
hardware qualification or measured performance claim.
