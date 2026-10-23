# QED supported delivery design

[GEM plans](README.md) · [Strategy](qed-port-strategy.md) ·
[Implementation plan](qed-delivery-implementation-plan.md) ·
[Initial scope](qed-scope-and-dependencies.md) ·
[Coexistence handoff](../../history/qed-coexistence.md#qc4-reconciled-gate-and-delivery-handoff)

Strategy step 7 delivers the agreed English, single-document QED through the
normal Exec816 demo build and ordinary Files and shell launch paths. A fresh
build must produce a self-contained boot package whose documented workflow,
source provenance and supported limits match its executable bytes.

This design starts from the passing
[QC4 development gate](../../development/qed-coexistence-qc4.json). Its scope is
delivery and reconciliation of the existing port. The
[QD1–QD7 implementation plan](qed-delivery-implementation-plan.md) derives the
executable work. [QD1–QD7 now pass](../../history/qed-delivery.md#qd7-supported-development-delivery)
at the supported development-delivery tier; full release qualification and
publication remain separate. Design-time grant questions below are resolved in
that record and the current licence map.

## Supported configuration and scope

Keep the step 6 native Exec implementation, pinned QED/cflib sources, ordered
patches, current C APP ABI/provider and compiler/runtime inputs. The donor
GEM4XE disk remains a comparison setup. Its executable and startup kit are not
runtime dependencies of this delivery.

| Area | Delivery contract |
| --- | --- |
| Machine | The QC4 AltirraSDL configuration: Atari 800XL, PAL, plain 65C816 at 8x, 64 KiB base RAM plus 63 high banks, VBXE FX 1.26 at D6xx with private 512 KiB VRAM, and ST Mouse on port 1. |
| OS and emulator | The exact ROM, emulator and configuration identities recorded by the candidate. Start from QC4 and the [GUI pin](../../../toolchain/altirra-gem-vdi.json); do not substitute another AltirraOS ROM or emulator and inherit its compatibility claims. |
| Boot and system media | OF816 with the standard five-second autoboot into the shell/desktop, read-only SDFS SYS in D1, optional read-only QED application disk in D2, and writable WORK in D8. Retain the normal shell/prime demo; QED starts on request. |
| Application | One ordinary loaded QED Process and one document, the adapted English resource, fixed font, existing editing/clipboard/Undo, literal Find/Find Next and checked saving/modified-document decisions. |
| Document storage | Writable RAM, MyDOS and SpartaDOS mounts remain in scope. SDFS system media is the delivered boot configuration; it does not narrow the supported document filesystems. |
| Capacity | Eight public Task slots and the current window/AES limits. QED may coexist with Counter or foreground shell checksum activity in the separately admitted QC4 cohorts. |

Keep BASIC, SIO patches, burst I/O and fast boot disabled as in the measured
configuration. The packaged guide must describe the high-memory/VBXE emulator
requirements and exact disk setup; booting an arbitrary stock emulator is not
the supported configuration. Physical hardware and other clock, video or
transport configurations require their own evidence.

The [initial scope](qed-scope-and-dependencies.md#initial-supported-scope) remains
authoritative. Preserve uniform LF/CRLF, tabs, empty text and absence of a final
newline through unchanged open/save. Unsupported text must be rejected before
destructive conversion. Publish the 1,023-byte line limit, native path and
selector limits, and memory-dependent document capacity from the current
implementation. A successfully exercised document size is an example, not a
guaranteed maximum. Allocation refusal must retain the editable document.

Multiple documents or QED instances, replacement/pattern search, external
clipboard exchange, printing/external fonts, QED preference persistence and the other
step 1 deferrals remain excluded. Checked backup/recovery does not promise
power-loss atomicity, autosave or safe concurrent writers to one destination.
Document RAM volatility and unavailable metadata according to the
[saving contract](qed-saving-design.md#filesystem-guarantees-and-limits).

## Normal build and reproducibility

Make QED an explicit supported selection of the GEM desktop build in
[`tools/build_demo.py`](../../../tools/build_demo.py). The ordinary builder
must prepare the pinned sources, build the current resident C provider, build
production QED and its adapted resource against that provider, populate media,
then generate OF816 and the ZIP. Reject incompatible build selections instead
of silently changing the requested machine or filesystem profile.

The preview's
[`prepare_qed_exec.py`](../../../tools/prepare_qed_exec.py) already checks source
patches, executable provenance, provider identity and media bytes. Move that
responsibility into reusable build/package helpers called by the normal
builder. A fresh checkout must not need historical saving/coexistence output
directories or an already prepared preview. Retire the preview-only assembly
path when the normal path covers it; keep one current packaging implementation.

Validate executable APP provenance and the matching provider/resource before
staging. Analysis images, interposed failure fixtures and unmatched ABI inputs
are not package inputs. Keep source pins in
[inputs.json](../../../ports/gem4xe/apps/qed/inputs.json), the compiler pin in
[actionc.json](../../../toolchain/actionc.json), and generated definitions under
their existing owners. No compiler refresh or ABI change is selected here.

Record source revision and dirty state, source/patch/resource hashes,
compiler/runtime identities, provider identity, machine profile and output
hashes in development manifests outside the boot ZIP. Reuse an existing APP or
native build only after these inputs match. Refresh must reject stale executable
inputs; updating a manifest cannot make an old executable current.

Two clean builds in separate output directories with identical frozen inputs
must produce identical runtime payloads and boot ZIP. Fix generated-media dates
and ordering as build inputs where needed. Absolute development paths and
measurement timestamps may remain in external reports; they must not affect
the runtime files. Reproduction requires the documented toolchain, not a copy
of another developer's build directory. Do not redistribute the compiler or
emulator as boot-package dependencies.

## Package contents and installation

| Location | Content and purpose |
| --- | --- |
| QED:QED.APP | The uninstrumented production APP; the normal C: assignment makes C:QED.APP available. |
| QED:QED.RSC | The matching adapted English resource. Preserve the current explicit SYS: lookup, independent of the document's directory. |
| SYS:README.TXT | Current desktop/QED usage and limits, consistent with the extracted package guide. |
| WORK:SAMPLE.TXT | A small disposable sample in the clean writable-media template. |
| Extracted package README.txt | Manual boot/mount instructions, Files and shell launch, controls, save/backup/recovery behavior, supported limits and notices. |

Use one authoritative source for shared guide text so the disk README and ZIP
README cannot describe different launch or saving behavior. The current
[preview guide source](../../qed-exec-distribution.txt) requires a delivery
revision: its primary instructions must work from the extracted ZIP. A local
launch script that is absent from the ZIP must not be a required first step.
Repository-only launcher convenience belongs in the [local guide](../../guides/qed-exec.md).

Continue distributing `exec816-demo.zip` through the standard builder. Its
explicit member list contains only boot files, system/work media, the pinned
ROM, a short user guide, required notices and `SHA256SUMS`. QED and its resource
are inside the system disk. Keep manifests, fixtures, traces, listings,
intermediates, private emulator settings and user disks outside this ZIP.
Independently audit the staged filesystem and extracted archive: names,
allocation, APP/resource bytes, allowed ZIP members and every checksum.

For a release package, add matching old/new Atarimax 8 Mbit CAR images and the
raw 1 MiB BIN alongside the matching XEX using
`tools/build_demo.py --cartridge-from`. Bind and boot-check these against the
same candidate and media; cartridge conversion must not silently rebuild a
different native payload. The normal five-second OF816 startup remains intact.

## Launch paths and ownership

Shell launch supports `RUN C:QED.APP` for an empty document and
`RUN C:QED.APP "WORK:SAMPLE.TXT"` for one document. Exercise native volume and
relative paths from a non-SYS current directory. Preserve the current argument
parser's bounded error reporting for extra or malformed arguments. A missing
or rejected document leaves a usable empty editor without writing a replacement.

The desktop's Files/folder path must launch QED.APP without arguments by
double-click and keyboard activation. For one-document launch, use the existing
desktop extension association mechanism, configured to C:QED.APP through the
ordinary DESKTOP.CFG path. Test that configuration on disposable WORK media and
document how to select it. Keep the default text-viewer association unless the
user explicitly changes it; no new Open With service or editor-specific kernel
launch operation is required. Respect the folder launcher's own path bound.

Shell RUN jobs remain shell-owned; folder launches remain desktop-owned. Closing
the launching folder must not terminate a desktop-owned QED. Quit and cooperative
Stop must use the existing Save/Discard/Cancel continuation and normal parent
collection. Cancel retains the document and application. Close QED before the
documented desktop EXIT sequence; do not add forced termination to make a test
finish. A full Task/window pool reports ordinary admission failure and releases
temporary ownership without enlarging the pools.

The explicit SYS: resource lookup must work from every supported launch path.
Missing or unreadable resource acquisition must fail boundedly, report the
startup problem and return ownership. Check resources when acquiring them;
retain the existing minimal-validation policy for subsequent live API use.

## Writable storage and upgrades

The packaged WORK image is always a clean template. Extracted-package users
mount a separate persistent writable copy; refreshes replace boot/system files
without replacing that copy. Development launch helpers use private emulator
settings and preserve the selected workspace across refreshes and relocation.
They must not edit the user's ordinary emulator configuration.

A changed template checksum must not silently switch an existing workspace to
a blank disk. Retain an explicit workspace selection independently of template
identity; create a copy only for a new workspace. Existing hash-named WORK
copies and the current local symlink remain valid selections. Any migration
must preserve the original disk and report the selected path, rather than
guessing among saved images. Check this host behavior with disposable disks.

All emitted acceptance tests use separate writable copies. Compare saved
document/backup bytes and filesystem allocation after closing the test image.
Never mount or modify the user's existing WORK for a build or test.

## Notices and source delivery

Build a component inventory from the actual retained link, source/patch ledger
and resource provenance. Preserve QED's donor NOTICE and author declarations,
including the no-fee redistribution condition; do not describe it as
unrestricted public domain or apply Exec's MIT grant to it. The original NOTICE
describes the donor binary: native provenance must identify the replaced
GEM4XE startup kit, adapted cflib and actual linked Calypsi/runtime components.

There is a concrete licensing question before supported distribution can close.
The [native QED adapter files](../../../ports/gem4xe/apps/qed/native/entry.c)
currently carry GPL-3.0-only notices, while the donor material retains its
no-fee terms. The [Exec application permission](../../../LICENSING.md#application-permission)
distinguishes independent applications using public interfaces from applications
incorporating GPL implementation code. Record the applicable grants for this
combined APP and resolve their compatibility explicitly. Changing an SPDX line
alone is not permission to relicense material. This design grants no new rights.

For retained LGPL cflib code, select accompanying corresponding library source,
modifications and the application source/object and build material needed to
relink a changed library, rather than relying on notices alone. The applicable
terms must also allow the user's modification and debugging of that combination;
see [LGPL 2.1 section 6](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.de.html).
Account for compiler-runtime redistribution terms when assembling relink
material. Provide versioned source/relink artifacts alongside the binary
download, with matching checksums, outside the small boot ZIP. Keep the
corresponding Exec sources/build scripts and required third-party notices
available under their own terms.

Update the repository licence map and shipped provenance to the resolved
component inventory. Verify that the supplied material can reconstruct/relink
the candidate with the documented toolchain. A local executable preview and
passing functional tests do not resolve distribution rights; an unresolved
grant or unavailable required source/relink material keeps delivery open.

## Scope reconciliation and validation

Reconcile every row of the step 1 scope and each relevant original gap against
current implementation and specific evidence. Distinguish an implemented
application adaptation from added general platform support. Keep the original
[gap assessment](qed-gap-analysis.md) and frozen records historical; add a
current reconciliation linking the authoritative contracts, supported behavior,
remaining exclusions and tests. Do not close a required behavior by moving it
into the deferred list.

| Evidence area | Required development result |
| --- | --- |
| Build/package | Two clean builds reproduce the candidate; APP/provider/resource agree; the exact extracted ZIP passes member, notice, checksum and filesystem audits. |
| Launch | Physical Files/folder and shell launch, each with zero or one document path, including inherited-directory/resource independence, parent collection and a rejected launch. |
| Complete editor | Production Open/Edit/Navigate/Select/Copy/Paste/Undo/Find/Save/Save As/reopen/Quit, with independent text/pixel and closed-image document/backup checks. Exercise Save/Discard/Cancel and Stop/Cancel on the delivered bytes. |
| Document formats/storage | Exact unchanged LF/CRLF, empty/no-final-newline/tab cases and non-destructive rejection; writable RAM, MyDOS and SpartaDOS documents, plus a read-only destination failure retaining the live document. |
| Coexistence/lifetime | Matched QC4 response, Counter/checksum progress, capacity refusal, heap/resource return and stack/guard evidence, retaining the original measured scope and limits. |
| Refresh | Private settings, clean templates and persistent workspace selection survive fresh preparation and refresh; prior saved bytes remain unchanged. |
| Source/notices | The actual component inventory, resolved grants and matching source/relink materials support the delivered binary. |

Use the [two-tier policy](../../contributing/testing.md). Ordinary implementation
slices run affected host checks and focused optimized emitted-code cases. Small
raw/optimized probes apply only if compiler-facing behavior changes. Reuse
prior evidence only for matching relevant inputs and its original scope. An
unchanged APP/provider may retain its QC4 measurements after packaging changes,
but the new exact ZIP still needs launch/save/return checks. Target-code,
provider or platform changes require affected editing/saving/coexistence
regressions before reuse; earlier compiler tests do not qualify the hosted system.

Record the candidate's code, provider, media, ROM/emulator, configuration,
observers, actual case counts and results together. Preserve interrupt/context,
DP, stack/domain guards and bounded completion. Prefer bounded checks without
large CPU traces unless a selected observation requires them. Historical
compressed logs may be restored for verification without changing their hashes.

## Memory budget and completion

The reservation target remains **0 fixed / 0 per-public-Task / 0 private idle
bank-zero bytes** of growth, including guards, alignment and unused capacity.
Keep the 2,560-byte QED stack admission, existing eight public Task slots and
current switching/IRQ/NMI protocol. No target worker or larger pool is selected.
Compare complete loading/runtime reservations against QC4 using the
[platform budget](../../reference/platform.md#bank-zero-memory-budget).
Report upper image/private backing and media capacity separately; any measured
departure needs an explicit budget decision and affected checks.

Step 7 closes when the normal reproducible build, extracted-package workflows,
persistent workspace behavior, complete scope reconciliation and source/notice
delivery all pass on one identified candidate. Publish current usage/build
instructions and a reconciled development record; remove obsolete preview
instructions while preserving historical evidence.

Supported development delivery and release qualification are distinct statuses.
When preparing a release or making a qualification claim, freeze the candidate
and run the applicable full qualification matrices, including the required
release boot forms. A design note, a local ZIP or the focused development
checks alone cannot mark that release qualified or published.


The delivery media revision requested after QD7 separates QED from the main
system: `qed.atr` carries APP/resource/notices, SYS stays generic, and WORK stays
private. The user mounts QED through the public MOUNT command; it is not a
required boot volume. The current guide and subsequent delivery history record
this revision; earlier QD1–QD7 hashes retain their original media layout.
