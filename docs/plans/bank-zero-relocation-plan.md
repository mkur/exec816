# Bank zero relocation and boot manifest retirement plan

[Implementation plans](README.md) · [GEM integration assessment](gem4xe/exec816-integration-assessment.md)

Status: implemented on 2026-10-01. See the
[development record](../development/bank-zero-relocation.json) for executed
checks, source pins, image hashes and reservation deltas. The design and
acceptance criteria below preserve the approved plan.

Move the 256-byte AltirraOS adapter state page from `$2000` to `$0800`, then
move the resident image's 2 KiB global-data arena from `$8800` to upper RAM.
After successful startup, release the 2 KiB boot-manifest reservation.
These are the first memory-layout changes for the VBXE-only GEM integration.
Together with reducing the low OS reservation to `$0000–$07FF`, they recover
10,240 bytes of bank zero after startup in the standard eight-Task configuration.

Use three executable implementation slices, followed by the integrated demo
check. Keep current Task stack and DP addresses, sizes, guards and capacity
through these slices. Leave the newly available holes unallocated until a
later layout change assigns them. The boot manifest occupies `$6000–$67FF`
only until its startup consumers have retired.
The standalone GEM repository is outside this change.

## Intended layout

| Storage | Before | Implemented |
| --- | --- | --- |
| Low OS reservation | `$0000–$1FFF` | `$0000–$07FF` |
| Adapter state and embedded contexts | `$2000–$20FF` | `$0800–$08FF`, same offsets and size |
| Resident compiled globals, arrays and literals | `$8800–$8FFF` | 2 KiB in the kernel's upper bank |
| Task stacks and DPs | Current generated pools | Same pools |
| Boot state | `$2C00–$2CFF` | Same reservation, including adoption status |
| Boot manifest | `$6000–$67FF`, retained at runtime | Same loading reservation; reusable after successful startup |

Boot assumes no resident Atari DOS. Exec's own DOS and filesystem services
continue to operate. Preserve the ROM's low-memory workspace and existing OS
transitions. Keep the current upper bank-zero boundary at `$9000`.

For global data, reserve 2 KiB after all resident metadata in the selected
kernel bank, align the start to 256 bytes, and start emitted kernel code after
that arena. Derive the address from the completed layout; do not give it a
separate hard-coded bank number. With the recorded eight-Task demo's metadata
ending at `$01:0B54`, the proposed arrangement is:

| Upper-memory region | Proposed address |
| --- | --- |
| Alignment padding | `$01:0B54–$01:0BFF`, 172 bytes |
| Global-data arena | `$01:0C00–$01:13FF`, 2,048 bytes |
| Emitted kernel code | From `$01:1400` |

The rebuilt standard demo confirms this placement.
Other capacities, metadata sizes and kernel-bank selections derive their own
addresses. Retaining the current arena capacity makes the first move bounded;
future growth can enlarge it in upper RAM. Reject overflow explicitly.
Do not reserve a new whole bank merely for this arena. Recompute actual code
bank occupancy after emission, since shifting code may cross a bank boundary.

## Slice 1 Move the adapter state page

Make the platform profile's state region the authority for the base address.
Represent fields inside that page as offsets and generate their resolved
assembly and Action! constants. Preserve existing symbol names where useful.
The implementation touches these connected sources:

- [Platform profile](../../platform/altirraos/memory-1m.json) and
  [memory generator](../../tools/generate_memory.py): set state to `$0800`
  with 256 reserved bytes, reduce `os-low` to 2 KiB, and set `memlo_limit`
  to `$0800`. Validate the entire page against all other reservations.
- [Adapter layout](../../platform/altirraos/layout.inc),
  [gateway definitions](../../abi/exec816-v1.json) and their
  [generator](../../tools/generate_exec_abi.py): derive status, counters,
  saved vectors, scheduling state, embedded contexts and probe addresses from
  that base. Regenerate both language includes through the generator.
- [Task generator](../../tools/generate_tasks.py): replace the independent
  `$203A/$203B` wake and IRQ fields with the same generated definitions.
  Preserve owner-pointer relationships, including the kernel context formerly
  at `$2060` and now at `$0860`.
