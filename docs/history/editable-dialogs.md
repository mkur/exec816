# Editable TEDINFO and Files dialogs

[Design](../plans/gem4xe/editable-dialogs-design.md) ·
[Plan](../plans/gem4xe/editable-dialogs-implementation-plan.md) ·
[Current AES contract](../reference/aes.md#application-object-trees-and-forms)

ED1 adds caller-local `objc_edit`, formatted/ordinary editable fields, form
traversal and one steady caret per application. Text/index mutation stays in
the application Task. Drawing composes the existing extracted GEM renderer under
DISPLAY ownership, using complete clipped strips and the existing UPDATE lock.
No timer, event service, Task or framebuffer is added. Resource admission checks
writable capacity once and preserves it through relocation. Failed replacement
retains the previous resource. Compiled trees remain trusted caller-owned data.

[ED1 evidence](../development/editable-dialogs-ed1.json) records 73 optimized
object/edit checks and 97 resource checks, exact pixels for formatted text,
viewport scrolling, caret removal and clipped repaint, plus the existing
noneditable/cross-bank TEDINFO cases. Raw and optimized layout/context probes each
pass 1,081 checks in both independent Tasks, with native bridge register/DP
restoration. Guards, ownership and heap return pass. Host checks pass: 419 tests,
four historical skips. These are development checks, not system qualification.

The private C context grows 308 → 318 bytes (312 → 320 allocated). Shared drawing
scratch adds 180 upper-image bytes. C import ABI 6 adds `objc_edit` and the thin
CreateDir/Rename bindings needed by Files, reusing the existing DOS/native call
bridge; their operational integration is covered by ED2. The DOS entry table adds
six upper-image bytes. Rebuild loadable APPs against this single current ABI.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 private idle**,
including alignment, guards and unused capacity. No VRAM allocation changes.

The editing contract is bounded to ASCII, single-line text, 128-byte storage
including NUL and 63-character templates/visible runs. Screen-modal form_do,
selection ranges, clipboard and multiline editing remain unsupported.

The integrated desktop needs 65 boot manifest extents. The configured limit is
now 96 inside the existing $6000–$67FF reservation; no bank-zero storage grows.
A 96-extent host wire round trip and exact-package cold startup beyond the old
64-descriptor limit pass. The loader's byte index and reserved-space bounds
remain enforced. Uncompressed cartridge capacity is informational for XEX demos;
OF816 exceeds that cartridge limit, and compression remains separate work.
