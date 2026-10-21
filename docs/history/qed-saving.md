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
