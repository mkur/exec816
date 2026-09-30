# Sector read cache

The filesystem adapter keeps recently read sectors in upper RAM, shared by
MyDOS and SDFS, all mounts and all open handles. File closes and command exits
preserve the cache. It defaults to **512 blocks of 128 bytes: 64 KiB payload**.
A 256-byte sector occupies two blocks; a hit requires both halves.

Capacity is a boot setting: zero or powers of two from 16 through 2048 blocks.
Zero retains only the existing scratch-sector buffer. If allocation fails,
partial storage is released and the shell reports the fallback. Use the
[OF816 boot monitor](../guides/boot-monitor.md) to change the request for one boot,
or `cache_blocks` in [kernel.json](../../config/kernel.json) for a build default.

A four-way set-associative table limits lookup to four tags per block and uses
round-robin replacement. Collisions can evict data before nominal capacity is
full. Successful exact-length reads populate it; failures do not. Detach and
transport errors drop the affected volume. A reset-required/offline SIO bus
drops all retained blocks and still prevents filesystem access to cached data.
Keep mounted media unchanged until unmount/remount; there is no automatic
media-change detection, prefetch, write support or write-back.

## Memory and lifetime

At the default capacity, payload is 65,536 bytes. Twelve-byte tags add 6,144 bytes,
and per-set replacement indices add 128, for 71,808 allocated bytes before the
service's existing control/transfer storage. The 256-byte transfer buffer remains.
Cache storage is shared, not allocated per file or per Task, and adds no bank-zero
reservation.

Tags identify a volume, mount generation and sector. Geometry is immutable for
the binding lifetime; the cache need not carry a second copy of it. A hit still
passes through normal availability, bounds and cancellation checks. Teardown
releases all cache allocations; closing an ordinary file does not.

Cache hits avoid serial transfers. They do not avoid executable validation,
relocation or Process startup. The [original cache record](../history/sector-cache.md)
contains measured cold/warm runs and the implementation's earlier size totals.
Use a current build's memory/compiler reports for current code size.
