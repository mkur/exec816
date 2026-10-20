# QED resource and application startup design

[GEM plans](README.md) · [Strategy](qed-port-strategy.md) ·
[Initial scope](qed-scope-and-dependencies.md) ·
[Native foundation](../../history/qed-native-feasibility.md)

Status: implemented through QS1–QS5 with
[development evidence](../../history/qed-startup.md). This is strategy step 3. Its gate is the
actual loaded QED application acquiring its resource and menu, opening an empty
document window, processing redraw/close, and returning through normal Process
collection. Editing and saving retain their separate strategy gates.

## Resource adaptation

Generate a native English RSC and matching resource identifiers from the pinned
donor input. Keep the generator and adaptation decisions in this repository;
never modify the verified upstream cache. Record input/output hashes, retained
trees, identifier mappings and stripped decorations. Preserve source notices.

Replace the 126-object menu with a compact menu for About, New, Open, Save,
Save As, Close, Quit, Undo, Cut, Copy, Paste, Select All, Find, Find Next, Insert
and Overwrite. Keep the menu within the existing 33-object service ceiling and
640-pixel desktop. Remove references to discarded menu objects from state
updates and shortcut dispatch; aliases to unrelated objects are unacceptable.
The controls expose the agreed eventual scope; step 3 does not qualify their
editing/file workflows.

Retain VERSION, the menu, About, supplementary About, text/block information,
Find, its auxiliary dialog, strings and the window icon where retained source
paths require them. Preserve local indices within retained non-menu trees.
Flatten 3D/outlined/shadow decorations, remove unused bitmap decoration and
replace character-button decoration with ordinary buttons. Explicitly disable
deferred Find options. Touch-exit controls use the native release-based button
semantics. Resource geometry uses the native 8×8 cell, with dialogs constrained
to the usable screen; donor layout is not executable compatibility evidence.

Use bounded general resource capacities: 256 total objects, 16 trees and 64
objects per tree, depth eight. The larger per-tree limit accommodates the
52-object string table. Audit traversal, form/popup saved-state storage and
menu admission together. Saved state remains in upper-memory owners; the menu
service ceiling stays 33. No bank-zero array grows.

Add standard free-string access: R_STRING returns the selected char pointer;
R_FRSTR returns the address of its relocated pointer slot. Admit and relocate
the bounded free-string table once at load, checking extents and termination.
QED obtains alerts with R_STRING. Resource replacement remains transactional:
a rejected load or failed terminal Close preserves the prior resource.

## Workstation, drawing and input

CFLIB owns the sole virtual workstation. QED borrows it until every window and
resource borrower retires. Close it once through CFLIB, then detach AES and
return through QedRuntimeRun. Do not introduce another workstation, kernel
service or Task reserved for QED.

Adapt the retained renderer to the built-in fixed font. Use existing public
v_bar/v_gtext, clipping, visible rectangles and UPDATE ownership. Convert the
editor's top-based text coordinates to the native baseline explicitly. Cursor
and scrolling use redraw-based application operations instead of XOR or raster
copies. Remove proportional/italic/justified drawing paths with their deferred
features. Preserve actual text storage and editor/window callbacks; a replacement
demo window is not the startup gate.

Keep the native presenter-owned pointer visible. Remove donor cursor-shape and
hide/show requests from the adapted source rather than returning fabricated
success from missing bindings. Flattened objects need no 3D capability probes.
Use native window movement and the existing release-based input contract.
Any remaining analysis binding must have an explicit call-site adaptation or
real implementation; a nonreturning trap or successful no-op prevents an
executable build.

Expose graf_mkstate as a general AES snapshot operation if retained input paths
need it: copy the current pointer/button/qualifier sample under the existing
short synchronization guard, without consuming queued events or changing their
interest. Add named and AESPB bindings together. Add the ordinary C import and
bump/rebuild the one current C APP ABI when its import table changes. No private
address or context access is permitted from QED.

## Startup and retirement

Acquire AES, workstation, resource, menu, editor state and document in ownership
order. Record acquisition success and unwind in reverse order on every normal
operational failure. Preserve the first unhandled native cause across cleanup.
Check each required tree/string acquisition before publishing its borrowers.
Keep resources alive until windows and menu have retired.

