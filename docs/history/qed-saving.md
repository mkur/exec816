# QED reliable saving

[Historical records](README.md) · [Saving design](../plans/gem4xe/qed-saving-design.md) ·
[Implementation plan](../plans/gem4xe/qed-saving-implementation-plan.md)

This page records strategy step 5 development slices. It does not qualify the
hosted system or a release. Earlier QE1–QE7 evidence remains immutable.

## QW1 Public C canonical-name binding

The ordinary C DOS interface now exposes native `NameFromLock`. C APP ABI 26
has one provider and import list; applications using ABI 25 are rejected by the
ordinary loader. DOS table indices and capacity come from
[the ABI definition](../../abi/c-program.json), with generated C and native
outputs. The operation returns the native physical canonical name and retains
the caller's lock ownership. QED Save/Save As remain disabled.

The [QW1 development record](../development/qed-saving-qw1.json) binds the actual
APP/provider, focused raw and optimized C/native NIR probes, ordinary loaded
QED lifecycle, stack samples and refreshed exact OF816 demo ZIP checks.
The name probes cover root/nested/relative/SYS/ASSIGN names, exact and short
capacities, full-width arguments and guard/context/resource restoration. The
optimized fixture rejects a copied ABI 25 APP before entering its body.
Both the standard and GEM packages were refreshed because the loader consumes
the generated ABI constant. Private QED remains outside those distributions.

The production APP uses 105,203 code bytes, 1,640 initialized bytes and 23,763
BSS bytes; its serialized size is 120,083 bytes. The source-frame bound remains
776 bytes, with 632 bytes of conditional margin at 2,560-byte admission.
Continuation and asynchronous-entry evidence retain their stated scope.
Reserved bank-zero growth is **0 fixed / 0 per-public-Task / 0 private idle
bytes**, including guards, alignment and unused capacity. Complete reservation
and Task-pool maps match the retained startup baseline.

## QW2 Canonical paths and parent ownership

Open and launch now establish a directory parent with ordinary Lock/Examine,
obtain its physical name through NameFromLock, and retain the parent until
candidate cancellation or commit. They read and commit one canonical path;
relative/SYS/ASSIGN input spellings remain accepted. Selected-file query locks
retire before later Rename. Save commands remain disabled.

The [QW2 record](../development/qed-saving-qw2.json) covers the actual path
owner, reassignment through a native child, retained-parent rename/deletion
exclusion, released query locks, nominal builder limits, two reader lifetimes
on each disk filesystem, and four real editor lifetimes with document pixels,
canonical names, failed launches and Stop decisions. The 255/256-byte builder
boundary is a pure emitted helper check; it does not claim a 255-byte physical
path in today's bounded 16-level namespace. Reader ownership includes two
80 KiB rings and 16 Open/New reuse pairs. Observed private peak is 214,860 bytes;
minimum reader headroom is 543 bytes.