- [Native runner](../../tools/native_program.py),
  [OS boundary tools](../../tools/os_boundary.py), emitted test fixtures and
  debugger observers: obtain state and field addresses from generated build
  metadata or symbols. Update status breakpoints, dumps, domain checks and
  fixtures that currently name `$2000`, `$2024`, `$2034`, `$203A` and related
  addresses. Audit references by meaning; unrelated masks and upper addresses
  are not relocation targets.

Update both supported four- and eight-Task builds together, along with the
small hosted/cooperative fixtures that use the same adapter. Do not retain a
second state layout. This is a platform placement change; COP signatures,
service selectors and public Task record layouts stay the same. Rebuild all
affected programs and generated bindings.

### Validate bounds before writing state

The current [hosted entry](../../platform/altirraos/hosted.s) clears `STATE`
before comparing the saved `MEMLO` with the state base. Move the bounds decision
ahead of the first state-page write. A rejected entry must report through
bootstrap-owned storage or a rejection label without modifying memory it has
not claimed.

The [banked loader](../../platform/altirraos/loader.s) must accept
`MEMLO <= $0800` and reject larger values before handing off. Check the
original saved MEMLO after loader reservation, not the raised live value.
Cover direct XEX entry and the OF816 path; keep boot-only storage alive until
its final callback or frame has retired. Preserve the existing IRQ/NMI entry
protocol and vector restoration while changing the preflight order.

### Retain pool placement and correct accounting

The lower ownership boundary and the Task pool placement policy are separate
in this slice. Keep existing pools at their current addresses instead of
lowering the first-fit search floor and silently moving every worker DP.
Record the new free holes in the generated map.

Replace the hard-coded OS total in
[Task capacity accounting](../../tools/task_capacity.py) with the sum of the
actual OS reservations. Update [four-Task accounting](../../tools/ports_budget.py)
as well. The state page still costs 256 bytes: moving it saves zero bytes by
itself. The 6,144-byte gain comes from shrinking `os-low`; do not count the
vacated state page a second time.

### Slice 1 acceptance

Run host checks and focused raw/optimized emitted-code cases. Require:

- `MEMLO=$0800` succeeds; a value just above it rejects without writing the
  state page. The usual cold-boot MEMLO succeeds through direct and monitor
  handoff paths.
- Status, timer counts, wake flags and context-owner pointers use `$0800`
  plus their defined offsets. A sentinel at the retired `$2000–$20FF` page
  remains unchanged while Tasks run.
- A bounded preemption and IRQ-wake workload completes with intact stack/DP
  guards and restored registers, vectors and MEMLO. Include a selected NMI
  transition case because startup ordering and asynchronous state access are
  affected.
- Four- and eight-Task generated pool addresses match the pre-change layouts;
  the latter's total reserved bank-zero bytes fall to 55,392.

Use the relevant cases in [Task tests](../../tools/test_tasks_exec.py),
[preemption tests](../../tools/test_preemptive.py) and
[boot-setting tests](../../tools/test_boot_config.py); add a small focused
relocation fixture for the preflight and retired-page checks.

## Slice 2 Move compiled global data to upper RAM

Finalize global placement after all resident metadata reservations, including
optional console and captured boot settings, and before compiler emission.
Publish an explicit `image_data` region and resolved `data_origin` in the
generated memory description. Advance `code_origin` past its full capacity
and alignment padding. Remove the bank-zero `image_near` reservation and
replace its `NEAR_BASE/NEAR_END` assumptions with the new data-region contract.

Keep protected metadata reservations distinct from storage into which the
loader is supposed to copy image data. In particular, adding the arena to
`upper_reservations` unchanged would make the current
[extent validator](../../tools/banked_image.py) reject its legitimate payload.
Define and test the allowed image range rather than bypassing overlap checks.

Update the memory generator, native build layout, extent validation,
four-Task pool validation and both budget paths together. Require that:

- Compiler-allocated globals, array storage, initialized pointers, literals
  and zero-fill objects fit in the declared upper arena. Explicit hardware,
  adapter and separately reserved metadata bindings retain their locations.
- Code cannot enter the arena, and ordinary resident image payload cannot
  fall back into `$8800–$8FFF` or other bank-zero holes. Existing separately
  placed native bindings and foreign C images remain subject to their own
  declared ranges; not every non-code segment is an ordinary global.
