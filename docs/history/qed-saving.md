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

## QW7 Operational failures and resource closure

The [QW7 record](../development/qed-saving-qw7.json) combines optimized
actual-source writer checks with the loaded editor's large-cleanup Stop case.
Consistent disposable 720-sector images cover payload exhaustion, checked
Close and cleanup, reclamation, successful retry and twelve further saves on
both formats. A separately prepared 64-entry MyDOS root rejects staging
creation without changing D/B. Each logical cohort runs two collected Process
lifetimes with exact warm heap return; closed-image audits check bytes and
whole-volume allocation. The GUI cleanup cohort uses 2,880 sectors.

The [saving fault pin](../../toolchain/qed-saving-sio-faults.json) identifies the
exact current bridge binary, ROM, configuration and existing D8 peripheral
fault code. Activation follows actual WRITE payload transmission, before its
checksum/data ACK/completion. Terminal E and protocol X reach QED's real writer
on both disk formats. They preserve causes 3/7, consume Close once, retain the
possible T and perform no speculative Rename/Delete. MyDOS's offline case
confirms a 253-byte prefix; it is never resent. Ordinary foreground RequestBreak
before Write and after 4,096 committed bytes similarly preserves ERROR_BREAK,
closed T and the original Process secondary result. GUI notices and cooperative
Stop remain independently checked through the real editor.

After retirement the selected interrupted writers have zero private allocation
blocks/payload/backing. Healthy cases check normal ownership and OS restoration.
Protocol/offline cases require `$FF93`, disabled interrupts, intact guards and
released caller-buffer pointers. The platform deliberately parks before
HEAP_SHUTDOWN: retained bank claims must be exclusively new HEAP-owned claims
from previously free banks. This is neither normal hosted return nor a healthy
volume claim. Invalidated images are kept separate; subsequent writes start
from newly constructed good media. Application/Process retirement is distinct
from kernel storage retained until reset.

The loaded-editor Stop check cancels staged writing, declines the fresh modified
decision, then retries. After publication the caller blocks in native deletion
of a 256 KiB E; a second ordinary RequestStop is delivered there. Deletion must
finish before clean retirement. The closed image retains the new D and original
D in B, with E reclaimed. Delete/Close have operation/volume bounds; the 4 KiB
serializer budget is not their frame deadline.

Two 80 KiB RAM files use 262,256 bytes including native nodes. With the staged
third buffer, observed post-poll growth is 399,168 bytes relative to the pre-file
baseline, including three 131,072-byte capacities and 5,952 bytes of private and
native overhead. Publication returns to the two-file cost; deletion returns
exactly to baseline. Source inspection of RAM growth adds a possible transient
65,536-byte old buffer before copy/free, giving a 464,704-byte bound for that
incremental interval; this transient is not claimed as a sampled watermark.
Normal writer private peak is 114,502 bytes and minimum selected headroom
1,733 bytes. Disk payloads, directory entries and retained recovery files are
accounted separately from private allocation backing.

No production source or public ABI changes were required. The matching QW6
production APP and its 503-byte source bound / 905-byte conditional margin are
reused. Provider and reserved bank-zero deltas remain **0 fixed / 0
per-public-Task / 0 private idle bytes**, including guards, alignment and unused
capacity. These are development checks; QW8 reconciles the complete saving gate.

## QW8 Saving gate and coexistence handoff

The [QW8 record](../development/qed-saving-qw8.json) reconciles the current
production sources, C APP ABI 26/provider, source-frame ledger, selected emitted
PCs, resource and runtime/toolchain with the frozen QW1–QW7 evidence. Earlier
records retain their exact executed scope and hashes. The current combined
session uses four ordinary loaded Processes on writable SpartaDOS; MyDOS's
current QW6 continuation and QW7 operational cohorts supply its complementary
scope. No old-ABI QE7 run is counted as current execution.

The combined workflow opens twelve maximum-length tabbed lines, copies/cuts,
toggles Undo, pastes, Finds/Finds Next and pans to a literal match. It checks
independent text, selection, caret, document/form and peer pixels. Save As
preserves the viewport/clipboard; named Save cancels by default, then rotates
the backup. A causal Write failure and uncertain Close keep dirty text; recovery
Cancel retains details, and explicit Forget leaves the uncertain T intact before
a successful fresh Save As. Ordinary reopen reads the saved bytes. Modified
Open saves the current document while retaining a separate candidate, then
rereads and commits the chosen path. Close Cancel preserves edits; Quit Discard
retires that session. Further lifetimes cover New Save, deep-path Close Save and
staged cancellation followed by Stop Save. All four retire normally. The last
Stop arrives during native reclamation of a 256 KiB older backup.

Closed-image audits independently check COMBO/FRESH destinations, their previous
backups, the retained uncertain T, deep-path output and CRLF output, together
with whole-volume allocation. A new native-service instance mounts that exact
SpartaDOS writer image read-only and reopens FRESH; a separate new-service MyDOS
reader reopens the exact QW6 writer image. Both verify document pixels, normal
collection and an unchanged complete ATR hash. Neither rebuilds the writer's
media nor inserts a replacement APP into it.

