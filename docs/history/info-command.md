# INFO implementation record

[Implementation plan](../plans/info-command-implementation-plan.md) ·
[Current DOS contract](../reference/dos.md)

## I1 public queries

DOS ABI 8 and COMMAND ABI 15 introduce GetVolume and Info with a copied
62-byte VolumeInfo. Enumeration follows the published registry under Forbid,
starts no service and borrows no mount pointer. Info retains the existing owned
lock/mount through the ordinary packet reply; its statistics action is explicitly
unsupported until I2. C record declarations and layout probes follow the same
machine-readable input.

Development checks: the host suite, generated definition checks, raw/optimized
emitted ABI probes and the focused RAM mount enumeration/lifetime fixture.
Builds and detailed results are under build/info; this does not qualify a release.
The host suite passes 444 checks and the public-query fixture passes 21
assertions, including empty slots before startup, unmount refusal with a live
lock, stale-lock rejection, stopped-service enumeration and complete heap
retirement. The ABI probes include guarded fields across a native bank boundary.

The complete provider manifest is 1,586 bytes within its unchanged 1,664-byte
reservation. No persistent query storage, new Task or sector buffer is added.
Reserved bank-zero deltas are zero fixed, zero per Task and zero idle, including
guards, alignment and spare capacity. Record and ABI probe storage are upper RAM.

## I2 filesystem statistics

MyDOS reuses its header count validation; SpartaDOS copies header counts and
the printable, trimmed label. The worker requests one cached metadata sector
and publishes only after successful validation and the final cancellation
checkpoint. RAM walks sixteen nodes per step and counts owned records/capacity.
Existing operation fields hold all intermediate results; no cache, node counter
or persistent query buffer was added.

Development checks pass for MyDOS 128/256 and SpartaDOS 128/256/512-byte sectors,
41 assertions per geometry. Independent allocation audits agree before/after
creation, overwrite, truncation, deletion and directory creation/removal;
unrelated file bytes remain exact. Cold queries make one physical read, warm
queries none, and neither writes. Corrupt counts, transport failure and BREAK
leave the cross-bank caller record untouched. RAM growth/truncate/delete and
complete heap retirement pass; the IDE fixture explicitly stops its resident
driver after filesystem shutdown. Empty disk files retain one sector, unlike
deleted files. Disposable SIO media uses accurate timing off; these checks do
not qualify transport timing or a release.

The public enumeration/lifetime fixture also passes its updated 21 assertions.
Evidence is under build/info/i2-queries, i2-statistics and i2-ide-statistics.
I1's raw/optimized ABI checks remain the small caller-facing probes. Reserved
bank-zero delta for I2 is zero fixed, zero per Task and zero idle, including
guards and unused capacity. The statistics routines add 3,384 resident bytes
to FSVOLUME; the same worker and its existing guarded stack reservation are used.

## I3 loadable command

C:INFO uses the checked COMMAND queries, the existing ReadArgs/help and WriteAll
providers, and CSTRING decimal conversion. One copied record and one 128-byte
line buffer serve the whole listing. It releases each root lock before output,
follows ordinary path/assign resolution for a named query, continues after
offline/query failures and preserves the first real cause across cleanup.
Offline rows return WARN/IoErr zero; cancellation and output failure stop
immediately. Ordinary rows and long-label wrapping fit the 40-column console.

The actual command body passes 26 cases each with raw and optimized emission:
all/named/assign/relative forms, RAM, empty/sparse/offline/mixed-error lists,
wide counts, MyDOS, long/empty labels, help and its console failures, short/zero
writes, output failure and BREAK. The selected output capture remains separate
from the help console, all borrowed locks/handles are balanced, and INFO consumes
no input data. The exact standard demo also passes loaded INFO, C: resolution,
RAM redirection/read-back and restored OS/ownership checks through physical keys.
Evidence: build/info/i3-command and demo-standard/info-results.json.

The optimized command has 6,752 routine bytes, 524 bytes of upper-RAM BSS
including padding, and an 8,611-byte relocatable disk image including imports,
profiles and relocation records. Maximum emitted local routine peak is 46 bytes;
that is not a whole-call-chain stack measurement. No new allocation or Task is
made by INFO itself. Existing loaded-Process stacks and guards remain unchanged:
reserved bank-zero delta is zero fixed, zero per Task and zero idle.

## I4 demo integration

Both standard/SIO and VBXE/IDE-only demos include C:INFO, the updated story and
distinct SpartaDOS SYS/WORK labels. The independent producer accepts an optional
eight-byte printable label; its EXEC816 default and unrelated fixture bytes are
preserved. Label read-back and complete file extraction verify the generated
media. IDE finalization retains SYS when embedding the matching boot XEX.

Development checks pass: 447 host tests, generated DOS/COMMAND/C layout checks,
and the exact packaged standard and VBXE/IDE demos through OF816's five-second
autoboot. Physical-key sessions verify SYS/WORK/RAM, C: assign resolution,
all-volume output, RAM redirection/read-back, shutdown, guards and ownership.
SYS/WORK counts agree with independent allocation audits; the IDE pair uses
native 512-byte sectors. The combined VBXE/IDE test environment now installs
both declared devices and checks the combined machine pin. Build intermediates,
development manifests and test evidence remain outside the distribution ZIPs.
This is development evidence, not release qualification.

The final OF816 boot XEX sizes are 338,469 bytes (standard) and 393,025 bytes
(VBXE/IDE), leaving 693,722 and 639,166 bytes within the cartridge payload limit.
The IDE ZIP includes both Atarimax cartridge variants. Packages are under
build/info/demo-standard and build/info/demo-vbxe-ide; they have not been
published. The refreshed IDE bundle retains matching OF816/media checksums.

All slices preserve zero additional reserved bank-zero bytes, fixed, per Task
and idle, including guards, alignment and unused reserved capacity. I2 adds
3,660 resident bytes across FSVOLUME, MyDOS validation and handler dispatch.
Its mutation/query fixture observes a maximum filesystem-worker watermark of
584 bytes within the existing 1,312-byte stack, with interrupt headroom intact;
watermarks are lower bounds, not independent whole-system qualification.
Detailed result files remain under build/info; the
[compact evidence record](info-command-evidence.json) records pins, sizes and
execution scope.
