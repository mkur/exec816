# QED supported delivery implementation plan

[GEM plans](README.md) · [Delivery design](qed-delivery-design.md) ·
[Strategy](qed-port-strategy.md) ·
[Coexistence handoff](../../history/qed-coexistence.md#qc4-reconciled-gate-and-delivery-handoff)

Implement strategy step 7 from the QC4 production editor. Build and validate the
supported package through the normal demo pipeline, preserve saved WORK, and
reconcile the agreed scope against current evidence. Each slice has a reviewable
result and commits after its selected development checks.

Status: [QD1 inventory passes](../../history/qed-delivery.md#qd1-component-and-scope-inventory);
[QD2 normal package passes](../../history/qed-delivery.md#qd2-normal-production-build-and-package);
[QD3 persistent WORK passes](../../history/qed-delivery.md#qd3-persistent-work-selection);
[QD4 launch paths pass](../../history/qed-delivery.md#qd4-ordinary-launch-parents-and-failures);
[QD5 functional gate passes](../../history/qed-delivery.md#qd5-editor-storage-and-matched-evidence);
[QD6 reproduction/source delivery passes](../../history/qed-delivery.md#qd6-reproducibility-grants-and-source-delivery).
[QD7 final delivery passes](../../history/qed-delivery.md#qd7-supported-development-delivery).
Strategy step 7 is complete at the supported development-delivery tier.
Full release qualification and publication are a separate phase.

| Slice | Completion result | Dependencies |
| --- | --- | --- |
| QD1 | Auditable component/input inventory and scope-to-evidence map, with distribution questions explicit | QC4 and the delivery design |
| QD2 | Normal GEM desktop builder produces and boots a checked production QED ZIP | QD1 inventory |
| QD3 | Explicit persistent WORK selection survives preparation, template changes and refresh | QD2 |
| QD4 | Extracted-package Files/folder and shell launch paths pass with normal ownership and bounded errors | QD2–QD3 |
| QD5 | Delivered editing, storage, decisions and relevant coexistence/lifetime checks pass | QD4 |
| QD6 | Two clean builds reproduce final runtime files; grants, notices and source/relink material are reconciled | QD1–QD5 |
| QD7 | One final candidate passes the delivery recorder and closes the supported development scope | QD1–QD6 |

QD1 may record unresolved grants while implementation and local testing proceed.
QD6 and QD7 cannot pass supported distribution with those questions unresolved.
This separates useful engineering progress from the delivery-completion decision.

## Rules for every slice

Keep the pinned QED/cflib inputs, current C APP ABI/provider, compiler/runtime,
ROM/emulator and QC4 PAL/8x/VBXE configuration. Preserve the standard five-second
OF816 startup. Use one current build/manifest interface and update its callers
and tests together. Keep historical artifacts and records unchanged; earlier
schema readers and reconstruction commands remain available through Git.

Implement donor changes through ordered patches and generated resource inputs.
Fix reusable GUI, DOS, loader or compiler defects in their owners with focused
regressions. No QED-specific kernel operation, private driver protocol, new
worker or capacity increase is selected.

Use fresh development directories under `build/qed-delivery/`. All writable
test media are disposable copies. Do not mount or modify the user's existing
WORK, replace existing local launch settings, or delete earlier evidence to
simulate a clean build. A separate checkout/output tree supplies that proof.
Retain compact summaries and use large CPU traces only where a selected
observation requires them.

Follow the [two-tier policy](../../contributing/testing.md): host checks for
changed build/launcher behavior, focused optimized emitted-code checks for
affected target behavior, and content/link checks for documentation. Add small
raw/optimized probes only for changed compiler-facing behavior. Do not run the
full qualification matrices after each slice.

Every result binds relevant source/patch/resource inputs, toolchain/runtime,
APP/provider, ROM/emulator/configuration, observer, ZIP and test-media hashes.
Report actual cases, ownership return, guards and bounded completion. Preserve
the [QC4 response limits](qed-coexistence-design.md#production-workflow-and-measurements)
and cohort admission rules. Reused results retain their original scope; a new
manifest must not relabel an old executable as current.

For each implementation slice report **0 fixed / 0 per-public-Task / 0 private
idle bank-zero bytes** of growth, including guards, alignment and unused
reserved capacity, unless an explicit measured design amendment changes that
target. Keep the eight public Task slots and 2,560-byte QED admission. Report
upper image/private backing and media usage separately.

## QD1 Inventory and delivery requirements

Extend the existing source/layout audit around
[`check_qed_baseline.py`](../../../tools/check_qed_baseline.py),
[`build_qed.py`](../../../tools/build_qed.py) and the retained link ledger.
Account for the application, adapted resource, selected cflib units, native
adapters, compiler/runtime objects, provider and boot components actually used.
Record each component's source identity, modifications, notices, applicable
grant and corresponding source/relink material. Do not copy the donor binary's
component description as though its startup kit were still linked.

Create a current reconciliation map from every step 1 scope row and relevant
original gap to its implementation, contract and evidence. Mark required work
still needing a delivered-package check separately from the original deferrals.
Include document/line/path/selector limits and configuration/capacity boundaries.
Older or unmatched ABI evidence cannot close a current requirement by itself.

Record the native adapters' GPL notices, donor no-fee terms and library/runtime
conditions identified in the design. Prepare a concrete file/owner inventory
for the compatibility decision. Do not infer permission to change licences from
the request to build or package QED. Keep unresolved grants machine-readable
and visible to the final delivery checker.

Completion checks:

- The inventory accounts for actual retained link units and the resource;
  each required scope row has an evidence reference or explicit remaining work.
- Host audit cases reject a changed source/patch/resource, mismatched provider
  or fixture/analysis APP. Missing component or grant information cannot yield
  a supported-delivery result.
- Current pins and QC4 identities remain unchanged. The audit identifies
  which prior cases can be reused and which need fresh candidate execution.

Commit the inventory/audit and initial reconciliation as QD1. An unresolved
rights entry remains an open delivery requirement, rather than stopping local
implementation of QD2–QD5.

## QD2 Normal build and production package

Add an explicit `--qed` selection to
[`build_demo.py`](../../../tools/build_demo.py) for the designed GEM desktop,
720 KiB SDFS system disk and 256-byte sectors. Reject incompatible combinations
before an expensive build. Preserve the existing non-QED demo selections.

Factor reusable QED preparation, validation, staging and notices out of
[`prepare_qed_exec.py`](../../../tools/prepare_qed_exec.py). The normal builder
must build the provider before QED, generate the matching resource, register
both as exact binary media inputs, then build media, OF816 and the ZIP. Remove
historical preview defaults and overlay assembly logic once current callers
use the normal path. A convenience entry point may call shared helpers; it
must not own another packaging implementation.

Remove incidental prerequisites such as `build_qed.py`'s fixed
`build/gem-vdi/upstream` header path. Obtain that input from the verified current
GUI preparation/provider chain, so no old research, saving or coexistence build
is needed. Use the normal source fetch/cache and documented tool prerequisites.

Introduce one normal QED manifest entry for APP/resource/provider and provenance.
Update the package, refresh and current observer consumers together, retiring
the preview-only marker. Preserve the frozen historical reports as records of
their original schema. Validate every reusable executable input before refresh.

Stage the design's SYS:C/QED.APP, SYS:QED.RSC and clean WORK sample. Generate
consistent disk/ZIP guides from shared authoritative text, with extracted-ZIP
manual boot instructions first. Retain notices and use an explicit ZIP member
list. Keep development manifests, settings, intermediates and test output outside
the ZIP. Use `tools/build_demo.py` for every OF816/package refresh.

The command introduced by this slice is:

```sh
python3 tools/build_demo.py --output build/qed-delivery/normal \
  --gem-desktop --qed --format sdfs --sector-bytes 256 --system-kib 720 \
  --mouse-profile mild --release-compiler
```

Completion checks:

- A fresh output builds without historical QED output directories; the APP is
  production code with the matching provider, generated resource and frame ledger.
- Host package tests reject stale/mismatched inputs and verify allowed members,
  required notices, checksums and absence of development/user files. Extend
  [`test_demo_package.py`](../../../tests/test_demo_package.py) for these boundaries.
- Independently audit system/work allocation and exact staged APP/resource/sample
  bytes. Check cartridge capacity without claiming a cartridge boot result.
- Cold-boot the exact extracted ZIP, observe the standard countdown, launch
  production QED through RUN, edit/save/quit and collect normally with intact
  guards and OS return. Reuse the existing package walkthrough's public paths.

Record complete native reservation deltas and package/media costs. Commit QD2.

## QD3 Persistent WORK and private launch settings

Extend [`launch_demo.py`](../../../tools/launch_demo.py) with explicit WORK
selection and a persisted workspace record independent of the template hash.
Create a writable copy only for a new workspace. Preparation and refresh must
reuse the recorded or explicitly supplied disk, even if the shipped template
changes. Keep the existing disk and report its selected path.

Adopt legacy hash-named copies or the current local symlink only through an
explicit selection or a known prior mount/selection record. Do not guess among
saved images or silently create a blank replacement when selection is broken.
Support relocation of a workspace together with its local files, while retaining
an explicitly external disk selection. Preserve the original disk throughout.

Move QED's deterministic private profile seed/launcher generation into the shared
normal build/launch path. Preserve normal emulator settings, profile isolation,
required hardware and argument quoting. The extracted boot ZIP continues to
work through its manual setup without these development-only helpers.

Completion checks:

- Extend [`test_qed_exec_launcher.py`](../../../tests/test_qed_exec_launcher.py)
  with saved bytes surviving repeated preparation, an altered template, refresh,
  relocation, paths with spaces and a selected legacy/symlink disk.
- Missing/ambiguous selections and an unwritable destination fail without
  overwriting a disk. The clean template and user's ordinary settings are unchanged.
- On disposable real media, save through QED, retire, prepare/refresh the setup
  and reopen the same bytes in a second normal loaded lifetime. Pair host path
  assertions with an independent audit of the closed image.

Commit QD3. These checks must not use the existing personal WORK disk.

## QD4 Files and shell launch paths

Extend [`test_qed_exec_setup.py`](../../../tools/test_qed_exec_setup.py) or its
shared delivery observer to select launch cases against the QD2 ZIP. Use physical
input and the uninstrumented production APP. Observe identity/completion through
public ownership records and matching target-emitted offsets; do not invoke
private application entry points to manufacture a launch.

| Launch case | Required behavior |
| --- | --- |
| Shell RUN, no argument | Empty document, ordinary QED Quit and shell JOBS collection. |
| Shell RUN, quoted native document path | Correct document bytes and canonical identity; Save/reopen/collection. |
| Shell RUN from a non-SYS directory, relative path | Resolve the document through the inherited directory while still loading SYS:QED.RSC. |
| Files/folder QED.APP activation | Double-click and keyboard activation open an empty editor. Closing the launching folder leaves desktop-owned QED running. |
| Files/folder document association | Load a documented DESKTOP.CFG association from disposable WORK and launch one document through C:QED.APP; preserve the unconfigured text-viewer default. |
| Rejected argument/document/startup acquisition | Bounded reporting and cleanup without writing a replacement or leaving a half-initialized owner. |

Cover malformed/extra arguments, a missing or unsupported document, and a
missing/unreadable resource. Resource-failure media are explicitly identified
diagnostic copies; they do not count as the healthy exact-package run. Fix any
demonstrated defect in its current owner and add the smallest affected regression.

Completion checks:

- Both launch parents retain their documented ownership and collect their own
  child. Repeat a lifecycle to demonstrate reuse; do not use shell JOBS to
  collect a desktop-owned child or start multiple QED instances.
- A launched document and its form/text pixels match independent expectations.
  Quitting/Stop follows the existing continuation, and Cancel retains a live editor.
- An extra launch at full capacity fails normally and restores temporary
  ownership. Respect the eight-Task/window budget and the shell's one RUN job.
- Each healthy case cold-boots the extracted candidate, exits normally and
  reports intact guards/context. No forced kill or debugger state mutation is
  substituted for application completion.

Record actual cases, media overrides and parent-specific cleanup. Commit QD4.

## QD5 Complete editor and storage gate

Exercise the delivered APP through Open/Edit/Navigate/selection, Cut/Copy/Paste,
grouped Undo, Find/Find Next, Save As, named Save/backup, reopen and Quit. Use
existing production pixel/text/form observers rather than a second editor model.
Extend current saving/continuation runners only where package selection or an
uncovered required behavior needs it.

Run unchanged-byte round trips for uniform LF/CRLF, tabs, empty text and no
final newline. Exercise the line bound and non-destructive unsupported-input
rejection. Use disposable writable RAM, MyDOS and SpartaDOS documents, with a
read-only destination failure retaining the live document. The delivered SDFS
system disk does not establish the other document-filesystem results.

Completion checks:

- Independently verify saved document/backup bytes, clean/dirty identity and
  closed-image allocation. New/Open/Close/Quit decisions exercise Save, Discard
  and Cancel as required by the scope map; cooperative Stop/Cancel resumes editing.
- Failed/declined writes retain the document and the existing recovery policy.
  Reuse matched QW operational-failure records for their original scope; rerun
  affected deeper cases if a target fix changes ownership or transport behavior.
- Cover peer overlap/exposure and progress with an admitted Counter, separately
  from foreground shell checksum activity. Keep production timing uninstrumented
  and retain QC4's limits; do not grow Task pools to combine these cohorts.
- Reconcile repeated use, allocation refusal, heap/resource restoration, source
  frame bounds, selected stack observations and guards with current admission.
  Reuse QC4 only where relevant APP/provider, platform and behavior inputs match.

Packaging-only changes with identical runtime bytes may reuse the original
coexistence measurements. Changed target/provider/runtime behavior needs its
affected QW/QC regressions. Record reused evidence separately from new execution;
do not restamp historical reports. Commit QD5 after the current requirement map
has no unexplained functional gap.

## QD6 Reproducibility and source delivery

Resolve the QD1 component/grant entries using the applicable recorded permissions.
Update source notices, LICENSING.md and native provenance only to reflect actual
grants. Do not assume that Exec's application permission relicenses GPL adapter
code or removes donor terms. An unresolved compatibility decision keeps this
slice's supported-distribution result incomplete while local testing continues.

Assemble versioned corresponding source and relink materials for the actual
candidate, including selected/modified cflib, application source/objects as
needed, ordered patches, resources and build/link instructions. Account for
runtime redistribution permissions. Include corresponding Exec sources/build
scripts and retain original notices. Keep these artifacts alongside the binary
delivery, outside the small boot ZIP, with external checksums binding them to
the candidate; avoid self-referential checksum dependencies.

Finalize guide/notice/provenance content before freezing the reproducibility
inputs. Build in two empty output directories, with one clean checkout proof
having only the documented toolchain and verified caches/source preparation.
Do not provide either build with a historical preview APP, provider or media.
Record a fixed media/build timestamp input where needed; canonicalize ordering
and exclude absolute development paths from runtime files.

Completion checks:

- Compare production APP/resource, native and OF816 XEX, system/work templates,
  ROM/notices/guides and boot ZIP byte for byte across the two builds. A runtime
  difference must be explained and fixed, not hidden by rewriting provenance.
- Rebuild/relink the application from the supplied materials with the documented
  toolchain. In a separate diagnostic copy, change a retained library routine,
  prove the replacement object enters the link, and boot a bounded QED workflow.
  That modified test APP is not substituted for the production candidate.
- Host audits reject missing source/relink material, an unresolved grant,
  incorrect component provenance or mismatched companion hashes. A notice-only
  boot ZIP does not satisfy the source/relink delivery requirement.
- If final notices/guides change ZIP/media bytes while runtime code stays
  identical, bind those differences explicitly. QD7 still runs the final exact
  package; target changes additionally refresh affected earlier gates.

Record source/artifact availability and the reproduction/relink results. Commit
QD6 only when both reproducibility and the supported-distribution requirements
pass. Keep any unresolved item explicit rather than claiming completion.

## QD7 Final reconciliation and supported delivery

Add a delivery recorder, for example `tools/record_qed_delivery.py`, and a current
history/development record following the repository's documentation organization.
The recorder must bind QD1–QD6 to one final candidate and reject stale runtime,
changed media/ZIP, missing scope rows, incomplete execution, unresolved grants
or absent required companion artifacts. Add focused host negative cases for
these failures, rather than checking only that JSON fields exist.

Run a final exact-extracted-ZIP session through both shell and Files/folder
parents. Include Save As, named Save with backup, reopen, required modified
decisions, normal collection and EXIT, with independent persisted-byte/allocation
and pixel checks. Bring QD4/QD5 results forward only after matching their relevant
inputs. A late package refresh needs this final exact-package check; a late
target change also needs the affected functional/coexistence cases.

Completion checks:

- The scope map closes every required behavior with current evidence and keeps
  the original exclusions explicit. Distinguish application adaptations from
  general platform support; retain the original gap assessment as historical.
- Actual configuration, case counts, source/APP/provider/observer/media hashes,
  reused evidence scope and runtime/guard/ownership results are recorded together.
- Native loading/runtime reservations, every Task/DP/stack/guard/alignment/slack
  reservation and upper/media costs agree with the budget decision. No presumed
  source bound or previous compiler test replaces current runtime evidence.
- Current build, package/local launch and save/recovery instructions describe
  this candidate. Update the strategy, relevant indexes and port README; remove
  obsolete preview instructions without changing frozen evidence.
- Host checks, affected generators and documentation/link checks pass. If these
  documentation edits change a packaged input, refresh and recheck the candidate
  before recording its final hashes.

Commit the reconciled record and documentation as QD7. Mark strategy step 7
complete at the supported development-delivery tier only when every required
gate passes. Otherwise name the remaining work and retain partial status.

## Release follow-up

When preparing a release or responding to an explicit qualification request,
freeze the final source/toolchain/platform/media/observer inputs and run the
complete applicable matrices from the testing policy. Add both old/new Atarimax
8 Mbit CAR images and the raw 1 MiB BIN using the builder's `--cartridge-from`
path with the matching source ZIP checksum. Verify unchanged XEX/media payloads,
checksums and actual cartridge boots against that candidate.

Record release qualification separately from QD7's development result; physical
hardware needs its own evidence. Release publication uses the matching boot
and source/relink artifacts only after those release requirements pass. Ordinary
QD1–QD7 execution does not automatically run that full matrix or publish a release.

Design/plan-only reserved bank-zero delta: **0 fixed / 0 per-public-Task /
0 private idle bytes**, including guards, alignment and unused capacity. These
documents change no executable, ABI, demo or runtime reservation.
