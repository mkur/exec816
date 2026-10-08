# GEM4XE calculator port implementation plan

[Plans](../README.md) · [Loadable GEM applications](loadable-gem-applications-implementation-plan.md) ·
[AES contract](../../reference/aes.md) · [C application profile](../../reference/c-program-loading.md)

Status: CAL1 implemented and checked at the development tier; CAL2–CAL4 pending.
Commit each passing executable slice. Reuse the established LG6 baseline; no separate
baseline slice is needed.

[CAL1 evidence](../../development/calculator-cal1.json): raw/optimized TEDINFO
layout and cross-bank access/measurement, 41 optimized object checks, three
independent text pixel comparisons and all 22 retained-widget pixel stages pass.
Fixed, per-public-Task and private-idle bank-zero deltas are all zero.

## Outcome

Ship the GEM4XE integer calculator as `C:CALC.APP`, with `SYS:CALC.RSC` on the
system disk. Launch it from Files or with `RUN C:CALC.APP`. It has an ordinary
movable, closable GEM window and runs beside the counter and shell.

Preserve the donor's arithmetic, object IDs, keypad layout and resource-owned
display buffer. Adapt its modal dialog loop to the existing windowed AES
subset. Add reusable noneditable TEDINFO text support to AES; keep calculator
code and state in its private loaded image.

The standard desktop already occupies all four layers. Close Panel before
launching Calculator from Files. Do not add Calculator to startup or enlarge
the Task, layer or AES-registration pools. The default OF816 shell/prime demo
and its five-second countdown remain unchanged.

## Inspected source and compatibility boundary

The source reviewed in `~/atari/gem4xe` is revision
`fbfea9b0b1233a5d659d5ec583c63f863cceadfa`:

| Donor file | Use in this port |
| --- | --- |
| `src/apps/calc.c` | Keep arithmetic, formatting and object-action dispatch; adapt pointer representation, resource path and event loop. |
| `src/apps/calcapp.c` | Adapt ordinary `main()` and resource/workstation cleanup to Exec Process ownership. |
| `tools/calcrsc.py` | Generate the same 21-object tree and C object-ID header. |
| `tools/rsc.py` and required host helpers | Generate the classic big-endian resource outside the donor checkout. |
| `tests/emu/m22_apps.py`, `docs/phase28.md` | Reference calculator behavior and the historical inaccessible bottom-row regression. |

Record revision, file hashes, notices and adaptation patches under
`ports/gem4xe/apps/calculator/`. Follow the existing extraction convention;
fetch/copy pinned inputs and generate outputs under `build/`, never inside
`~/atari/gem4xe`. Preserve the donor application licence and notices; this is
not an Exec-authored MIT example. Include its provenance in packaging.

The existing AES/VDI extraction is pinned separately by
[the GUI inputs](../../../ports/gem4xe/inputs.json) and
[the AES inputs](../../../ports/gem4xe/aes/inputs.json). Keep those pins while
adding the calculator source pin. Do not turn this port into an upstream GUI
refresh. No compiler-pin change is expected; any demonstrated compiler defect
needs an upstream fix and focused regression before changing the pin.

The donor builds a different executable/ABI profile. Recompile with the current
Exec Calypsi large-code/huge-data builder and normal `int main(void)` entry;
do not load its PRG/G4A file or import its GEMDOS/call-gate runtime.

## Selected behavior

### Arithmetic and interaction

Keep the actual donor semantics: whole numbers in the symmetric range
`-2147483647..2147483647`, division truncating toward zero, and eleven display
positions plus NUL. Excess digit entry, arithmetic overflow and division by
zero leave the displayed value unchanged. Preserve the subsequent operator
and `fresh` transitions as well as the visible result. The donor's opening
comment describes a remainder feature that its implementation does not have;
do not advertise or invent one in this port.

Use one object-action routine for accepted mouse and keyboard activation.
Support the existing keys, Tab/Shift-Tab focus, Space activation and Return
for the default equals button. Map digits, `+`, `-`, `*`, `/`, `=` and `C`/`c`
to their existing objects; `-` remains subtraction and sign change remains
the `+/-` button. Escape cancels an armed press. Quit and `WM_CLOSED` return
through the same cleanup path.

Reuse the Control Panel's small `evnt_multi` press/release/cancel pattern.
Handle redraw, move, top and close messages while waiting for input; cancel
an armed gesture on input loss or window movement. Do not hold an update lock
across an event wait. No timer, polling loop or additional worker is needed.

