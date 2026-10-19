# QED initial scope and source dependencies

[GEM plans](README.md) · [Port strategy](qed-port-strategy.md) ·
[Gap analysis](qed-gap-analysis.md) ·
[Source inputs](../../../ports/gem4xe/apps/qed/inputs.json)

Step 1 fixes an English, single-document native editor and an explicit QED and
cflib source pair. Preserve the editor core, adapt its platform assumptions,
and extend reusable Exec interfaces only for behavior in this scope. The next
step is the native build and runtime feasibility work in the
[strategy](qed-port-strategy.md#prove-native-build-and-runtime-feasibility).

Status: scope and source baseline fixed on 2026-10-19. Verification covers
source identities, build-input selection and the dependency paths below.
Compilation, linking and execution of this pair on Exec remain step 2 work.

## Initial supported scope

| Area | Selected behavior |
| --- | --- |
| Launch and exit | One native QED Process, launched from Files or the shell, with zero or one document path. Normal close and cooperative Stop use the same modified-document decision and return through the Process wrapper. |
| Document ownership | One open document per QED Process. New or Open while a document is modified offers Save, Discard and Cancel before replacing it. Additional document windows and multiple simultaneous QED instances are outside the initial acceptance scope. |
| Text | Byte-oriented plain text using the existing fixed font. Support uniform LF and CRLF files, tabs, empty files and a final line without a newline. Preserve those properties through an unchanged open/save round trip. New documents use LF. Unicode, mixed line endings, CR-only files and binary editing are deferred; unsupported input must be reported before destructive conversion. |
| Editing | Character insertion and deletion, line breaks, keyboard navigation, access to long lines, mouse cursor placement, ordinary contiguous selection, Select All, Cut, Copy, Paste and the donor's existing undo behavior. Clipboard contents remain private to the application. |
| Search | Literal text Find and Find Next in the current document, with cancellation. Replacement, pattern matching, search histories and searching other files are deferred. Adapt the donor's combined search/replace dialog to this smaller scope. |
| Files | Open, Save and Save As on writable RAM, MyDOS and SpartaDOS mounts, including existing-file confirmation, checked backup/recovery behavior and final Close errors. Report read-only media and unavailable metadata honestly. Numeric document and line limits must follow the measured implementation and produce explicit errors. |
| Appearance and dialogs | English resource identities, a compact menu with every selected action reachable, the built-in fixed font, move/exposure/redraw, scrolling and the dialogs required for opening, finding, saving and closing. Other applications must remain usable during those dialogs. |
| Settings | Fixed initial defaults. Resource discovery is required; loading or saving legacy preferences, remembered windows, syntax files and printer configuration is deferred. No background autosave or configuration write on exit. |
| Coexistence | One QED instance beside the shell and another GEM application in a configuration fitting the shared Task and window capacity. Repeated use must return application allocations and owned resources. |

Use native Exec paths, including volume prefixes and relative paths, at the
application boundary. A GEMDOS compatibility function name does not imply a
drive-letter namespace, a separate OS personality or permission to truncate a
native pointer into a short file handle. The port must translate handles,
counts and errors deliberately. See the [DOS contract](../../reference/dos.md).

Printing and GDOS, external or proportional fonts, syntax highlighting, project
management, macros, column selection, file-management commands, accessory
integration, external help, desktop clipboard exchange and AV, OLGA, SE or MiNT
integration are deferred. Disable their entry points and automatic startup,
timer and exit paths together. Hiding a menu command alone does not remove a
dependency.

These are port targets, not a claim that the selected donor already implements
them with Exec semantics. In particular, the donor text loader replaces NUL
bytes with spaces, and the donor find dialog also exposes replacement.
[File source][qed-files], [find source][qed-find].

## Frozen source inputs

The machine-readable [input manifest](../../../ports/gem4xe/apps/qed/inputs.json)
is authoritative for revisions, tree identities, raw-byte SHA-256 hashes and
the donor compilation inventory. The
[source baseline guide](../../../ports/gem4xe/apps/qed/README.md) describes
restoring and checking those inputs without building an application.

| Input | Role in the Exec port |
| --- | --- |
| QED GEM4XE fork | The pinned editor sources, English resource and donor adaptation examples. All 37 editor C files and 41 headers remain in the source baseline. |
| FreeMiNT cflib | The explicitly selected source revision for rebuilding the library against Exec. Its root contains 141 C files; the donor exclusion rule selects 120 archive candidates and excludes 21. |
| QED donor shims | Three port C files and the two files in `gem4xe/cflib/`, already inside the QED pin. They are adaptation references, not another external cflib4xe dependency. |
| Existing Exec GUI and toolchain inputs | Keep the current Action!, Calypsi, AES and VDI inputs. The manifest records their existing pins and native build/profile hashes; no override or upstream GUI refresh is selected. |

The donor [build][qed-build] and [README][qed-readme] use an external cflib
checkout and GEM4XE SDK without fixing their revisions. Consequently, the
selected pair is reproducible for Exec development but does not reconstruct
the source combination behind the donor's historical test result. Source
checks confirm the expected cflib files and helper interfaces; they do not
establish binary compatibility or a successful link.

Keep the complete source baseline even for deferred modules. The recorded
120 cflib files are archive candidates, not a claim that all are needed at
runtime. Later explicit adaptations and link results determine the required
subset; record those changes rather than inferring that dead code will remove
every reference.

Use Exec's large-code/huge-data application profile and native Process startup.
The donor's large-data SDK, startup objects, GEMDOS transport, G4A packaging and
SDX test environment are not selected build dependencies. Its unsigned-character
and word-type assumptions remain inputs to the ABI review. The donor recommends
Calypsi 5.18.2 or later, while the existing Exec builder enforces its checked
5.18 profile; step 2 must establish whether the current toolchain suffices before
changing a pin. See the [C profile](../../reference/c-program-loading.md) and
[native builder](../../../tools/calypsi_build.py).

## Required dependency paths

QED filenames below are under `src/`; cflib filenames are at its repository
root. The donor's `select_file` is in `gem4xe/src/qed4xe.c`. The categories
identify the work needed; they do not prescribe new APIs or implementation
algorithms.

| Workflow and source path | Existing foundation | Required adaptation or reusable support |
| --- | --- | --- |
| Startup: QED `main.c` and `global.c`; cflib `appinit.c` and `vopnvwk.c` | Native Process entry, private application data and AES registration. | Adapt argument/resource discovery, platform/font enquiries and workstation ownership. Handle initialization failures through native cleanup. |
| Resources: QED `rsc.c` and `qed.h` | Existing resource loading, objects and editable forms. | Larger resource/tree handling and free-string access; preserve IDs while adapting unsupported decorations and removing deferred initialization. |
| Menus: QED `menu.c` and its resource | Application menus and existing window focus. | Fit the selected actions into the desktop geometry and supported menu representation; apply the same scope to keyboard dispatch. |
| Text and editing: QED `text.c`, `memory.c`, `edit.c` and `block.c` | Upper-memory allocation and private image data. | Preserve the editor core while adapting huge pointers, bank-contained allocations, allocation failure and explicit arena release. |
| Input and display: QED `event.c`, `ausgabe.c`, `global.c` and `window.c` | Keyboard/mouse events, windows, clipping, fixed-font text and bars. | Translate button/key semantics; supply real metrics/alignment or adapt their callers; implement visible cursor, selection and scrolling. Keep window messages flowing. |
| Find: QED `find.c`; cflib `mdopen.c`, `mddo.c` and `mdclose.c` | Editable dialogs, forms and event waits. | Adapt the combined find/replace UI and dialog lifetime to literal Find/Find Next without requiring replacement, history popups or global mouse ownership. |
| Open and Save As: QED `file.c`; donor `select_file` | Native file selector, Read/Write/Open/Close, locks and enumeration. | Provide a bounded GEMDOS/runtime translation over native paths and handles. Remove the donor selector's UPDATE ownership across its wait. |
| Saving: QED `save`, `save_as`, `save_datei`, `back_up` and `restore_back_up` in `file.c` | Writable filesystems, rename/delete and ordinary error reporting. | Check every mutation and final Close, preserve the modified document on failure, and define recovery for the actual filesystem guarantees. |
| Clipboard and undo: QED `clipbrd.c` | Application-private text storage. | Retain in-memory clipboard and undo initialization while bypassing disk scrap discovery, `scrp_*` calls and clipboard notifications. |
| Time, metadata and C runtime: QED `global.c`, `file.c`; cflib allocation/error paths | Native metadata, timer services, heap and locally linked C helpers. | Translate only needed `stat`/time and stdio behavior. Preserve unavailable metadata and errors; an unsupported timestamp must not masquerade as change detection. |
| Exit and failure: QED `menu.c` and `main.c`; cflib `appexit.c`, `appexitg.c` and `cfmalloc.c` | Process/AES/DOS teardown and image collection. | Replace board-style `exit` assumptions with owned cleanup and normal Process return, including early allocation failure; do not assume Process cleanup reclaims arbitrary heap blocks. |

The corresponding native contracts are [AES](../../reference/aes.md),
[VDI](../../reference/gem-vdi.md), [memory](../../reference/memory.md),
[file writes](../../reference/filesystem-writes.md) and
[Process entry](../../reference/c-program-loading.md#storage-and-entry-bridge).
Reusable compatibility support uses public Exec operations. No QED-specific
kernel operation or separate compiler ABI is selected.

## Startup and save constraints discovered now

QED `main` calls cflib `init_app`, then `init_colorpop`, then QED `init_global`.
Each reaches `open_vwork`; the color-popup workstation remains until
`exit_colorpop`. The initial scope excludes color settings, so its startup and
resource conversion must be removed together. The remaining cflib/editor
workstation relationship still needs a deliberate ownership design.
[Startup][qed-main], [cflib initialization][cf-init], [color popups][cf-color].

QED `init_resource` eagerly fetches trees for printing, projects and options,
then converts color objects to `G_USERDEF`. `init_all` also loads configuration
and syntax data and initializes clipboard and communication services. Scope
adaptations must address those calls explicitly, preserving the default state
needed by editing. They must not rely on hiding the deferred commands.
[Resource initialization][qed-rsc], [startup][qed-main].

The donor save path ignores backup/restore rename results and the final
`Fclose` result; `save_as` has a separate failure path that must be audited as
well. Native `Seek` returns the old position, rename does not replace an
existing destination, and final Close can fail after confirmed writes.
Short-handle tests such as `fd > 0` also require a real handle translation.
These are runtime and application dependencies to settle before trusted saving,
not reasons to broaden the kernel. [File source][qed-files],
[native file operations](../../reference/dos.md#files-and-directories).

Disabling configuration persistence does not by itself eliminate every stdio
or exit dependency. For example, cflib `cf_malloc` reports errors through
`form_alert` or `fprintf` and can call `exit`. Audit the retained error paths
when establishing the native runtime. [Allocation errors][cf-alloc].

## Notices to retain

Preserve the donor's [NOTICE][qed-notice], the author's declarations in
`dist/liesmich.txt` and `doc/qed-en.stg`, and file-specific notices. The donor
describes QED and the port files as public domain with an explicit restriction
on charging for redistribution; record that restriction rather than labeling
the material as unrestricted public domain or applying Exec's MIT grant.

cflib's source headers specify LGPL 2.1 or later. Keep its `COPYING.LIB`, source
and modification notices with later distribution work. The donor also carries
Apache/NuttX and compiler-runtime notices; final notices must describe what the
Exec binary actually incorporates. The donor GEM4XE SDK is not selected here.
[Donor notices][qed-notice], [cflib source notice][cf-init].

## Step 1 completion and next decision

The source check verifies both pinned commit/tree identities against upstream,
all 260 recorded donor-file hashes, the 37-file QED and 120-file cflib inventories,
all 21 cflib exclusions, and the English resource header and menu extent.
The manifest also records nine existing Exec input hashes. These are development
source/content checks; they provide no emitted-code or hosted-system result.

Proceed using the [native feasibility design](qed-native-feasibility-design.md)
and [QF1–QF6 implementation plan](qed-native-feasibility-implementation-plan.md).
The unresolved measured decisions are actual native image size,
the retained runtime/link dependency set, allocator and error-exit ownership,
stack requirements and any general Process admission change they require.
Resource/VDI designs and the complete save recovery protocol follow in their
respective strategy steps.

Reserved bank-zero change: **0 fixed, 0 per-Task, 0 private idle**, including
guards, alignment and unused capacity. No executable or demo is changed.

[qed-readme]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/gem4xe/README.md
[qed-build]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/gem4xe/Makefile
[qed-main]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/src/main.c
[qed-rsc]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/src/rsc.c
[qed-files]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/src/file.c
[qed-find]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/src/find.c
[qed-notice]: https://github.com/slaapliedje/qed-gem4xe/blob/454beb35fccd72c15a8494431f6637cd0cb553c7/gem4xe/NOTICE
[cf-init]: https://github.com/freemint/cflib/blob/ce57817c3f68c7d346d1081768505e81acaee807/appinit.c
[cf-color]: https://github.com/freemint/cflib/blob/ce57817c3f68c7d346d1081768505e81acaee807/colorpop.c
[cf-alloc]: https://github.com/freemint/cflib/blob/ce57817c3f68c7d346d1081768505e81acaee807/cfmalloc.c
