# Original MagiC MGVIEW port execution

[Plan](../plans/gem4xe/mgview-port-plan.md) · [GEM history](README.md) ·
[Source selection](../../ports/magic/mgview/README.md)

This is development work, not release qualification. The user requested minimal
testing: focused original-viewer/Counter checks, no release matrix and no routine
QED execution. The plan's larger acceptance inventory remains optional deeper
coverage, rather than a claim that every failure/timing case has run.

## MP1: first viewer

The pinned original MGVIEW, MGWIND and WINDOWS modules build as a disk-loaded
APP using the current argument/GEMDOS runtime. Pure C integer and event layouts,
rectangle calls, workstation/error helpers and the assembly scanner are adapted.
The common rectangle module now also serves QED; no APP/kernel ABI is added.
Loading publishes only fully allocated documents, terminates file data, supports
empty input and frees window records. Navigation initially uses full redraw.

The draw buffer uses 273 upper BSS bytes per image. Reserved bank-zero changes:
fixed 0, root 0, kernel 0, private idle 0 and every public Task 0, including
guards, alignment and unused reserved capacity.

Development checks: `build/mgview-dev/model-raw/results.json` and `model-opt/`
each pass 30 original-parser/callback/rectangle checks, with emitted WINDOW
layout 338 bytes and four-byte huge pointers. `build/mgview-dev/noinline-run.log` records the passing loaded run:
four loaded Process lifetimes (three MGVIEW, one Counter), 25 native
checks and exact 123,200/4,096-pixel populated/empty viewports. Quoted path,
physical Ctrl-U, no-argument exit, stop, heap restoration and stack/domain guards
are covered. The largest touched 1,312-byte public pool is 816 bytes in this
fixture; it leaves 240 untouched bytes above the 256-byte interrupt floor.

