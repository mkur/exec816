# Platform contracts for the kernel

**Status:** preserved GEM4XE baseline analysis; see the
[scope and source baseline](README.md). These are historical findings
and proposals, not current Exec816 platform contracts.

Companion to the [architecture analysis](README.md), at the same source baseline.
“Current” describes this repository. “Kernel requirement” or “proposal” describes
work still to do.

Exec's standalone role is the [confirmed direction](README.md#confirmed-direction).
The maps and ABI details below describe the current port and the constraints a
GUI adapter must handle. CPU and board constraints also apply to Exec itself;
GEM's linker regions, process limits and binary interfaces do not prescribe the
new kernel layout or API.

## 1. CPU constraints versus current implementation choices

The W65C816 has bank-$00 hardware stacks and direct addressing. Native interrupt
vectors are also in bank $00; the CPU enters an interrupt handler there. Native
mode does not provide an ordinary user/supervisor execution split. Program-counter
increment does not carry into the next bank. `SEI` masks IRQ, not NMI. These CPU
facts constrain the design independently of GEM.
[WDC datasheet, sections 2.6, 2.11, 3.1–3.4 and 7](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf).

| Constraint | Origin | Design consequence |
|---|---|---|
| Active hardware S and direct page use bank $00 | CPU | Far RAM cannot directly supply a task's hardware stack |
| Native task code uses E=0 | Proposed initial kernel rule | Keep emulation-mode execution inside a controlled compatibility path |
| GEM's DB is `$00`, with near globals and constants | Calypsi small-data build | Relinking code into far RAM does not relocate those data references |
| Default GEM engine stack is 2 KB | Linker/build choice | Measure a new call chain; do not assume an extra kernel frame will fit |
| `FAR` arithmetic wraps its offset at a bank boundary | Current compiler model | Use bank-contained objects or explicit address-based span operations |
| A function cannot cross a code bank | CPU plus linker placement | Preserve separate linker memories per bank |
| `$xxD500–$xxD5FF` holes in far code | Historical emulator workaround | Keep until the selected emulator and boundary tests justify removal |
| `$4000–$7FFF` can disappear during DOS banking | Atari/expansion mapping | No kernel interrupt dependency may live there while that backend runs |
| ANTIC sees motherboard memory, not arbitrary far/SRAM memory | Board/display interface | DMA-visible allocation is a distinct memory class |

Do not equate E=0 with privilege. Without an additional board protection design,
native programs share writable memory and can alter hardware or disable IRQs.
The initial kernel should state that it serves trusted programs. Pointer checks
and ownership accounting improve reliability but do not create hardware isolation.

## 2. Bank $00 budget

Authoritative source: the executable `bank0` and `layout` definitions in
[gem4xe.scm](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/gem4xe.scm), not the historical map comment above them.

| Inclusive addresses | Bytes | Present use |
|---|---:|---|
| `$0000–$00FF` | 256 | Atari OS zero page |
| `$0100–$01FF` | 256 | Emulation stack, including the DOS caller's frames |
| `$0200–$06FF` | 1,280 | OS variables, vectors and page-six area |
| `$0700–$1FFF` | 6,400 | Reserved for resident DOS in this layout |
| `$2000–$20FF` | 256 | GEM direct page: compiler registers and tiny statics |
| `$2100–$367F` | 5,504 | LoRAM: data/BSS/stack; includes the 2,048-byte stack |
| `$3680–$3FFD` | 2,430 | Near code, library code and near constants |
| `$3FFE–$3FFF` | 2 | Inert runtime reset word |
| `$4000–$47FF` | 2,048 | `zwin`: non-interrupt GEM state |
| `$4800–$7FFF` | 14,336 | Product application pool, shared with AES allocations |
| `$4800–$67FF` | 8,192 | Alternative test-runner pool |
| `$6800–$7FFF` | 6,144 | Test-runner buffers; absent from the product layout |
| `$8000–$9BFF` | 7,168 | Load-time stage/unpacker; runtime display use below |
| `$9C00–$9FFF` | 1,024 | Kept for SDX's screen during loading |
| `$A000–$BFFF` | 8,192 | Cartridge/SDX region, not GEM storage |
| `$C000–$CFFF`, `$D800–$FFFF` | 14,336 | OS ROM/shadow; motherboard RAM may contain DOS |
| `$D000–$D7FF` | 2,048 | Hardware region |

