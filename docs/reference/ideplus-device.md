# IDE Plus device

[Reference index](README.md) · [Implementation plan](../plans/ideplus-block-driver-implementation-plan.md)

`ideplus.device` is an on-demand resident Task using native ATA PIO. The initial
target is IDE Plus 2.0 revision E, PBI ID 0, ATA master, 512-byte physical sectors,
LBA28, and the pinned AltirraOS816 platform. It uses ordinary public Task, lease,
message, signal and timer facilities. There is no firmware SIO fallback.

Unit 0 exposes read-only physical sectors; units 1–15 expose active APT DOS
mapping slots. All units are read-only in this slice. Its generated
[interface](../../lib/io/ideplus.act) uses IOStdReq: READ_SECTOR addresses a
zero-based physical sector in io_Offset and transfers exactly one opened unit sector. Raw reads use 512 bytes;
mapped units use 128 or 256. The first three 256-byte sectors also admit a
128-byte prefix.
GET_GEOMETRY returns a 12-byte record containing sector bytes, flags, sector
count and controller generation. Writes and unsupported commands fail.

APT may start at LBA 0 or inside a single protective MBR type $7F container.
The driver decodes low-byte tables and follows at most sixteen headers to
collect the normal fifteen mapping slots. Unsupported slots fail on open.
Malformed revisions, bounds, links, cycles, reserved offsets and overlapping
mappings reject the mapped-unit set; raw diagnostics remain available on an
otherwise healthy controller. Partition sector-1 offsets are physical offsets.

All four documented 256-byte packing modes are supported: low bytes, consecutive
padded bytes, interleaved bytes and interleaved sectors. A 128-byte unit uses
every other byte of the same 256-byte container. Short boot-sector transfers
do not change that container stride. Table sectors and metadata leaders are
never exposed as logical file data. See the [APT specification](https://drac030.krap.pl/APT_spec.pdf).
All successful requests publish the full length, with one terminal reply.

The worker polls status briefly, then sleeps one timer.device VBI tick. Each
hardware wait has a 250-tick deadline (five seconds on the initial PAL target).
A timeout or absent medium marks the controller offline; cold reset is required.
No ATA software-reset register is assumed. A queued cancellation removes/replies;
an active read drains before replying aborted and does not copy client bytes.

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
are consumed on open, without growing any pool. New upper state is 1,024 bytes,
plus a 512-byte heap buffer, timer port and clock request while active. Four-slot
profiles without the requested small stack fail normally rather than taking a
larger stack. The first linear RAM bank remains reserved.

Other revisions, slaves, LBA48, hot removal, ATA-backed SYS: and partition editing
are unsupported. Development emulator checks do not establish physical hardware
compatibility or qualify the hosted platform.
