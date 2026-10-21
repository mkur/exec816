# QED practical coexistence

[History](README.md) · [Design](../plans/gem4xe/qed-coexistence-design.md) ·
[Implementation plan](../plans/gem4xe/qed-coexistence-implementation-plan.md) ·
[Saving handoff](qed-saving.md#qw8-saving-gate-and-coexistence-handoff)

Strategy step 6 is in progress. The production baseline, Counter/shell cohorts
and repeated lifetime gate will establish the selected development scope.

## QC1a Incremental edit damage

The first physical-input baseline exposed a second-character delay above the
design's insertion limit. `qed_replace` marked every edit as `TOTAL_CHANGE`,
including replacements contained in one row. The editor finished repainting
the rest of the viewport before handling the following key.

Patch 0018 marks same-row replacements as `LINE_CHANGE`. Splits, joins and Undo
retain full damage. If shortening the longest line clamps the viewport origin,
`restore_edit` requests a complete redraw so other rows cannot retain the old
horizontal position. The existing scroll owner still performs cursor-revelation
redraws. No renderer, scheduler, driver or public ABI changes are required.

The [QC1a record](../development/qed-coexistence-qc1a.json) binds the measured
failure, correction, current production image and source-frame ledger. The
actual-source core passes two loaded lifetimes, including explicit damage-kind
checks and the existing clipboard/Undo, allocation rollback and multi-bank
cases. Six production insertions pass the unchanged response limit. The broader
workflow and concurrent cohorts remain separate gates. The record also
distinguishes the core's retained compiled sources from its earlier preparation
ledger and the low-word-only diagnostic callgraph.

QED stack admission and the conditional source bound remain unchanged.
Production costs and upper-image backing deltas are in the record. Reserved
bank-zero growth is **0 fixed / 0 per-public-Task / 0 private idle bytes**,
including guards, alignment and unused capacity. The native desktop and its
provider remain byte-identical to the interactive cursor-paint preview.

## QC1 Production baseline

The [QC1 record](../development/qed-coexistence-qc1.json) binds a complete
production session cold-booted from the refreshed exact OF816 ZIP. Ordinary
shell RUN opens a tabbed document, six insertions coalesce into Undo, navigation
crosses the visible viewport, Find opens/searches/reopens/cancels, two saves
create and rotate a backup, and ordinary Open rereads the saved document.
Independent text/form pixels and closed-image bytes/allocation pass. Quit,
shell collection and EXIT restore ordinary ownership and native guards.

Insertion, navigation, Find and clean Quit pass their original design limits.
Paused snapshots use the existing `SWITCHING` exclusion for all system heap
writers; they validate free-list order, bounds, alignment and totals using the
machine-readable heap records. The final warmed free bytes, largest extent and
extent count equal the initial checkpoint. The record keeps QED private backing
separate from the system heap and aligned image allocation. Seven host cases
cover valid fragmented/allocated heaps and corrupt lists/accounting.

The refreshed demo uses the standard builder, matching OF816, media, ROM and
notices, with its five-second startup intact. Package and observer hashes are
retained; the native desktop XEX is unchanged. Reserved bank-zero delta remains
**0 fixed / 0 per-public-Task / 0 private idle bytes**, including guards,
alignment and unused capacity. Concurrent cohorts and repeated use remain
QC2–QC3; this baseline does not complete step 6.

## QC3 Lifetime and allocation failures

The [QC3 record](../development/qed-coexistence-qc3.json) binds four loaded
lifetimes using the current production patches and forwarding refusal hooks.
The first opens a larger document beside an ordinary periodic peer. A failed
line allocation retains its bytes and clean state; clipboard and Undo then
coexist with that document. Modified New Cancel preserves the edit, Discard
commits an empty document, and an actual form-allocation refusal retains it.
Twelve edit/paste/Undo/New cycles preserve the clipboard and restore identical
heap extents after each warmed reset, while the peer continues painting.

Later lifetimes cover a missing launch, a deep path and cooperative Stop during
Find, followed by Cancel and a second Stop/Discard. Normal collection restores
the native parent's warmed memory baseline. The record keeps this fixture's
Stop scope separate from the normal Counter/shell Stop check in QC2. Selected
ordinary/native/asynchronous stack observations and all guards pass; production
latency remains the uninstrumented cohort's measurement.

A separate small emitted probe executes the actual `restore_edit` and
`make_chg` code against drawing-boundary observers. It checks row damage,
horizontal and vertical clamp promotion, an unchanged origin and explicit full
damage across two loaded lifetimes. This verifies the incremental fix's clamp
policy without claiming that stubbed drawing is a GUI pixel check. Complete
costs, peak samples and headroom are retained in the record.

Reserved bank-zero delta remains **0 fixed / 0 per-public-Task / 0 private idle
bytes**, including guards, alignment and unused capacity. No native parent,
provider or Task-pool growth is required.


## QC2a Bounded selection, caret and navigation painting

Loaded measurements found three sources of avoidable work: selection endpoint
pairs each repainted the whole viewport; character edits hid and revealed the
caret in separate transactions; ordinary rows cleared the background before
painting text. Patches 0019–0022 retain paired row damage, include the caret in
edit/navigation paints, use existing opaque replace text for default-colour
unselected rows, and let the scroll owner paint a revealed viewport once.
Selected rows retain explicit background fills. Idle blinking retains patch
0017's narrow caret band.

The actual-source damage probe now covers 14 cases over two loaded lifetimes,
including paired/reversed/clipped selection damage, viewport clamps, scroll
ownership and current-row caret inclusion. Its drawing observers establish
requested rectangles; the normal cohorts and cursor fixture supply independent
GUI pixels. The cursor fixture checks actual completed visible and hidden
caret frames, allowing either a row paint or the blink callback to reveal it.

The QC2a source bound is 520 bytes, with the existing 768-byte continuation
allowance, 256-byte interrupt reserve, 128-byte headroom target and 2,560-byte
admission. Its conditional margin is 888 bytes. Native reservations remain
**0 fixed / 0 per-public-Task / 0 private idle bank-zero bytes**, including
guards, alignment and unused capacity. ABI, provider and Task pools are unchanged.

The [QC2a record](../development/qed-coexistence-qc2a.json) freezes this
intermediate production image. The baseline passes all response and collection
checks; the cursor fixture completes four lifetimes and verifies real hidden
caret pixels. The checksum cohort still reaches 1,043 ms on a later viewport
navigation, exceeding the unchanged 1,000 ms limit. This slice therefore keeps
the coexistence gate open. Timed navigation begins after an independently
completed warm-up frame; the earlier logical-only warm-up could queue a paint.


## QC2b Multi-row paper and text runs

The later checksum scroll still exceeded its fixed limit. Patch 0023 clears a
clipped multi-row damage rectangle once, then draws its rows without padded
trailing spaces. Selected/non-default colours retain their explicit fills;
single-row edits retain the opaque path. This reduces glyph work through
existing VDI calls and keeps damage, clipping and application policy in QED.

The [QC2b record](../development/qed-coexistence-qc2b.json) binds the production
image and focused emitted checks: 14 actual-source rectangle cases over two
lifetimes and four cursor/exposure/lifecycle sessions with real visible and
hidden caret pixels. Normal production cohorts and repeated-use evidence remain
separate. The source bound is 554 bytes, leaving an 854-byte conditional margin
under the unchanged 2,560-byte admission. The image needs 245,096 bytes of
8-byte-aligned backing. Reserved bank-zero delta is **0 fixed /
0 per-public-Task / 0 private idle bytes**, including guards, alignment and
unused capacity; native/provider and shared Task capacities are unchanged.