The product and test pool rows are alternatives, not additive. The entire
`$2000–$3FFF` region is only 8 KB, including the direct page, code and stack.
The actual stack base depends on the link; old measured stack addresses are not
an ABI. A 14 KB application pool is not 14 KB of free task stacks: it also holds
process records, application data, resources, queues and transient I/O buffers.

**Kernel requirement:** produce a new link-map budget with separate allocations
for the kernel direct page, entry code, interrupt stack space, task stacks, GEM
near data and DMA buffers. With resident DOS retained, this is a constrained
coexistence map. With DOS removed, some reservations can be reclaimed only after
its services and return path have been replaced.

## 3. Far memory and allocation contracts

[farmem.c](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/farmem.c) rounds `_fl_top` up to the first unused bank,
writes a probe byte at offset `$0100` in candidate banks through `$FE`, then keeps
the largest contiguous run that reads back correctly. Bank `$FF` is omitted from
the write probe because Rapidus registers live there. This is a destructive
bootstrap probe, not a general free-memory discovery service.

If the kernel has already loaded code or allocated objects above GEM, `_fl_top`
does not describe those reservations. Calling `farmem_probe()` then could corrupt
them. A kernel-hosted GEM must receive owned memory regions from the kernel and
must skip this probe. A custom board also needs a safe map of RAM versus I/O
before probing; avoiding bank `$FF` alone is not universal hardware discovery.

Current allocation operations:

- `far_alloc(bytes)`: a four-byte-aligned block contained within one bank;
  requests over a bank are refused, and insufficient bank tails are skipped.
- `far_alloc_span(bytes)`: a contiguous span that may cross banks.
- `far_alloc_banks(n)`: whole banks, aligned to a bank boundary.
- `far_release(mark)` and `pool_release(mark)`: rewind global cursors, subject
  to their permanent floors. They are not per-allocation frees.
- `far_put/get/copy/fill` walk far pointers. Their operands must remain within
  their respective banks. The `_span` variants recompute full addresses.

Use distinct allocator capabilities in the kernel: **always-mapped near RAM**,
**ordinary far RAM**, **bank-contained far objects**, **contiguous spans**, and
**DMA-visible memory**. Treat VBXE VRAM as device memory with its own allocator.
Record ownership and reservations independently of the legacy GEM cursors.

## 4. Compiler and application ABI

The engine builds with `--code-model=large --data-model=small -O2` and
`clib-lc-sd.a`. CPU address values use 24 bits, while many stored ABI addresses
occupy 32 bits. Near pointers and the small model's `size_t` are 16 bits.
The application build additionally supports the large-data runtime; GEM itself
still expects its near objects. See [Makefile](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/Makefile),
[portab.h](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/portab.h) and [gemapp.scm](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/app/gemapp.scm).

Changing the compiler requires validating layout and calling conventions as well
as editing `portab.h`. The tree has documented compiler workarounds for struct
layout constant expressions, near/far copies, byte-width control flow, arithmetic
and spilled pointers. The kernel's context structure and assembly offsets should
be checked with the target compiler and actual emitted code. Preserve the
[`_Div16/_Mod16` override](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/div16.s) until compiler tests establish
it is unnecessary; see [compiler notebook](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/tools/ccbug/README.md).

### GEM entry contract

| COP signature | Service | Input |
|---|---|---|
| `$56` (`V`) | VDI | X:C points to a five-address parameter block |
| `$41` (`A`) | AES | X:C points to a six-address parameter block |
| `$44` (`D`) | GEMDOS | X:C points to result LONG, function WORD, then arguments |

Here C means the full 16-bit accumulator, not the carry flag; X supplies the
upper address word. [Application stubs](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/app/gemabi.s) and
[system handler](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/abi.s) implement this interface. The public
[header](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/app/gem.h) permits A/X/Y to be clobbered; the present handler
actually restores them. Preserve at least the published D/DB/S/P guarantees.

The handler saves the native frame and registers, selects GEM's D and DB,
switches the outer application call onto `gem_api_sp`, and re-enables IRQ if the
caller allowed it. It does **not** serialize independent kernel callers.
`gem_depth` handles the existing stack-switch discipline; it is not a general
reentrancy guarantee.