- The arena's bank is mapped, below `MAX_BANKS`, and owned by the resident
  image. Data and BSS survive adoption and heap startup; unused arena capacity
  cannot be offered to another owner.
- [Writable bindings](../../tools/generate_tasks.py) retain full 24-bit
  addresses and their existing public/kernel distinctions. Do not grant
  application writes to every byte of the arena merely because it moved.
- Build reports measure data against generated ranges, replacing helpers that
  count only `$8800–$8FFF`. The loaders' existing 24-bit copy/zero descriptors
  suffice; no boot-manifest wire-format change is planned.

Preserve the existing Task pool placements when removing the near reservation.
Do not reuse the retired arena during this slice. Low-memory-only compiler
and adapter fixtures remain separate test workloads; they do not provide an
alternative resident Exec memory layout.

### Slice 2 acceptance

Extend [package tests](../../tests/test_banked_package.py) and
[binding tests](../../tests/test_task_bindings.py) for allowed data writes,
code/data/metadata overlap rejection, arena overflow, unavailable banks and
ownership exclusion. Generate layouts for both Task capacities and a selected
alternate kernel bank, since placement is directly affected.

Execute a focused fixture in raw and optimized modes through the real loader.
Exercise initialized and zero-filled globals, an array, a string pointer, a
pointer stored in another global, mutation across a task switch and a public
writable-buffer operation. Check the actual upper addresses and preserve a
sentinel over `$8800–$8FFF` throughout execution. Retain guard, register,
ownership and bounded-completion assertions.

If emission or runtime behavior exposes a compiler defect, fix it in actionc
with a focused regression and record the compiler revision or explicit local
override. Do not introduce special cases for individual Exec globals.

## Slice 3 Retire the boot manifest after startup

Keep the manifest at `$6000–$67FF` throughout loading and adoption, then release
its complete 2,048-byte reservation at the final startup handoff. The boundary
is after successful memory adoption and Task initialization, including captured
boot settings, with no remaining loader/INITAD or monitor activation that can
read the manifest, and before ordinary Task dispatch. Failed startup does not
publish the range as reusable. Apply the same lifetime rule to banked fixtures
without general Tasks once their startup consumers have completed.

The live ownership table and `M_ADOPTED` remain authoritative at runtime.
Normal bank-manager operations already use them instead of the manifest.
Keep the separate boot-state page and any shutdown fields it contains; this
slice does not reclaim that page or copy the manifest elsewhere in bank zero.

Change [EXECMEMORY.Adopt and Init](../../lib/exec/execmemory.act) so that a
repeat call after successful adoption returns success immediately, before any
manifest access, and leaves the live ownership table unchanged. The current
implementation rechecks manifest fields and the original seed table on every
call. That must stop before the manifest can be overwritten. Initial adoption
still performs all existing identity, extent-completion and ownership checks;
only a successful adoption enables the repeat-call path.

Audit startup, shutdown, error handling and monitor handoff for retained
manifest pointers or deferred reads. Keep runtime state needed by those paths
in its existing permanent reservation. A cold boot reloads a fresh manifest;
restarting through retired bootstrap code is not a supported runtime operation.

Describe the manifest as loading-only storage in generated layout metadata.
Keep it protected against image writes during loading, while excluding it from
reservations after successful startup. Update both Task-capacity budget paths
and their tests. The existing `reclaimed_after_adopt` loader/staging lifetime
does not by itself describe this later retirement point; record the startup
phase explicitly. Do not lower the loading budget or count already reclaimed
loader/staging storage again. Preserve existing Task pool addresses, and leave
the recovered manifest range available for a later allocation decision rather
than registering all of bank zero as free.

Keep `manifest.bin` and its hashes as development/build inputs: dropping the
in-memory runtime reservation does not remove the manifest from XEX loading,
validation or OF816 packaging. The loader's embedded comparison copy retires
with the loader and provides no additional saving in this slice.

### Slice 3 acceptance

Extend the focused raw/optimized startup fixture to overwrite all 2,048 bytes
of the manifest range after the documented retirement point. Then repeat
`Adopt` and `Init`, exercise bank ownership queries and allocation/release,
run preempted Tasks and complete normal shutdown. Verify that the live table
retains ownership changes made since adoption, and that the replacement bytes
remain intact. Use a bounded read watchpoint or equivalent observation over
the retired range to catch stale readers as well as stale writers.

