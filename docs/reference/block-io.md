# Filesystem block adapter

[Reference index](README.md) · [Filesystem architecture](../architecture/filesystems.md)

The internal block adapter dispatches filesystem sector requests through a small internal transport binding.
Supported bindings are `sio.device` and `ideplus.device`.
It runs with the shared filesystem worker, not as another worker or public
block device. The [SIO interface](device-io.md) retains raw wire commands.

## Geometry and identity

A mount supplies its device/unit, timing profile, sector count, data-sector size
and short-boot-sector layout. Geometry is validated before attachment and remains
immutable until detach. Filesystem type does not choose the peripheral speed.
A backend/unit identity and mount generation distinguish live bindings and cached data.
The 46-byte mount descriptor stores its backend in the former padding byte at
offset 45. Source configurations without `device` still select `sio.device`.
Transfers use the common IOStdReq prefix in storage sized for IOSIOReq.

Sector numbers are one-based. Reject zero, values beyond the configured count,
and values beyond `$FFFF` before conversion to transport addressing. Sector zero
may terminate a filesystem chain but is never a wire sector request. Widen
arithmetic before addition or multiplication.

SIO data sectors contain 128 or 256 bytes, with `boot=1`: sectors 1–3 transfer
128 bytes. Thus a 256-byte floppy volume's logical byte stream has offsets:

```text
sectors 1..3: (sector - 1) * 128
sectors 4..:  384 + (sector - 4) * 256
```

IDE partitions use uniform 512-byte sectors (`boot=0`), including sector 1.
The adapter submits zero-based logical sector indices and compares configured
geometry with GET_GEOMETRY on attachment. Controller ownership belongs to
[ideplus.device](ideplus-device.md). Mount layout remains 46 bytes; the boot byte
describes transfer geometry, not firmware bootability.

The ATR header is a host-container detail, not guest filesystem data. Do not infer
geometry from VTOC free counts or probe it with mismatched wire lengths. STATUS/
PERCOM discovery is outside the current contract. Profile-specific 256-byte READ
and WRITE support is described in [device I/O](device-io.md#siodevice).

## Transfers and retained data

SIO reads send wire READ `$52`, sector low byte in Aux1 and high byte in Aux2.
Success requires both no I/O error and exactly the expected byte count. A short
or failed response supplies no valid sector, even if some wire bytes arrived.
Framing and checksums remain the SIO driver's responsibility.

BeginStore borrows one complete sector and sends SIO PUT `$50`, without readback
verification. IDE uses ATA WRITE with terminal status and any required cache
flush, also without automatic readback. BeginStore rejects
overlapping requests and invalid geometry before submission. Sources are live
caller-owned complete-sector buffers and stay immutable until FinishStore
collects the reply; the adapter does not walk their RAM map or stage another
copy. A cancelled request retains that borrow until its terminal reply.
Invalidate
the scratch tag and all cached pieces of that sector first; FinishStore publishes
replacement bytes from the submitted source only after an error-free,
exact-length terminal completion. Scratch is tagged only if it was the source.
Writes reuse the same request as reads, with no write-back
queue or additional reservation. The [filesystem writers](filesystem-writes.md)
use these operations to commit data and metadata on explicitly writable mounts.

BeginStoreRange/FinishStoreRange borrow up to four complete adjacent IDE sectors.
Every affected cache tag is retired before submission; successful full completion
publishes each sector from its part of the actual source span. Failed or short
completion invalidates the volume. SIO accepts only the single-sector path.
SpartaDOS coalesces contiguous new payload reservations within its existing
four-sector extension group. Partial final sectors and fragmented reservations
remain individual transfers; metadata publication and confirmed file prefixes
are unchanged. No range staging buffer or larger request record is allocated.

BeginFetchRange/FinishFetchRange use the shared 2048-byte staging buffer for up to
four adjacent IDE sectors. The in/out count is reduced to one on a first-sector
hit, or shortened before any later retained sector. Presence probes do not copy
bytes or change cache counters; admitted misses are counted once per sector.
Exact successful completion publishes each sector and tags only the first in
scratch. Failure publishes none and invalidates retained data for that volume.
Availability is checked before hits, including with the cache disabled. SIO
remains single-sector.

The filesystem Workspace carries the admitted count alongside its needed sector
until completion and consumption. Metadata and MyDOS requests set the count to
one; SDFS selects bounded regular-file ranges from its current validated map.
Operation startup, retirement and payload consumption reset the count to one.

The filesystem service owns one reusable transfer request and 2048-byte upper-RAM
buffer. Each mount retains its owning device-open request. Transfers borrow that
binding without copying Message links and cannot reuse the request or buffer
until exact reply collection. Filesystem validation precedes copying payload to
client buffers, which may cross banks.

The [shared sector cache](../architecture/sector-cache.md) retains successful
reads across file closes. Lookup checks volume/generation, sector bounds and
service availability without revalidating immutable geometry on every hit.
Detach and transport errors invalidate affected data; an offline/reset-required
bus invalidates its own retained blocks and cannot be bypassed with a cache hit.
External writers must leave mounted media unchanged until detach/remount.

Public file positions are not physical byte offsets: MyDOS trailers and
fragmented file chains, or SpartaDOS maps, determine payload placement. Their
contracts are in [MyDOS](mydos.md) and [SpartaDOS](spartados.md).