Exercise the real main/event loop. Empty-document Close, Quit and cooperative
Stop must retire windows, menu, resource and workstation before ordinary return.
Repeat launch/collect/unload using normal Process admission. Inspect allocation,
signals, contexts, windows, menu, UPDATE depth and image references. Failure
injection belongs to development fixtures at acquisition boundaries, not a
production QED command or alternate launch protocol.

Build a real APP only after the complete selected graph links without analysis
bindings or marker. Keep the analysis rejection in the ordinary packer/media
tools. The executable builder records resource bytes, imports, source/runtime
hashes, legal-base relocation checks and the declared 2,560-byte stack requirement.

## Memory and executable evidence

Keep the step 2 private allowances (32 KiB code, 16 KiB data/BSS, 16 KiB container
metadata) and resident allowances (16 KiB code, 4 KiB tables, 16 KiB data/BSS)
relative to its frozen baseline. Report actual growth and remaining allowance;
an exceeded cap requires a revised fit decision before proceeding.

The 1,375-byte source bound and 768-byte continuation cap are conditional input,
not a measured GUI guarantee. Observe the real Process and physical stack pool
after emitted reservations and across native/library/GEM calls, with DP/lifetime
attribution. Require 128 bytes above the 256-byte interrupt floor in the admitted
2,560-byte pool. Reconcile changed source frames and indirect calls. Reopen the
fit decision if the continuation cap or pool budget fails; retain guard and
IRQ/NMI/context checks.

Target reserved bank-zero delta: **0 fixed, 0 per-public-Task, 0 private idle
bytes**, including guards, alignment and unused reserved capacity. Report upper
resource, form, application and provider storage separately in every slice.

Use development-tier host/generator checks and focused optimized emitted-code
resource, drawing, startup, rollback and reuse scenarios. Use small raw/optimized
probes for changed ABI/record/binding boundaries. Rebuild matched callers after
ABI changes. Refresh standard and GEM development packages with build_demo.py,
OF816 and pinned ROM/notices; preserve five-second standard shell/prime autoboot.
Run affected smokes on the exact ZIP. Keep private QED fixtures and reports out
of distribution; QED delivery remains strategy step 7.

## QS4 fixture and error policy refinement

Acquisition-failure wrappers exist only in the development APP. They fail the
application's AES initialization, workstation/resource acquisition, menu
publication and window create/open calls, forwarding every non-failing request
to the public binding. Process startup has already established the native AES
registration before QED's idempotent initialization call; this case tests QED's
unwind, not failure inside that earlier provider registration. Existing provider
and Process failure checks own that lower boundary. No production entry mode,
kernel hook or successful substitute binding is introduced. Missing/malformed
resource cases use the real DOS/resource loader. A separate fixture wrapper
refuses private allocator backing from a selected acquisition onward.

Startup failure returns a Process error and its original native cause rather
than attempting an alert before the application is ready. Ordinary editor
alerts become available when the first document is acquired. Private backing
allocation failure records ERROR_NO_FREE_STORE; cleanup preserves that cause.
The passive observer covers each failing Process lifetime and the normal Stop
paths. Controls are set only after ordinary image ownership, before entry, and
are omitted from the production APP.

Failed window-open rollback snapshots its cause before deleting the partial
document. Closing-position history publication is removed from the initial
native scope: retirement must not allocate a history node or query a default
directory for an unnamed document. This was exposed by the window-open failure
case, which otherwise replaced ERROR_NO_FREE_STORE with ERROR_NO_DEFAULT_DIR.

For the failure sweep, the supervisor copies the unchanged serialized APP from
SYS: to a normal RAM: file through public DOS Read/Write, then performs fresh
ProgramFile.Load/start/wait/unload cycles from that file. QED still reads its
resource from SYS:. This removes repeated serial transfer from the acquisition
failure sweep; the separate production cohort retains repeated disk APP loads.
The RAM file and temporary copy buffer are fixture-only upper-memory costs,
retired before fixture completion. Bank-zero reservations stay unchanged.
