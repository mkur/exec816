# SYS: system volume

`SYS:` names the root of the explicitly selected system volume. It does not
identify where the kernel XEX came from. SYS and the physical name share one
mount, generation, worker, cache and normal file/lock references.

The standard configuration selects D1:

```json
{
  "system_mount": "D1",
  "mounts": [
    {"alias":"D1", "unit":49, "sectors":720,
     "sector_bytes":128, "profile":4, "format":2}
  ]
}
```

Selection is by name, independent of descriptor order. Only the selected
mount must use D1..D8 matching its SIO unit. SYS is reserved and cannot be a
separate mount. Omitting `system_mount` leaves explicit-volume access intact
but makes SYS unavailable.

Before handoff, OF816 can move the selected descriptor to another drive:

```forth
decimal
2 SYSTEM-DRIVE!
SYSTEM-DRIVE@ .
EXEC816
```

The same companion disk must then be in D2. Its geometry, filesystem and SIO
profile stay unchanged. SYS resolves to D2, and the old D1 name is absent.
`SYSTEM-DRIVE!` accepts full-cell values 1..8, requires a selected descriptor,
and rejects unit/name conflicts without changing the previous request.
The getter reports the request, not a successful mount. Five-second autoboot
uses the image's default. Settings last for one boot and freeze at handoff.

The native startup path independently validates the shared eight-byte
[boot record](platform.md#boot-service-settings). Malformed input
uses build defaults with a diagnostic. A valid but conflicting drive fails
before publishing any mounts. There is no fallback drive scan.

Ordinary DOS callers can use case-insensitive paths such as `SYS:TOOLS/FILE`.
SYS always starts at the selected root; relative paths and an initial colon
retain their current-directory/current-volume meanings. `CurrentDir(NULL)`
still removes the caller's default directory. `NameFromLock` returns canonical
physical names, such as `D2:TOOLS`.

SYS itself holds no reference. Busy unmount leaves it intact; successful
unmount makes it unavailable until the same slot is remounted with a new
generation. Service restart preserves selection, not old mount objects.
Absent/unpublished selection reports `ERROR_DEVICE_NOT_MOUNTED`; offline media
retains its causal error. SYS is one fixed alias, separate from the ordinary
[directory assigns](assigns.md); there is no RAM: filesystem. Command search is
separate per-shell policy.

The standard shell starts with a real SYS root lock and reports its mapping.
Initial filesystem startup publishes all configured volumes together; after
success, the shell reports each volume's physical drive and access mode.
For the demo, these are SYS: on D1: read-only and WORK: on D8: read-write.
`MOUNT` lists the physical volume once. Startup also assigns `C:` to the existing
`SYS:C` command directory and `S:` to `SYS:S` when present. It runs optional
`S:STARTUP` and `S:USER` before the first prompt; both mappings follow the selected
system drive. See [startup scripts](../guides/shell.md#startup-scripts).
The shell's default
[PATH](../guides/shell.md#path) searches CurrentDir and then C:, so `HELLO` or
`CAT SYS:STORY.TXT | WC` works from another directory. Explicit command paths
such as `C:HELLO` or `SYS:C/HELLO` bypass search. File arguments still resolve
against CurrentDir; the shell starts at SYS root. A failed initial mount leaves
a usable console; after correcting media, `CD SYS:` retries filesystem startup,
then `SYS:C/ASSIGN C: SYS:C` establishes the command assignment. An offline SIO
device after a transport timeout requires a cold boot. Initial filesystem
startup publishes the configured mount set together: every configured volume
must mount successfully. In demo builds this includes WORK: on D8:, even when
the first request names SYS:. Missing WORK: therefore prevents SYS: startup as
well. The failure message lists the other required drives instead of
attributing every startup error to the system disk.

Validation is focused development coverage; see the
[implementation record](../plans/sys-volume-implementation-plan.md).
