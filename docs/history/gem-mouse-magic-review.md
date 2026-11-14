# GEM mouse plan: MagiC cross-check

[Mouse implementation plan](../plans/gem4xe/gem-mouse-plan.md) ·
[MagiC source model](../architecture/magic.md) ·
[MagiC-to-Exec mapping](../architecture/magic-exec-mapping.md) ·
[Drawing boundaries](magic-operation-boundaries.md)

Source review, 2026-11-14. Compared the proposed GM1–GM5 plan with Atari MagiC
revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d` and the selected GEM4XE 0.17
revision `ac476b8bdeda63b8b53ad22ec25b9d88bd7886af`. MagiC source files and hashes
are already recorded in [the source-model inputs](../development/magic-architecture.json).
This review changes the proposed adaptation, not the implemented AES/VDI
contracts. No emulator run, performance measurement or hosted qualification is
claimed. Runtime changes and added bank-zero reservations: zero.

## Structure to extract

GEM4XE is the implementation/artwork donor. MagiC provides the useful
multitasking boundary: application-owned AES cursor state above one shared
screen device. These are separate responsibilities even when the calls reach
the same packing/rendering helpers.

GEM4XE's [mode dispatcher][G4MODES], [AES mouse helpers][G4AES] and
[VDI cursor state][G4VDI] establish the donor side of this comparison.

| Concern | GEM4XE selection | MagiC observation | Exec adaptation |
| --- | --- | --- | --- |
| Form history | Global current/previous/saved slots; gr_mouse explicitly assumes one application. | Three 37-word forms in each APPL. | Three forms per AES registration in upper RAM. |
| Form installation | Single application's form goes to the device. | Install the caller's form only if it is mouse_app; ownership changes install the new owner's stored form. | Derive presentation from existing input routing/capture/MCTRL. |
| AES visibility | One gl_moff counter. | Per-APPL hide contribution plus shared moff_cnt; outer transitions call VDI. | Local contributions and a shared aggregate, with device calls only on outer transitions. |
| Raw VDI | Shared form/hide depth below AES. | Shared Line-A/VDI form and M_HID_CT, independent of APPL history. | Keep public VDI device operations distinct from AES policy. |
| Program cleanup | Whole-program mouse reset can reset both global counters. | Clear the departing APPL's contribution and reconcile live applications. | Retire only that registration's AES state; preserve peers and pending physical work. |
| Concurrent entry | Donor globals belong to one application/runtime. | Ordinary Atari timer preemption does not suspend supervisor-mode execution; explicit waits can schedule. | Retain normal Exec Task preemption and guard coherent publication explicitly. |

The source locators below establish the MagiC observations. The Exec column is
the proposed design, not a claim that MagiC uses Exec's display grants or input
snapshot protocol.

## Application state and ownership

`KERNEL.INC:193–196` gives each APPL a local hide word and saved, previous and
current 37-word forms. `init_APPL` initializes all three forms to ARROW. APPL is
the AES application/thread record; these fields are not attached to a window
or selected afresh whenever a different CPU context runs. [APPL], [INIT]

`_graf_mouse` uses `act_appl` to choose whose history to change, with SCRENMGR as
the fallback for an invalid active application. Ordinary form selection moves
current to previous and copies the new form to current. Only the final
`mouse_app == caller` check permits `set_mform`. A background application can
therefore prepare its own form without replacing the current recipient's form.
`set_mouse_app` installs the new owner's current form when ownership changes.
[FORM], [OWNER]

Ownership changes are UI operations. `_set_topwind_app` calls `set_mouse_app`;
MCTRL saves/replaces routing through `_set_topwind_app`; menu entry and window
interaction temporarily select SCRENMGR and restore routing afterward. There
is no need to install a form at every CPU switch. [TOP], [MCTRL], [MENU], [FRAME]

For Exec, reuse the input routing already published by `AESSNAPSHOT`, capture
retained by `AESMOUSE`, and system frame/menu handling. Preserve the selected
form while Counter runs, a peer performs file I/O or an UPDATE-only owner paints.
`AESLOCKS` writes `service.mouseOwner` for both UPDATE and MCTRL, while
`AESSNAPSHOT` applies it as an input owner only when `mouseHolds != 0`. Using that
field alone for cursor selection would introduce a new ownership bug.

## Hide/show is shared, with local accounting

MagiC's `gm_hide` increments `ap_mhidecnt` and calls shared `mouse_off` without
testing whether the caller owns the mouse. `gm_show` decrements the local count
and calls `mouse_on`. `mouse_off` calls VDI hide only at the outer zero-to-one
transition; `mouse_on` calls VDI show on the final one-to-zero transition.
Visibility therefore does not become private to the focused application.
A background application's hide remains effective across a recipient change.
[HIDE], [AESDEVICE]

`reset_mouse` sums local counts for live APPLs and reconciles `moff_cnt`.
`wind_new` clears the departing application's local count and calls this
reconciliation before resetting its own form. It does not clear every live
APPL's count. This is the important replacement for GEM4XE's whole-program
reset. [RESET], [EXIT]

Exec should maintain the aggregate incrementally under its existing AES policy
gate. With balanced public AES calls, its contribution ledger must equal the sum
of live registration depths. The sequence A:M_OFF, B:M_OFF, A:M_ON must remain
hidden; removing A must also preserve B's hide. Changing recipient or running
Task does not change this result. Inner nesting needs no device operation, RPC
or repaint. Internal overlay erasure remains backend state, outside API counts.

MagiC directly increments/decrements WORD counts and can underflow. Exec keeps
the plan's zero-depth show no-op and overflow rejection rather than importing
that behavior. Exit removes one registration's contribution and balances the
AES aggregate's device hide only when the final contribution disappears. It
does not indiscriminately force VDI visible or reset a peer's form.

## AES policy and public VDI are different interfaces

The inspected VDI `INPUT.S` writes the device form without looking up APPL
current/previous/saved buffers. Its hide/show code operates on shared
`M_HID_CT`; `v_show_c(0)` resets that device counter. It does not clear
`ap_mhidecnt` or AES `moff_cnt`. Neither the device counter nor installed form
is local to each virtual workstation. `vq_mouse` samples shared coordinates and
button state under a short interrupt guard. [VDIFORM], [VDIVIS]

Thus two initial draft choices needed correction:

- `vsc_form` must share packing/physical admission with AES USER_DEF without
  becoming an AES history-changing operation. A later AES owner installation
  can replace the raw VDI form; ordinary movement or CPU switching need not.
- `v_show_c(0)` must not erase every application's AES hide bookkeeping.
  It is a raw shared-device operation and can defeat an enclosing AES hide.
  Mixing it into an AES-managed sequence requires caller coordination.

This retains the conventional lower-level VDI contract. GEMlib's
[vsc_form](https://raw.githubusercontent.com/freemint/gemlib/master/vsc_form.c),
[v_hide_c](https://raw.githubusercontent.com/freemint/gemlib/master/v_hide_c.c)
and [v_show_c](https://raw.githubusercontent.com/freemint/gemlib/master/v_show_c.c)
documentation directs AES applications to graf_mouse. Exec will document that
boundary rather than add a new cross-application VDI ownership scheme. Raw VDI
balance remains the caller's responsibility; the AES contribution ledger
provides application-managed cleanup.

`graf_mkstate` also reads MagiC's shared current mouse/qualifier values without
consuming queued events. The existing Exec binding reads its context's latest
inbox sample. GM1 must make the common query helper observe a coherent shared
current sample even before the first window and while inactive, without
replacing frozen event-selection records. Reuse the current input capture and
publication path. [QUERY], [VDIVIS]

## Flags, saved forms and preemption

MagiC clears bit 15 at the start of `_graf_mouse`, with a comment that the
MultiTOS feature is unnecessary there. The later owner check still applies.
The draft's forced-owner override, expiry rules and teardown state were not
drawn from MagiC. The revised plan accepts/strips M_FORCE and keeps recipient
ownership. This deliberately selects MagiC behavior rather than the forcing
behavior described by the general [GEMlib AES contract](https://raw.githubusercontent.com/freemint/gemlib/master/a_graf_mouse.c).
Do not advertise that MultiTOS behavior. [FORM]

M_PREVIOUS really swaps an APPL's current and previous forms. M_RESTORE uses its
saved form through the ordinary transition. A less obvious detail is that
M_SAVE copies current to saved and then falls through to M_RESTORE's form path,
also changing previous to the current form. Exec retains GEM4XE's save-only
operation without this history side effect and records that small semantic
choice explicitly. All three initial forms remain ARROW. [HISTORY], [INIT]

MagiC's physical `set_mform` brackets a VDI form call with shared hide/show,
while VDI uses `MOUSE_FLAG` and short SR masking around cursor publication.
Its timer path checks the saved supervisor state before suspending an
application. Those protocols explain how global scratch is used in the Atari
implementation; they do not supply a critical section for native Exec callers.
[AESDEVICE], [VDIFORM], [TIMER]

Exec must copy caller form data before waiting, publish form/counter revisions
under its existing policy guards, and serialize erase/upload/redraw through
the current display backend. Release policy ownership before hardware waits.
No scheduler hook, global preemption suspension or new mouse Task is required.
An application holding UPDATE must be able to hide/change/show through the
owner-safe pointer path without waiting for its own UPDATE to end.

## Changes to acceptance

GM1 now checks local AES contributions, the outer device transition, raw VDI
counter boundaries, peer-preserving exit and shared non-consuming queries.
GM2 checks recipient selection before custom forms are available, including
UPDATE-only handoffs, MCTRL/capture, stationary changes and raw VDI form
installation without AES history changes. GM3 checks M_FORCE compatibility
without forced-override state. GM4 checks the documented save-only choice and
teardown of pending effects. GM5 retains loaded small-app/Counter acceptance
and one final demo refresh. Commit each executable slice after its own checks.

This review is validated as documentation: source-file hashes against the
existing pin, the cited normalized source ranges and local links. It does not
change runtime reservations; the implementation plan still targets zero added
reserved bank-zero bytes, with actual maps and per-Task costs checked per slice.

[APPL]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/INC/KERNEL.INC#L193-196
[INIT]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L946-959
[OWNER]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7143-7160
[FORM]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7244-7283
[TOP]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L4196-4224
[MCTRL]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L580-630
[MENU]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L1981-2008
[FRAME]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESWIN.S#L3082-3139
[HIDE]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7200-7208
[AESDEVICE]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESOBJ.S#L327-376
[RESET]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7111-7138
[EXIT]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L11116-11144
[VDIFORM]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/VDI/SRC/MAGICVDI.2/INPUT.S#L161-217
[VDIVIS]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/VDI/SRC/MAGICVDI.2/INPUT.S#L233-285
[QUERY]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L5970-5983
[HISTORY]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESMAIN.S#L7210-7236
[TIMER]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/BIOS/ATARI/MAGIBIOS.S#L3711-3724
[G4MODES]: https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/src/aes/grlib.c
[G4AES]: https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/src/aes/graf.c
[G4VDI]: https://github.com/slaapliedje/gem4xe/blob/ac476b8bdeda63b8b53ad22ec25b9d88bd7886af/src/vdi/vdi.c
