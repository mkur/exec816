# ARC on the SDX personality

A1/A2 admit the pinned 6502 SDX 4.50 `ARC.COM`, `ARCLST.OVL` and `ARCEXT.OVL` for listing/extraction as
ordinary Exec Processes. [Manifest](../../compat/sdx/arc-450.json),
[plan](../plans/spartados-personality-implementation-plan.md),
[service contract](../reference/sdx-services.md) and
[execution record](sdx-arc-a1.json) define the development scope. Mutation remains disabled until its own acceptance gate passes. This is not
full hosted-system qualification.

## A1 loading and listing

`L archive [mask ...]` and `V archive [mask ...]` execute the original command
and listing overlay, with the checked six-inline-byte helper patch. `N` and `W`
are the only additional admitted flags. Hardware `H` is rejected before entry.
Guest A: maps to the immutable `sdx_drive_a` root; CAR: maps to
`sdx_car_root` (both default RAM:). CAR: accepts only the exact admitted overlay
name and verifies its original size/CRC32 before relocation and execution.
No binaries are redistributed and no global assignments are changed.

The loader accepts caller-owned import bindings. Each Image supplies its own
`_ARC` export, rather than a global current-parent pointer. One overlay runs
synchronously above the main image at $4A6C; its frame and trap level are
retired before returning to the main command. All overlay-owned native handles
are closed on return and the overlay extent is cleared. Native file loading
and waits release physical page one through the existing service bridge.

COMTAB is private guest address $1000. ARC's arithmetic workspace extends through
COMTAB+$10A; the old $0600 placement collided with FILE_P and the kernel entry.
Ordinary pointers select the private bank. Audited header reads and inline
PRINTF operand sites select the private direct page; strings cannot cross its
256-byte boundary. The formatter admits ARC's 587-byte help record structurally,
although help execution is not yet admitted. The sole VPRINTF callback is the
pinned main module's single RTS leaf: the adapter consumes its format and emits
nothing, matching that leaf. General callbacks remain unsupported.

`__MISC` was traced in the original SDX cartridge at $BF4E. A=1 reads DAYTIME;
with the variable absent, it returns A=$9A, X=$FE, Y=$9B. ARC tests X to choose
day/month and 24-hour output. The personality freezes that policy and the
40-column console width, matching the original control. DIV_32's zero divisor
produces zero with carry, which preserves ARC's 100% display for empty entries.

`tools/sdx_arc_audit.py` verifies the frozen inputs and walks reachable code,
skipping inline records and following the main export table and trap entries.
It inventories 704 main, 244 listing, 488 extraction and 1,471 addition
instructions. None of those decoded instructions is SEI. The extraction inventory includes both targets of each mutable LZW code/output
vector. Addition remains preparation, not admission.

The optimized A1 run covers L/V, masks, an empty member, missing/corrupt overlays
and subsequent recovery. Four outputs match original SDX byte for byte. Every
Process result is checked; the original control records output but does not
capture an exit code. Native cleanup checks handle/trap retirement, guards and
heap recovery. Small raw/optimized shape probes cover the shared ABI; the
loader probe exercises two private parent bindings with nonzero import addends.
MD5 and the existing service suite provide regressions. Full run artifacts stay
under `build/sdx-arc/`.

```sh
python3 tools/test_sdx_arc.py --group reference --output build/sdx-arc/reference
python3 tools/test_sdx_arc.py --group a1 --output build/sdx-arc/a1-final
python3 tools/sdx_arc_audit.py --help
```

A1 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and unused capacity. The enabled profile retains its 544-byte guarded
DP pool. Each Image's upper Session grows by **32 bytes**, from 864 to **896**.
The private 64 KiB guest bank still uses 131,072 backing bytes; resident upper
capacity is unchanged. Listing load temporarily stages 1,999 bytes plus the
ordinary loader layout and its 8,192-byte relocation bitmap. The test program's
12,288-byte upper static arena is test-only.

## File-date dependency

`DOS.SetFileDate` is implemented as a public reusable path operation, following
Amiga semantics. Its [write contract](../reference/filesystem-writes.md) covers
ownership and representable dates. The [execution record](dos-file-date.json)
contains 15 raw RAM checks and 26 optimized RAM/SDFS checks: public argument
marshalling, exact dates, live-lock rejection, invalid values, missing paths,
heap/guard retirement and independent persisted timestamp bytes. The 47 DOS
host tests pass. Fixed and per-Task reserved bank-zero growth are both zero.
The test-only upper static arena is 4,096 bytes.

```sh
python3 tools/test_dos_file_date.py --raw --output build/sdx-arc/file-date-raw
python3 tools/test_dos_file_date.py --output build/sdx-arc/file-date-opt
```

## A2 extraction

`X archive [mask ...]` and its `E` synonym now run the original extraction
overlay. Supported methods are old/new stored (1/2), RLE (3), Huffman plus RLE
(4), 12-bit LZW plus RLE (8), and SDX LZW (15). Method 15 uses a 16-bit byte sum;
the others use ARC CRC-16. The independent host fixture writer/reader and original
SDX cartridge controls agree on all six methods. The original algorithms run
inside the guest; the adapter does not implement a decompressor.

Native output uses owned handles, bounded writes and public SetFileDate after
successful Close. A captured timestamp must be representable before output is
opened. Output cannot exceed the member's declared length. A short header,
packed extent beyond the archive, inconsistent stored length or unsupported
method fails before the member is opened. These checks are not a sandbox or a
general malformed-compressor-stream validator. Member names are bounded 8.3
leaves; directory/path members, hardware H, encryption G and P/T are excluded.

Overwrite Y/N/A is read from ordinary Process input. W skips prompts and
suppresses warnings, as the original binary does. A CRC mismatch prints a
warning without changing the original zero exit status; a native I/O failure
still returns primary 20 and its first native cause. Failed/BREAK extraction can
leave a partial member; the input archive is unchanged. No successful completion
or timestamp preservation is claimed for that partial output.

The [A2 record](sdx-arc-a2.json) contains **525 optimized RAM checks**: all codecs,
empty/binary/multiple members, 65,537-byte streaming, overwrite decline/accept,
CRC output, truncation/length/method rejection, missing/corrupt overlays, locked
targets and subsequent listing. It adds three **33-check native SDFS runs**:
normal persistence, real full media and BREAK after the first output-write
service. Independent directory/file read-back verifies bytes and timestamps.
Full media reports IoErr 221 with a valid 37,120-byte prefix; BREAK reports 304
with a zero-byte partial member. The BREAK run observed 15 PAL ticks (300 ms)
between request and retirement using the test's byte RTC counter; this is an
observation on the pinned configuration, not a universal latency guarantee.
The normal run saw 45,739 native IRQs. Small raw/optimized ABI probes each pass
44 checks. All 15 SDX host tests pass.

A2 adds **0 fixed and 0 per-Task reserved bank-zero bytes**, including guards,
alignment and spare capacity. Each upper Image Session grows **560 bytes**, to
**1,456**, including the private directory FIB, captured output pathname/date,
length ownership and handle-size table. The extraction overlay reaches $9438,
inside the same private bank; staging needs 1,912 bytes, below A1's 1,999-byte
maximum. Existing guest-bank backing and resident capacities are unchanged.
The expanded test reserves a 16,384-byte upper static arena only.

```sh
python3 tools/test_sdx_arc.py --group reference-extract --output build/sdx-arc/reference-extract
python3 tools/test_sdx_arc.py --group a2 --output build/sdx-arc/a2-final
python3 tools/test_sdx_arc_disk.py --output build/sdx-arc/a2-sdfs
```
