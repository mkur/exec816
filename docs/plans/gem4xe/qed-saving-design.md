# QED reliable saving design

[GEM plans](README.md) · [Strategy](qed-port-strategy.md) ·
[Implementation plan](qed-saving-implementation-plan.md) ·
[Initial scope](qed-scope-and-dependencies.md) ·
[Editing design](qed-editing-design.md) ·
[Editing handoff](../../history/qed-editing.md#qe7-editing-gate-and-saving-handoff)

Status: accepted design for strategy step 5, based on the
[QE7 development baseline](../../development/qed-editing-qe7.json). The
[QW1–QW8 plan](qed-saving-implementation-plan.md) derives the executable work.
Save/Save As remain disabled until the corresponding executable acceptance
checks pass. Implementation progress and measured evidence belong to the
[historical record](../../history/qed-saving.md).

The gate is the real loaded QED saving and reopening exact document bytes on
RAM, MyDOS and SpartaDOS, including existing-file replacement, backups, failed
writes/finalization and modified-document decisions. A reported failure must
leave the editable document available and explain which disk files may exist.
Practical workload responsiveness and supported distribution remain steps 6–7.

## Starting point and ownership

Keep the pinned QED/cflib sources and native Process, AES and DOS ownership.
Preserve the donor LINE ring, current window, internal clipboard and grouped
Undo. Saving policy belongs in the native QED controller; filesystem mutation,
leases, cancellation and transport policy stay with their existing owners.
Use public DOS operations, without a QED-specific kernel service or filesystem
transaction protocol.

The source audit identifies these changes to the retained workflow:

| Source | Finding and selected treatment |
| --- | --- |
| Prepared QED `file.c`: `back_up`, `restore_back_up` | Deletes an existing backup and ignores rename results. Replace with the checked namespace sequence below. |
| `file.c`: `save_to_fd`, `save_datei` | Allocates both transfer and line buffers, leaks a successful allocation when its peer fails, collapses write failures to disk-full and ignores terminal Close. Replace the live path with a bounded serializer and checked writer. |
| `file.c`: `save`, `save_as` | Uses donor metadata assumptions and can restore the current document's backup after a Save As failure against another path. One native save owner must retain the actual destination and phase. |
| QED `edit.c`, `menu.c`, `event.c` | Save is disabled; retirement currently offers Discard/Cancel. Replace all live Save and modified-decision entry points together, without retaining a second save implementation. |
| QED `clipbrd.c` | Undo already marks dirty conservatively. Its `end_undo_seq` is currently a no-op; Save needs an explicit typing-group boundary that retains Undo, rather than assuming this call provides one. |
| Native [commands.c](../../../ports/gem4xe/apps/qed/native/commands.c) and [document.c](../../../ports/gem4xe/apps/qed/native/document.c) | Already own resumable commands and detached Open/New candidates. Add saving as a sub-operation with an explicit pending continuation. |
| Native [files.c](../../../ports/gem4xe/apps/qed/native/files.c) | Already translates owned descriptors, full native errors and exclusive C `open` flags; terminal Close consumes its descriptor. Extend/reuse this ownership rather than introducing another handle table. |

Prepared donor paths refer to the source pair and ordered patches recorded in
[inputs.json](../../../ports/gem4xe/apps/qed/inputs.json); generated work copies
are not authoritative sources. Retire live autosave, block-save, formatting and
configuration-save paths together with the donor save controller. Those features
remain outside the initial scope.

## Filesystem guarantees and limits

The [write contract](../../reference/filesystem-writes.md),
[DOS API](../../reference/dos.md) and
[RAM contract](../../reference/ram-filesystem.md) are authoritative:

- `MODE_NEWFILE` truncates during Open. Never use it on the destination or an
  existing backup. `MODE_CREATE_EXCLUSIVE` reserves a new temporary file without
  truncating a collision.
- Rename is within one parent and does not replace another object. Individual
  namespace calls are serialized by the filesystem worker; a sequence of calls
  is not an atomic replacement operation.
- Write returns a confirmed prefix or failure. Capture `IoErr` even for a full
  or positive count. Terminal Close must succeed and consumes the handle on
  either result. Flush is not a substitute for terminal Close.
- Physical mutation failure or uncertain completion can invalidate the mount.
  Ordinary recovery operations may then fail. Close and UnLock still retire
  ownership; successful earlier replies do not promise whole-volume rollback.
- Neither disk format is journaled. This design offers checked application
  recovery during ordinary execution, not power-loss atomicity or durability.
  RAM saves remain volatile.

QED does not hold an exclusive namespace transaction across these calls.
Concurrent mutation of the selected destination, backup or temporary names by
another application is outside this gate. Other applications may use unrelated
files. No-replacement Rename and exclusive creation still protect collisions;
an unexpected object is never deleted to force progress. Do not add repeated
pointer/handle validation to compensate for the single-user ownership model.

## Destination, consent and metadata

Save uses the named document's path; an unnamed document enters Save As.
Save As selects one native file and leaves the current name unchanged until
success. A deliberate Save on a clean named document performs the same checked
workflow, permitting an unchanged open/save round trip.

Resolve and retain the destination's parent directory, establish that it is a
directory, and obtain its canonical physical name before creating anything.
Join the admitted leaf to that name; use this frozen parent for every sibling
path. Relative paths use the inherited current directory. Resolving an ASSIGN
once prevents a later reassignment from splitting the operation across parents.
Retain the parent lock through recovery/cleanup, preventing parent identity
changes and unmount; release selected-file query locks before Rename.

Apply the same canonical-parent preparation to Open/launch paths before their
first candidate read. Relative and logical spellings remain accepted input;
newly committed document names use the canonical path. Carry this identity
through a later modified decision instead of resolving an ASSIGN a second time.
Update callers and expected titles/paths together; retain one current behavior.

QW1 exposes the existing native `NameFromLock` operation to loaded C callers
through the [C DOS declarations](../../../c/include/proto/dos.h), the
machine-readable [C import ABI](../../../abi/c-program.json) and generated
bridge. The one current C APP ABI is 26; provider and callers are rebuilt together.
Its native semantics stay unchanged;
no new DOS operation or kernel selector is needed. Do not inspect private lock
records or change QED's current directory to simulate this operation.

Native paths are at most 255 bytes plus NUL; new leaves follow native 8.3 rules.
The selector retains its path[128]/leaf[13] bounds. Check the complete canonical
destination and all sibling names before mutation, including cases where a
short destination leaf would fit but a generated temporary leaf would not.
Reject overflow, streams/devices, directories and invalid names explicitly.
Do not truncate or translate a path into a GEMDOS drive spelling.

Use ordinary Lock/Examine for existence, kind and available protection flags;
an exact file-chain measurement is not needed merely to ask for consent.
Treat only the specific not-found result as absence. Report in-use, protection,
unavailable-directory and transport errors as errors. Check each resource when
acquiring it; the native mutation operation still owns its own preflight.

Every existing destination requires explicit Replace/Cancel consent, with
Cancel as the default, including a named Save. If its backup already exists,
obtain separate consent to replace that backup after a successful save. An
existing directory or protected object subject to mutation rejects replacement.
Only query/rotate B when D exists; an unrelated B is left alone for a new D.
Cancellation changes neither namespace nor the document's name/dirty state.

This deliberately avoids promising external-change detection from metadata.
MyDOS has no timestamp, SDFS may report an unspecified date, and the editor does
not retain an immutable baseline for byte comparison. Show the selected target;
do not label it unchanged merely because size/date match or are unavailable.

The new file uses the backend's normal creation metadata. The previous object
and its metadata survive in the backup. Preserve text bytes and ending
convention; do not claim to preserve the replaced object's identity, timestamps
or hidden/archive attributes. Disclose known hidden/archive loss in replacement
consent; write/delete protection is never overridden. There is no selected
SetProtection extension or fabricated calendar time. After success, refresh
available metadata or retain explicit unknown values; a failed advisory query
does not undo a confirmed save or authorize destructive recovery.

## Serialized bytes and bounded writing

Serialize the live LINE ring without mutating it. Copy each line's exact bytes
and emit LF or CRLF only between logical lines. The trailing-empty-line
representation preserves a final newline; an unterminated last line gains none.
One empty logical line produces a zero-byte file. Preserve multiple trailing
newlines, tabs, high bytes and ATASCII bytes unchanged. Do not trim, wrap,
format, expand tabs, encode text or support CR-only output.

Compute the serialized length with checked signed-LONG arithmetic before the
first create. Preserve the existing 1,023-byte logical-line limit and reject an
unsupported ending convention. Count through bounded resumable steps so many
empty lines cannot create an unbounded event-loop turn.

Own one bank-contained 4 KiB upper-heap transfer buffer, a borrowed LINE cursor,
byte offset and pending separator state. No full-document snapshot or second
line-copy buffer is required. A step emits at most 4 KiB and visits at most 256
line boundaries, then returns to event handling. A separator may cross buffer
boundaries. Empty output still requires successful creation and terminal Close.

Use the private descriptor adapter with exclusive creation over public
`MODE_CREATE_EXCLUSIVE`; do not use truncating `Fcreate` for staging. The saver
owns exactly one writable descriptor and closes it explicitly. Runtime cleanup
remains a final ownership safeguard, not evidence of a completed save.

After each Write, save its result and native cause before any cleanup. Advance
only by confirmed bytes. A short positive write with no secondary error may
continue from its remaining suffix on a later step; zero progress, a negative
result or any nonzero cause fails the write. Supply an explicit write failure
if zero progress has no native cause. Never spin, resend a confirmed prefix or
convert every failure to disk-full. Preserve the first causal failure across
Close, cleanup and reporting, while retaining a separate recovery error.

Close the completed staging descriptor exactly once before namespace changes.
Even a full final Write with a secondary error is failure. A failed Close must
not publish the temporary file. Test Close's primary return: success preserves
the entry `IoErr`, which may describe an earlier Write failure. Do not mistake
that preserved cause for a second Close failure. Normal success relies on
native completion; production does not require a second whole-file read to
replace that contract.
Independent persisted-byte checks belong to acceptance testing.

## Backup and publication protocol

Use these four application-owned names in one canonical parent:

| Name | Role |
| --- | --- |
| D | Requested destination. |
| T | Exclusively created sibling temporary file containing the complete new bytes. |
| B | One retained previous destination: replace the leaf extension with `.BAK`, or `.BKP` when D already has extension `.BAK`. |
| E | Optional temporary sibling holding the older B until the new D is published. |

Generated T/E leaves use a bounded counter in an uppercase 8.3 pattern such as
`Q0000000.TMP` and `Q0000000.OLD`. Exclude D/B and each other under native name
comparison. Try at most 256 candidates for each allocation, then report name
exhaustion. The counter is not proof of uniqueness. T uses exclusive create;
E is claimed by no-replacement Rename of B, retrying only a confirmed collision.
Do not reserve E by creating an empty file that Rename would have to overwrite.

Always retain B when replacing an existing D; there is no backup-off preference
in this initial scope. D and a same-path Save As use the same protocol; no
lexical SYS/physical-alias comparison selects an unsafe alternate path.

| Phase | Required action and confirmed state |
| --- | --- |
| Prepare | Allocate state, paths and buffer; resolve/query names and obtain consent. D and any prior B are untouched. |
| Stage | Exclusively create T, serialize all bytes and successfully close it. D/B remain untouched. |
| Preserve older backup | If D and B exist, rename B to unused E. E now owns the older backup; do not delete it yet. |
| Preserve destination | Rename existing D to B. B now owns the previous destination. |
| Publish | Rename closed T to D. This successful reply is the publication point. A previously absent D skips both backup moves. |
| Complete | Delete E only after publication and only under the earlier consent. Release owners, commit the document name/clean state, and resume an authorized continuation. |

When D is absent, leave any independently existing B untouched. Do not create a
backup for a nonexistent destination. No in-place fallback is selected when
temporary storage, directory slots or backup space are exhausted. Peak disk
usage includes old D, new T and a prior backup; extra temporary directory entries
matter on MyDOS even when payload space is available.

After a definite logical error before publication, reverse only confirmed
namespace moves: B to D, then E to B. Each reversal uses no-replacement Rename.
If all restoration succeeds, remove the owned T when safe. If any reversal
fails, stop destructive cleanup and retain every remaining recovery file.
Never delete an unexpected D or B to make restoration succeed.

After publication, do not roll back by deleting the new D. If E cleanup fails,
report that publication completed but cleanup failed, preserve all known paths
and keep the document modified; do not continue a pending Close/Open as though
the full save succeeded. A later attempt needs a fresh decision.

After uncertain mutation or an invalidated mount, perform no speculative
rename/delete recovery. Drain terminal ownership, record the last confirmed
phase, and report uncertainty rather than asserting that D or B is intact.
External disk checking/restoration is outside QED. Remount alone is not recovery.

Classify errors from the documented contract of the particular operation.
Known collision, in-use, protection, absence or cancellation rejections before
that operation mutates state permit the stated logical recovery. Confirmed
disk exhaustion during staging likewise leaves only T to settle. An unclassified
mutation/Close error, physical error or uncertain completion is Uncertain by
default. Do not infer mount health from an errno translation, probe private
worker state, or attempt rollback merely to discover whether the mount works.

## Outcomes, document state and reporting

Distinguish Saved, Cancelled, Failed and Uncertain outcomes. Saved requires the
expected write count, successful terminal Close, successful publication and
required older-backup cleanup. A caller must never interpret a nonnegative
legacy result or a dismissed error notice as Saved.

Return Cancelled only after draining calls and reaching a known safe cleanup
outcome. A cleanup failure promotes it to Failed or Uncertain, while preserving
the original cause and the separate cleanup cause.

On Saved, commit the full canonical name and named state for Save As, clear the
modified/title state, and end the typing Undo group. Keep the LINE ring,
selection, cursor, viewport, clipboard and Undo contents. Undo after saving
marks dirty conservatively; it must not restore a captured clean flag or
coalesce later typing into the pre-save group. Equality with saved bytes is not
inferred from an Undo toggle.

Before publication, cancellation or a definite failure preserves the old name
and dirty state. Dirty documents remain dirty. If publication/cleanup failed
or disk state is uncertain, force dirty even for a previously clean document;
Save As retains its former document identity on any non-Saved outcome. Report
the possibly published destination separately. No file operation changes text,
selection, clipboard or Undo; user-requested navigation/geometry changes need
not be rolled back.

Preallocate a recovery record with D/T/B/E, confirmed phases, causal error and
any restoration/cleanup error before starting mutations. Keep it after the
operation fails. Native notices must distinguish a retained original, restored
original, completed temporary, published destination and uncertain state.
Show complete paths with roles, using a paged native form when necessary;
truncated alert text cannot be the only recovery information.

If reporting cannot allocate/open its native form, retain the record and the
live document, show an available status indication and permit retry. Do not
discard recovery information or retire the document because reporting failed.
Automatic attempts to reuse/delete recovery files are deferred. After the
notice is acknowledged, explicit Save As to another path remains a recovery
route; a new operation must not silently overwrite unresolved recovery names.

The QW5 review offers Details, Forget and Cancel before replacing a retained
record with a new save. Forget explicitly releases the private record and
parent lease, leaving every recovery file for manual handling. Cancel retains
the record. Reporting refusal keeps the document and record live for retry;
an explicit Discard decision may retire them. No review choice automatically
repairs, renames or deletes recovery files.

## Modified decisions and event ownership

Use one Save/Discard/Cancel policy for modified New, Open, Close, Quit and
cooperative Stop. Cancel is the default; dismissal, zero, interrupted forms and
allocation errors cancel the destructive action. The result has three distinct
meanings:

- Save starts the same save controller as the menu. Continue only after Saved;
  selector cancellation, failed consent, failure or uncertainty cancels the
  original destructive action.
- Discard authorizes that particular replacement/retirement without saving.
- Cancel retains the current document and declines a cooperative Stop.

Represent the continuation explicitly instead of recursively calling Save from
a Close callback. For Open/New, retain QE6's fully prepared candidate while
saving the current document. It is a separate owner from T and the serializer.
Save As must not overwrite the pending candidate's name. Freeze an Open
candidate's canonical path/parent before its first read, using the same public
path resolution; retain that parent as needed until the continuation retires.

On Saved, New may commit its empty candidate once. Open must release its earlier
candidate and reread the frozen canonical Open path before committing: Save or
Save As may have just changed that file, including through an alias. Always
reread instead of guessing identity from path spelling or timestamps. If this
fresh read fails, retain the now-saved current document and report Open failure;
do not misreport the completed Save as failed. On non-Saved outcome, release
the replacement candidate and retain the current document. Discard continues to
use the original prepared candidate. This extends QE6's preparation rule only
for the new Save continuation.

Freeze text mutation and overlapping commands while serialization borrows the
ring. Do not queue keystrokes for later insertion. Permit redraw, accepted
geometry/focus messages and navigation that cannot mutate the source. Return
to the outer loop between bounded steps; retain no UPDATE/MCTRL ownership,
Forbid region or interrupt mask across DOS I/O or a dialog.

Before the first backup move or publication Rename, Escape or a new destructive
request can cancel staging: drain an outstanding call, close T once and clean
only safe owned files. A newer Close/Stop supersedes an older replacement continuation;
release that candidate and dispatch a fresh modified decision after cleanup.
The general command-cancel helper must understand these save owners.

From the first backup move through restoration/publication and required cleanup,
defer cancellation and destructive dispatch until the sequence reaches a stable
outcome. Retain at most one pending destructive intent, with Stop taking
precedence. Pump compatible events between DOS replies, but do not recursively
dispatch another file command. Late cancellation cannot undo a published save.
If saving succeeds, a queued retirement can proceed against its clean document;
if it fails, obtain a fresh decision. Do not auto-retry Save or imply Discard.

Native Write/Close and namespace calls retain their existing BREAK protocols.
Application-level deferral does not mask native BREAK: a rejection between
namespace calls follows the same confirmed-phase recovery rules, and recovery
can itself fail. Do not clear another owner's signals to force completion.
One Delete of a large older backup can take a volume-bounded reclaim walk;
4 KiB application steps do not promise a frame-level cancellation deadline for
that operation. Keep the working indication accurate and measure the reached
paths without changing the worker's policy merely for QED.

## Memory, ABI and stack constraints

Use QE7 as the measured baseline; retain its source pins and compiler profile.
Charge the private operation/recovery state, path buffers, 4 KiB transfer buffer,
native descriptor/lock/form owners and allocator rounding separately. On RAM,
include old/new filesystem buffers and their growth peaks. Pending Open/New
can retain an entire candidate alongside the live document, clipboard, Undo
and save buffer. Do not hide that peak by discarding an owner early.

Target **0 fixed, 0 per-public-Task and 0 private idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. This design-only change adds
exactly zero. Do not add a save worker Task or put path/transfer arrays on the
native stack. Measure the new C binding's provider/thunk costs and remaining
growth allowances from the actual build.

The existing stack admission, interrupt reserve, required headroom and
continuation cap in the [QE7 record](../../development/qed-editing-qe7.json)
remain starting constraints, not proof that Save fits. Update the emitted source
frame ledger and sample full save/selector/consent/error/recovery/Close/Stop
chains at actual loaded image bases and after frame reservations. Preserve DP,
context and guards. A stack increase is permitted if measurements justify it;
record the complete pool reservation change before depending on it.

## Acceptance and handoff to implementation planning

The [implementation plan](qed-saving-implementation-plan.md) derives executable
slices from these ownership boundaries. Require:

- Focused actual-source serializer/transaction checks, then physical menu,
  selector, consent and Save/Discard/Cancel interaction in the loaded QED APP.
  Fixture-only failure wrappers forward every successful real operation.
- Exact empty/LF/CRLF/tab/high-byte output, absent and multiple final newlines,
  1,023-byte lines, split separators/buffer boundaries, signed-length overflow
  rejection and multi-bank documents. Check unchanged open/save bytes too.
- New destination, repeated existing Save with one retained backup, replacement
  of an older backup under consent, `.BAK` destinations, aliases/relative paths,
  canonical/path limits, name exhaustion, in-use/protected/directory collisions,
  full media and full directories. Verify D/B/E/T independently at every phase.
- Allocation failure, positive short Write with/without a cause, zero/negative
  Write, full count with error, terminal Close failure, every rename/delete
  boundary, restoration failure and uncertainty/offline behavior. Check first
  error preservation, one-time descriptor retirement and no destructive fallback.
- RAM, MyDOS and SpartaDOS success/failure/reuse coverage. Reopen through native
  DOS and independently audit bytes/allocation in closed disk images; use fresh
  service/media state where needed so a cache cannot be the persisted oracle.
  Do not attempt writable recovery on an invalidated fixture image.
- Dirty/clean state, title/name, clipboard/Undo after Save, and edits/Undo after
  saving; modified Open/New and Close/Quit/Stop through Save, Discard, Cancel and
  failed Save. Include Open of the current file, Save As to the pending Open
  target, SYS/physical/ASSIGN aliases and failure of the post-save Open reread.
  Exercise interruptions, peer progress, normal collection/unload,
  exact warm resource return and bounded completion where applicable.
- A raw/optimized focused boundary probe for the added public C binding and its
  failure/capacity behavior. Routine editor/filesystem scenarios stay optimized
  under the [two-tier policy](../../contributing/testing.md).

Bind artifacts to the current resource, ABI, source/runtime/provider inputs,
emulator/ROM configuration, frames and actual execution scope. Keep QE1–QE7
evidence unchanged. The C ABI addition requires rebuilt callers/providers and
matching standard/GEM package checks where affected, using `tools/build_demo.py`
with OF816, pinned ROM/notices and the five-second standard shell/prime autoboot.
Release ZIPs retain the required matching XEX, old/new CAR and raw BIN files.
QED delivery stays with strategy step 7; implementation evidence remains in the
development tree and does not qualify the hosted system or physical media.
