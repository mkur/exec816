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
