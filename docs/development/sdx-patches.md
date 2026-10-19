# SDX patch infrastructure

Status: partial implementation of P0/P1, 18 October 2026.
[Plan](../plans/spartados-personality-implementation-plan.md) ·
[Design](../plans/spartados-personality-design.md) ·
[Execution record](sdx-patches.json)

CRC32 identification and checked patch application now run as native Exec Task
code. The audited MD5 interrupt-mask edit and ARC inline-argument replacement
have executable component tests. **MD5 and ARC do not yet run as Exec Processes.**
The [next runtime slice](sdx-runtime.md) implements synthetic guest page-one
ownership and IRQ/NMI bridges. Production guest admission, complete interrupt
proof, SDX services and overlay loading remain open. No demo or release was rebuilt.

## Implemented behavior

- [Input preparation](../../tools/prepare_sdx_inputs.py) checks the distribution
  and module SHA-256 pins, extracts MD5 from the Toolkit archive, and reconstructs
  the four ARC modules from recorded cartridge ranges. Downloads and originals
  remain separate from patched images. An existing differing input is rejected.
- [Manifests](../../compat/sdx/) identify the five original files by size and
  CRC-32/ISO-HDLC, with SHA-256 retained for host verification. Entries remain
  explicitly `patch-probe-only`; an empty overlay patch list is not an execution
  approval or a completed instruction audit.
- The [host loader oracle](../../tools/sdx_patch.py) checks exact original
  preimages, bounds, patch overlap and whole relocation-word intersections;
  performs ordinary SDX relocation/import binding; checks relocated preimages;
  then applies replacements and their typed fixups. It returns a private bank
  image and diagnostics without publishing an executable. No second relocation
  pass touches replacement bytes.
- [SDXIDENTIFY](../../lib/dos/sdxidentify.act) hashes staged bytes through an
  ordinary native function, then selects a generated module ID. It supports
  split updates for a 65,536-byte staged input. Ambiguous size/CRC selectors fail
  host generation. CRC32 is a version/corruption check, not authentication.
- [SDXPATCH](../../lib/dos/sdxpatch.act) accepts at most sixteen prepared spans
  in an unpublished private bank. It checks their extents, disjointness and all
  expected bytes before writing any replacements. A mismatch in a later patch
  leaves earlier sites untouched. Immutable expected/replacement buffers and
  exclusive ownership of the unpublished bank are caller responsibilities.

The native transaction currently consumes prepared spans. Native SDX record
decoding, relocation, import resolution and generation of those spans are still
part of the loader work. The host oracle supplies them in development fixtures.
This distinction is why P1 and P3 are not marked complete.

The [machine-readable checksum ABI](../../abi/sdx.json) generates assembly
constants, the shared CRC table and the Action module catalog. Native builds
include the checksum wrapper only with `sdx_patches=True`. This enables component
testing; it does not enable an SDX Image kind or change shell command admission.
No new COP selector or Task ABI was introduced.

## Binary edits and executable checks

MD5 block 1 offset `$041A` changes `SEI` to `NOP`, retaining the surrounding
`PHP`/`PLP`. Original and patched binaries both pass controls under original
SDX 4.50: empty input, `abc`, a 65,537-byte streamed file, multiple filenames,
and matching/mismatching checksum lists. Redirected mismatch output contains
inverse ATASCII `BAD` (`C2 C1 C4`); the fixture preserves those exact bytes.
The missing-file command was run, but its redirected stdout is empty and the
runner does not capture command return codes or stderr. These controls do not
establish Exec error translation or the complete MD5 instruction audit.

ARC block 1 offsets `$05ED–$0612` receive a 38-byte replacement, including two
trailing NOPs. Stack-relative `3,S`/`4,S` access the actual outer return address;
`STA $EF,X` stores through D. The helper preserves its original register/flag
contract and all six argument bytes. Its three count-variable operands receive
new block-relative fixups after the original relocations retire.

