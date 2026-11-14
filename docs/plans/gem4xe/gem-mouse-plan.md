# GEM mouse calls

[GEM plans](README.md) · [AES contract](../../reference/aes.md) ·
[VDI contract](../../reference/gem-vdi.md) ·
[Display ownership](../../reference/display.md) ·
[MGVIEW foundations](mgview-foundation-plan.md) ·
[MagiC mouse cross-check](../../history/gem-mouse-magic-review.md)

Status: proposed, 2026-11-14. Deliver GM1–GM5 as executable slices, committing
each after its development checks pass. This plan adds shared SDK services;
MGVIEW itself remains a separate application port. Current contracts continue
to describe the implemented system until each slice lands.

Cross-checked against the pinned multitasking MagiC implementation on
2026-11-14. GEM4XE supplies forms and rendering algorithms; MagiC supplies the
application-state and shared-device structure. The review replaces the initial
draft's forced form override and unified AES/VDI bookkeeping with the layered
model below. It adds no implementation or runtime qualification.

## Public surface

Use conventional GEM declarations and parameter blocks. Add the functions to
`<gem.h>` and the loaded C provider as they become executable; do not add
application-specific replacements or success-returning stubs.

| Interface | Behavior and parameter block |
| --- | --- |
| `graf_mouse(mode, form)` | AES 78: one integer input, one integer result, one address input. Nonzero success, zero failure. |
| `graf_mkstate(x,y,buttons,qualifiers)` | Existing AES 79; use a coherent current shared sample without consuming events. |
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
M_OFF, M_ON, M_SAVE, M_RESTORE, M_PREVIOUS and the AES M_FORCE constant. Accept
and strip M_FORCE as MagiC does; it does not bypass recipient ownership. Do not
advertise MultiTOS forced-selection semantics. Numeric values, layouts and call
counts belong in machine-readable ABI inputs and generated definitions.
Ordinary and parameter-block calls share helpers.

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
| `src/vdi/vdi.c` | MFORM interpretation, nested hide/show and state query. | Shared screen-device state below AES application policy; use existing captured input. |
| `src/vdi/dev_vbxe.c` | Foreground/background mask packing, parity strips, hotspot/clipped save/paint geometry. | Existing Exec pen mapping, VRAM layout, fences, overlays and display grants. |
| `src/app/gem.h`, `gemlib.c` | Names, constants, signatures and call counts. | Independently written native bindings; no Atari trap/runtime import. |

Do not import donor mouse polling, hardware input capture, cooperative
scheduling, startup or the device driver. Existing INPUT capture, DESKMOUSE
acceleration, event routing and physical completion remain authoritative.
GEM4XE's global form slots and whole-program mouse reset assume one application.
Replace them with MagiC's per-application forms, local AES hide bookkeeping,
shared AES aggregate and recipient-controlled installation. Retain the separate
VDI device layer: its global counter is not a second copy of an application's
AES count. The [source review](../../history/gem-mouse-magic-review.md) traces
initialization, ownership changes, outer hide/show transitions, raw VDI calls,
cleanup and the preemption adaptation. Keep source observations distinct from
the explicitly chosen Exec differences.

## Logical state and ownership

Keep these responsibilities separate:

- AES owns one cursor-policy record per registration in upper RAM. It contains
  current/previous/saved forms as each feature lands and the application's AES
  hide depth. The C binding does not maintain another copy of policy state.
- Shared AES policy selects the mouse recipient and maintains the sum of live
  registrations' AES hide contributions. Recipient changes select forms without
  rewriting application history or clearing this aggregate.
- The screen-device layer owns the installed form, VDI hide depth and a physical
  revision. The backend also owns masks, clipped saved pixels and drawn/erased
  state. Temporary erasure around drawing does not change either API counter.

Normal form changes update the calling application's history. Install them
when it is the mouse recipient; inactive applications cannot replace a peer's
form merely by selecting one. A recipient change selects the new recipient's
current form, with system ARROW as the fallback. Accept and strip M_FORCE before
mode dispatch, following MagiC. There is no forced-owner slot, extra lifetime or
cursor-specific lock. Form selection alone does not change focus/input routing
or acquire UPDATE.

CPU scheduling is independent of this recipient. Do not change forms when a
different Task runs or enters disk I/O. Reuse published input routing, active
work capture and explicit MCTRL; frame/menu gestures select the system form
without changing application history. In particular, `service.mouseOwner` also
records UPDATE admission: with `mouseHolds=0` it is not an input/cursor owner.
An UPDATE-only handoff must not steal another registration's selected form.

M_OFF adds one caller-owned AES contribution; M_ON removes one. A show at local
zero is a no-op and cannot consume a peer's contribution. At aggregate 0->1,
add one screen-device hide; at 1->0, balance that hide. Nested AES calls do not
each invoke a device operation. Maintain a sufficiently wide aggregate and
reject exhaustion rather than wrapping. Hide contributions remain effective
across recipient changes and background execution. Capture and input continue.