Production remains 110,152 code / 2,770 initialized / 22,212 BSS bytes,
serialized 127,210 bytes and aligned image backing 241,224 bytes. Against QE7,
code grows 4,953 bytes, initialized plus BSS shrinks 421, container metadata
grows 1,056 and aligned image backing grows 4,952. Remaining private growth
allowances from that editing baseline are 27,815 code / 16,384 data-BSS /
15,328 metadata bytes. The public canonical-name binding costs 25 provider code
and four data-BSS bytes; remaining provider allowances are 15,132 code / 16,380
data-BSS / 4,096 table bytes. No later slice changes that provider.

Admission remains 2,560 bytes: source bound 503, continuation allowance 768,
interrupt reserve 256 and required headroom 128 leave conditional margin 905.
The combined session retains 1,324 bytes of minimum selected headroom and
58,892 bytes of observed private peak. Its held Save has a 13-line Open
candidate, clipboard and Undo live together with 58,889 bytes of private
backing, while the ordinary peer continues painting. Complete reservation maps
and the selected-PC measurements are bound in the record. Save's state/buffer, independent candidate, clipboard/Undo, native
parent and filesystem backing remain distinct owners; QW7 records RAM capacity
and transient-copy costs rather than counting disk payload as private heap.
Reserved bank-zero delta is **0 fixed / 0 per-public-Task / 0 private idle
bytes**, including guards, alignment and unused reserved capacity.

Both exact QW1 demo ZIPs retain matching source inputs (128 standard, 206 GEM),
all packaged checksums, OF816, pinned ROM/notices and their passing 249-frame
five-second shell/prime smokes. They are reused without rebuilding unchanged
packages. Private QED remains outside them. No publication is requested; old/new
Atarimax CAR and raw 1 MiB BIN images remain required before a future release.

Strategy step 5 is complete at this development scope. The step 6 starting
point is a working native Open/Edit/Find/Save/Close session with normal
collection and warm reuse. Measure responsiveness, fragmentation, peak backing
and cleanup under an ordinary GEM peer plus shell or MD5/ARC activity, respecting
shared Task capacity. Existing peer progress is not a realistic-load latency
claim. Supported delivery and final QED notices remain strategy step 7.
Power-loss atomicity, concurrent same-target mutation, autosave, broader metadata
restoration and automatic repair/recovery scanning remain unsupported. These
checks do not qualify the hosted system, a release or physical media.

## Interactive native preview

At the user's request, the [native Altirra setup](../guides/qed-exec.md) makes
the current production APP available on the normal Exec GEM desktop before
strategy steps 6/7. The [setup record](../development/qed-exec-setup.json) binds
the exact ZIP, APP/resource, pinned ROM/emulator and normal launch walkthrough.
It reuses the verified desktop XEX, adds QED to C: and its resource to SYS:,
and supplies a separate writable WORK disk with SAMPLE.TXT. OF816 retains the
five-second startup; the launcher uses private settings and preserves its local
writable disk. The ordinary demo builder refreshes matching boot media/notices.

The selected development check launches production QED through the shell,
edits and saves three times across two loaded lifetimes, reopens, rotates the
backup and checks exact persisted bytes/allocation. QED retires normally;
`JOBS` at the next shell command boundary collects its completed Process.
The preview does not extend practical-workload or release qualification.
Native code and all stack/DP reservations stay unchanged: **0 fixed / 0
per-public-Task / 0 private idle reserved bank-zero bytes**, including guards,
alignment and unused capacity.

## Idle cursor repaint correction

Interactive use exposed row flicker while QED was idle. Each timer-driven caret
blink called `line_out`, clearing and redrawing the complete cursor row. Patch
0017 limits the visible-rectangle clip and painting to the caret band: two
pixels in insert mode or one font cell in overwrite mode. Hiding the caret
restores the underlying background and one glyph, retaining selection colours,
tab and end-of-line handling. The timer and normal text redraw paths remain
unchanged.

The [cursor-paint development record](../development/qed-cursor.json) binds the
new production image, source-frame measurement and emitted checks. The focused
test observes actual forwarded VDI requests during idle blinking, checks both
caret states against independent text pixels, covers/exposes the window behind
an ordinary peer, selects text and checks normal retirement across four loaded
lifetimes. The exact refreshed production ZIP also passes the normal shell
launch, editing/save/backup/reopen and ownership-return walkthrough. Earlier
records and their packaged artifacts retain their original hashes and paths.

The updated [interactive setup](../guides/qed-exec.md) retains the user's existing
writable WORK disk through a link and redirects the old local QED launcher to
the refreshed package. Restarting Altirra loads the new APP. Stack admission and
the source-frame bound are unchanged; code and image growth are recorded in the
development record. Native desktop code and all bank-zero reservations remain
unchanged: **0 fixed / 0 per-public-Task / 0 private idle bytes**, including
guards, alignment and unused capacity. This correction does not extend strategy
steps 6/7 or hosted/release qualification.