Retain the existing invalid-manifest and failed-adoption cases: corruption
before adoption must still reject startup, leave `M_ADOPTED` unset and keep
the manifest reservation live. Cover direct XEX and OF816 handoff. Verify a
fresh cold boot reloads and validates its manifest independently of the prior
run. Host checks must distinguish the unchanged loading reservation from the
2,048-byte reduction in runtime reservations, with identical Task pools.

## Expected bank zero budget

These figures retain the standard eight public Tasks and private idle pool,
including all guards and reserved padding. They are generated reservation totals,
not measured high-water marks or a promise that the holes form a single arena.

| Reservation | Before | After slice 1 | After slice 2 | After slice 3 startup |
| --- | ---: | ---: | ---: | ---: |
| OS ranges | 36,864 | 30,720 | 30,720 | 30,720 |
| Fixed Exec runtime | 10,560 | 10,560 | 8,512 | 6,464 |
| Public and idle Task pools | 14,112 | 14,112 | 14,112 | 14,112 |
| Total reserved | 61,536 | 55,392 | 53,344 | 51,296 |
| Unreserved | 4,000 | 10,144 | 12,192 | 14,240 |

Slice 1 changes fixed OS reservations by **−6,144 bytes**, fixed Exec runtime
by **0 bytes**, and each Task by **0 bytes**. Slice 2 changes fixed Exec runtime
by **−2,048 bytes** and each Task by **0 bytes**. Slice 3 changes fixed Exec
runtime by another **−2,048 bytes**, loading reservations by **0 bytes**, and
each Task by **0 bytes**. Report the derived four-Task totals separately. Count
upper-memory arena capacity, alignment and any new occupied code bank in the
implementation record as well.

These three slices clear the global arena's part of the future VBXE aperture.
The stack overlap at `$8000–$82DF` is resolved by the subsequent
[aperture reservation slice](../development/vbxe-aperture.json), outside this
plan's original scope. Mapping VBXE and integrating its driver remain separate.

## Integrated checks and delivery

Use the [development tier](../contributing/testing.md), including the host
suite and affected generators' freshness checks after each coherent slice:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

After all three slices pass their focused native cases, rebuild the standard demo
with [build_demo.py](../../tools/build_demo.py) and run the
[OF816 checks](../../tools/test_of816.py). Preserve five-second autoboot,
monitor cancellation, shell/prime behavior, disk command loading, the CAT/WC
pipeline, and exit restoration. Verify that the monitor's borrowed upper
banks exclude the relocated data and any shifted code extents. These checks
exercise the changed startup and image ownership paths without launching the
full release qualification matrix.

Update the [platform contract](../reference/platform.md),
[Task capacity description](../architecture/task-capacity.md) and GEM
assessment when executable results establish the new current map. Save fresh
development evidence with compiler, ROM, emulator, layout and image hashes;
preserve historical qualification records. Rebuild callers with the new
bindings. Package the demo through the normal OF816 route, keeping development
manifests and test output outside `exec816-demo.zip`.

The implementation recovers **10,240 fixed bank-zero bytes and changes per-Task
reservations by 0 bytes**. It also reserves 2,048 upper bytes plus 172 alignment
bytes in the standard demo, without adding another occupied code bank. The ROM
console adapter needs 256 additional temporary caller-stack bytes when staging
upper data; stack pool reservations are unchanged.

Development checks cover host packaging/layout checks, raw/optimized native
relocation with poisoned retired ranges, repeated adoption against live heap
ownership, boundary rejection, selected NMI/IRQ/register cases, and both OF816
routes through the standard shell/prime demo. The pinned bridge's access
watchpoints alias the low 16 bits of upper-bank accesses, so they cannot qualify
a watch over this bank-zero range. The stale-reader check instead poisons every
manifest validation field before repeat calls and audits all manifest consumers;
it does not claim a hardware range-watch result. Emulator observers now support
upper reads and bounded paused test writes; those instrumented writes are not
interrupt qualification. The scope and hashes are in the development record.
No full hosted-system qualification or working VBXE aperture is claimed.
