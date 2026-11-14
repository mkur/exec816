# GEM mouse calls

[GEM plans](README.md) · [AES contract](../../reference/aes.md) ·
[VDI contract](../../reference/gem-vdi.md) ·
[Display ownership](../../reference/display.md) ·
[MGVIEW foundations](mgview-foundation-plan.md)

Status: proposed, 2026-11-14. Deliver GM1–GM5 as executable slices, committing
each after its development checks pass. This plan adds shared SDK services;
MGVIEW itself remains a separate application port. Current contracts continue
to describe the implemented system until each slice lands.

## Public surface

Use conventional GEM declarations and parameter blocks. Add the functions to
`<gem.h>` and the loaded C provider as they become executable; do not add
application-specific replacements or success-returning stubs.

| Interface | Behavior and parameter block |
| --- | --- |
| `graf_mouse(mode, form)` | AES 78: one integer input, one integer result, one address input. Nonzero success, zero failure. |
| `graf_mkstate(x,y,buttons,qualifiers)` | Existing AES 79; retain coherent observation without consuming events. |
| `vsc_form(handle, form)` | VDI 111: 37 integer inputs, no point inputs or outputs. |
| `v_show_c(handle, reset)` | VDI 122: one integer input. Zero forces visible; any nonzero value balances one hide. |
| `v_hide_c(handle)` | VDI 123: no inputs or outputs. Add one hide. |
| `vq_mouse(handle, buttons,x,y)` | VDI 124: one integer result and one point result; no inputs. |

Publish `MFORM` with conventional field names: five WORDs for `mf_xhot`,
`mf_yhot`, `mf_nplanes`, `mf_bg`, `mf_fg`, then sixteen WORDs each for
`mf_mask` and `mf_data`. Size is 74 bytes. Mask/data words are interpreted as
unsigned bit patterns, with bit 15 at the left. Use the customary typed MFORM
pointer for `graf_mouse` and word-array interface for `vsc_form`.

Support the eight standard forms: ARROW, TEXT_CRSR, HOURGLASS/BUSYBEE/BUSY_BEE,
POINT_HAND, FLAT_HAND, THIN_CROSS, THICK_CROSS and OUTLN_CROSS. Add USER_DEF,
M_OFF, M_ON, M_SAVE, M_RESTORE, M_PREVIOUS and the AES M_FORCE flag. Numeric
values, layouts and call counts belong in machine-readable ABI inputs and
generated definitions. Ordinary and parameter-block calls share helpers.

`graf_mouse` requires an AES registration, but no window, VDI workstation or
UPDATE acquisition. VDI calls use the current supported screen-workstation
contract. Opening/closing a virtual workstation does not reset the physical
mouse or another application's state. Queries return the logical pointer
position, not the form's top-left corner, including while hidden or inactive.

USER_DEF initially admits one plane, hotspots 0..15 and logical pens 0..15,
matching the display profile. Copy all 37 words before any wait or publication;
retain no application form pointer after return. Null is ignored for modes
that do not use a form. Report unsupported formats/modes without mutation.
Geneva animations/extensions, locator request/sample APIs, vector callbacks,
pointer warping and interactive graf drag/rubber/slide boxes are outside this
plan. Do not advertise their support through capability queries.

## Reuse and provenance

Select GEM4XE 0.17, revision
`ac476b8bdeda63b8b53ad22ec25b9d88bd7886af`, inspected for this plan. Keep this
component's pin separate from the existing VDI/raster and reference-media pins.
GM1 records exact input hashes and extraction selections under
`ports/gem4xe/mouse/`; preserve GEM4XE and EmuTOS file notices and artwork
provenance. Keep copied implementation/artwork there, with public Exec-authored
declarations under the existing MIT interface licence.