The maintained [assembly](../../compat/sdx/arc-inline.s) is independently
assembled and compared byte-for-byte with each relocated replacement. Original
helper controls use D=DBR=0; patched runs use private D and an upper-bank DBR.
Tests cover two code placements, two guest banks, three stack depths, hidden B,
both nested returns, carry from `$7FFE` to `$8004`, overflow, and distinct upper
low-page sentinels. The helper probes disable IRQ/NMI. Their interruption and
production entry tests remain open; they do not reuse the earlier NMI experiment
as qualification.

The selected development checks are:

| Check | Result and scope |
| --- | --- |
| Host transaction tests | 11 passing tests, including identity/preimage failures, relocation intersections, overlap, branch range, capacity, missing imports/entry and repeat application. |
| Assembly probes | Two native/guest bank pairs, 2/3 and 5/6; each runs nine CRC vectors with split updates and twelve ARC original/patched cases. |
| Native Task fixture, optimized | 43 checks: five-file identification, corruption outside patch sites, two placements for both applications, rollback and bank-edge failures. |
| Native Task fixture, raw | 37 focused ABI/layout checks; one placement per application. |
| Default build regression | 58 DOS checks plus stack/ownership checks, with SDX checksum support disabled; the existing eight-slot fixture was replayed on the installed paced emulator. |
| Existing host suite | 509 tests: 503 pass, four skip, two pre-existing failures in C-program ABI/provider-size expectations. |

The native Task fixtures use the pinned actionc revision and normal platform
interrupts. Their root-stack touched-byte observations are 87 bytes optimized
and 91 bytes raw, with guards and ownership checks passing. These observations
are lower bounds for these component fixtures, not guest-runtime stack budgets.

## Cost and remaining gate

The native checksum uses 52 bytes of code, a 31-byte Action ABI wrapper and a
1,024-byte table: **1,107 bytes consumed within the existing upper-memory native
work reservation**. There is no table alignment padding. The wrapper borrows
three pointer bytes and four CRC bytes from existing native DP scratch. The
Action identification/patch routines are ordinary upper-memory image code.

**Reserved bank-zero delta: 0 fixed bytes and 0 bytes per Task**, including
guards and unused capacity. The proposed two-page guest DP pool has not been
allocated; no guest descriptor or page-one snapshot pool is installed.

On the pinned PAL 8× machine, isolated CRC measurements are about 18 ms for
MD5.COM and 24 ms for ARCADD.OVL. A 65,535-byte crossing-buffer case takes about
337 ms, roughly 190 KiB/s. These measurements include the fixture call/return
and display bus stalls, exclude disk I/O, and disable IRQ/NMI. They are not
hosted loader or serial-latency qualification. Exact samples and hashes are in
the execution record; no SHA-256 routine was added to the target.

The next runtime gate is P2: the pinned ROM's emulation NMI entry touches
DBR-relative `D40F` before the VBI hook. Guest DBR therefore cannot enter the
current OS path unchanged. Production early routing, fast IRQ handling,
page-one exchange, ordinary Task preemption and native service suspension must
pass together before either command is admitted. The subsequent loader and
MD5/ARC service milestones remain open in the plan.

## Reproduce

Use the pinned ROM/emulator and compiler described by the repository's
[build instructions](../contributing/building.md). Input preparation additionally
needs `nomarch` for the Toolkit MD5 archive; pass its path explicitly if it is
not at the runner's existing research-build default.

```sh
python3 tools/prepare_sdx_inputs.py --nomarch /path/to/nomarch
python3 tools/generate_sdx.py --check
python3 -m unittest discover -s tests -p test_sdx_patch.py
python3 tools/test_sdx_md5.py --group reference --inputs build/sdx-inputs/md5 --output build/sdx-md5/reference
python3 tools/test_sdx_md5.py --group reference-patched --inputs build/sdx-inputs/md5 --output build/sdx-md5/reference-patched
python3 tools/test_sdx_patches.py --banks 2 3 --output build/sdx-patches/banks-2-3
python3 tools/test_sdx_patches.py --banks 5 6 --output build/sdx-patches/banks-5-6
python3 tools/test_sdx_native.py --case opt --output build/sdx-native/opt
python3 tools/test_sdx_native.py --case raw --output build/sdx-native/raw
```

Full media, binaries, disassemblies, compiler outputs and test logs stay in
`build/`. Original third-party SDX executables are not added to the repository
or the distribution by this slice.
