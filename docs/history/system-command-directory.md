# System command directory

The current contracts are in the [shell guide](../guides/shell.md#external-commands),
[SYS: reference](../reference/sys-volume.md) and [ASSIGN reference](../reference/assigns.md).
The supplied external commands now live in `SYS:C`, following the AmigaDOS
command-directory convention. Text data remains at the system root; built-ins
remain in the shell.

After selecting the SYS root, standard shell startup calls the existing
`DOS.AssignPath("C", "SYS:C")`. The resulting ordinary assignment stores the
selected physical directory, such as `D1:C` or `D2:C`, and occupies one of the
four slots. It can be listed, replaced or removed using ASSIGN. It holds no
permanent filesystem lock and survives filesystem-service restart within the
boot, like the other assignments. A failed assignment leaves a usable console
with a startup diagnostic. After correcting media, `SYS:C/ASSIGN C: SYS:C`
restores it.

Default command lookup tries CurrentDir and then the symbolic `C:` PATH entry.
`PATH RESET` restores that list without changing C:'s target; `PATH CLEAR`
leaves only CurrentDir. Reassigning C: redirects future lookup. Explicit paths
such as `C:HELLO` or `SYS:C/HELLO` bypass PATH. The shell starts in SYS root,
and command arguments continue to resolve relative to CurrentDir. No extra
implicit search step is added after the configured PATH.

The demo builder stages commands under `media/C`, classifies their complete
relative names as binary, and keeps compiler sidecars outside the disk. Its
manifest records files as `C/HELLO`, `C/CAT`, and so on. Both media builders
preserve the binaries exactly. The smaller shell playground includes a C
directory with a readme, allowing its boot assignment without supplying the
external commands. Command-loading measurement tools follow the new layout.

## Cost and development checks

Compared with the preceding alias demo, optimized resident routines grow from
624,507 to 624,910 bytes (**403 bytes**), and the program XEX grows from 662,667
to 663,097 bytes (**430 bytes**). ShellBootStart's local stack peak increases
from 26 to 28 bytes. Both builds use the pinned actionc revision
`f1ff4ce0d16b4705e66d69aad00ca4a7be3e1d08`, without a local override. Public
interfaces and provider capacity are unchanged.

The C: assignment uses one existing 288-byte upper-RAM record. Default C:
lookup also exercises the existing lazy 256-byte path-expansion buffer in each
shell's DOS context; teardown frees that buffer. There are no new tables,
Tasks, stacks or direct-page reservations. Fixed, idle and per-public-Task
reserved bank-zero deltas are **zero**, counting guards, alignment and unused
reserved capacity. The earlier enlarged Task stacks remain unchanged.

Development checks passed: 340 host tests and 118 PATH-fixture checks in each
of raw and optimized mode. Raw/optimized physical-key sessions cover real command loading
from C:, current-directory precedence, exact paths, PATH clear/reset,
assignment replacement/removal and filesystem writes through DATA: on both
formats. Packaged OF816 checks exercise the five-second autoboot on D1 and
the Forth-command handoff selecting D2, with canonical C: mappings, disk
commands, a pipeline, stack/domain guards, ownership cleanup and OS
restoration. The ZIP retains the eleven boot/media/guide/licence/checksum
entries, with all sixteen external commands under C. Host tests include exact
nested binary extraction; complete 720 KiB MyDOS and SDFS images also passed
byte-for-byte extraction and allocation audits. OF816 autoboot took 249 PAL
frames. Local documentation links and whitespace checks passed. These are focused
development checks, not release or physical-hardware qualification.
