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

## ED2: Files dialogs

Files now uses a six-object compiled tree and one writable TEDINFO for Path,
New Folder and Rename. The dialog occupies the existing Files work area;
the application keeps servicing geometry, exposure, child completion and close.
Tab/Shift-Tab moves focus, Return accepts, Escape cancels, and pointer activation
uses the same actions. Other applications continue running. Ordinary filesystem
errors retain the field for correction. Path replaces the current directory
only after Lock/Examine succeeds; creation and rename refresh the snapshot and
select the result. The public C bindings use the existing DOS operations.

The Browser model grows 2,672 → 3,054 upper-image bytes: 72 bytes for the three
menu entries and 310 for the dialog state. It remains within the application's
existing two-bank image allocation. Its 28,672-byte snapshot is unchanged.
Rename temporarily allocates 256 upper-heap bytes for
the second full path and frees them after the DOS call, keeping both paths off
the Task stack. No new Task, timer, screen surface or event abstraction is added.
ED2 reserved bank-zero delta is **0 fixed, 0 per public Task, 0 private idle**,
including guards, alignment and unused capacity.

ED2 development checks pass in the exact OF816 package: keyboard/pointer
accept/cancel, duplicate creation, invalid leaf, missing/file path, empty
directory, caret exposure, resize while editing and counter coexistence.
Child collection preserves an open dialog; closing while editing stops and
collects a child. Relaunch restores heap/ownership, and guards and OS restoration
pass. An independent SDFS audit confirms that New Folder/Rename persists `BBB`,
removes `AAA` and leaves consistent allocation. The initial desktop runner's
last host assertion expected only the root directory; it is corrected to audit
this intentional fixture result. ED3 records the rerun with that final audit.
