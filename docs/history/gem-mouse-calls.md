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
