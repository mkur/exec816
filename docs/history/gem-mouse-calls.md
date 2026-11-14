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
