# XLOS support in the SDX firmware adapter

[Plans](README.md) · [ROM audit](../history/xlos-sdx-audit.md)

Deliver one current adapter and one demo image admitting the pinned AltirraOS
3.44/816 and stock XLOS816F 2.48/2.49. Preserve guest semantics, one active
page-one lease, BASIC parking, COP `$50`/OS `$00`, native scheduling and existing
memory reservations. This is development support under pinned emulator setups;
physical accelerator/FujiNet qualification is separate.

## Architecture

Keep firmware identity and ROM entry/stack contracts in a machine-readable
catalog. Generate assembly constants/tables and validate catalog inputs against
the exact ROM SHA-256 on the host. Runtime admission checks CRC-32/ISO-HDLC over
all 14,336 CPU-visible ROM bytes, plus original emulation vector destinations.
This is accidental-change identification, consistent with the SDX executable
catalog, not a cryptographic authentication boundary. ROMs with modified visible
bytes are unsupported. The unavailable `$D000–$D7FF` file interval is excluded.

Capture visible ROM bytes into the existing 16 KiB upper shadow source before
changing mapping. Identify that snapshot, retain original NMI/IRQ destinations,
and initialize the three existing bank-zero jump operands before enabling
interrupts. Never chain through already-patched hardware vectors. Unknown
firmware fails before mapping/underlay changes. Preserve backup/restore ordering
and foreign-mapping rejection. No XLOS ROM bytes belong in the distribution.

Use the snapshot's unused I/O gap for installation-only checksum/profile
scratch; do not enlarge the two-byte ownership record or overlap resident state.
Keep ROM/driver state serialized and immutable after publication. No firmware
callbacks or Task dispatch cross installation/removal.

## Executable slices

| Slice | Change | Development acceptance |
| --- | --- | --- |
| XF0 | Catalog, generator and implementation contract | Host validates hashes, visible checksums, vector destinations, generated products and rejection of altered inputs. |
| XF1 | Shared snapshot/admission and original-vector chaining; remove embedded expected ROM | Emitted install/remove on all three ROMs, unknown-image rejection, repeat/foreign-mapping failures, exact underlay and vector restoration. Existing AltirraOS path remains covered. |
| XF2 | Firmware-specific stack accounting and asynchronous transitions | Review XLOS COP/CIO/editor/native VBI/IRQ paths; establish a conservative reserve bound. Current minimum-anchor scrolling, borrow gates and context/guard checks pass. Include a small raw/optimized bridge check. |
| XF3 | Current application and lifetime coverage | Real MD5, argument-free ARC and archive operations, EDX physical editing/save, and retained FastBasic Run/reset under XLOS; include native peer/SIO and shutdown coverage. No ROM-image/jump injection in acceptance. |
| XF4 | Contract/evidence and rebuilt demo | One OF816-enabled combined-ATR/XEX/cart distribution; five-second autoboot, ported tools and WORK assignment retained. Pin actual firmware/configuration in results and record actual boot routes/limits. |

Implement and check each slice before advancing. An insufficient stack bound
must be resolved in the shared stack contract and its callers before admitting
the affected firmware; a passing canary alone is insufficient. Unsupported
third-party native/PBI interrupt handlers and arbitrary firmware allocations
remain outside the profile.

## Budget and validation

Target **zero additional reserved bank-zero bytes**: fixed, root/kernel, each
public Task and idle, including guards/alignment/spare capacity. Reuse existing
three JML operands and the 64 KiB bridge reservation. Record actual emitted
growth separately; no private driver-specific kernel service is needed.

Use the pinned compiler, optimized fixtures and pinned emulator. Run host checks
and focused emitted-code regressions; small raw/optimized coverage is for the
changed language/bridge boundary, not duplicate full application matrices.
Record failures and exclusions explicitly. Development checks do not extend
full hosted-system qualification. Preserve published release assets/tags;
new demo artifacts are development outputs.

## Execution

**XF0–XF4 are implemented.** The
[implementation history](../history/xlos-sdx-support.md) records the executed
development checks, 119/121-byte stack bounds, unchanged bank-zero reservations,
upper-image cost and rebuilt demo. Exact input/result hashes and tested boot
routes are in the [machine record](../development/xlos-sdx-support.json).
The original audit remains a historical pre-refactor record; release and
physical-hardware qualification are separate work.