| Donor | Reusable material | Exec adaptation |
| --- | --- | --- |
| `tools/gemdata.py` | Eight 37-word MFORMs, transcribed from EmuTOS. | Reproducible selection into upper read-only storage; update the current arrow pixel oracle together. |
| `src/aes/grlib.c:gr_mouse` | Mode dispatch, USER_DEF and saved/previous operations. | Per-registration state and shared native policy. Reject unsupported modes explicitly. |
| `src/aes/graf.c:gsx_mfset/mfget/mfsave` | Form copy/history and replacement while stationary. | Upper-RAM records, no far allocator or shared global parameter arrays. |
| `src/vdi/vdi.c` | MFORM interpretation, nested hide/show and state query. | One coherent policy for the public AES/VDI calls, using existing captured input. |
| `src/vdi/dev_vbxe.c` | Foreground/background mask packing, parity strips, hotspot/clipped save/paint geometry. | Existing Exec pen mapping, VRAM layout, fences, overlays and display grants. |
| `src/app/gem.h`, `gemlib.c` | Names, constants, signatures and call counts. | Independently written native bindings; no Atari trap/runtime import. |

Do not import donor mouse polling, hardware input capture, cooperative
scheduling, startup or the device driver. Existing INPUT capture, DESKMOUSE
acceleration, event routing and physical completion remain authoritative.
GEM4XE's AES and VDI hide counters must not be copied as independent counters:
forced VDI show can otherwise leave AES bookkeeping out of sync. Its global
form slots also need adaptation for independent Exec applications. The pinned
MagiC [`AESMAIN.S`](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7164-7283)
provides the complementary model: application current,
previous and saved forms, local hide bookkeeping, and installation for the
current mouse recipient.

## Logical state and ownership

Keep these responsibilities separate:

- AES owns one cursor-policy record per registration in upper RAM. It contains
  current/previous/saved forms as each feature lands and the application's hide
  depth. The C binding does not maintain a competing copy of policy state.
- A shared policy record selects the visible form and tracks global logical
  visibility and a revision. Use existing pointer recipient, capture and MCTRL
  ownership; keyboard focus alone does not select the form. Frame/menu handling
  can select the system arrow without overwriting an application's saved forms.
- The backend owns only installed masks, clipped save geometry and physical
  drawn/erased state. Its temporary erasure around drawing is independent of
  the GEM hide count.

Normal form changes update the calling application's history. Install them
when it is the mouse recipient; inactive applications cannot replace a peer's
form merely by selecting one. A recipient change selects the new recipient's
current form, with system ARROW as the fallback. M_FORCE allows immediate form
installation without changing focus or input routing. Retain that override
until recipient selection changes, the active owner replaces the form, or the
forcing registration exits. Accept the flag without adding an undocumented
mandatory UPDATE lock; UPDATE remains the conventional way to protect a forced
temporary form sequence. The flag does not bypass physical serialization.

Hide/show operates on the single physical pointer. Balanced M_OFF/v_hide_c
calls add the caller's contribution; M_ON/v_show_c(nonzero) remove one. A show
at zero is a no-op and must not consume another application's contribution.
Maintain a sufficiently wide shared total; reject depth exhaustion rather
than wrapping. Exit removes only that registration's outstanding contributions.
Capture, input events and application execution continue while hidden.

`v_show_c(0)` resets all API hide contributions and forces logical visibility.
Clear the corresponding ownership bookkeeping atomically so later shows or
exit cannot revive stale depths. It never overrides temporary backend erasure,
active DMA, shutdown or a display fault. This unified mixed AES/VDI policy is
an explicit Exec integration choice; test it rather than inheriting the
donor's two-counter inconsistencies.

Initialize current, previous and saved forms to ARROW. M_SAVE copies the
caller's current form without changing appearance or previous state.
M_RESTORE installs its saved form as an ordinary transition; M_PREVIOUS swaps
current and previous, allowing repeated toggling. USER_DEF and vsc_form use
the same ordinary form transition; saved state remains unchanged. Copy input
before overwriting history to avoid aliasing the previous/saved slot.

Registration exit, forced program stop and repeated execution must remove hide
contributions, forced ownership and pending effects before freeing state. Select
the remaining recipient's form; exiting a background application must not reset
a live peer to ARROW. Form state is per application, never per window.

## Physical execution

Use one shared cursor-policy operation behind caller and system entries. It is
an AES service, not a new Exec kernel selector or driver-specific gateway.
Publish logical transitions under the existing policy gate, with no hardware
wait while holding a Layers scene token or Forbid.

