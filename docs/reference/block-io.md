# Filesystem block adapter

[Reference index](README.md) · [Filesystem architecture](../architecture/filesystems.md)

The internal block adapter maps filesystem sector requests onto `sio.device`.
It runs with the shared filesystem worker, not as another worker or public
block device. The [SIO interface](device-io.md) retains raw wire commands.

## Geometry and identity

A mount supplies its device/unit, timing profile, sector count, data-sector size
and short-boot-sector layout. Geometry is validated before attachment and remains
immutable until detach. Filesystem type does not choose the peripheral speed.
A volume identity and mount generation distinguish live bindings and cached data.

Sector numbers are one-based. Reject zero, values beyond the configured count,
and values beyond `$FFFF` before conversion to SIO auxiliary bytes. Sector zero
may terminate a filesystem chain but is never a wire sector request. Widen
arithmetic before addition or multiplication.

Supported data sectors contain 128 or 256 bytes. Sectors 1–3 always transfer 128
bytes. Thus a 256-byte volume's logical byte stream has offsets:

```text
sectors 1..3: (sector - 1) * 128
sectors 4..:  384 + (sector - 4) * 256
```

The ATR header is a host-container detail, not guest filesystem data. Do not infer
geometry from VTOC free counts or probe it with mismatched wire lengths. STATUS/
PERCOM discovery is outside the current contract. Profile-specific 256-byte READ
support is described in [device I/O](device-io.md#siodevice).

## Transfers and retained data

A read sends wire READ `$52`, sector low byte in Aux1 and high byte in Aux2.
Success requires both no I/O error and exactly the expected byte count. A short
or failed response supplies no valid sector, even if some wire bytes arrived.
Framing and checksums remain the SIO driver's responsibility.

The filesystem service owns one reusable transfer request and 256-byte upper-RAM
buffer. Each mount retains its owning device-open request. Transfers borrow that
binding without copying Message links and cannot reuse the request or buffer
until exact reply collection. Filesystem validation precedes copying payload to
client buffers, which may cross banks.

The [shared sector cache](../architecture/sector-cache.md) retains successful
reads across file closes. Lookup checks volume/generation, sector bounds and
service availability without revalidating immutable geometry on every hit.
Detach and transport errors invalidate affected data; an offline/reset-required
bus invalidates all retained blocks and cannot be bypassed with a cache hit.
Mounted media must remain unchanged until detach/remount.

Public file positions are not physical byte offsets: MyDOS trailers and
fragmented file chains, or SpartaDOS maps, determine payload placement. Their
contracts are in [MyDOS](mydos.md) and [SpartaDOS](spartados.md).