The APP grows by 1,518 code bytes and six BSS bytes to 106,721 code / 1,640
initialized / 23,769 BSS bytes, with a 121,709-byte container. Path preparation's
256-byte name scratch and 260-byte FIB use 540 private backing bytes (544 after
Exec's eight-byte allocation rounding); the retained native parent is a separate
DOS owner. Source-frame bound remains 776 bytes, conditional margin 632 bytes.
The provider is unchanged. Reserved bank-zero delta is **0 fixed / 0
per-public-Task / 0 private idle bytes**, including guards, alignment and slack.

## QW3 Exact serialization and exclusive staging

The resumable writer counts before creation, then emits at most 4,096 bytes and
visits at most 256 line boundaries per poll. It preserves LINE bytes and emits
LF/CRLF only between logical lines. One bank-contained 4 KiB upper-heap buffer
retains partial-output and separator state. Exclusive creation admits its
private descriptor slot before native Open; exhaustion cannot leave a created
file. Confirmed short prefixes advance once. Zero/negative progress or any
causal Write error fails; terminal Close consumes its identity once and retains
its separate cause. Unknown mutation/Close outcomes retain the possible T.

The [QW3 record](../development/qed-saving-qw3.json) binds optimized actual-source
RAM/SpartaDOS/MyDOS checks, two Process lifetimes per cohort, collision/exhaustion,
allocation/admission failure, causal short/full writes, Close uncertainty,
cancellation/cleanup failure, count overflow, empty/trailing lines, maximum
lines and 80 KiB output. Focused cases split CR from LF at byte 4,096 and retain
literal ATASCII 155. Independent closed-ATR audits find two exact 81,920-byte
staged files on each disk filesystem with consistent allocation and no lost
sectors. The files are staging artifacts, not published destinations.

Observed private peak is 108,984 bytes, including the multi-bank LINE owner and
allocation headers; the serialization buffer costs 4,108 backing bytes (4,112
after Exec allocation rounding). The main cohorts' minimum observed headroom
is 1,807 bytes in an existing compatible pool. The production APP grows by 44
code and four BSS bytes for adapter lifecycle accounting: 106,765 code / 1,640
initialized / 23,773 BSS, serialized 121,789 bytes. The uncalled stage unit is
not a production entry point. Production source bound remains 776 bytes,
conditional margin 632 bytes. Provider and reserved bank-zero growth remain
**0 fixed / 0 per-public-Task / 0 private idle bytes**, with complete maps equal.

Save/Save As remain disabled. Staging readiness is not Saved; no D/B
publication or GUI consent is claimed by this slice.

## QW4 Backup/publication transaction and recovery ownership

The production core preallocates D/T/B/E and metadata/phase/error state. A
preauthorized caller stages and closes T, moves any older B to a unique E,
moves D to B, publishes T to D and only then removes E. `.BAK` destinations use
`.BKP`. If D is absent, an independent B is neither queried nor changed.
Logical forward failures reverse only confirmed moves. A failed reversal stops
cleanup. Unknown mutation/Close outcomes retain names and never trigger
speculative restoration/deletion. After publication, new D is never deleted
for rollback. Required E cleanup failure is a non-Saved result with publication
recorded. The record retains both causes and confirmed staging/namespace phases.

The [QW4 record](../development/qed-saving-qw4.json) binds two ordinary Process
lifetimes per cohort on RAM and both writable disk formats: new/existing D/B,
separate authorization cancellation, twelve repeated saves, real E collision,
256-candidate exhaustion, all three forward renames, both reversals, T/E cleanup,
Close failure, cancellation and unknown-error policy. It also covers allocation
refusal before creation, in-use D/B, directory collisions, protected D/B and
preservation of the previous object's protection/date metadata in B. SDFS
Hidden/Archive flags are disclosed inputs; a newly created D uses defaults.
Independent closed-ATR audits find the exact five-byte new D and original
three-byte B, consistent allocation and no unexpected T/E files. Injected
uncertainty establishes policy coverage; physical offline transport remains QW7.

Observed private peak is 57,974 bytes with the small test ring. The save owner
costs 1,398 payload / 1,410 private backing bytes (1,416 after Exec rounding);
with its buffer the incremental private backing is 5,518 bytes (5,528 rounded),
plus the native directory owner. The buffer retires before namespace moves.
Minimum core headroom is 1,745 bytes in an existing compatible pool.
The uncalled production APP layout remains 106,765 code / 1,640 initialized /
23,773 BSS bytes, serialized 121,789 bytes; source bound 776, conditional margin
632. Provider and reserved bank-zero deltas remain **0 fixed / 0
per-public-Task / 0 private idle bytes**, including guards, alignment and slack.

Save menus remain disabled. These explicit preauthorized core intents do not
establish loaded-editor consent, modified decisions or GUI recovery reporting.

## QW5 Loaded-editor Save and Save As

Save and Save As now share one event-owned production transaction and always
serialize the complete document. The native selector and separate
Cancel-default destination/older-backup consents precede creation. Consent
shows the canonical target and default-attribute/Hidden/Archive restriction.
The donor save/backup/restore paths are removed from the selected graph.

Saved alone commits the canonical identity and clean state. Text, selection,
view, clipboard and functional Undo survive; an explicit typing boundary
prevents new input coalescing into the pre-save group. Mutating input is consumed
while the transaction borrows the ring. An idle input/queue drain precedes
unfreezing. Escape after publication cannot change Saved into Cancelled.
Close/Stop cancels safe staging or waits for namespace work to stabilize.

The [QW5 record](../development/qed-saving-qw5.json) binds four loaded-editor
lifetimes on each writable disk format, with RAM saving/reopening, menu and
shortcut input, default cancellation, full selected-document output, Undo,
busy-key rejection, ordinary-peer paint progress, failed Write, uncertain Close,
publication rollback, complete long-path paging and cooperative Stop. A true
native allocation refusal preserves the notice record/document; Escape retries.
A further GUI cohort checks published-but-failed E cleanup, forced dirty state,
review/Cancel/explicit Forget, selector cancellation and a fresh successful Save
As. Recovery Forget leaves files intact; no automatic repair is attempted.

Independent closed-image audits check exact D/B bytes, unchanged CRLF/deep
inputs, the retained uncertain T or E, and consistent whole-volume ownership.
These are development checks; injected adapter failures do not establish an
offline transport result. QW7 supplies selected physical faults.

Production size is 109,678 code / 2,818 initialized / 22,208 BSS bytes,
serialized 126,500 bytes. The source-frame bound is 503 bytes, conditional margin
905; the main GUI cohorts' observed minimum headroom is 1,328 bytes and observed
private peak 111,309 bytes. Changing the descriptive selection scope leaves
the production APP byte-identical. The provider is unchanged. Reserved
bank-zero delta is **0 fixed / 0 per-public-Task / 0 private idle bytes**,
including guards, alignment and unused reserved capacity.

Save/Save As are enabled; modified New/Open/Close/Quit/Stop still use
Discard/Cancel until QW6. Saving remains a private development feature and the
strategy step 5 gate remains open through QW8.

## QW6 Save/Discard/Cancel continuations

One Cancel-default decision now controls modified New/Open/Close/Quit/Stop.
Save retains an explicit continuation without recursive file policy. Only Saved
continues. Cancel, interrupted/zero decisions and non-Saved outcomes retire the
prepared replacement and preserve the current document. A newer Close/Stop
supersedes an older replacement after publication/restoration/cleanup stabilizes.

Open always drops its earlier ring and rereads its frozen canonical path after
Saved, retaining the directory parent continuously. This also handles Save As
to the pending Open target. Failed rereading reports Open failure while keeping
the now-saved clean document and committed Save As name. New's independent
empty candidate is committed only after success or explicit Discard.

The [QW6 record](../development/qed-saving-qw6.json) covers four loaded-editor
lifetimes on each disk format, physical New/Open/Close/Quit choices and ordinary
RequestStop, unnamed Save As, selector cancellation, failed Save, D1/SYS/ASSIGN
same-target rereads, Save As to the Open candidate, injected reread failure and
a Close superseding New at a held native Rename. The interrupted New/Stop
case retires the candidate; Cancel leaves the Process live and a later Stop
saves before retirement. Closed-image audits check exact saved/backup bytes and
allocation. The focused SpartaDOS retry uses a one-byte initial launch; MyDOS
keeps the 80 KiB launch. Existing multi-bank reader/stager cohorts remain separate.

Stack sampling now resolves retained C entries and TCS sites through object
sections and linker placement, checking each emitted opcode. This distinguishes
private helpers with the same name as an exported function in another unit.
Active editing observers use the current three-button choices and selector
cancellation in place of former disabled-Save checks. Historical traces/records
retain their original scope. Current observed minimum
headroom is 1,324 bytes; observed private peak is 111,309 bytes. Production is
110,152 code / 2,770 initialized / 22,212 BSS bytes, serialized 127,210 bytes;
source bound 503 and conditional margin 905 bytes. The descriptive selection
update leaves APP bytes unchanged. Provider growth and reserved bank-zero delta
remain **0 fixed / 0 per-public-Task / 0 private idle bytes**, including guards,
alignment and unused capacity. These checks are development evidence.
