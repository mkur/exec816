# QED source baseline

[Initial scope and dependencies](../../../../docs/plans/gem4xe/qed-scope-and-dependencies.md) ·
[Port strategy](../../../../docs/plans/gem4xe/qed-port-strategy.md)

For interactive use, the [native Exec Altirra setup](../../../../docs/guides/qed-exec.md)
packages the current production editor on the ordinary GEM desktop, with a
private launcher and persistent writable WORK disk. Strategy step 6 passes its
selected coexistence development checks. The [delivery record](../../../../docs/history/qed-delivery.md) tracks the normal package and final step 7 gates.

[inputs.json](inputs.json) pins the selected QED GEM4XE fork and FreeMiNT cflib
sources, their Git trees and the raw-byte SHA-256 hashes of the editor, headers,
resource, donor adaptation examples and notices. It records the donor's source
selection and the existing Exec toolchain/GUI inputs separately.

This is an input baseline for the native Exec port. The donor does not pin its
external cflib checkout; this pair is the fixed source input. The native work below records compilation and focused execution separately.
Strategy step 3 builds a runnable development APP and exercises real startup;
the editing, saving and practical coexistence slices extend that baseline.
The [step 7 delivery gate](../../../../docs/history/qed-delivery.md#qd7-supported-development-delivery)
now passes for the supported development port; full release qualification is separate.
The donor's SDK, startup and G4A build are references,
not the Exec build recipe. No donor sources are vendored by this baseline.

## Restore and verify

Preparation also generates the compact English resource and matching `qed.h`
from [resource-selection.json](resource-selection.json). It retains ten trees,
185 objects, a 30-object menu and 44 free strings. Current byte sizes are
recorded in the generated resource manifest. Local indices
within non-menu trees are preserved; discarded menu identifiers are removed.
The donor cache remains unchanged. The selection strips decoration and marks
deferred Find controls disabled. Generated artifacts are under `OUTPUT/resource/`.

```sh
python3 tools/test_qed_startup.py --group resources --output build/qed-startup/resources
```

The resource check runs a loaded C Process, standard named/AESPB string access,
all retained trees, writable fields, menu installation, rejected replacement
and cleanup/reuse. These are development checks for startup resources.

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

## Editing development checks

```sh
python3 tools/test_qed_editing.py --group core --output build/qed-editing/core
python3 tools/test_qed_editing.py --output build/qed-editing/editor
python3 tools/test_qed_viewport.py --output build/qed-editing/viewport
python3 tools/test_vdi_modes_abi.py --mode opt --output build/qed-editing/vdi-opt
python3 tools/test_vdi_modes_abi.py --mode raw --output build/qed-editing/vdi-raw
```

QE1 enables keyboard editing and Cancel-default Discard/Cancel retirement.
QE2 adds transparent VDI text, widened long-line navigation and exposure/geometry
checks with another ordinary GEM client. The viewport runner can select
`--scenario long` or `--scenario geometry`; the default runs both in one session.
The core probe exercises actual donor text routines at the line limit and
under upper-heap exhaustion. The loaded editor uses physical keys, native
dialogs and an independent text/pixel observer; its allocation wrapper refuses
selected acquisitions and forwards every successful call to the actual allocator.
The supervisor checks normal collection, unload and exact heap reuse.
See the [editing record](../../../../docs/history/qed-editing.md) for the
implemented slice, evidence and remaining commands. Save/Save As remain disabled.

QE3 enables event-driven pointer/Shift selection, Select All, release rearming
and bounded outside-work autoscroll. The loaded-editor runner verifies ranges
and pixels, cancellation, peer drawing, ordinary retirement and heap reuse:

```sh
python3 tools/test_qed_selection.py --output build/qed-editing/selection
python3 tools/test_qed_selection.py --group logical --output build/qed-editing/selection-logical
python3 tools/test_qed_selection.py --group logical --raw --output build/qed-editing/selection-logical-raw
python3 tools/test_qed_selection.py --group shortcuts --output build/qed-editing/shortcuts
python3 tools/test_qed_selection.py --group shortcuts --raw --output build/qed-editing/shortcuts-raw
```

The small raw/optimized comparisons cover actual-source navigation and the
shortcut parser after the documented Calypsi profile/source corrections.
See the [selection evidence](../../../../docs/history/qed-editing.md#qe3-event-driven-selection)
for physical key limitations, stack accounting and exact executed scope.
QE4 enables clipboard/Undo and edits replacing an active selection;
QE5 adds native dialogs and literal Find. QE6 adds checked New/Open and launch
replacement. QE7 reconciles the combined editing session and package evidence;
reliable saving remains strategy step 5.

`--from-build` rebuilds the APP against an unchanged emitted native fixture.
`--reuse-app` additionally verifies recorded APP input hashes for observer-only
reruns. Omit both after changing provider or native fixture inputs.

## Complete retained-source layout

```sh
python3 tools/test_qed_native.py --group layout --case opt --output build/qed-native/layout-opt
python3 tools/build_qed.py --output build/qed-native/layout --provider build/qed-native/layout-opt/c-image.json
```

The [selection ledger](native-selection.json) accounts for every pinned editor
and cflib source with explicit selections and exclusions. Native startup,
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
**analysis ELF and layout report** by default. The catalog now records explicit
adaptations and the real input binding; no trap remains in the selected graph.
An unresolved essential helper fails the real link.
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

## Stack and admission checks

```sh
python3 tools/test_qed_native.py --group admission --output build/qed-native/admission
python3 tools/test_qed_native.py --group masks --output build/qed-native/masks
python3 tools/measure_qed_frames.py --layout build/qed-native/layout
```

The current C APP ABI retains a general minimum-stack requirement in the existing
header. QED requests 2,560 total bytes, including the 256-byte interrupt reserve;
ordinary Process admission selects a compatible free pool or fails before
entry. The two existing larger pools keep their normal owners and capacities.
The admission fixture checks ordinary selection, larger-pool occupancy,
pre-entry exhaustion, image rollback and collection/reuse.

Patch 0004 moves per-command paths, undo/line scratch and the persistent event
record into private upper-image storage. Nested file/dialog loops deliver
redraw and geometry messages, with finite Close-to-Save action nesting. The
file-mask matcher is iterative; Find remains literal. The mask fixture links
that actual source. `-O2` remains enabled; the port disables cross-call and
cross-function tail sharing to keep emitted function frames auditable. The
QE3 profile also disables C inlining after the actual-source Ctrl-End probe
exposed an incorrect field access in Calypsi 5.18's inlined code. Shortcut
normalization also keeps its character intermediate word-wide: the compiler
omitted a width restore after its conditional byte increment. The
[focused raw/optimized checks](../../../../docs/development/qed-shortcuts.json)
execute the actual CF-Lib parser. The layout
report charges the resulting code cost.

QED native groups collect passive S samples at emitted entries/frame sites,
with physical pool, DP and per-pool Process lifetime ordinal. These samples
retain the 128-byte headroom requirement and complement the source frame ledger.
The ledger rejects unclassified indirect sites or unbounded source call cycles.
It records a separate continuation cap for library/native/GEM work, which later
GUI implementations must establish by full-chain measurements. The independent analysis artifact remains unsuitable for execution.

## Reconciled foundation

QF1–QF6 are complete for strategy step 2. The
[final development record](../../../../docs/development/qed-native-qf6.json)
identifies the actual compiled baseline, selected native executions, stack
conditions, rebuilt demo callers and exact-package smokes. Run
`tools/check_qed_baseline.py --help` to audit a reproduced layout and cohorts.
The source frame tool accepts `--output` to preserve earlier ledgers.

The [startup work](../../../../docs/history/qed-startup.md) has adapted the
resources and fixed-font source and implemented the general input snapshot.
The complete graph links without analysis traps; the catalog records each
former binding's disposition. Analysis mode retains its packaging marker;
ordinary executable mode supplies the implemented startup and editing slices.
Future GUI chains must establish the continuation cap. Proof fixtures and
analysis artifacts remain outside the ZIP.

## Notices

The QED pin includes `gem4xe/NOTICE`, `dist/liesmich.txt`, `doc/qed-en.stg`,
`gem4xe/COPYING.LIB` and `gem4xe/LICENSE-APACHE-2.0`; the cflib pin includes its
own `COPYING.LIB`. Retain their terms and file-specific notices in future source
adaptations and distributions. The donor states a no-fee redistribution
condition for QED and its port files. Exec's MIT interface licence does not
relicense that material. Final binary notices must match the actual linked
components.

## Real application startup

```sh
python3 tools/test_qed_startup.py --group binding --output build/qed-startup/qs2-binding-opt
python3 tools/build_qed.py --executable --output build/qed-startup/app \
  --provider build/qed-startup/qs2-binding-opt/c-image.json
python3 tools/test_qed_startup.py --group startup --output build/qed-startup/startup
```

Executable mode requires a matching current provider and no pending analysis
bindings. It packs an ordinary APP with the 2,560-byte minimum stack after
all legal-base relinks. Default analysis mode keeps its packaging rejection.
Use a provider produced by the resource/binding fixture if the example path
does not yet exist.

The startup cohort loads the complete application and its generated resource
through ordinary DOS/Process operations. It checks the actual menu, 8×8 font,
single borrowed workstation, one document window and native empty-work-area
pixels. Physical window Close, Ctrl+Q, another Close and cooperative RequestStop
each retire normally. The supervisor collects/unloads and checks exact memory
recovery. A focused
`--group event` probe also executes the adapted poller request. Native event
requests use supported left-button/down semantics, and menu shortcuts precede
character insertion. See [startup evidence](../../../../docs/history/qed-startup.md).

These are development startup checks, not editing, dialog or Save qualification.
The normal `build_demo.py --gem-desktop --qed` path now packages the production APP. These earlier startup checks retain their original scope.

```sh
python3 tools/test_qed_startup.py --group failures --output build/qed-startup/failures
python3 tools/measure_qed_frames.py --layout build/qed-startup/startup/app
```

The failure group builds a separate development APP with acquisition failures
and persistent private allocation refusal. It executes missing/malformed resource
loads through the real loader. It copies the unchanged APP to RAM: using DOS
Read/Write for the failure sweep; resource reads stay on SYS:. The production
startup cohort repeats disk APP loads. The ordinary executable omits the
failure controls.
Both cohorts require normal collection, clean owners and exact memory reuse;
the observer attributes stack samples to each owned physical Process lifetime.
The [current reconciled record](../../../../docs/development/qed-startup-qs5.json)
identifies the matched ABI 25 callers, sources, runtime, ROM/emulator and exact
standard/GEM package checks. Earlier QF/QS records retain their historical scope.

QE1 detaches the document pointer callback and removes its donor MU_M2 wait.
Document pointer interaction remains disabled until QE3 supplies the outer-event
selection protocol. Startup Close/Quit/Stop evidence does not establish
New/Open policy, text editing, selection, dialogs or saved-file behavior.

QE4's transaction and loaded-editor checks:

```sh
python3 tools/test_qed_clipboard.py --output build/qed-editing/clipboard-core
python3 tools/test_qed_clipboard.py --group editor --output build/qed-editing/clipboard-editor
```

The focused core exercises actual donor LINE/clipboard/Undo ownership, allocation
refusal, line bounds and multi-bank content; notification sinks do not claim GUI
behavior. The editor cohort uses physical keys and menu clicks, independent
text/clipboard/pixel checks and four ordinary Process lifetimes. Undo swaps one
affected-line group without allocating and toggles on repetition. See the
[QE4 evidence](../../../../docs/history/qed-editing.md#qe4-internal-clipboard-and-grouped-undo)
for exact stack, heap and development scope. Save/Save As remain disabled.

QE5's native dialogs and literal Find checks:

```sh
python3 tools/test_qed_dialogs.py --group editor --output build/qed-editing/dialog-editor
python3 tools/test_qed_dialogs.py --group core --output build/qed-editing/dialog-core
python3 tools/test_qed_dialogs.py --group selector --output build/qed-editing/dialog-selector
```

Find accepts up to 50 literal, case-sensitive bytes, searches forward without
wrap, and selects the match. Find Next continues from the cursor. Cancel keeps
the last accepted pattern; not-found keeps the position/range. Geometry policy
can resume a retired native Find draft; Close/Stop cancels it. The controller
returns to normal event handling after each 256 search positions. About and
Find use native forms; the ten unused donor MDIAL units are excluded. The
selector adapter uses native path[128]/leaf[13] buffers and preserves native
volume/relative paths. QE6 connects an accepted choice to checked replacement.

The core cohort isolates signed results, path capacities and bounded search;
the selector cohort uses the real native selector. The loaded editor checks
physical input, document/form pixels, cancellation, allocation failure and peer
progress. See [QE5 evidence](../../../../docs/history/qed-editing.md#qe5-native-dialogs-and-literal-find).

QE6's checked loading and replacement checks:

```sh
python3 tools/test_qed_documents.py --output build/qed-editing/documents
python3 tools/test_qed_documents.py --group core --output build/qed-editing/document-core
python3 tools/test_qed_documents.py --group title --output build/qed-editing/document-title
```

Open, New and a zero/one document argument use one controller and the existing
document/window. A detached candidate must finish its checked read and Close
before a modified document prompts for Discard/Cancel. Cancel, interrupted
selection, read/format/allocation failure retain the old editing state. Commit
resets Undo, cursor, selection and viewport while preserving the clipboard.
The native title is bounded to 64 characters; the full path stays in TEXT.

The reader accepts uniform LF/CRLF, empty text and an absent final newline. It
rejects NUL, mixed/CR-only endings and logical lines beyond 1,023 bytes without
conversion. It returns to the outer event loop between 4 KiB reads. Relative
paths use the inherited current directory; invalid/extra launch arguments are
reported beside an empty editable document. No automatic binary mode, file
creation, Save, backup or persisted-byte claim is selected.


QE7's combined session uses the same ordinary APP and four-lifetime supervisor:

```sh
python3 tools/test_qed_documents.py --combined --output build/qed-editing/combined
```

QE1–QE7 pass the [editing development gate](../../../../docs/history/qed-editing.md#qe7-editing-gate-and-saving-handoff).
The combined session uses an 81,920-byte launch and twelve maximum-length lines
for interaction. It combines long tabbed text, selection/clipboard/Undo, literal Find/Next,
horizontal panning, peer overlap/exposure, cancelled and committed replacement,
and dirty Close/Stop decisions. State, document/caret/peer pixels and collection
are checked independently. New passive stack summaries resolve APP sites against
the captured Process image base; prior evidence keeps its original interpretation.

| Supported in the private development APP | Remaining acceptance work |
| --- | --- |
| One document; zero/one launch path; native selector Open and New | Multiple document windows and donor multi-file loading are deferred. |
| Byte text, uniform LF/CRLF, absent final newline, literal tabs; 1,023-byte logical lines | NUL, mixed/CR-only endings and wider lines are rejected; no conversion or Unicode decoding. |
| Fixed-font editing, navigation/panning, selection, internal clipboard, grouped toggling Undo | Printing, external fonts, macros, external clipboard and advanced block modes are deferred. |
| Native Find/Find Next and About; cancellable forms, selector and read preparation | Find is literal, case-sensitive and forward without wrap; replacement/regex search is deferred. |
| Save/Save As, checked staging/publication and one retained backup; Cancel-default Save/Discard/Cancel for replacement and retirement | Selected logical/transport failures and exact persisted bytes pass development checks; power-loss atomicity, concurrent same-target writers, autosave and automatic recovery are unsupported. |
| Selected ordinary-peer, failure, reuse and stack development checks | Practical workload responsiveness and supported QED distribution remain steps 6–7; QED is absent from demo ZIPs. |

## QW5 loaded-editor saving

The private development APP now enables full-document Save and Save As through
one event-owned native transaction. Existing destination and older-backup
replacement have separate Cancel-default consent. Recovery pages retain
D/T/B/E roles, causes and phases; dismissing a notice never means Saved.
Unresolved details require an explicit Forget before another save. This frees
the record, leaving files for manual recovery. Save preserves clipboard,
selection, view and Undo, and starts a new typing group. Busy mutations are
consumed before the document unfreezes; Close/Stop waits for a safe boundary.
The donor save/backup/restore implementation is retired from the selected graph.

See the [saving record](../../../../docs/history/qed-saving.md#qw5-loaded-editor-save-and-save-as)
for actual filesystem, error, stack and resource checks. New/Open/Exit still
use Discard/Cancel until QW6; strategy step 5 remains open through QW8.

## QW6 modified continuations

New, Open, Close, Quit and cooperative Stop use one Cancel-default
Save/Discard/Cancel decision. Only Saved continues the original action.
A retained Open parent/name survives Save As, then Open drops its earlier ring
and rereads that same canonical path. A failed reread keeps the saved clean
current document and its committed identity. New keeps its independent empty
candidate. A newer Close/Stop supersedes an older replacement after save work
stabilizes; a declined Stop leaves the Process live.

The [QW6 record](../../../../docs/history/qed-saving.md#qw6-savediscardcancel-continuations)
binds physical decisions, aliases, reread failure, supersession and resource
reuse. QW7–QW8 add operational failure closure and the reconciled saving gate.


## Saving gate and coexistence handoff

The [saving implementation record](../../../../docs/history/qed-saving.md#qw8-saving-gate-and-coexistence-handoff)
reconciles QW1–QW8 under C APP ABI 26. The combined editor checks use the same
selected production sources and a fixture that forwards successful operations:

```sh
python3 tools/test_qed_saving_gate.py --output build/qed-saving/combined \
  --native-from build/qed-saving/qw7-cleanup-stop-bounded
python3 tools/test_qed_fresh_reopen.py --output build/qed-saving/fresh-sdfs \
  --writer build/qed-saving/combined --filesystem sdfs --combined \
  --native-from build/qed-saving/qw8-fresh-mydos
```

The fresh reader mounts the exact closed writer ATR read-only with newly
started native services. It neither regenerates the volume nor substitutes its
APP, and verifies that the image hash remains unchanged. The separate
operational probes select consistent disposable volumes, actual physical
faults and foreground BREAK; reset-required outcomes are not normal OS return.
See the immutable records for exact commands, filesystems, inputs and limits.

Save serializes the whole document, preserves LF/CRLF and trailing newlines,
and checks terminal Close before publication. Existing D and B require separate
consent. The old D becomes B; failure retains confirmed recovery paths and both
causes. A new destination uses normal creation metadata. Hidden/Archive and
broader metadata preservation are not promised. Review/Forget releases only the
recovery record; it leaves disk files intact for manual handling.

The [step 6 workload gate](../../../../docs/history/qed-coexistence.md#qc4-reconciled-gate-and-delivery-handoff)
now passes measured responsiveness, fragmentation and retirement beside Counter
and a shell checksum command. The normal delivery build and final
source/notices gates are recorded in [delivery history](../../../../docs/history/qed-delivery.md).
Full release qualification and publication remain separate.

## Idle caret painting

Patch 0017 restores only the caret band during blinking, avoiding the visible
clear/redraw of the whole cursor row. The [development record](../../../../docs/history/qed-saving.md#idle-cursor-repaint-correction)
binds the updated production build and local preview. The focused emitted check
forwards real VDI calls, rejects row-wide caret requests, and verifies idle
pixels, selection and peer-window exposure:

```sh
python3 tools/test_qed_cursor.py --output build/qed-cursor/editor \
  --native-from build/qed-saving/qw7-cleanup-stop-bounded
```


## Practical workload development checks

The [coexistence design](../../../../docs/plans/gem4xe/qed-coexistence-design.md)
and [implementation history](../../../../docs/history/qed-coexistence.md) define
separate production baseline, Counter and shell-checksum cohorts within the
eight public Task slots. The production APP has no measurement interposition;
its observers use physical input and independently rendered completed frames.
A separate fixture supplies real allocation refusals and four repeated lifetimes.

```sh
python3 tools/test_qed_damage.py --output build/qed-coexist/damage-reproduced
python3 tools/test_qed_coexist_lifetime.py --output build/qed-coexist/lifetime-reproduced \
  --native-from build/qed-coexist/qc3-caption
python3 tools/test_qed_coexist.py --output build/qed-coexist/baseline-reproduced
python3 tools/test_qed_coexist_load.py --cohort peer --output build/qed-coexist/peer-reproduced
python3 tools/test_qed_coexist_load.py --cohort checksum --output build/qed-coexist/checksum-reproduced
```

Build current production sources through the normal demo builder before the
production cohorts. Their `--production`, `--bundle` and `--layout-from`
arguments select separate reproduced artifacts. The layout input is a fixture
compiled with matching headers; its emitted offsets describe the production
records without adding instrumentation to the shipped APP. Test disks are
disposable and separate from the interactive WORK disk.

Patches 0018–0026 bound same-row/selection damage, combine text and caret paints,
use existing opaque default-colour text, avoid duplicate scroll paints,
clear multi-row damage once before drawing unpadded text runs, and retain
plain screen cells for consecutive full-work navigation paints. Messages,
non-navigation input and partial/selected paints invalidate that snapshot.
Content painting completes before position/modified caption publication;
caption invalidation remains outside visible-rectangle iteration.
The actual-source damage probe covers 16 rectangle/slider-policy cases; full drawing
and independent pixels belong to the production and cursor checks. Bank-zero
reservations and shared Task capacities remain unchanged.


## Supported development delivery

[QD1–QD7](../../../../docs/history/qed-delivery.md#qd7-supported-development-delivery)
close the initial English single-document scope through the ordinary demo builder.
See the [current guide](../../../../docs/guides/qed-exec.md) for manual ZIP boot,
private local launch, persistent WORK, normal builds and source/relink use.
The boot ZIP and versioned source/relink archive have matching external checksums;
keep both when redistributing QED, which must remain free of charge.

The native adapters use the copyright holder's authorized MIT grant; generated
GEM declarations retain LGPL, and donor/runtime material retains its own terms.
The delivered APP/resource/provider match the measured QC4 production editor.
Fresh exact-ZIP checks cover both ordinary launch parents and persisted saves;
the complete original gap/scope reconciliation and limits are in the delivery record.
Full release/hosted/hardware qualification and cartridge publication remain separate.
