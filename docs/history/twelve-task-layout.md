# Twelve-Task layout

[Historical records](README.md) · [Task capacity](../architecture/task-capacity.md)

The standard XEX/OF816 demo now provides twelve public Task slots, including
root, plus private idle. Four additional Tasks can wait or run without replacing
the existing kernel, Task API, boot arena or physical pools. Cartridge launching
is unsupported. The [high-RAM audit](high-bank-zero-audit.md) established the
usable RAM; the [platform contract](../reference/platform.md#bank-zero-memory-budget)
publishes the current ownership map.

## Implementation

Public slots 8–11 own DPs `$9000`, `$9100`, `$9200`, `$9300`; their stack bases
are `$9410`, `$9950`, `$9E90`, `$A3D0`. Three allocations are 1,312 bytes and
the fourth 2,560, with two 16-byte outer guards each. Idle becomes logical slot
12 while retaining DP `$1500` and stack `$60D0`. Generated explicit DP arrays
replace the generator's former assumption of one contiguous sequence. Kernel
scheduling already consumes those per-slot arrays.

Loader and native entry require MEMTOP at least `$BC00` and claim RAM through
MEMLO `$BC00`, restoring original MEMLO on normal shutdown. The minimum and
claim are generated from the profile; the standalone image/console boundary
remains `$9000`. The OS display stays at `$BC20–$BFFF`. All existing boot
lifetimes and the five-second OF816 autoboot remain intact.

Task, Process and DOS capacities follow twelve. The SDX personality admits
supported maps with at least eight native Tasks, retaining two guest slots and
its 544-byte guarded guest-DP pool at the existing address. AES clients, windows
and console-instance limits are unchanged.

The composed desktop exceeded the previous 64-entry writable-range packaging
cap. The machine-readable build limit is now 96. Its table remains allocated
in upper memory, with the existing count/pointer format and exact permissions;
private metadata and stack guards do not become writable application buffers.
The rebuilt desktop has 67 exact ranges (58 previously), adding 72 upper bytes
to the serialized table; unused entry capacity is not preallocated.
No public Task/Process ABI version or wire layout changed. All demo programs
were rebuilt against the resulting image.

## Budget

Compared with the previous eight-Task SDX demo:

| Change | Reserved bank-zero bytes |
| --- | ---: |
| Fixed Exec, root, kernel, existing public pools, idle | 0 |
| Three ordinary public pools, including DPs and guards | +4,800 |
| Third large public pool, including DP and guards | +2,848 |
| Reclaimed OS reservation | −11,264 |
| Net total reservation change | **−3,616** |

The standard SDX-enabled build reserves 55,008 bank-zero bytes and leaves
**10,528 free**, including all guards, padding and reserved slack. Its native
Task metadata adds 512 upper bytes, Process records 512 and DOS slots 64;
generated pool arrays and the exact writable-range table also grow in upper RAM.
The register probe borrows another 128 high-RAM bytes only while testing;
production reservations do not grow for diagnostics.

## Development checks

The [frozen evidence](../development/twelve-task-layout.json) records the actual
compiler, ROM, emulator, media, image hashes and execution scope. This is the
development tier; full release qualification remains separate.

- Host tests check exact twelve-pool placement and budget, unchanged existing
  domains, SDX guest pages, metadata capacity, rejected overlaps/DP aliases and
  the writable table's exact disjoint permissions and capacity bound.
- The existing full-capacity signal fixture runs raw and optimized with all
  twelve Tasks live. It verifies complete register restoration in each public
  slot, independent buffers, overflow rejection, retirement, slot reuse and
  guards. Register capture covers the new high DPs and stacks.
  An additional optimized case uses 8-bit A/X with decimal mode and hidden B.
- An optimized twelve-Task burst exercises the full wake queue and protected
  IRQ window. The later packaging-limit change was rebuilt against those
  fixtures and compared byte-for-byte with their executed XEX images.
- A new managed-pool fixture admits three simultaneous 2,560-byte requests,
  rejects a fourth, fills the eight ordinary pools and rejects a thirteenth
  public Task. Each large worker retains six local arrays across ROM output,
  real preemption and a kernel wait. Saved NMI frames include slot 11 with
  `D=$9300`; measured peak stack use is 1,583 bytes, leaving 721 above the
  interrupt reserve. Every Task retires and ownership returns to baseline.
- Injected MEMTOP `$BBFF` is rejected by both loader and native entry before
  adapter-state writes, high-pool initialization or vector installation.
- The rebuilt graphical programming demo checks two shells beside BASIC,
  a ten-Task native pipeline, floating-point Run/Stop with nine Tasks, finite
  Run, normal GUI close, final EXIT and existing guard/ownership/OS-restoration
  assertions. Its ZIP contains OF816, matching media, pinned ROM, guide,
  licenses and checksums.

Relevant commands:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_task_capacity.py --compiler-dir build/actionc \
  --release-compiler --bridge-dir build/altirra-irq-bridge \
  --capacity 12 --kernel-bank 2 --mode opt --flags 0 \
  --output build/twelve-task/capacity-opt
python3 tools/test_twelve_task_pools.py --output build/twelve-task/managed
python3 tools/build_demo.py --compiler-dir build/actionc --release-compiler \
  --gem-desktop --basic-workbench --output build/twelve-task/demo
python3 tools/test_twelve_task_demo.py --bundle build/twelve-task/demo
```

Select raw mode for the focused context probe and optimized `--burst 3` without
register capture for the queue/IRQ case. No full raw desktop or release matrix
was run.