Raw `v_hide_c`/`v_show_c` operate on the shared VDI device depth, not AES local
counts. `v_show_c(nonzero)` balances one device hide; zero resets that device
depth and requests visibility, without deleting any registration's AES count.
It never overrides temporary backend erasure, active DMA, shutdown or a fault.
As in MagiC, raw VDI is a lower-level interface: applications must balance and
coordinate it, and should use graf_mouse for application-managed hide/show.
Do not promise that raw forced show preserves an enclosing AES hide sequence.

Likewise, `vsc_form` replaces the shared device form, leaving AES current,
previous and saved forms unchanged. It remains installed through motion and
ordinary Task switches until an explicit form installation or recipient change.
Share packing/admission helpers with USER_DEF, not the AES history mutation.

Initialize current, previous and saved forms to ARROW. M_SAVE copies the
caller's current form without changing appearance or previous state. This
follows GEM4XE's save-only operation; MagiC's implementation falls through to
reinstall that same form and also changes previous. Record this small deliberate
difference rather than attributing save-only behavior to MagiC. M_RESTORE
installs the saved form as an ordinary AES transition; M_PREVIOUS swaps current
and previous, allowing repeated toggling. USER_DEF performs an ordinary AES
transition; saved state remains unchanged. Copy input before overwriting history
to avoid aliasing the previous/saved slot.

Registration exit, forced program stop and repeated execution must remove that
registration's AES hide contributions and pending effects before freeing state.
Balance the aggregate's device hide only when its final contribution disappears.
Select the remaining recipient's form; exiting a background application must not
reset a live peer to ARROW or force the device visible. Do not call GEM4XE's
whole-program reset. Raw VDI calls retain their caller-managed balance contract;
closing a workstation does not clear the shared device counter. Form state in
AES is per registration, never per window or CPU-running Task.

## Physical execution

Use shared AES policy behind caller and system entries, and one serialized
screen-device helper layer also reached by the public VDI bindings. Add no
Exec kernel selector or driver-specific gateway. Publish logical transitions
under the existing policy gate, with no hardware wait while holding a Layers
scene token or Forbid. MagiC's ordinary supervisor-mode timer-preemption gate
does not carry over: copy form data and publish coherent state under Exec's
existing guards, then wait for physical work after releasing policy ownership.

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
Drawing repair may not resurrect a pointer hidden by the device's logical
state. State queries use a coherent latest shared INPUT/AES sample, including
for windowless/inactive callers; a context's frozen event-selection snapshot
is not an authoritative global query. Preserve queued input and wait interests.

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
The common mode decoder strips M_FORCE from the first slice.
Extend graf_mkstate's common helper to observe current shared state independently
of per-context event delivery. Include AES-local/shared and VDI-device counter
boundaries, cleanup, raw forced-show semantics, before-workstation admission
and the UPDATE-owner fast path now. Unsupported
selectors fail explicitly until their slice lands. Use the pinned standard
ARROW and update affected current pixel expectations.

Check small raw/optimized public-layout/API probes, nested AES hide/show, raw
VDI nesting and mixed-layer boundaries, two registrations, raw force reset
without ledger clearing, queries without event consumption, no-op/overflow,
exit while hidden, pre-window use and UPDATE-held completion. Add optimized
physical pixels for hide/draw/copy/show, continuing input and peer Counter ticks.
Verify A:M_OFF, B:M_OFF, A:M_ON leaves the pointer hidden; removing A does not
remove B's contribution. Changing input recipient or the running Task also
leaves it hidden.
Check zero physical work for inner AES hide/show and stationary no-op queries.

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
system overrides without overwriting another application's state. Include
UPDATE-only handoff, windowless MCTRL, work capture through release and raw
vsc_form surviving ordinary motion until an AES installation replaces it.

### GM3: standard forms and MagiC flag compatibility

Add all eight named forms and aliases. Confirm M_FORCE is stripped by the common
mode dispatcher, including for inactive callers, with no forced-override state.
Use the custom-form pipeline and recipient integration delivered by GM2.
Test stationary transitions as well as movement between applications.

Use two small cursor applications/Counter, overlapping windows, title/menu/work
crossings, held UPDATE/MCTRL, inactive selection with/without M_FORCE, input loss
and owner exit. Ordinary input must keep flowing;
cursor calls must not focus a window or consume queued buttons/keys.

### GM4: saved forms and lifecycle completion

Implement M_SAVE/M_RESTORE/M_PREVIOUS per registration, including initialized
defaults and repeated previous toggles. Test background save/restore, USER_DEF
history, raw VDI installation without AES-history mutation, interleaved
applications and repeated execution. Verify menu/system overrides do not alter
application history. Test the documented save-only difference from MagiC.

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