The donor root is 23 by 20 character cells, currently 184 by 160 pixels. Derive
the window border with `wind_calc` and position the resource in the work area.
Keep every key, especially the bottom-row equals and Quit buttons, inside
that area. Paint only affected buttons/focus marks and the display on input;
use a clipped tree redraw for `WM_REDRAW`. Do not repaint the whole form for
each digit. Arithmetic multiply/divide operations occur once per user action;
optimizing them is outside this port.

### AES additions

Expose the standard packed, 28-byte `TEDINFO` record and the noneditable
`G_TEXT`/`G_BOXTEXT` object types. Keep the existing 24-byte `OBJECT` layout and
flat 32-bit `ob_spec` address representation. Preserve complete huge pointers
through `ob_spec`, TEDINFO and text access; remove the donor's `.index` union
access in the source adapter.

Render system-font text with left/center/right justification, the TED color
word and signed border thickness. Reuse the extracted GEM4XE text/box logic
and current VDI primitives. Restore only the needed drawing branches and
helpers through the extraction selection/patches. Do not restore donor
bank-zero string buffers or near-pointer casts. Include outward border pixels
in object culling and damage bounds; the calculator display uses thickness
`-1`.

Extend the existing resource allocation and in-place fixup to TEDINFO records.
Validate supported file extents and offsets once before publication, convert
big-endian fields, and relocate each TED record once even when objects share
it. Normalize `te_txtlen` and `te_tmplen` from the bounded NUL-terminated
strings: the donor generator deliberately writes zero length fields. The
calculator's initial eleven spaces provide its twelve-byte writable buffer.
Keep strings within the existing 63-character bound. Preserve the existing
resource on failed replacement and free the one owned allocation normally.

Generate a flat resource by explicitly disabling `look3d` in the adapted
generator; retain geometry, labels and IDs. Do not silently accept unsupported
3D flags. Editable/formatted text, `objc_edit`, modal `form_do`/`form_dial`,
desk accessories, icons and general resource editing remain outside scope.

The calculator needs no new function import or AES opcode. Keep the current
import ABI and rebuild the matching provider/apps. Valid application trees,
pointers and text updates remain caller responsibilities; add no recurring
tree, pointer or buffer audit to drawing or input dispatch.

## Executable slices

### CAL1 — Draw application-owned TEDINFO text

Change `c/include/gem/objects.h`, the hosted AES declarations and extraction
patches/selections under `ports/gem4xe/aes/`, and `c/calypsi/aes-objects.c`.
Add only the text helpers needed by the two supported types. Cover both the
application-owned and retained widget builds that consume this extraction.

Gate:

- A small emitted layout/access probe confirms TEDINFO size/offsets, unchanged
  OBJECT layout and full upper-memory text pointers in raw and optimized modes.
- An optimized compiled-tree fixture draws left/center/right text, positive
  and negative numbers, a boxed display and its outward border. Changing a
  long value to a short one clears old glyphs; partial clipping/exposure repairs
  the correct pixels. Include an upper-memory bank-crossing text case.
- Existing button/focus rendering still passes. Record drawing stack use and
  keep display ownership, update-lock and stack/domain checks intact.

Update the AES reference with the supported record/objects and explicit text
editing exclusions. Commit the passing rendering slice.

### CAL2 — Load the calculator's classic resource

Add pinned calculator/resource inputs and the small reproducible extraction
and generation step. Produce `CALC.RSC` and `calcrsc.h` from one adapted donor
description. Extend `c/calypsi/aes-resource.c` to admit and fix TEDINFO.
Keep `R_TREE` sufficient for this app; no extra address-query API is needed.

Gate:

- Host checks confirm 21 objects, one TEDINFO, the original IDs, flat flags,
  and all key bounds within the root, including equals and Quit.
- Extend `tests/programs/aes_resources.c` and its optimized runner to load the
  generated resource, check upper-memory pointers and normalized lengths,
  update the display buffer and draw it through CAL1 on SDFS and MyDOS.
- Focused cases cover a shared TEDINFO, truncated table/string, invalid TED
  offset and failed replacement. Repeated load/free and automatic AES cleanup
  restore ownership without leaking the previous resource.

Update the resource contract and donor provenance/licence mapping. Commit the
passing loader/resource slice; it must work before Calculator depends on it.

### CAL3 — Run the port as CALC.APP