For warm calls with an existing workstation, reuse its display grant and add a
trusted pointer-only borrow helper sharing the current backend admission/fence
code. A call made before opening a workstation uses the existing AES system
effect/continuation and reply signal. Metadata-only calls and transitions that
do not change physical presentation need neither a render operation nor RPC.
No new grant, signal, port, Task or timer is allocated per mouse call.

In particular, M_OFF/M_ON under the caller's UPDATE must complete without
waiting for that same UPDATE/MCTRL ownership to be released. Allow the cursor
continuation through the existing owner-safe pointer path. Competing physical
access waits for the current quantum; normal Task preemption continues.
Warm MGVIEW-style hide/draw/show must not add a system round trip per row.

When a transition requires physical work, acknowledge after that work completes
or a newer coherent policy revision supersedes it. Retain copied effect data
and registration lifetime while waiting. A delayed effect must not reinstall an
older form or visibility state. Named and PB calls report the same failures;
void VDI calls use the existing diagnostic channel.

Restore the old saved pixels before uploading a changed form. Extend the
fixed-arrow renderer to signed hotspot-relative origins and correct clipping
on all four edges. Reuse existing even/odd AND/OR masks, cursor-save VRAM and
bounded command/staging storage. Data bits select foreground, otherwise mask
bits select background, otherwise pixels are untouched. Use Exec's pen map.

The current `cursor_render` same-X/Y shortcut must also test form identity:
changing shape or colours while stationary must erase/install/redraw without
requiring a movement event. Identical installed pixels may skip uploads while
logical previous/saved transitions still occur. DESKINPUT.Present must use
logical visibility instead of its current unconditional visible=1 request.
Drawing repair may not resurrect a pointer hidden by GEM.

Main implementation locations:

| Responsibility | Existing locations |
| --- | --- |
| Public declarations, bindings and ABI | `c/include/gem.h`, `c/calypsi/aes-input.c`, `c/calypsi/vdi.c`, `abi/` and their generators/provider exports. |
| Registration state, caller policy and continuations | `lib/aes/aesstate.act`, `aeslocal.act`, `aeswait.act`, `aessystem.act` and retirement in `aescore.act`. |
| Recipient selection and physical pointer presentation | `lib/aes/aesmouse.act`, `aessnapshot.act`, `lib/desktop/deskinput.act`. |
| Form packing, display admission and overlay repair | `ports/gem4xe/adapter/gem-vbxe.c`, `gem-drawing.h`, the cursor generator and emitted-code cursor tests. |

## Executable slices

### GM1: real hide/show and state calls

Pin the donor, publish MFORM/constants and implement ARROW, M_OFF/M_ON,
v_hide_c, v_show_c and vq_mouse through the shared policy and named/PB bindings.
Reuse graf_mkstate's coherent snapshot, extending the common helper if needed
for correct pre-window/inactive queries. Include cleanup, forced-show semantics,
before-workstation admission and the UPDATE-owner fast path now. Unsupported
selectors fail explicitly until their slice lands. Use the pinned standard
ARROW and update affected current pixel expectations.

Check small raw/optimized public-layout/API probes, nested and mixed hide/show,
two registrations, force reset, queries without event consumption, no-op/overflow,
exit while hidden, pre-window use and UPDATE-held completion. Add optimized
physical pixels for hide/draw/copy/show, continuing input and peer Counter ticks.

### GM2: custom forms and complete hotspot rendering

Implement USER_DEF/vsc_form, owned input copies, form generation and dynamic
mask upload. Cover stationary replacement, every mask/data bit combination,
all logical pens, even/odd X, nonzero hotspots and clipping on every edge.
Preserve neighboring nibbles and restore the old background exactly. Reject
unsupported planes/pens/hotspots before mutation. Keep form scratch in upper
RAM and avoid placing multiple 74-byte forms on a small Task stack.

Introduce recipient selection, capture/MCTRL and system-arrow overrides here,
before applications can install distinct forms. Use actual clipped save geometry
for drawing/copy intersection checks; a nonzero hotspot invalidates the current
assumption that the pointer position is the saved rectangle's origin.

