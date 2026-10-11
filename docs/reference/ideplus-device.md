# IDE Plus device

[Reference index](README.md) · [Implementation plan](../plans/ideplus-block-driver-implementation-plan.md)

`ideplus.device` is an on-demand resident Task using native ATA PIO. The initial
target is IDE Plus 2.0 revision E, PBI ID 0, ATA master, 512-byte physical sectors,
LBA28, and the pinned AltirraOS816 platform. It uses ordinary public Task, lease,
message, signal and timer facilities. There is no firmware SIO fallback.

Unit 0 exposes read-only physical sectors; units 1–15 expose active APT DOS
mapping slots. Mapped units support explicitly enabled writes. Its generated
[interface](../../lib/io/ideplus.act) uses IOStdReq: READ_SECTOR addresses a
zero-based sector within the opened unit in io_Offset and transfers exactly one
512-byte sector, including sector 1. Raw and mapped units reject shorter
requests. One partition sector maps directly to one ATA sector.
GET_GEOMETRY returns a 12-byte record containing sector bytes, flags, sector
count and controller generation. Unsupported commands fail.

The native driver also provides Task-only copied queries:
`Diagnostics(info)` returns the last admission/transport observations in the
generated 24-byte `IDEPLUS.Diagnostics` record; `PartitionStatus(unit, info)`
copies a 16-byte `IDEPLUS.PartitionInfo` for APT slots 1–15. Callers own valid
output storage. These queries do not open the device, select the PBI, allocate
memory or issue I/O. Observations survive worker retirement until another
admission starts; a starting worker exposes only its starting state. Invalid APT
tables expose no partially parsed mappings. Empty, deleted, non-DOS, inactive and
unsupported-sector slots have distinct reasons.

Capacity is the IDENTIFY LBA28 physical sector count, distinct from partition
or filesystem capacity. Admission failures retain their phase, reason, table
LBA and offending slot; ATA status/error bytes are saved separately from the
driver's logical error. A card-register response of `$FF` means no detected
controller at the configured PBI ID; a responding board with its card-absent
bit set reports missing media. Detection targets revision E, ID 0 only.

APT may start at LBA 0 or inside a single protective MBR type $7F container.
The driver decodes low-byte tables and follows at most sixteen headers to
collect the normal fifteen mapping slots. Unsupported slots fail on open.
Malformed revisions, bounds, links, cycles, reserved offsets and overlapping
mappings reject the mapped-unit set; raw diagnostics remain available on an
otherwise healthy controller. Partition sector-1 offsets are physical offsets.

