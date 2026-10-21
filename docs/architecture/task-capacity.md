# Task capacity and bank-zero storage

[Architecture index](README.md) · [Runtime model](runtime.md)

The standard demo provides **twelve public Tasks plus private idle** on the
pinned cartridge-free AltirraOS platform. Root and service workers count toward
public capacity; kernel service entry and idle do not. Four- and eight-Task
fixtures use the same kernel and Task API. Plain native test builds default to
four; `tools/build_demo.py` selects twelve.

## Slots and lifetime

A waiting Task retains its slot, native stack and direct page. Removal makes
those pools reusable; more prepared descriptors do not increase simultaneous
capacity. Files, mounts, ports and console instances allocate state without
adding execution pools once their shared service exists.

Select `--task-capacity 12` when packaging a resident application with the
standard map. Root and eleven workers can be live simultaneously; another
admission fails without disturbing their ownership. Supported fixture maps are
four and eight; other capacities require a checked map and are rejected.
Guest slots, AES clients, windows and console instances retain their own limits.

Use generated `TASKSTACKS.StackLower(slot)` and `StackUpper(slot)` values, with
an exclusive upper bound. Prepare `tc_SPReg=tc_SPUpper-SIZE(2)` as required by
the [Task API](../reference/tasks.md). Do not infer stack addresses from slot
numbers. A Task owns a 256-byte aligned DP, but the twelve-Task DP map is not
contiguous: public slots 8–11 use `$9000–$93FF`; idle becomes slot 12 while
keeping DP `$1500` and stack `$60D0`.

## Placement and admission

Stacks and DPs require bank zero; Task, Process and DOS metadata lives in upper
RAM. The twelve-Task map keeps all existing physical pools, root/kernel
contexts, boot storage and SDX guest pages. It adds three ordinary worker
stacks and a third large stack above the VBXE aperture. The
[platform contract](../reference/platform.md#bank-zero-memory-budget) defines
those addresses. The [high-RAM audit](../history/high-bank-zero-audit.md)
records the source and machine evidence for reclaiming that RAM.

`CreateTask` chooses the smallest free pool that fits the rounded request,
breaking equal-size ties by slot order. Eight ordinary pools have 1,312-byte
stacks; large pools in slots 6, 7 and 11 have 2,560 bytes. Three large requests
can coexist; a fourth fails even when ordinary pools remain free. Small
requests prefer ordinary pools but can consume large ones. Root and idle are
never creation candidates. Process launch uses the same shared pools and has
no stack-size argument. No pool is reserved for GEM.

Each stack has two 16-byte outer guards and an internal 256-byte interrupt
reserve. Large stacks leave 2,304 bytes before native frames and adapter use.
Root and kernel each have 1,536 bytes, idle 512. Four-Task fixtures retain
1,536-byte stacks; eight-Task fixtures retain five ordinary and two large
workers. Explicit `--worker-stack` overrides change allocations without moving
bases; overlap and malformed ranges are rejected. A request never dynamically
grows a bank-zero stack. Keep checked bounds enabled and measure actual depth.

The map excludes the VBXE aperture at `$8000–$8FFF` and reserves
`$BC00–$FFFF` for OS display, ROM and hardware. BASIC must be disabled and no
cartridge may be mapped. Loader and native entry require MEMTOP at least
`$BC00`, claim memory through MEMLO `$BC00`, and restore the original MEMLO on
shutdown. Native graphics retains the OS display at `$BC20–$BFFF` for return.

## Reservation accounting

The build's `memory.json` is authoritative. Count guards, alignment, reserved
slack and every DP, separating fixed and per-Task costs. These 4 MiB budgets
exclude the optional 544-byte SDX guest-DP pool:

| Runtime reservation | Four public Tasks | Eight public Tasks | Twelve public Tasks |
| --- | ---: | ---: | ---: |
| OS ranges | 19,968 | 19,968 | 19,968 |
| Fixed Exec, including kernel stack and aperture | 11,552 | 10,528 | 10,528 |
| Public and idle pools | 9,120 | 16,320 | 23,968 |
| Total reserved | 40,640 | 46,816 | 54,464 |
| Total unreserved | 24,896 | 18,720 | 11,072 |

Loading reservations are 41,584 bytes for four Tasks and 40,336 for eight or
twelve. Initialization retains the 2 KiB manifest until `startup_complete`.
Persistent pools do not overlap any live bootstrap bytes. Runtime unreserved
ranges are not automatically registered with the general heap.

Compared with the previous standard eight-Task SDX build, existing public
slots, root, kernel, idle and fixed Exec storage grow by **zero bytes**. Three
new ordinary slots cost 1,600 bytes each and the new large slot 2,848 bytes:
**7,648 added pool bytes**. Reclaiming 11,264 OS-reserved bytes reduces total
reserved bank zero by **3,616 bytes**. The SDX build has **10,528 bytes free**,
split between the low retired boot area and `$ADE0–$BBFF`. Task metadata adds
512 upper bytes, Process records 512 and DOS slots 64; generated pool arrays
also grow in upper RAM. Test-only register capture borrows an additional
128 bytes without reserving production memory.

See the [twelve-Task delivery record](../history/twelve-task-layout.md) for
actual development execution, remaining qualification scope and the OF816 demo.
Older reservation records retain their original layouts and hashes.