Apply the bounded source adaptations described above and build with
`tools/build_c_program.py`. Keep the arithmetic helpers and action switch
recognizable against the donor. Use `SYS:CALC.RSC` explicitly, so Files or
shell working directories do not determine whether the resource is found.

Give each loaded image its own calculator globals, resource and workstation.
Open a `NAME | CLOSER | MOVER` window and use the public GEM calls throughout.
Normal and partial-startup exits close acquired resources and return a Process
result. Leave DOS detach and final Process retirement to the established C
startup wrapper. Cooperative Stop is handled as `WM_CLOSED`.

Gate:

- The normal APP builder verifies relocation at every legal bank base. Run
  optimized machine-code arithmetic cases: clear/entry, `7*6=42`, chained
  operations, sign change, `7/3=2`, `-7/3=-2`, zero, excess entry, both range
  boundaries, overflow and divide-by-zero followed by recovery. Expected
  results must include state transitions, not just display formatting.
- Physical clicks and keys operate the window while the counter and shell
  remain usable. Verify equals/Quit using actual bottom-row coordinates;
  matching a renderer oracle alone did not catch the donor's old geometry bug.
- Check press/release cancellation, focus changes, overlap/exposure, dragging
  and close while a key is armed. Changed-object redraws must not erase another
  window or leave old display digits behind.
- Measure stack high-water through loading, drawing, arithmetic and teardown
  with normal interrupt activity. Use the existing stack pools and reserve;
  move avoidable application temporaries to private upper data if necessary.
  Do not silently enlarge bank-zero pools or remove guards to make it pass.

Commit the independently executable calculator before demo integration.

### CAL4 — Package and prove desktop lifetime

Add the app/resource to `tools/build_gem_desktop.py` and `tools/build_demo.py`
media/provenance handling, keeping the existing three-app startup list.
Extend the shared-image exclusion checks to calculator bodies/state. Reuse
loaded-symbol resolution and physical interaction helpers from the current
desktop tests; add a focused calculator walkthrough rather than a new harness.

Gate:

- Close Panel, launch Calculator from Files, perform a calculation, Stop it,
  collect and relaunch. Also launch with `RUN C:CALC.APP` and collect after
  window close while the shell is idle. Confirm fresh display/state on reload.
- With capacity made available, run two independently loaded calculators
  from the existing Files and shell owners; prove separate display/resource
  state and heap restoration after both are collected. Do not add pool slots.
- Missing/bad `CALC.RSC`, unavailable window capacity and an early close leave
  no orphan Process, image, workstation or resource. Files/session exit with
  Calculator alive follows the existing cooperative child-shutdown path.
- Build the OF816 GUI demo through `tools/build_demo.py`. Run the calculator
  walkthrough from the extracted ZIP on the pinned emulator/ROM, check both
  packaged Atarimax variants for cold boot, and retain the default OF816
  shell/prime boot smoke. Record exact artifacts and actual execution scope.
- Keep calculator code/state out of the cartridge/shared component; report
  the remaining XEX cartridge capacity against LG6 and retain its at-least
  32 KiB headroom objective. Ship APP/RSC and required notices on the matching
  disk, with only boot assets, guide, notices and checksums in the demo ZIP.

Update the application guide, current AES/resource contracts and plan status.
Store measurements in `docs/development/` and an implementation record under
`docs/history/`, updating their indexes. Commit the passing integrated slice.

## Budgets and validation policy

Use [LG6 evidence](../../development/loadable-gem-lg6.json) for the established
capacity and coexistence baseline. It records 56,444 bytes of cartridge
headroom and a narrowest measured public-Task stack margin of 54 bytes above
the interrupt reserve. That margin is not a calculator stack qualification;
CAL1/CAL3 must measure the added call paths early.

Every slice targets **zero additional reserved bank-zero bytes**: fixed 0,
per-public-Task 0, private idle 0, including guards, padding and unused capacity.
Calculator uses a slot from the existing pools. Report actual upper-memory
costs separately: shared text support, APP serialized size/span, allocator
rounding and alignment waste, resource storage and transient loading storage.
Account for the existing `span + 65535` image backing reservation, not just
the calculator's small file size.

Use the [development tier](../../contributing/testing.md): host checks and
affected generators, focused optimized execution, and small raw/optimized
probes for changed record or compiler-facing behavior. Do not duplicate the
full desktop suite in raw mode or rerun unrelated qualification matrices.
Record a bounded input-to-visible-feedback sample and check for new whole-form
flicker; this port does not reopen HY4/PI4 latency optimization or claim hardware
qualification.
