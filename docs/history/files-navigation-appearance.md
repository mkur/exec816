# Files navigation and appearance

[Current desktop contract](../reference/aes.md#small-gem-desktop) ·
[Implementation plan](../plans/gem4xe/files-navigation-appearance-plan.md) ·
[Development evidence](../development/files-navigation-appearance.json)

## FR1: distinct title gadgets

Close uses GEM font glyph 5; full/restore uses glyph 7. Existing borders,
hit areas and window geometry are unchanged. The linked resident C image
increases by 43 bytes. Fixed, per-Task and idle reserved bank-zero deltas are
all **zero**, including guards, alignment and unused capacity.

Development checks pass on the exact extracted OF816 ZIP: independent pixels
for active/inactive frames, full/restore, close and shell exposure, plus HELLO
and orderly EXIT with guards intact. The host suite passes 455 tests with four
existing skips. No compiler suite or release/hardware qualification runs.

The full-screen check exposed duplicate menu observations for the desktop and
its full-screen folder, which share one source tree. The oracle now counts
unique source trees. The walkthrough also uses bulk debug memory reads instead
of one bridge expression per word; target execution and pixel expectations are
unchanged.

## FR2: compact content and top summary

The default window now shows a 3×3 icon grid. The toolbar is removed and the
summary is fixed above the content. Parent uses File > Parent or Esc; roots
ignore Esc without repainting or scanning. Backspace does not navigate, and
Esc in a dialog only cancels the dialog. Refresh remains File > Refresh/Ctrl+L.

The exact packaged demo passes independent pixels for the new layout, icon/list
selection and focus, scrolling, resizing, full/restore and exposure, plus
Parent/Refresh input checks and orderly EXIT. Host checks pass 455 tests with
four existing skips. The Browser remains 4,039 upper-memory bytes; removing
two OBJECTs saves 48 heap bytes per folder (552 instead of 600). Fixed,
per-Task and idle reserved bank-zero deltas are all **zero**.

## FR3: virtual parent and upward selection

Subdirectories have a scrolling `..` item using the approved 32×16 artwork.
Display positions map to the existing snapshot; its 256 entries and 32-byte
bitmap are unchanged. Parent selection clears file membership, and file
operations and drag admission exclude it. Up reuses the existing edit buffer
to remember the child name, then selects and reveals it after a successful scan.
An unsuccessful scan does not change the path.

The optimized desktop passes the compact walkthrough with empty-directory
parent selection, refresh, Return/Esc/menu navigation, offscreen child reveal,
name/disk order, mutation exclusion and root omission. A separate real-directory
run passes 256 real entries plus parent, Select All, the final bitmap bit,
scrollbar access and list switching. Both complete EXIT with guards intact.
The host drag fixture also rejects the parent as a source and destination.
The final integration slice exercises actual disk copies and standalone Files.

The Browser grows by two upper-memory bytes to 4,041. O0/O2 emitted layout
probes pass; the host suite passes 455 tests with four existing skips. Fixed,
per-Task and idle reserved bank-zero deltas are all **zero**.

## FR4: colour file icons

Folders reuse the beige desktop icon. The four known GUI programs share their
desktop artwork; extensionless commands use a `>_` terminal, other `.APP`
programs a generic window, and data files the existing neutral page. A four-row
filename table and existing wildcard matcher select these stock assets without
reading executables. Per-cell descriptors retain paper labels and shared bitmap
pointers. Selection preserves artwork; no renderer, palette or resource-format
extension is added.

The packaged run passes independent pixel comparisons for every category,
selected/clipped/scrolled views, parent keyboard focus and double-click. Panel,
Calculator, Text and Counter each launch from Files and close normally. HELLO
and EXIT pass with guards intact. Host checks pass 455 tests and four skips.
The resource is 7,058 bytes. Fixed, per-Task and idle reserved bank-zero deltas
are all **zero**; Browser and OBJECT storage are unchanged from FR3.

## FR5: final integration and distribution

The final extracted ZIP passes actual file drops in both views, independent
readback of README.TXT, LONG.TXT and VIEW.TXT, overwrite cancellation and Counter
coexistence. Twelve idle and twelve loaded outline trials restore exact pixels.
The parent is rejected as both source and destination; Esc consumes a captured
file drag in a subdirectory, and a subsequent ordinary Esc navigates upward.

Standalone Files passes independent selection, list view, resizing, parent
navigation and upward child selection. Its before/after heap totals and ownership
ledger match exactly. Both final runs complete orderly EXIT with guards intact.
The selected development checks observe at least 156 bytes of ordinary-Task
headroom and 121 idle bytes above the guarded floor. No stacks or DPs grow.
The final host suite passes 455 tests with four existing skips.

| Final storage | Bytes | Change from the committed compact Files baseline |
| --- | ---: | ---: |
| Desktop APP file | 70,829 | +2,591 |
| Files APP file | 48,948 | +2,570 |
| DESKTOP.RSC | 7,058 | +786 |
| Browser record | 4,041 | +2 |
| Folder OBJECT pool | 552 | −48 |

The selection bitmap, 256-entry capacity, Desktop record, file job and 16 KiB
copy buffer are unchanged. Every slice has **0 fixed, 0 per-Task and 0 idle
reserved bank-zero bytes** of change, counting guards, alignment and unused
capacity. No renderer, public ABI, VRAM reservation, Task, signal or timer is added.

Packaging uses `tools/build_demo.py`, retains OF816 and five-second autoboot,
the pinned ROM, system/WORK disks, guide, notices and checksums. The resident is
rebuilt for FR1 and reused unchanged afterward; its boot banner identifies that
resident build. Files, Desktop and their resource match the final implementation.
The recorded compiler pin is unchanged, with an optimized host compiler at the
same revision. These are development checks, not a compiler qualification suite
or release/hardware qualification.

The 602,771-byte ZIP contains 23 distribution files and no build intermediates
or test output. The [evidence](../development/files-navigation-appearance.json)
records its checksum, exact inputs and execution scope. Development artifacts
remain under `build/files-refinement/`; the user package is
`build/files-refinement/distribution/exec816-demo.zip`. Launch with:

```sh
./build/files-refinement/distribution/launch-altirra.command
```
