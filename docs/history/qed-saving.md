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