Only native 512-byte DOS mappings (BPS bits `%11`, zero packing bits) are
supported. Other sector sizes are skipped without hiding valid mappings in the
same APT. Low-byte APT table storage remains supported; it is independent of
partition-sector packing. Table sectors and metadata leaders are never exposed
as logical file data. See the [APT specification](https://drac030.krap.pl/APT_spec.pdf).
All successful requests publish the full length, with one terminal reply.
PIO uses the request's live buffer directly. Write buffers remain immutable
until reply collection. A failed or cancelled raw read may have changed its
destination even when io_Actual is zero; those bytes are invalid. Filesystem
reads retain their validation buffer and do not expose failed sectors.

The worker polls status briefly, then sleeps one timer.device VBI tick. Each
hardware wait has a 250-tick deadline (five seconds on the initial PAL target).
A timeout, absent medium or failed accepted write marks the controller offline;
cold reset is required.
No ATA software-reset register is assumed. A queued cancellation removes/replies;
an active read drains before replying aborted; its destination may contain
invalid data even with zero actual bytes.

## Write completion

WRITE_SECTOR retains all 512 caller bytes, writes them directly and waits
for terminal ATA status. It performs no preparation read or automatic readback.
Other physical sectors remain intact. There is one controller owner throughout;
no zero fill or dirty physical cache.

WRITE_SECTORS (command 13) writes 1–4 consecutive 512-byte sectors. io_Offset
names the first zero-based partition sector; io_Length is a nonzero multiple
of 512, at most 2048. Misaligned, oversized and partition-crossing requests fail
before command issue. The one ATA command drains all requested payloads and
settles terminal status/flush before reporting the full length. On failure
io_Actual is zero: no partial durable prefix or rollback is promised, and some
physical sectors may have changed. Queued/preparing cancellation remains
supported; an issued range drains as one bounded write. Each hardware wait has
the existing deadline. The maximum bounds the request's total number of waits.
The constants and completion rules are in [ideplus.json](../../abi/ideplus.json).
READ_SECTORS (command 14) reads 1–4 consecutive 512-byte sectors on raw or mapped
units. Its length and extent admission match the write range. The driver uses
one ATA READ, drains every DRQ span and checks terminal status before reporting
the full length. Failure/abort reports zero actual bytes; destination contents
may have changed and are invalid. An issued read drains before an aborted reply.
Timeout, absent media or an ATA error after read-range issue requires cold reset;
local rejection and a successfully drained abort do not disable the controller.
The existing READ_SECTOR command remains available. Both range contracts are
machine-readable in ideplus.json; request layouts are unchanged.

IDENTIFY with no advertised volatile write cache admits terminal-status durability.
A cached device must advertise FLUSH CACHE support; each accepted write must
complete that flush before reply. Otherwise writable capability
is withheld. CMD_UPDATE flushes cached media, succeeds on cache-free media and
rejects an unsupported durability policy. APT read-only/reserved access flags,
the board protection switch and raw unit 0 always prohibit writes.

Cancellation accepted before ATA command issue prevents mutation. Once
the write command is issued, abort is declined and completion reports the actual
write/flush outcome. Failure publishes zero actual bytes, disables
further requests and retains the controller IRQ mask until cold reset. An
ambiguous write is never retried. An offline controller cannot be restarted by
closing/reopening it or remounting a filesystem.

## Hardware ownership and interrupts

A native register or word-pair transaction saves SHPDVS ($0247), selects ID 0
through SHPDVS followed by $D1FF, and restores the prior selection in that order.
Low data at $D110 advances the ATA word; high data at $D100 is its latch. Writes
stage high then commit low. Selection is released between pairs and before
public services or waits. Flash/RAM selectors, RTC and SDX controls are untouched.

SEI excludes PBI IRQ dispatch. SWITCHING excludes Task changes across selection
and latch access. NMI remains enabled: the complete native context is preserved,
the pinned ROM VBI performs no PBI/ATA access, and deferred scheduling waits until
SWITCHING retires. This ownership rule also excludes foreign VBI hooks accessing
PBI/ATA. DLI is unsupported by the initial platform. SWITCHING does not mask NMI.
The controller IRQ source is disabled while the worker owns it.

New fixed/per-Task/idle bank-zero reservation: zero bytes. One existing 1,024-byte
worker stack (including its interrupt reserve), 32 guard bytes and 256-byte DP
are consumed on open, without growing any pool. Builds with small pools verify
the complete timer-bound worker call path fits before packaging. New upper state is 1,024 bytes,
plus a 512-byte heap buffer, timer port and clock request while active. Four-slot
profiles without the requested small stack fail normally rather than taking a
larger stack. The first linear RAM bank remains reserved.

Configured filesystem mounts select `device: "ideplus.device"`, unit 1–15,
profile 0, 512-byte sectors and uniform geometry (`boot: 0`). IDE filesystems
require SDFS 2.1; MyDOS on IDE is unsupported. Use `access: "readonly"` by default;
`access: "readwrite"` requires reported writable and durable capability. Geometry must
match GET_GEOMETRY exactly. SIO stays the default device. SYS may select an IDE
mount with a fixed configured unit; OF816 system-drive overrides remain SIO-only.
MOUNT and DEVICES identify the transport
and unit without probing hardware. An offline controller cannot satisfy cached
reads and only invalidates volumes belonging to that backend.
`MOUNT DIAGNOSTICS` and verbose boot format the copied IDE observations;
plain `MOUNT` includes retained mount failures and offline causal errors.
Shell boot initializes the controller when IDE mounts are configured, then
prints verbose hardware diagnostics before starting filesystem mounting.
See the [shell guide](../guides/shell.md) for capture instructions.

Other revisions, slaves, LBA48, hot removal and partition editing
are unsupported. Development emulator checks do not establish physical hardware
compatibility or qualify the hosted platform.

The separate `build_demo.py --ide-only --text-shell-only` profile admits fixed
IDE SYS/WORK mounts and excludes Exec SIO registration, driver code and serial
IRQ engine. Opening sio.device fails normally; shared keyboard/timer services
remain available. Ordinary and mixed IDE builds retain SIO. The profile does
not reserve additional bank-zero or Task capacity.