The inlining-enabled C build opened a blank viewport despite correct input,
index, metrics, UPDATE and visible enumeration. Temporary observations changed
that result. The clean optimized application passes with `--no-inline` applied
uniformly to its source units, matching QED's existing
[Calypsi 5.18 restriction](../plans/gem4xe/qed-editing-design.md#memory-stack-and-evidence).
No drawing-policy or actionc change accommodates that compiler issue. The
uninstrumented APP is 27,853 serialized bytes with a 66,786-byte loaded span
and 1,020 BSS bytes at this slice; these include ordinary runtime state.

## MP2: bounded loader and model lifetime

The private file/index ceilings are explicit. Original CR/CRLF scanning now
checks the declared end before looking at the following byte. The loader fixes
from MP1 retain single descriptor consumption and publication only after both
buffers exist; later failures cannot leave a dangling slot or count.

`build/mgview-dev/mp2-results.json` passes rejection of a 65,520-byte file and
16,381-line index through the original loader, dismissal of their real alerts,
no-argument exit, unchanged Counter and restored heap across all four loaded
lifetimes. The optimized original-parser probe passes 30 checks after the end
bounds change (`build/mgview-dev/model-mp2/results.json`). This small development
pass does not inject every allocation/short-read failure or exhaust capacity.
Reserved bank-zero deltas remain zero for fixed/root/kernel/idle and every Task.

## MP3: original copy/strip scrolling

Original `set_shift` now owns UPDATE from scroll/slider publication through
visible enumeration, mouse hide, S_ONLY screen copy, exposed-strip repaint and
truthful completion. MFDBs are initialized. Non-current source pixels or large
jumps use the existing model-redraw path. Each completed fragment is claimed
only after its copied/repainted content is reconstructed; failed claims retain
repaint fallback. Normal Task preemption and existing drawing limits remain.

`build/mgview-dev/smoke/results-scroll.json` passes six exact viewport checks:
initial, down/right/up, horizontal left gadget and empty document. The model
must reach each expected row/column; unchanged pixels cannot pass a navigation
step. Counter progress, Ctrl-U, no-argument exit, stop and heap/guard restoration
also pass. The pinned bridge has no physical PLUS key name, so the real left
GEM gadget supplies the reverse horizontal action. No timing, RPC or complete
occlusion/fault matrix is claimed by this minimal check. All reserved bank-zero
deltas remain zero, including each public Task.

## MP4: interaction and document ownership

Keyboard dispatch uses the accepted key's owning window, rather than a later
query of the current top window. Tab-width scans run outside UPDATE; publishing
new tab/column state and sliders uses UPDATE, followed by ordinary full redraw.
Ctrl-close retires all documents through the normal close path instead of direct
Pterm. Original move/size/full/previous, slider, digit and key callbacks remain.

`build/mgview-dev/smoke/results-interactions.json` passes two documents in one
registration, Ctrl-W routing, resize, move, full/previous restore, digit-5 tab
expansion, Ctrl-U/Ctrl-Q, empty/no-argument restart and stop beside Counter.
Seven exact completed viewport comparisons, four Process lifetimes, restored heap
and stack/domain ownership pass. The observer waits for UPDATE completion before
checking a repaint and uses the complete banked PC for fault detection. Physical
button tests wait for the pointer to reach its target before pressing.

This is the small interaction case, not a full capacity, occlusion, every-slider
endpoint or stop/fault injection matrix. Fixed/root/kernel/idle and each public
Task reserve zero additional bank-zero bytes.

## MP5: paired original-viewer baseline

`tools/test_mgview_pair.py` verifies the pinned MagiC disk/binaries, checks its
floppy and host document bytes agree, and makes an isolated reference run.
The same document is staged byte-for-byte for the current native APP. The
single-viewer option in the existing MagiC capture avoids running unrelated
applications. Exec reuses the small provider, loaded APP and Counter.

`build/mgview-dev/paired/results.json` passes original MGVIEW line down/up on
both machines. The 56,746-byte, 901-line document has SHA-256
`4e2b4c68e01f9d1fa52811a56536267ab19b90502051a4cba22b4cacddac4ee3`. MagiC passes exact old-row-two/new-row-one and
reverse correspondence; Exec passes complete model/pixel comparisons before,
after and back, plus empty/no-argument restart and Counter progress.

This is a functional baseline. MagiC uses its unchanged 8x16 monochrome font and
8 MHz 68000 without Counter; Exec uses 8x8 on the pinned 65816/VBXE with Counter.
No latency/CPU/RPC benchmark or speed ratio was run under the user's minimal
check scope. Quantitative normalization and the larger timing inventory remain
follow-up work. Source/compiler policy, drawing limits and all fixed/per-Task
bank-zero reservations are unchanged.

## MP6: delivery and narrowed build scope

The common APP/demo build includes original-source `MGVIEW.APP`, byte-preserved
ASCII `SYS:MGVIEW.TXT`, usage guidance and original MagiC licence/provenance.
The ordinary Text association and OF816/default startup behavior are retained.
The generated ZIP contains only boot images, short guides, licences and checksums.

The full demo and QED rebuild completed, which exceeded the user's requested
minimal development scope. QED was not executed. The cold ATR boot check was
interrupted when the user reiterated that builds and testing must stay minimal;
it does not establish native-entry or hosted qualification for this package.
Future ordinary MGVIEW iterations build only that APP and reuse the unchanged
Counter/provider. Full demo, QED and cold-boot runs are opt-in work.

Completed checks: 14 packaging host tests, committed donor byte/hash checks,
current generated QED declarations and local documentation links. The host-only
`build/gem-mgview/delivery/results.json` audit verifies all ZIP checksums,
16 current-ABI SYS APP headers, original MagiC notices, exact 6,862-byte sample
and packaged MGVIEW/Counter identity against the focused loaded checks.
It requires no QED build or execution. The tool defaults to host audit only;
`--cold-boot` is an explicit longer check.

Final MGVIEW is 29,521 serialized bytes; upper code is 25,399 bytes, initialized
data 270 and BSS 1,020, including the 273-byte draw scratch. Loaded span is
66,826 bytes, including its bank gap. The largest observed touched 1,312-byte
public pool is 884 bytes in the scroll fixture, leaving 172 bytes above the
256-byte interrupt floor. Reserved bank-zero changes remain **0 fixed, 0 root,
0 kernel, 0 private idle and 0 for every public Task**, including guards,
alignment and unused reserved capacity. No new Task or ABI operation was added.

Artifacts:

- `build/gem-mgview/demo/exec816-demo.zip`
- `build/gem-mgview/demo/launch-altirra.command`
- ZIP SHA-256: `8ac09519db970d0c2011beea80a404aed8ffa679fe5608ee54bfe381e9a89aa3`
- MGVIEW APP SHA-256: `432d17cb7a03ef402e109eabe4c1f1891e90c07cee60d85add2624ff453a83e5`

Run `RUN C:MGVIEW.APP SYS:MGVIEW.TXT`. The
[usage guide](../guides/mgview.md) lists controls, bounds and omitted protocols.
For a source-only iteration with unchanged ABI:

```sh
python3 tools/build_mgview.py --output build/mgview-dev/smoke/apps/mgview
python3 tools/test_mgview.py --output build/mgview-dev/smoke --reuse --scroll
```
