# QED source baseline

[Initial scope and dependencies](../../../../docs/plans/gem4xe/qed-scope-and-dependencies.md) ·
[Port strategy](../../../../docs/plans/gem4xe/qed-port-strategy.md)

[inputs.json](inputs.json) pins the selected QED GEM4XE fork and FreeMiNT cflib
sources, their Git trees and the raw-byte SHA-256 hashes of the editor, headers,
resource, donor adaptation examples and notices. It records the donor's source
selection and the existing Exec toolchain/GUI inputs separately.

This is an input baseline for the native Exec port. The donor does not pin its
external cflib checkout; this pair is the fixed source input. The native work below records compilation
and focused execution separately; it does not establish a runnable editor. The donor's SDK, startup and G4A build are references,
not the Exec build recipe. No donor sources are vendored by this baseline.

## Restore and verify

Run from the Exec repository root:

```sh
python3 tools/prepare_qed.py --output build/qed-native/work
python3 tools/test_qed_native.py --group sources --output build/qed-native/sources
python3 tools/test_qed_native.py --group abi --case opt --output build/qed-native/abi-opt
python3 tools/test_qed_native.py --group abi --case raw --output build/qed-native/abi-raw
```

Preparation verifies every pinned raw file under `build/qed-sources/`, fetching
missing files from the pinned revisions. Existing Git caches must also match
the recorded commit and tree. Changed cached files are rejected. It copies the
original bytes into `OUTPUT/source/`, then applies the ordered [patches](patches/).
Repeating preparation replaces that generated work copy; keep edits in patches
or [native sources](native/). Work and cache trees must be separate.

`sources.json` identifies the source pins, patch and native-adapter hashes,
current Exec inputs and deliberate changes against the frozen step 1 baseline.
The historical baseline stays fixed. The inventory adds each candidate's actual
native compiler command, diagnostics and undefined symbols. Its pending entries
are adaptation work, not a passing complete build or link. Donor exclusions and
board-support reference files have separate dispositions.

The ABI group executes the port boundary through an ordinary loaded C Process.
The raw cohort selects two ABI/return cycles; optimized checks also retain the
existing Process concurrency, reuse and loader-failure scenarios. Both retain
native IRQ/NMI, guard, context and ownership checks. These are development
checks, not hosted-system qualification or full QED execution. See the
[implementation record](../../../../docs/history/qed-native-feasibility.md).

## Owned runtime development checks

```sh
python3 tools/test_qed_native.py --group runtime --case opt --output build/qed-native/runtime-opt
python3 tools/test_qed_native.py --group stop --case opt --output build/qed-native/stop-opt
```

These link the actual patched QED text allocator. Notification and highlighting
callbacks belong only to the fixture. The allocation implementation keeps a
12-byte owned header in upper memory, returns bank-contained blocks and uses
the public `AvailMem` import for `Malloc(-1)`. The current loaded C ABI is in
[abi/c-program.json](../../../../abi/c-program.json); rebuild the matched
provider and applications after changes to it.

For an existing fixture with unchanged native code, `--from-build` rebuilds
its C APP and media while retaining the emitted native provider. It rejects a
provider/import ABI mismatch. Omit it after changing native fixture/provider
inputs. `--focused-abi` selects two ABI/return cycles in either compiler mode.

See the [native runtime contract](native/README.md) for descriptor ownership,
errors, stdio bounds and explicit calendar limitations.

The body passed to `QedRuntimeRun` must retire GUI borrowers before returning.
The Stop fixture exercises a borrowed allocated title, cooperative native
`RequestStop`, window retirement, heap cleanup and ordinary collection; no
private Task exit or donor board termination is used.

## Complete retained-source layout

```sh
python3 tools/test_qed_native.py --group layout --case opt --output build/qed-native/layout-opt
python3 tools/build_qed.py --output build/qed-native/layout --provider build/qed-native/layout-opt/c-image.json
```

The [selection ledger](native-selection.json) accounts for every pinned editor
and cflib source: 131 selected units and 47 explicit exclusions. Native startup,
fixed defaults, clipboard ownership, file metadata and ordinary retirement
replace donor OS, configuration and accessory paths. Source patches retain the
editor core. The resource location is `SYS:QED.RSC`; document paths keep their
inherited native current directory. CFLIB's private path seed is an empty
relative prefix, with no invented drive or application-directory identity.

The declaration generator fetches only the hash-checked GEM reference header
already pinned by Exec. It selects private constants/declarations, preserving
the public native records. It imports no donor gateway or SDK runtime.
`tools/generate_qed_compat.py --check` verifies the checked-in result.

`build_qed.py` compiles the complete selection with the real runtime and an
explicit [later-GEM binding catalog](analysis-bindings.json). It writes an
**analysis ELF and layout report**, with no APP. Nonreturning bindings are
limited to that catalog; an unresolved essential helper fails the real link.
The report includes every retained archive member and verifies independent
relinks at every legal base. The packer and both filesystem media producers
reject the embedded analysis marker, including a renamed artifact.

The layout group executes an independent loaded six-segment probe with its
entry in the third code bank. It also checks real private string/geometry/key
helpers; optimized cases reject excessive segment counts/spans through the
native loader. Raw mode focuses on the compiler/layout boundary. Use the
[history and evidence](../../../../docs/history/qed-native-feasibility.md) for
exact measured costs, allowances and execution scope. This is not full QED
startup, editing or saving evidence.

## Notices

The QED pin includes `gem4xe/NOTICE`, `dist/liesmich.txt`, `doc/qed-en.stg`,
`gem4xe/COPYING.LIB` and `gem4xe/LICENSE-APACHE-2.0`; the cflib pin includes its
own `COPYING.LIB`. Retain their terms and file-specific notices in future source
adaptations and distributions. The donor states a no-fee redistribution
condition for QED and its port files. Exec's MIT interface licence does not
relicense that material. Final binary notices must match the actual linked
components.