Run both-mode MFORM word/field access and VDI PB-count probes, then optimized
pixel, lifetime, preemption and bounded display-failure cases. Test the user
buffer being reused after return and a form spanning a CPU-bank boundary.
Use two registrations to verify inactive form selection, recipient changes and
system overrides without overwriting another application's state.

### GM3: standard forms and recipient selection

Add all eight named forms and aliases, plus M_FORCE. Use the same custom-form
pipeline and recipient integration delivered by GM2. Add forced-override
retirement and restore the correct form on ownership changes. Test stationary
transitions as well as movement between applications.

Use two small cursor applications/Counter, overlapping windows, title/menu/work
crossings, held UPDATE/MCTRL, inactive selection, forced selection inside and
outside UPDATE, input loss and owner exit. Ordinary input must keep flowing;
cursor calls must not focus a window or consume queued buttons/keys.

### GM4: saved forms and lifecycle completion

Implement M_SAVE/M_RESTORE/M_PREVIOUS per registration, including initialized
defaults and repeated previous toggles. Test background save/restore, USER_DEF
history, mixed AES/VDI form installation, interleaved applications and repeated
execution. Verify menu/system overrides do not alter application history.

Exercise stop while hidden, a pending contended effect, workstation close,
window close and registration teardown. Preserve outstanding DMA/storage on
reset-required failure; quiescent failures retain truthful diagnostics and
permit ordinary cleanup. Reuse the existing cursor fault-injection boundaries.

### GM5: shared SDK acceptance and delivery

Use a tiny disk-loaded cursor probe and two loaded Counters. Include an
MGVIEW-style hide/copy/exposed-strip/show sequence without substituting it for
the later original MGVIEW port. Verify the supported named/PB surface, correct
visible completion, background/input progress, close/restart and heap/guards.
Record warm call/RPC counts and physical-unit costs against the fixed-arrow
baseline; retain the current drawing quantum limits and healthy idle waits.

Refresh the demo once through `tools/build_demo.py`, including OF816, pinned ROM
and notices, writable combined SYS/WORK, standard five-second autoboot and
current ABI consumers. Rebuild QED when required by the ABI; routine integration
uses the small probe and Counters. Audit ZIP/SYS, boot to native entry and record
the exact execution scope. Do not claim full GEM input or release qualification.

## Memory and validation gates

Target zero added reserved bank-zero bytes: fixed, root, kernel, idle and each
public Task, including guards, alignment and unused capacity. No stack/DP pool
growth is planned. Compare production memory maps and measured stack headroom;
reduce scratch/call depth before considering a larger reservation.

Final form storage is 222 bytes per registration before counters/metadata;
eight read-only builtins use 592 bytes. Allocate history fields only when used
by their slice. Measure alignment, allocator rounding, effect copies and shared
policy overhead rather than reporting these payload sizes as complete costs.
Reuse the current 256-byte cursor save and 1,024-byte mask VRAM reservations;
keep packing scratch in the existing protected upper buffer.

Use development-tier checks: the host suite and affected generators per code
slice; raw/optimized only for small changed ABI/layout/calling probes; optimized
functional, ownership, pixel, failure and performance checks. Preserve stack,
domain, register, heap, display and OS-restoration checks. Update the AES, VDI,
display/pointer references and history/evidence after implementation. Regenerate
QED's supplementary declarations so they defer to the shared SDK definitions.
Bump current ABI versions when required and rebuild callers together; retain
one implementation and no obsolete compatibility profile.

The plan itself changes no runtime reservation or executable code. Planning
validation is limited to source review and documentation content/link checks.

## Primary source references

- [GEM4XE grlib mode dispatcher](https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/src/aes/grlib.c)
- [GEM4XE form bookkeeping](https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/src/aes/graf.c)
- [GEM4XE cursor packing and clipping](https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/src/vdi/dev_vbxe.c)
- [GEM4XE standard form artwork](https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/tools/gemdata.py)
- [GEMlib graf_mouse contract](https://github.com/freemint/gemlib/blob/master/a_graf_mouse.c)
- [GEMlib forced-show convention](https://github.com/freemint/gemlib/blob/master/v_show_c.c)