AES argument arrays and results are copied through far pointers. Object trees,
editable structures and several path buffers must be near. Selected short input
strings are bounced through a shared 64-byte scratch area. Bitmap data can be far.
Array-walking helpers still need bank-contained buffers even though their base
addresses can be far. A far-address field alone is not a cross-bank buffer promise.

VDI uses global arrays of 12 control, 128 integer-input, 128 point-input,
64 integer-output and 32 point-output words. AES has stack-local copied arrays,
but calls into shared engine state. Requests that suspend need their argument
storage and referenced buffers to remain alive until completion. Persistent
references such as registered menus/resources require longer ownership as well.

### COP ownership

Release 0.2 explicitly stopped using `$73/$C8/$01`. The current handler recognizes
only its three selectors, and when `@:SYSDEF` advertises Rapidus native services,
chains foreign COPs through the OS's long RAM vector at `$0256`.
[Phase 41](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/docs/phase41.md) documents the collision with Rapidus `$00/$01`.
WDC reserves `$80–$FF` for future use.
[WDC datasheet, section 7.15](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf).

The kernel must dispatch COP before entering GEM or touching GEM scratch state.
Keep a selector registry/versioned service discovery mechanism; do not silently
reuse the historical selectors for kernel calls. Preserve OS chaining only in
boot modes where that OS service remains valid.

### G4A executable format

[mkg4a.py](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/tools/mkg4a.py) compares three links: the base layout, near base
shifted by one page, and far base shifted by one bank. Four relocation lists name
the bytes to adjust: near-page and far-bank references in each image part.

The current 32-byte header contains near size/base, far offset/image size/bank
count, entry address and fixup counts. Formats **3 and 4** use the current COP ABI;
3 has 16-bit far fixup offsets, 4 has 24-bit offsets for larger images. Versions
1/2 are explicitly refused as old SDK files. Far BSS is reserved from the link
map and can extend beyond the bytes stored in the image.

This is a useful existing GEM program format. It has no general shared-library
import table, kernel task metadata, protection attributes or independent segment
ownership. Initially keep a compatibility launch wrapper using its current CRT.
A directly scheduled kernel program needs a startup/exit contract and validated
stack/DP placement; changing that may warrant a separate format or version.

## 5. Context switching and interrupt entry

Current [`CTX`](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/ctx.h) carries the saved engine S, far save buffer,
saved length/high-water measurement, entry/liveness and four COP call-state
fields. [`ctx.s`](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/ctx.s) pushes 32 bytes of Calypsi's register area,
copies `[S+1 .. ctx_base]` to far RAM, changes S, restores the incoming extent
to the same addresses and returns through it. `ctx_regs_ok()` rejects a compiler
register section larger than the saved allowance.

This works at its C calling-convention yield points. It neither snapshots the
whole machine at an arbitrary instruction nor virtualizes every GEM global.
The park/unpark helpers themselves need stack space below the copied extent.
`CTX_MAX` is a storage limit, not an interrupt-stack overflow detector.

For native kernel preemption, define a separate trap frame that preserves full
A/X/Y, D, DB, S and the interrupted P/PBR/PC. In particular, capture the hidden
accumulator high byte even when M=1 and restore the width flags correctly. Give
each task its own compiler workspace, or explicitly save every shared workspace
byte required by the compiler. The 32-byte cooperative save is not sufficient
evidence for arbitrary preemption. ISR code calling C also needs its own valid
D/DB/runtime state. Interrupts can occur while block-move code has changed DB.

Hardware pushes the interrupt frame onto the interrupted stack before software
can select another stack. Therefore even a dedicated kernel/interrupt stack
requires headroom on every task's active bank-$00 stack. Define behavior for an
interrupt during a stack change and for NMI during an IRQ critical section.

Current sources:

- ANTIC NMI increments `irq_frames` and clears the latch; it does no AES work.
- POKEY timer 1 samples quadrature at approximately 4 kHz and updates two counters.
- POKEY keyboard input enters an eight-entry ring with seven usable queued slots.
- BRK/ABORT set a byte and stop; unknown non-POKEY IRQs are not a general driver
  dispatch mechanism.

Preserve the short ISR/deferred-consumer split. A timer interrupt should request
rescheduling only when the kernel entry/critical-section protocol permits it.
Keep input sampling frequency separate from scheduler quantum.

