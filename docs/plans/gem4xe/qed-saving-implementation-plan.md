# QED reliable saving implementation plan

[GEM plans](README.md) · [Saving design](qed-saving-design.md) ·
[Strategy](qed-port-strategy.md) ·
[Editing handoff](../../history/qed-editing.md#qe7-editing-gate-and-saving-handoff)

Status: QW1–QW2 implemented; QW3–QW8 remain for strategy step 5. See the
[implementation record](../../history/qed-saving.md). The
[QE7 development baseline](../../development/qed-editing-qe7.json) is the
starting point. Save/Save As
remain disabled until QW5 establishes their loaded-editor acceptance; the full
Save/Discard/Cancel workflow follows in QW6. Step 5 closes only after QW8
reconciles the complete saving gate.

Implement the [saving design](qed-saving-design.md) in the order below. Each
slice has an executable result and commits after its selected development
checks. Record a design amendment before depending on a measured departure.

| Slice | Runnable result | Depends on |
| --- | --- | --- |
| QW1 | Public C NameFromLock binding, one current C APP ABI and rebuilt callers | QE7 |
| QW2 | Canonical native paths and retained parent ownership in Open/launch and save preparation | QW1 |
| QW3 | Bounded exact serializer and checked exclusive staging writer | QW2 |
| QW4 | Checked backup/publication transaction with explicit recovery results | QW3 |
| QW5 | Real menu/shortcut Save and Save As, consent, recovery reporting and safe busy-state handling | QW4 |
| QW6 | Save/Discard/Cancel continuations for New/Open/Close/Quit/Stop | QW5 |
| QW7 | Targeted disk-failure, cancellation, repeated-use and resource closure evidence | QW6 |
| QW8 | Reconciled saving session, current artifacts/packages and step 6 handoff | QW1–QW7 |

## Rules for every slice

- Keep QED/cflib pins, the compiler profile and preparation reproducible. Use
  [actionc.json](../../../toolchain/actionc.json), recording any justified
  override. Change donor code through ordered patches and the source-selection
  ledger; change resource/ABI outputs through their inputs and generators.
  Fix compiler/emulator defects in their owning projects with focused
  regressions, without per-routine QED workarounds.
- Keep one implementation and one current ABI. Do not retain an old save
  controller as a compatibility path. Focused probes execute actual production
  helpers; test interposition belongs only to fixture builds. Successful
  acquisitions and operations forward to the real implementation.
- Use ordinary public Exec/DOS/AES services. Leave device queues, native write
  publication, leases and cancellation policy with their current owners. Do not
  add a private QED kernel service, save Task or repeated pointer validation.
- Run host checks, affected generators and focused emitted-code development
  cases for code changes. QW1 covers the added bridge in raw and optimized NIR
  with small C/native boundary probes. Routine saving/editor/failure checks use
  optimized builds. Do not duplicate the whole editor in raw mode.
- Preserve native IRQ/NMI, DP/context restoration, stack/domain guards, bounded
  completion and ordinary collection/unload. Measure newly reached source and
  native continuation chains in the owning slice; QW7/QW8 reconcile earlier
  measurements rather than deferring basic safety until the end.
- Record actual APP code/data/container/alignment costs, provider growth and
  remaining allowances against QE7 and the retained feasibility budgets. Charge
  live document/candidate/clipboard/Undo, save state/buffer, recovery forms,
  filesystem backing and allocator rounding separately.
- Target reserved bank-zero delta **0 fixed / 0 per-public-Task / 0 private
  idle bytes**, counting guards, alignment and unused capacity. Report the
  actual complete reservation delta for every slice. A measured stack increase
  is permitted under the [platform budget](../../reference/platform.md#bank-zero-memory-budget),
  but update admission and the pool accounting before depending on it.
- Preserve QE1–QE7 results, traces and hashes. Current acceptance requires the
  current ABI/provider and matching linked inputs. Historical success is not a
  replacement for rebuilding after QW1; reuse a passed result only when its
  relevant inputs remain identical and its original scope is sufficient.
- Keep partial slices honest: QW3 staging readiness is not Saved, QW4 core
  publication is not GUI consent, and menu saving does not establish QW6's
  retirement workflow. Disabled entry points must remain disabled until their
  owning acceptance checks pass.

Follow the [two-tier policy](../../contributing/testing.md). This is development
work, not hosted-system or release qualification. Documentation-only changes
need content/link checks. Broader qualification runs only for a release,
explicit qualification claim or explicit request.

## QW1 Public C canonical-name binding

Expose the existing native `NameFromLock` through the ordinary C DOS bridge.
Update [abi/c-program.json](../../../abi/c-program.json),
[C declarations](../../../c/include/proto/dos.h),
[dos.c](../../../c/calypsi/dos.c), the native bridge/table definitions and
affected generators/binding catalogs together. Preserve the native call's
ownership, capacity and error semantics; add no filesystem operation or kernel
selector. Generate shared entry indices/counts from their machine-readable
definitions rather than maintaining independent table-size constants.
Bump the one C APP ABI, regenerate its shared definitions, and update
the current C-loading/DOS reference pages with the public binding contract.

Rebuild the production QED APP, the native/provider fixtures needed by the
next slices, and other affected C callers. Reject stale APPs through the
ordinary loader; do not bypass import/version checks to reuse older artifacts.
QED's editing behavior remains at its existing scope at this slice.

Completion checks:

- Focused raw/optimized C/native bridge probes cover root and nested directory
  names, exact-capacity and too-small buffers, native failure results, argument
  widths, full pointer/lock identities and normal ownership retirement. Arrange
  current directories in the native fixture instead of assuming a default.
- The returned path is the native physical canonical name, including resolution
  through SYS and an ASSIGN established by the native fixture. No private lock
  layout is read by C. Buffer/domain guards and DP/register restoration hold.
- A rebuilt ordinary QED opens its resource/window and retires normally under
  the new ABI. A copied old-version APP is rejected without entering its body
  or leaking an image, handle or Task owner.
- Rebuild matching GEM demo provider/callers through `tools/build_demo.py` and
  smoke the exact OF816 package. Audit packaged APP versions and rebuilt caller
  hashes. Audit/reuse the standard demo only if its relevant inputs are
  unchanged; otherwise refresh and smoke it too. Keep private QED out of ZIPs.

Record bridge/provider/thunk costs, the updated QED source-frame ledger and
observed binding/startup chains. Commit QW1 after these development checks.

## QW2 Canonical paths and parent ownership

Add one private QED path-preparation owner using Lock, ordinary Examine and
NameFromLock. Establish a directory parent, retain its lock, and construct a
bounded canonical destination. Prepare D/B/T/E sibling storage without creating
files. Preserve native paths; use no GEMDOS spelling, private lock access or
temporary CurrentDir change.

Apply this preparation before the first Open/launch candidate read. Store the
canonical candidate name and retain its parent through the modified decision
and any later continuation. Integrate release/transfer into candidate cancel,
commit and normal exit. New remains an unnamed LF document. Update active
callers, observers and expected titles/paths to this single canonical behavior.

Separate not-found from errors when querying destinations. Use ordinary
Examine for kind/protection/available metadata; exact chain measurements do not
belong in a consent-only query. Release selected-file query locks before a
later Rename, while keeping the parent retained. Save commands remain disabled.

Completion checks:

- Actual-source probes and a loaded-editor Open/launch cohort cover relative,
  SYS/physical and ASSIGN paths, root/nested parents, missing/default-directory
  failures, streams/devices, directories and malformed/overlong names.
- Exercise the 255-byte native limit, selector path[128]/leaf[13] limits and a
  destination that fits while a generated sibling does not. Fail before any
  namespace mutation; do not truncate.
- A native fixture reassigns a logical prefix after canonical preparation.
  The prepared operation stays on its original physical parent; a new operation
  sees the new assignment. This uses public native fixture operations, without
  adding an unnecessary C assignment binding.
- Candidate failure, cancellation, commit, Stop and collection return parent
  and query locks exactly once. Existing reader failure behavior, clipboard
  persistence and the single TEXT/window invariant remain intact.
  Retained parents prevent their rename/deletion and unmount until release;
  selected-file query locks do not linger and block later publication.

Record parent/candidate backing and the newly reached name-resolution/reader
stack chains. Commit QW2.

## QW3 Exact serialization and staging

Implement resumable length counting and serialization over the actual LINE
ring. Preserve byte text, uniform LF/CRLF and the trailing-empty-line model.
Count with checked signed-LONG arithmetic before creation; emit separators only
between logical lines. Use one bank-contained 4 KiB upper-heap buffer, bounded
to 4 KiB and 256 line-boundary visits per step, with pending separator/suffix
state across steps. Do not format, trim or snapshot the entire document.

Reuse/extend the descriptor adapter for exclusive creation over public
MODE_CREATE_EXCLUSIVE. Own one descriptor; distinguish internal staging
readiness from final Saved. Store each Write result/cause, advance only its
confirmed prefix, retry a cause-free short suffix on a later step, and reject
zero progress or any causal error. Check terminal Close's primary result and
consume its identity once, including on failure. Preserve the first error and
any cleanup error separately.

At this slice the executable probe produces and inspects T only. It never
renames, truncates or deletes D/B. Menu Save/Save As remain disabled; no
production test entry or successful publication stub is selected.

Completion checks:

- Actual-source emitted probes compare exact staged bytes for empty, LF/CRLF,
  no final newline, multiple trailing newlines, tabs, high bytes/ATASCII,
  1,023-byte lines, buffer boundaries and split CRLF output. Many empty lines
  respect the visit budget. Include multi-bank text and overflow rejection.
- Execute on RAM and writable MyDOS/SpartaDOS fixtures. T collisions never
  truncate an existing object; cover bounded candidate-name exhaustion and
  allocation failure before creation. Verify unrelated D/B bytes remain exact.
- Inject positive short writes with/without a cause, zero/negative writes,
  full counts with errors and terminal Close failure at the actual adapter
  boundary. Check no resend/spin, confirmed totals, original causes, descriptor
  counts and one-time Close. A preserved IoErr after successful Close is not
  misclassified as a new Close failure.
- Cancellation drains calls and retires owners; cleanup failures cannot return
  Cancelled as though cleanup succeeded. Repeated stage/dispose cycles and two
  ordinary Process lifetimes return backing and guards.

Record staging peaks and full serializer/write/Close/unwind stack chains.
Commit QW3.

## QW4 Backup transaction and recovery ownership

Build the production transaction over the staged writer and canonical paths.
Preallocate D/T/B/E, confirmed-phase flags and causal/recovery error storage.
Follow the design's sequence: close T; move an existing older B to an unused E;
move existing D to B; publish T to D; remove E only after publication and prior
consent. Use `.BKP` for a `.BAK` destination. When D is absent, leave any
independent B untouched.

The focused core accepts an explicit preauthorized intent from its caller; a
probe supplying that intent does not establish real GUI consent. No menu entry
is enabled yet. Keep one production transaction implementation and explicit
Saved/Cancelled/Failed/Uncertain outcomes.

Recover only from confirmed logical failures and only by reversing confirmed
moves using no-replacement Rename. Stop destructive cleanup at a failed
reversal. After publication, never delete the new D to roll back; failed E
cleanup retains recovery details and forces dirty at the editor boundary.
Classify unknown mutation/Close failures as Uncertain. Do not probe private
worker state or attempt speculative operations on an invalidated mount.

Completion checks:

- Real RAM/MyDOS/SpartaDOS core transactions cover new D, existing D without B,
  existing D/B, repeated saves, `.BAK` targets, protected/in-use/directory
  collisions and the T/E allocation bounds. Exact D/B/E/T bytes and existence
  match the last confirmed phase; retained old-object metadata follows Rename.
- Fail every forward rename, E deletion and each reverse rename. Include
  failed restoration and post-publication cleanup failure. Preserve unexpected
  colliding files and both causes; no in-place or delete-to-restore fallback
  occurs. The original dirty/name state is committed only by the later UI owner.
- Assert the core's call sequence: no publication before successful Close;
  no speculative rename/delete after uncertainty; no cleanup of unowned names.
  Label adapter-injected uncertainty as policy coverage, not a real offline
  transport result. QW7 supplies the selected deeper transport cases.
- Recovery storage survives a failed operation and blocks silent reuse of
  unresolved names. Safe cancellation, resource release, reuse and normal
  collection work with complete or partially completed transactions.

Record live/temporary disk and heap costs, phase outcomes and the source/native
publication/restoration chains. Commit QW4.

## QW5 Loaded-editor Save and Save As

Connect the transaction to the real QED command controller and menu/shortcuts.
Named Save and Save As use the same owner; unnamed Save selects a destination.
Both serialize the full document even when a range is selected; block saving
remains deferred.
Every existing D uses Cancel-default Replace/Cancel, and replacement of an older
B requires its own consent. Show the actual target and disclose the selected
metadata restrictions. No unknown metadata is presented as change detection.

Implement native working/error/recovery presentation before enabling commands.
Recovery pages retain and show complete paths, roles, phases and both causes.
If native form allocation fails, keep the record/document live and allow a
retry; dismissing an error is not Saved. Generate any resource changes and
matching headers through their existing inputs/generator.

Freeze mutations while serialization borrows the ring. Handle compatible
redraw/geometry/focus and safe navigation without held UPDATE/MCTRL or scheduler
exclusion. Before publication, a newer Close/Stop cancels staging and then
enters the existing modified policy after cleanup. During namespace changes,
retain one pending intent, with Stop precedence, until a stable outcome.
Native BREAK still follows its contract; do not clear another owner's signals.
These safety rules land here, before writes become user-accessible.

On Saved, commit name/clean state and refresh bounded title/available metadata.
Preserve text, selection, viewport, clipboard and Undo. Add an explicit typing
group boundary; do not rely on the current no-op end_undo_seq or discard Undo.
On non-Saved outcomes, apply the design's identity/dirty rules, including forced
dirty after publication/cleanup failure or uncertainty.

Retire the donor's live save/backup/restore and automatic save paths, updating
patches, source selection and reachable callers together. Enable menu Save and
Save As only after this slice's real-editor checks pass. New/Open/Close/Quit/Stop
retain Discard/Cancel until QW6 adds their Save continuation.

Completion checks:

- Physical menu/shortcut Save and Save As produce matching native file bytes
  on RAM and both disk filesystems. Cover unnamed and clean named documents,
  existing-file and backup consent/cancellation, selector cancellation and
  current path/title limits. Independently check document and form pixels.
- Success changes name/dirty state only at completion; failure/Cancel retain
  the required state. Clipboard, cursor/range, viewport and Undo survive Save.
  Undo marks dirty; typing before and after Save forms separate groups.
- A selected Write/Close/publication/cleanup failure reaches the real notice
  with correct full paths and outcomes. Exercise a non-fitting/reporting form,
  allocation refusal, interruption/resume and retry without lost information.
- Another ordinary GEM client paints while forms or staging are active.
  Text-changing input cannot alter the borrowed ring or replay later. Test
  Close/Stop before publication and at a namespace boundary, exact message
  delivery, cleanup completion and ordinary return through Discard/Cancel.

Record the actual GUI/save/recovery/Stop stack chains, allocation peaks and
resource return. Commit QW5.

## QW6 Save/Discard/Cancel continuations

Replace modified decisions for New, Open, Close, Quit and cooperative Stop with
one Cancel-default Save/Discard/Cancel policy. Capture one explicit continuation;
do not recursively call Save or file policy from a close callback. Continue
only after Saved. Selector/consent cancellation, error, uncertainty, zero or
interrupted dialogs cancel the original destructive action.

Keep an Open/New candidate as a separate owner during Save. After Saved, New
may commit its empty candidate. Open must discard its earlier candidate and
reread the frozen canonical path before committing, including when paths look
different. If rereading fails, retain the just-saved current document and report
Open failure without relabeling Save as failed. Discard uses the already
prepared candidate; Cancel/non-Saved releases it.

Complete intent supersession and general command cancellation for these
owners. A newer Close/Stop releases an older replacement continuation safely;
late intent waits for publication/restoration/cleanup. After non-Saved outcomes
it receives a fresh modified decision. A declined Stop leaves the Process live.

Completion checks:

- Exercise Save, Discard and Cancel for dirty New/Open/Close/Quit/Stop through
  the loaded editor, including unnamed Save As. Pair physical Close/Quit and
  ordinary cooperative RequestStop with actual persisted bytes and collection.
- Failed Save, selector cancellation, failed consent, interrupted/zero alerts
  and recovery-report allocation failure never authorize replacement or exit.
  Preserve the current document and retire candidates/locks exactly once.
- Open the current file through its own name and SYS/physical/ASSIGN aliases;
  Save As to the pending Open target. The post-save reread supplies the newly
  saved bytes. An injected reread failure retains the saved clean document and
  its committed Save As identity. No stale candidate is published.
- New candidate and Open path/name storage survive Save As without aliasing
  the save draft. Repeated/newer Close/Stop during forms, writing, publication
  and cleanup respect supersession, Stop precedence and exact-once continuation.
- Measure simultaneous document/candidate/clipboard/Undo/save peaks and the
  new full continuation/reread/Stop stack chains. Check native guards, context,
  exact warm resource reuse, collection and unload.

Commit QW6 after the full modified-decision workflow passes its development
checks.

## QW7 Targeted disk failures and resource closure

Extend the passing application/core cohorts with selected deeper ownership,
transport and reuse cases. Keep basic failure/cancellation checks in QW3–QW6;
this slice establishes the combined operational scope and fixes demonstrated
defects in their owning layers.

Reuse the existing [filesystem edge fixtures](../../../tools/test_filesystem_write_edges.py),
[fault tooling](../../../tools/test_sio_write_faults.py) and
[allocation audit](../../../tools/filesystem_audit.py) where applicable. Adapter
failures and real transport failures are separate evidence. Pin and record any
fault-responder emulator/configuration separately from the normal editor setup.

Completion checks:

- On both disk formats, use consistent disposable images to cover payload/full
  directory exhaustion, backup rotation, retained recovery files and repeated
  save/open/new cycles. Audit exact bytes and whole-volume ownership/free counts
  after safe logical cases. A failed save cannot erase unrelated content.
- Reach an actual physical mutation/finalization failure and a completion-
  uncertain/offline case through QED's writer on the affected formats. Assert
  conservative outcome/reporting, no speculative namespace recovery, consumed
  Close and released locks/buffers. Restore a known-good image for subsequent
  writes; never use a lightweight remount as proof of repaired state.
  A focused actual-source emitted writer probe can isolate this transport
  behavior; the loaded-editor notice cases remain a separate QW5/QW6 gate.
- Distinguish complete software ownership retirement from OS-restoration/reset
  expectations in an unsafe transport case. Do not claim a healthy volume or
  normal hosted return where the selected fault contract requires reset.
- Cover BREAK/Stop before a Write, during accepted payload progress, between
  namespace calls and during large E reclamation. Record operation/volume
  bounds instead of claiming a 4 KiB frame deadline for Delete/Close.
- Measure RAM old/new buffer growth plus private saving/candidate peaks; disk
  directory/temporary costs; repeated loaded lifetimes; native ownership,
  image references, guards, DP, UPDATE/MCTRL and exact warm heap return.

Reconcile source frame bounds, actual image-base stack observations, admission
and growth allowances for the reached success/error/recovery chains. Commit
the executable failure/reuse checks and any required fixes as QW7.

## QW8 Reconcile the saving gate and hand off coexistence

Extend the baseline audit and recorder for canonical names, saving phases,
recovery results, persisted media and current C ABI/provider. Create current
slice development records and saving history using the repository's existing
organization; update the relevant indexes. Bind actual source/fixture/observer,
resource, runtime/toolchain, ROM/emulator, APP/provider, trace and media hashes.

Run one combined real editor workflow: launch/Open, edit long tabbed text,
selection/clipboard/Undo and Find, Save As, named Save with backup rotation,
cancelled/failed Save with recovery, successful retry to a fresh destination,
reopen saved bytes, modified Open and Close/Stop through the new decisions.
Include peer overlap/exposure, document/form/caret pixels, normal collection,
unload and warm reuse. Pair this with current matching QW1–QW7 cohorts rather
than repeating every full scenario. Record exact filesystem and failure scope.

Independently verify closed disk-image bytes/allocation after ordinary reopen;
use fresh service/media state where required to exclude cache-only success.
Keep normal evidence and invalidated fault images distinct. Source/layout and
selected-PC stack checks must agree with current admission and reservations.
Do not combine old-ABI QE7 cohorts into a claim about the current executable.

Reconcile the standard/GEM demo artifacts from QW1 and any later affected
refresh. Reuse passing packages only with matching relevant inputs and exact
ZIP/smoke bindings; do not rebuild/retest unchanged packages solely for this
documentation commit. Refresh affected packages through `tools/build_demo.py`,
including OF816, pinned ROM/notices and the five-second standard shell/prime
autoboot. Before publication, add matching old/new Atarimax CAR and raw 1 MiB
BIN images with `--cartridge-from`. Private QED/fixtures remain out of demo ZIPs
until strategy step 7 selects supported QED delivery.

Run affected host/generator/content/link checks. Mark strategy step 5 complete
only when exact saved/reopened bytes, backup/recovery behavior, all modified
continuations, operational failures, reuse and current resource/stack costs are
supported by development evidence. Update supported/unsupported behavior and
hand step 6 a working Open/Edit/Find/Save/Close workflow with its measured limits.
Power-loss atomicity, same-target concurrent writers, autosave, broader metadata
restoration and automatic repair/recovery scanning remain unsupported.

Commit the reconciled evidence and documentation as QW8. These checks do not
qualify the hosted system, a release or physical media.

Design/plan-only reserved bank-zero delta: **0 fixed, 0 per-public-Task and
0 private idle bytes**, including guards, alignment and unused capacity. Preparing
these documents changes no executable, ABI, runtime reservation or demo.
