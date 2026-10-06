# OF816 before kernel loading

> Implementation record for the working tree based on `328baef`.
> Current behavior is documented in the [monitor guide](../guides/boot-monitor.md)
> and [platform contract](../reference/platform.md).

The [B1–B4 plan](../plans/of816-first-boot-implementation-plan.md) runs OF816
before the large native image. One combined XEX supplies the small loader,
resident adapter and manifest first, initializes default settings, then loads
OF816 and invokes it through INITAD. Countdown expiry and `EXEC816` retire
Forth, restore the live caller context and return with RTS. The paused XEX or
cartridge reader resumes the unchanged native record stream. The final guarded
RUNAD still validates completion before entering the kernel.

Startup prints `Exec816 boot`, `Loading OF816 ` and `Loading Exec816 `.
A dot represents 16 KiB of completed copying or zero-fill, with another dot
for a final nonempty remainder. The setup record and failed records do not
count. Output preserves IOCB0 and callback registers; it does not reopen E:
or borrow the reader's channel. OF816 appends its banner without clearing
the screen. Console output failure does not change image validation.

The existing boot record and kernel capture code are unchanged. Defaults are
initialized once before Forth. `CACHE-BLOCKS!` and `SYSTEM-DRIVE!` edits survive
all remaining callbacks and kernel capture. No additional record, flag or
copy-back mechanism is needed.

The adapter saves P, full A including hidden B, X/Y, DBR and D on the incoming
page-one stack, then records the resulting S as the ROM stack anchor. ROM calls
and native interrupt wrappers use that anchor when entering from an OF stack;
nested page-one activations keep their live S. IRQ and NMI are masked during
the retirement stack/mode/vector transition. VBI resumes only with a valid
emulation-mode OS stack. The epilogue restores the caller's original interrupt
state. BYE, a busy keyboard IOCB and initialization failure retain the existing
nonreturning restoration/park behavior.

The checked packaging helper identifies the generated setup and empty INITAD
record, validates the later record/callback pairs and retains the safe default
and final RUNAD. It rejects unexpected direct writes or callbacks. Existing
arena and free-bank admission checks remain in force. Build metadata records
the monitor callback boundary and the remaining payload count.

## Memory

All figures include reserved guards, alignment and unused capacity. B1–B4 each
add **0 fixed runtime, 0 root/kernel, 0 per public Task, 0 idle and 0 boot-only
reserved bank-zero bytes**. The existing 3,392-byte OF borrowed arenas,
5,120-byte loader reservation and 1,024-byte cartridge reservation are retained.

| Emitted storage | Before | After | Change |
| --- | ---: | ---: | ---: |
| OF adapter code/state | 1,053 | 1,124 | +71 bytes, including a two-byte stack anchor |
| Native loader code/state and manifest | 1,322 | 1,690 | +368 bytes, including five bytes of progress state |
| Saved INITAD context on the live caller stack | 0 | 8 | +8 temporary bytes; no enlarged stack reservation |

The OF adapter remains below its 1,264-byte limit. Progress output temporarily
stacks the 16-byte IOCB and complete register context, with ordinary ROM call
and interrupt nesting below the anchor. Emitted return probes cover incoming
S at `$01D0` and `$01B0`, preserve the caller frames above them, and run with real
VBI; an additional case verifies that an incoming IRQ mask survives return.
The preview borrows upper banks `$3E` and `$3D` for OF code and dictionary.
Kernel startup later makes both available to Exec as before.

## Development evidence and preview

The [execution record](../development/of816-first-boot.json) pins source inputs,
compiler, ROM, emulator, machine settings, images, media and checks. It records
the host suite, focused emitted loader cases, both XEX monitor routes and both
Atarimax forms. Shell routes check command lookup, aliases, relative directory
writes, invalid paths, pipelines, ownership, stack/domain guards, persisted
media and OS restoration after EXIT. Manual Forth checks use a 128-block cache
request and select SYS on D2; effective settings are checked after startup.

The focused observer compares all 42 native extents: **789,764 bytes** of
initialized code/data and zero-fill. Its diagnostic transfers mask NMI, borrow
only existing staging/unused loader capacity, and restore that scratch; they
do not provide interrupt qualification. Separate context probes exercise VBI
and live caller frames. Feedback cases cover one byte, an exact 16 KiB,
a remainder, zero-fill, and bounds/record/incomplete rejection.

Each shell run now uses an independent writable WORK copy. This avoids a host
fixture race between concurrent walkthroughs. The cache observer retains the
miss-free warmed-read check at the standard capacity; smaller requested caches
must increase hits and may incur misses only with observed eviction.

The local preview is `build/release-preview-of816-first/assets/exec816-demo.zip`.
It contains the bitmap shell without primes, OF816 with five-second autoboot,
the matching system/work disks and pinned AltirraOS ROM, old/new Atarimax CAR
images, the raw BIN, user guides, licenses and checksums. Manifests, listings
and test output remain outside the archive. The archive is unpublished.

The supported baseline remains the pinned AltirraOS 65816 build. The execution
record also identifies bounded default-XEX startup/EXIT checks using the local
patched XLOS A/F ROMs. Those overrides do not change the bundled firmware or
qualify other firmware services or hardware. No remote loader, full Open
Firmware layer or physical cartridge qualification is added.
