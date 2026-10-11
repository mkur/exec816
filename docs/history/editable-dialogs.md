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

## ED3: Integrated OF816 package

[ED3 evidence](../development/editable-dialogs-ed3.json) records two passing
walkthroughs of the same exact ZIP. The Files-focused run covers all three
dialogs, independent pixels, scrolling/resizing, native and GEM child launch,
Stop, close while editing, idle collection, heap restoration, disk allocation,
guards and OS return. Its initial panel/settings matrix is explicitly omitted.
The separate calculator run checks full-window rejection cleanup, launch/Stop,
two independent instances, resource isolation, shell/counter coexistence, heap
return and desktop exit with a calculator and popup still active.

The earlier full desktop run also passed the menu/settings/runtime checks,
then reached the obsolete final WORK assertion described above. The focused
rerun passes the corrected assertion and verifies the persisted `BBB` directory;
it does not relabel that earlier run as a complete pass. The calculator observer
now waits for Files to finish directory enumeration before taking its heap
baseline; the exact first-child timer allocation expectation remains 112 bytes.

`tools/build_demo.py --gem-desktop` produced
`build/desktop-milestones/complete/exec816-demo.zip`, retaining OF816 and the
five-second autoboot. All 127 recorded source inputs match the current tree.
The ZIP has 19 distribution files and 18 verified payload checksums; it includes
the matching disks, pinned ROM, guide and notices, with no build intermediates.
The compiler pin is unchanged; `CARGO_PROFILE_DEV_OPT_LEVEL=2` optimizes the
host compiler build only. All target fixtures and the package use optimized
emission with stack checks. Host tests pass (419, four historical skips), and
the affected generated ABI definitions are current.

The smallest observed public-Task margin above its checked floor is **17 bytes**
in the Files walkthrough and **49 bytes** in the calculator walkthrough;
presenter margins are 1,494 and 1,470 bytes respectively. Guards remain intact.
These narrow application-stack margins are an observed limit of this development
coverage, not a qualification of every possible input or call path. ED3 adds
**0 fixed, 0 per-public-Task and 0 private-idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. HY4/PI4 and release
qualification remain open; these functional runs make no new latency claim.