## 6. DOS and firmware calls

[`cio.s`](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/cio.s) is bank-$00 code because the OS call executes in
emulation mode. It saves GEM state, selects D=0/DB=0 and the saved page-one DOS
stack, changes mode/mappings and interrupt masks, calls CIOV/SIOV/the SpartaDOS
kernel, then reverses the transition. Its saved S/status/IOCB fields are global.
It must have one owner across the entire round trip.

The GEM engine stack stays below `$4000`. Application stacks can be in the banked
pool because COP has moved away from them before DOS banks `$4000–$7FFF` out.
Kernel task records, active interrupt data and entry code must obey the same
mapping invariant if legacy DOS is retained.

While DOS runs, GEM's POKEY sampler is off. Frame time is caught up from Atari
`RTCLOK` and an OS-collected key can be transferred back, but quadrature movement
during the call is lost. A worker task can serialize requests; it cannot make
this particular firmware interval responsive without a substantially different
interrupt/emulation design or native drivers.

CIO provides seven available IOCBs (1–7; 0 is the console), with 16-bit names
and buffers. GEMDOS maps a file handle to IOCB+6 and bounces far buffers through
near slices. Searches use seven far cache slots keyed by DTA; a new search can
evict an old slot. Current drive/directories remain global. Preserve GEM errors,
byte counts and DTA layout when substituting a filesystem service.

### ROM shadow caveat

[`irq_install()`](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/sys/irq.c) tries Rapidus SRAM-only, write-through and
motherboard-only routes for writable native vectors. It verifies vector bytes,
which caught a real-board failure that an identical ROM-copy comparison missed.
The write-through and motherboard routes can overwrite DOS data under ROM;
the source explicitly describes that tradeoff. Do not generalize “returns to
DOS” into a guarantee for every firmware/DOS/mapping combination.

In kernel-hosted mode GEM must not reinstall vectors or restore the machine to
DOS on its own. Replace `irq_install/remove`, `rapidus_speedup/restore`,
`farmem_probe` and `_sys_exit` with kernel-owned initialization/termination paths.

## 7. Display, time and other device ownership

The [`VDIDEV`](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/vdi/vdidev.h) table is a strong reuse boundary. Its three
backends are VBXE, ANTIC and a 640×800 one-bit printer page. Renderer operations
include synchronous cursor save/restore; replacing a blit with asynchronous work
must preserve completion ordering at that boundary.

- **VBXE:** default 640×240, 4 bpp; 200/224-line variants exist. VRAM is accessed
  through MEMAC A at `$8000–$9FFF`. The encompassing Rapidus window must reach
  the motherboard bus. MEMAC selection, blitter submission, palette and cursor
  scratch belong to one driver/graphics owner. VBXE VRAM addresses are not CPU
  RAM pointers despite both being stored in 32-bit fields.
- **ANTIC:** 320×168, 1 bpp; display list at `$8000`, framebuffer at
  `$8100–$9B3F`. It must remain visible to ANTIC during DOS banking. A display-list
  reload at line 96 handles the 4 KB fetch boundary. Keep those constraints if
  relocating the framebuffer. See [antic.h](https://github.com/slaapliedje/gem4xe/blob/01c2e17b072e079443a11eff11d3ab3229db5ed5/src/antic/antic.h).
- **Printer:** the 64,000-byte page fits in one far bank. PCL/PostScript emission
  reaches CIO and may block. A spool service is a later consumer of kernel I/O,
  not a reason to put printing into the scheduler.
- **Input/time:** VDI polling consumes interrupt counters, runs callback vectors
  and advances AES ticks. This is deferred task work, not ISR callback semantics.
  Replace polling with signal-driven service work while preserving click and
  gesture behavior. Use a monotonic kernel clock with a defined time unit;
  GEM's current 20-ms PAL conversion is a compatibility layer.
- **Wall clock:** `clock.c` reads U1MB/SIDE DS1305 hardware or asks DOS. Keep wall
  time separate from timer deadlines. Its read-before-write card detection is
  important: `$D3E2` without U1MB can alias PIA and break mouse input.

Rapidus register semantics in this tree were partly inferred from emulator code
and refined on hardware. Preserve board capability checks and measured mappings;
do not bake one accelerator's SRAM/coherence behavior into portable kernel code.
