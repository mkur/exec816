# SDX loader and Process development

The P3 native record decoder passes development checks on the pinned
AltirraOS/65816 platform. Process admission and P4 services remain in progress.
[Plan](../plans/spartados-personality-implementation-plan.md) ·
[Execution record](sdx-loader.json)

`SDXFILE.Load` decodes conventional `$FFFE` blocks, `$FFFD` relocations,
`$FFFB` imports and `$FFFC` exports into an unpublished caller-owned bank.
It supports forward references, nonzero assembled origins, page alignment and
BSS. Limits are 16 blocks, 32 exports and 65,536 serialized bytes. The staged
input remains immutable and must outlive the returned layout. Releasing the
layout does not release the caller's bank.

Unknown imports, duplicate blocks/exports, malformed or overlapping fixups,
fixups into BSS, invalid exports and placement overflow fail explicitly.
Absolute and extended-memory records are unsupported. Failure can change the
unpublished destination; the caller must discard it. This decoder grants no
permission to execute a third-party module.

The optimized run passes 61 checks, comparing every placed byte of all five
pinned MD5/ARC modules at `$2000` and `$4100` against the independent host
parser/relocator. It also tests forward references, alignment, BSS and malformed
records. The focused raw build passes 20 checks with MD5 at one placement and
the small structural cases. Both run as emitted native code, preserve platform
stack guards and restore the memory ownership table at shutdown.

```sh
python3 tools/test_sdx_loader.py --output build/sdx-loader/opt
python3 tools/test_sdx_loader.py --case raw --output build/sdx-loader/raw
```

Reserved bank-zero change: **0 fixed bytes, 0 per Task**. The bounded layout
and transient 8,192-byte relocation bitmap use the upper heap. The bitmap is
released before a successful return; error paths release both allocations.
These are development component results, not hosted-system qualification.
