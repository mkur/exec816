# OF816 before kernel loading

Status: implemented through B4 at the development tier. OF816 runs from an
XEX INITAD callback, returns to the paused loader, and the Exec image loads
afterward. Small boot messages preserve the five-second autoboot and settings
entered in Forth. See the [implementation record](../history/of816-first-boot.md)
and [execution evidence](../development/of816-first-boot.json).

Follow the [platform contract](../reference/platform.md),
[boot service settings](../reference/platform.md#boot-service-settings), and
[development testing policy](../contributing/testing.md). The
[current monitor guide](../guides/boot-monitor.md) describes the returning
INITAD handoff.

## Intended behavior

Keep one combined boot XEX and the corresponding Atarimax cartridge images.
Use the existing loader for the remaining image records:

```text
OS or cartridge reader
  -> load the small Exec bootstrap, resident adapter and manifest
  -> first INITAD: validate bootstrap bounds and initialize boot settings
  -> load OF816
  -> INITAD: enter OF816
       -> five-second countdown, or stay at the Forth prompt
       -> EXEC816: restore the paused loader context and RTS
  -> load and validate the remaining Exec image records
  -> final RUNAD: enter Exec through loader_start
```

OF816 becomes available before the large native payload has loaded. The small
bootstrap and manifest still precede it so memory bounds, default settings and
the guarded final entry exist before the monitor runs. No Exec Tasks, heap
allocation or native console ownership start during the monitor phase.

`EXEC816` and countdown expiry use the same return path. The word continues
loading the embedded image; it no longer jumps directly into the kernel.
Cancellation still consumes the key, including repeats, and leaves the monitor
available indefinitely. Keep the current PAL five-second timing.

Startup appends text to the existing ROM console:

```text
Exec816 boot
Loading OF816 ..
OF816 by M.G.
Press a key for Forth.
Exec816 in: 5 4 3 2 1
Loading Exec816 ....................
```

The dot count above is illustrative. Emit one dot per 16 KiB of successfully
completed image work and one for a final nonempty remainder. Exec work includes
validated copy and zero-fill records; OF work counts completed page copies.
Exclude headers, the initial empty setup record and unsuccessful records.
Reset the small counter between stages and end each stage with a newline.
Allow normal text-console wrapping; do not add a percentage, timer or animation.
OF816 startup must preserve earlier text and cursor placement, printing its
normal newline and banner without clearing or reopening the screen editor.

Remote loading is a future extension. This slice adds no network transport,
filesystem reader, separate kernel file, image format or Open Firmware layer.
The early monitor provides a place for a later remote-load command; returning
with RTS remains the ordinary embedded-image boot route.

## Settings survive loading

Keep [exec816.boot.v1](../../abi/boot-v1.json) unchanged. Use the generated
`boot_config` address and field definitions.

1. Run the existing empty-record `loader_init` setup before entering OF816.
   It initializes the boot-state page and default record once, saves MEMLO,
   validates the manifest and sets `loader_initialized`.
2. OF816 edits that live record with `CACHE-BLOCKS!` and `SYSTEM-DRIVE!`.
3. Returning from OF816 preserves the record, loader initialization state,
   manifest and raised MEMLO. Subsequent callbacks consume payload records;
   they must not clear boot state or repeat setup.
4. Kernel startup validates and captures the existing request before admitting
   Tasks. Valid settings survive unchanged. Preserve the existing reported
   fallback for invalid headers or values and existing mount-conflict checks.
5. Protect the manifest through capture and retire it only at the established
   `startup_complete` boundary. The boot-state page retains its current lifetime.

Do not add a second settings record, copy-back protocol or new validity flag.
The existing initialization state and boot-record contract are sufficient.

## Return safely to the paused loader

The current [OF adapter](../../platform/of816/boot.s) replaces S with a fixed
OS stack position and later jumps to `EXEC_LOADER`. Convert it to an INITAD
entry with an explicit return epilogue.

Save the complete incoming emulation-mode context before changing it: S, P,
the full accumulator including hidden B, X/Y, D and DBR. Leave the loader's
return address and caller frames intact. OF816 still uses its existing guarded
native stacks and direct page.

Keep the saved context on the loader stack and establish an OS stack anchor
below that saved frame. ROM calls and native interrupt wrappers must use this
anchor instead of resetting S to `$01EF`. A nested interrupt already on the
OS stack keeps its current S. Account for the saved frame, ROM nesting and
interrupt headroom; do not copy the whole stack page into another buffer.

On `EXEC816` or timeout, abandon the Forth activation, close only the monitor's
keyboard channel, restore borrowed IOCBs and vectors, restore the saved caller
context, and RTS. Do not restore pre-bootstrap MEMLO on this continuation path.
Cover all mode, stack, DP and vector transitions with the documented IRQ/NMI
protocol: SEI alone does not exclude NMI. Restore the caller's interrupt state
instead of ending with an unconditional CLI.

Preserve the existing occupied-IOCB admission rule. In this slice, `BYE`, a busy
keyboard channel or monitor initialization failure restores owned OS state and
parks without returning to payload loading. An abandoned boot may restore the
original MEMLO. Reset/reload is required to start again; returning to the
retired interpreter after Exec exits remains unsupported.

The cartridge stays disabled throughout each INITAD activation. After RTS,
its existing reader masks interrupts, remaps the cartridge and continues.
Retain the TRIG3/GINTLK interlock and the existing mapping protocol.

## Executable slices

### B1: returning monitor entry

Change [boot.s](../../platform/of816/boot.s) and
[platform-words.s](../../platform/of816/platform-words.s) to implement the
saved loader context, shared OS stack anchor and return epilogue. Preserve
screen contents, cancellation and countdown behavior. Replace the current
direct handoff rather than retaining two monitor startup implementations.

Exercise the new entry with a small emitted INITAD harness whose continuation
has an observable marker. Check manual and automatic return, complete caller
context, intact live caller frames, real VBI during Forth/CIO, guarded OF
storage, and the BYE/busy-channel nonreturn paths. Test more than one incoming
page-one stack depth so the fixed-stack assumption cannot pass accidentally.

### B2: reorder the combined XEX and retain settings

Update [build_of816.py](../../tools/build_of816.py) to place OF816 between the
native setup callback and the first image payload record. Add one checked
helper in [banked_image.py](../../tools/banked_image.py) if needed to expose
that boundary. Validate the actual setup callback and empty staging record;
do not split at an unexplained segment number or any arbitrary INITAD.

Keep all native image records, their order, validation and final guarded RUNAD.
Preserve a safe default RUNAD during partial loading. Retain current borrowed
arena and upper-bank overlap checks. Reject later direct segments as well as
copy/zero destinations that would overwrite protected bootstrap state or OF
storage. Record the monitor callback boundary and remaining payload count in
build metadata for independent test assertions.

Add host checks for the exact order and malformed/missing setup boundaries.
Through emitted code, prove native payload loading is still pending at the
Forth prompt, stays pending beyond the original countdown after cancellation,
and resumes exactly once after return. Verify all intended payload bytes and
zero-fill ranges before kernel entry. Keep truncated/incomplete and malformed
record rejection; final RUNAD must never enter a partial kernel.

Set nondefault cache and system-drive requests through physical Forth input.
Check the complete record at monitor return, after resumed loading and at
kernel capture. Verify effective cache capacity and SYS on the requested drive,
including C: lookup. Cover cache disabled and invalid setter attempts using
the existing rejection semantics. Change kernel capture code only if these
checks reveal a reset; retain its existing validation contract.

### B3: small boot feedback

Add boot-only ROM-console output and progress accounting to the existing
[loader](../../platform/altirraos/loader.s) and OF page-copy callback. Prefer a
shared small output helper in the loader's existing reservation. Preserve the
callback context and any borrowed IOCB fields; never reopen E: or disturb the
paused reader's channel. Output occurs only while the cartridge is disabled.

Print the boot banner once after safe setup, label each loading stage, and
count only completed work. Print a short failure message when the native
loader detects an error, then keep its existing refusal to enter Exec.
Console-output failure must not corrupt image validation or settings.

Check small payloads, exact 16 KiB multiples, final remainders, zero-fill and
an invalid record. Seed a visible text marker before startup and verify it
survives both OF initialization and the countdown, with the banner appended
below it. Verify no extra delay beyond console output was introduced.

### B4: cartridge integration, demo and documentation

Update [test_of816.py](../../tools/test_of816.py),
[test_of816_shell.py](../../tools/test_of816_shell.py),
[test_demo.py](../../tools/test_demo.py), and
[test_cartridge.py](../../tools/test_cartridge.py) for the new boundary. In
particular, cartridge loading is intentionally incomplete at `of_start`;
assert final segment/callback totals and zero remaining bytes after monitor
return and resumed loading. Retain the final interlock, unmapped-window, OS
restoration, stack/domain and ownership checks.

Build the user's bitmap shell preview with no primes through
[build_demo.py](../../tools/build_demo.py), preserving OF816, five-second
autoboot, the matching system/work disks, pinned ROM and upstream notices.
Generate both old/new Atarimax CAR images and the raw BIN from the same boot
XEX. Verify the ZIP's boot files, guide, licenses and checksums; leave listings,
manifests and test output in the development directory. Do not publish it.

Update the monitor guide, applicable distribution guides and platform startup
description together. Record the implementation in history/development and
update their indexes, this plan's status and the roadmap.

## Validation and memory gates

Use the development tier: host suite plus the focused emitted checks above.
Use the compiler selected by [actionc.json](../../toolchain/actionc.json) and
the existing OF816 pin. Reuse unchanged native compiler output where practical;
raw/optimized compiler probes are required only if a compiler-facing interface
actually changes.

Pin the actual ROM, emulator binary, configuration, boot XEX, native image and
media hashes in the execution record. Use the bitmap demo's recorded machine
pin, based on [altirra-gem-vdi.json](../../toolchain/altirra-gem-vdi.json), and
its selected emulator, PAL timing, 4 MiB RAM, VBXE and disk settings. Adapt the
OF runners to that recorded pin rather than silently using an older profile.

| Route | Required focused checks |
| --- | --- |
| Default XEX, autoboot | OF before payload; five seconds including clock wrap; resumed loading; default settings; bitmap shell and EXIT |
| Default XEX, manual | Late/held-key cancellation; Forth arithmetic; nondefault settings survive loading/capture; resumed loading; disk command and EXIT |
| New Atarimax, autoboot | Paused and resumed cart reader; final record totals; correct interlock/mapping; shell and EXIT |
| Old Atarimax, manual | Forth return and modified settings; resumed reader; final totals; shell and EXIT |
| Monitor/loader failures | Busy IOCB and BYE park; native bounds/record/incomplete rejection; live stack and OS coexistence |

Retain guard, adjacent-DP, aperture, register, ownership, OS restoration and
bounded-completion assertions relevant to each case. Test guards before Exec
reinitializes borrowed monitor storage. Keep full qualification and hardware
claims separate. If retaining XLOS preview claims, rerun the affected boot
cases against the recorded patched ROMs with explicit diagnostic overrides;
those results do not extend the supported platform contract or change the
bundled AltirraOS ROM.

Target reserved bank-zero delta: **0 fixed runtime, 0 root/kernel, 0 per public
Task, 0 idle and 0 additional boot-only bytes**, counting guards, alignment
and unused reserved capacity. Continue borrowing the existing 3,392-byte OF
root/kernel/DP arenas and two free upper banks. The loader has a 5,120-byte
reservation; OF code/state in the kernel arena retains its 1,264-byte limit
and guarded caller stack. Keep the cartridge's 1,024-byte boot reservation.

Place new saved-context fields, the stack anchor and small progress counters
inside these existing boot reservations. Report actual code/state growth,
temporary page-one stack use and the final reservation deltas per slice.
Do not weaken guards or expand Task stacks to accommodate the change. A layout
that cannot meet these limits needs an explicit revised memory budget before
implementation proceeds.

Completion means all selected development checks pass, boot text and settings
survive the monitor return, both cartridge forms resume correctly, the bitmap
shell ZIP is built and verified, and the documentation describes the new
sequence and unsupported behavior. No remote-boot capability is claimed.

The completed checks comprise 364 host tests, 12 focused emitted loader cases,
both XEX monitor routes, BYE/busy-channel exits and both cartridge forms. The
four shell routes exercise 42 commands each, guards, ownership, persisted media
and EXIT. The local bitmap/no-primes ZIP contains both CAR forms and a raw BIN;
all 18 payload checksums and the matching embedded XEX were verified. Reserved
bank-zero deltas are zero in every slice; emitted adapter and loader storage
grow by 71 and 368 bytes respectively, within their existing reservations.
Bounded patched-XLOS A/F default-XEX startup/EXIT diagnostics also passed.
These results remain development evidence, without a full qualification matrix,
hardware claim or publication.
