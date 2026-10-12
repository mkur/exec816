# CG4: a desktop that owns launches and everyday file operations

[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) · [Plan](colour-launcher-plan.md)

The [copy-throughput follow-up](../../history/desktop-copy-performance.md)
replaces the initial 512-byte buffer described below with 16 KiB, prioritizing
throughput while retaining this ownership and file-publication model.

The persistent desktop owns a bounded table of program handles. Directory windows
only request launches; closing them leaves the programs alive. Use existing
ExecStartProgram/ExecCollectProgram. While children exist, an ordinary 100 ms
MU_TIMER wait bounds completion collection; this avoids extending evnt_multi
with an unrelated signal subscription API. Idle desktops without children or a
copy job use no periodic timer. Keep child
arguments copied by the Process API. Closing the desktop itself requests stop
and collects its children before disposing application storage. Resource limits
report an ordinary launch failure and leave the desktop usable.

The optional desktop boots the desktop and shell. Panel, Calculator, Text and
other tools start on demand. This uses Task slots for useful running applications
instead of keeping demonstration clients alive. A small association table maps
filename extensions to Exec program paths; TXT defaults to C:TEXT.APP. Native
commands retain ordinary Exec streams and errors. Directory paths use SYS:, C:
and other Exec volumes/assigns directly.

Keep file management inside the existing desktop loop. New Folder and Rename
reuse Files' dialogs. Copy handles one regular file at a time through a 512-byte
upper-memory buffer, advancing one read/write chunk between event decisions.
Cancel closes handles and removes the incomplete EXECCOPY.TMP in the target
directory, preserving an existing destination. An existing temporary file blocks
admission. Ask before replacing a destination. Once copying and closing succeed,
delete the old target if necessary and rename the temporary file. This commit is
not atomic: a failed final rename retains the completed temporary file for manual
recovery. Preserve the first I/O error, including close errors. Delete operates on the selected file or empty directory after a
confirmation. Delete and Replace use the existing inline two-button tree, with
Cancel as the default, so sibling redraws remain in the desktop event loop. A
synchronous form_alert can return AES_PENDING for a sibling notification; the
desktop does not add a modal dispatcher to hide that contract. Save Settings
reports its result in the desktop status line. Recursive copies, trash semantics, multiple selection and dragging
are separate later slices. No file-operation daemon is needed.

A small text file, WORK:DESKTOP.CFG, stores view/sort preferences, directory paths
and geometry, mouse preference and associations. Read it at startup and write it
only on an explicit Save Settings command. The demo mounts SYS: read-only,
so use the existing writable WORK: volume; do not redirect the system S: assign. Use bounded fields and ordinary DOS
errors; ignore unsupported entries. Missing settings use defaults. Avoid a new
configuration service, per-file metadata database or registry.

Use upper RAM for launch/job/preferences state and the copy buffer. Add no Task
or signal for each directory or copy operation. Report actual fixed/per-Task
bank-zero deltas and stack margins. Verify independent launch lifetime, capacity
failure, cancellation/partial I/O and restart with saved settings in the packaged
OF816 desktop. Existing release qualification remains separate.
