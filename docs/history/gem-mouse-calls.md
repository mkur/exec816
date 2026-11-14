# GEM mouse calls

[History index](README.md) · [Plan](../plans/gem4xe/gem-mouse-plan.md) ·
[AES contract](../reference/aes.md) · [VDI contract](../reference/gem-vdi.md)

## GM1: hide/show and shared queries

Implements named/PB graf_mouse ARROW, M_OFF/M_ON, v_hide_c, v_show_c and
vq_mouse. Each registration owns its AES contributions; only outer aggregate
transitions affect the separate VDI device counter. Raw forced show clears
that device counter without clearing AES bookkeeping. M_FORCE is stripped,
following the pinned MagiC dispatcher. Other form modes remain unsupported.

Logical publication uses the existing policy gate and short Forbid guards.
Warm calls borrow the workstation's existing display grant; cold calls wait on
the existing private reply signal for a durable physical revision. No hardware
wait holds Forbid or a scene token. UPDATE-held calls complete, including
before a workstation opens. Registration retirement balances its contributions
and waits for physical acknowledgement before freeing its state. Queries read
current shared capture without consuming a registration's input queues.

The pinned GEM4XE 0.17 artwork input and extraction hashes live in
[mouse provenance](../../ports/gem4xe/mouse/README.md). The selected ARROW
replaces the old oracle together with the renderer masks. Existing saved-pixel,
overlay and fence handling remains authoritative.

[GM1 development evidence](../development/gem-mouse-gm1.json) records small
raw/optimized layout and policy probes, optimized renderer/failure, input,
lock/cache and graphical API checks. A non-yielding background counter checks
normal preemption during UPDATE-held hide/copy/strip/show. Pixel comparisons
start after initial desktop painting retires; shutdown similarly drains queued
desktop work. These are development checks, without QED execution or a hosted
release qualification claim. The original MGVIEW application is separate work.

APP ABI 44, AES protocol 23 and console bitmap protocol 15 require rebuilt
consumers. The request grows four upper bytes, each C context four bytes and the
native service 36 bytes (24 shared, two per client and four aggregate). The
MFORM declaration is 74 bytes without allocating a form per client in GM1.
Fixed, root, kernel, idle and every public Task reserve zero additional
bank-zero bytes, including guards, alignment and unused capacity. The existing
256-byte cursor-save and 1,024-byte mask VRAM reservations are unchanged.

## GM2: owned custom forms and hotspot rendering

USER_DEF and raw VDI 111/vsc_form share a validated 37-word request copy.
The per-registration current form is separate from the installed device form;
raw VDI changes no AES state. Recipient selection reuses published routing,
work capture, explicit MCTRL and native/menu gesture state. UPDATE-only owners
and ordinary CPU scheduling do not change the installed form.

The renderer adapts the pinned GEM4XE mask/data expansion, maps both pens and
subtracts the hotspot before screen clipping. It restores old saved pixels
before replacing masks, including stationary changes, and uses the clipped
saved rectangle for drawing intersection checks. Both parity strips are packed
in the existing protected upper buffer. The old 1,024-byte readonly ARROW masks
are replaced with 74 readonly MFORM bytes; VRAM reservations stay unchanged.

APP ABI 45 and AES protocol 24 replace GM1's wire layouts. The request grows
74 upper bytes (418 total), each C context likewise (678), each native client
76 (224), and the service 384 (1,716, including four clients, shared device form
and recipient identity). Eight-byte rounding increases each context allocation
by 72 bytes and the service allocation by 384. Form/request copies are embedded;
there is no per-call allocation. The renderer adds 76 cached-form bytes and
four saved-rectangle bytes in upper static storage. Fixed, root, kernel, idle and every public Task add
zero reserved bank-zero bytes, including guards, alignment and unused capacity.

The [GM2 development record](../development/gem-mouse-gm2.json) records both-mode
layout/field probes, exact custom-form pixels for sixteen pens and eight
positions, source reuse after return, a form crossing a CPU-bank boundary,
stationary replacement and raw VDI motion. Native routing checks cover work
capture through release, UPDATE-only admission, windowless MCTRL, menus, title
capture and endpoint holds. The two-registration application checks inactive
selection, M_FORCE stripping and owner exit under normal preemption.

## GM3: standard forms and flags

All eight pinned standard forms now use the custom-form pipeline, including
HOURGLASS's BUSYBEE/BUSY_BEE aliases. The common dispatcher strips M_FORCE
before selecting or updating the caller's form. It introduces no forced-owner
state and cannot replace an active peer's form from an inactive registration.
Stationary selection uses the same erase/install/redraw path as USER_DEF.

Readonly forms grow from 74 to 592 upper bytes, a 518-byte increase. Structure
sizes, allocations, cursor VRAM and public ABI are unchanged. Reserved bank-zero
growth is zero for fixed, root, kernel, idle and every public Task, including
guards, alignment and unused capacity. Saved/previous operations remain GM4.

[GM3 development evidence](../development/gem-mouse-gm3.json) records 394 API
checks, all standard-form scanouts and the 22 native routing assertions.
The 715 host checks pass with five skips. Guards, heap ownership and OS
restoration remain enabled; these checks do not establish release qualification.

## GM4: saved/previous forms and lifetime

Current, previous and saved forms are now per-registration owned records.
M_SAVE copies current without changing previous; M_RESTORE performs an ordinary
selection and M_PREVIOUS swaps current/previous using the request's owned
scratch. This preserves USER_DEF data across source reuse and avoids overwriting
an aliased history input. Raw VDI and temporary system forms do not mutate AES
history. Saved and inactive form operations return without borrowing a display
grant or waiting for unrelated physical work.

Retirement preserves the registration until its last visibility/form revision
completes or a newer coherent target supersedes it. Driver fault handling stays
in the existing fenced backend; reset-required failure retains the outstanding
request, lease and renderer storage. Repeated application init/exit clears the
native client record, including all three forms and local hide contributions.

Each native client grows 152 upper bytes to 376, and the four-client service
grows 608 bytes to 2,324 (2,328 after heap rounding). No new per-call allocation,
readonly form, scratch or VRAM reservation is added. Public ABI remains APP 45 /
AES 24. Fixed, root, kernel, idle and every public Task reserve zero additional
bank-zero bytes, including guards, alignment and unused capacity.

The lifecycle fixture now collects an independent malformed-message reply
before freeing that descriptor. A completed caller-local window operation does
not prove that unrelated reply arrived. The previous single poll followed by
freeing the still-owned message could corrupt shutdown. The fixture also drains
pending desktop work before stopping the console, as the other window tests do.

[GM4 development evidence](../development/gem-mouse-gm4.json) records 52 policy
checks in each compiler mode, 431 cursor/history assertions, the complete hidden
window lifecycle and reset-required cursor storage retention. The host suite
passes 715 checks with five skips. This is development coverage.
