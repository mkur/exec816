# FastBasic floating point delivery

20 October 2026. Development tier; hosted-system release and physical hardware
qualification remain separate.

[Current contract](../reference/fastbasic.md) · [Programming guide](../guides/fastbasic.md) ·
[Design](../plans/fastbasic-floating-point-design.md) ·
[Implementation plan](../plans/fastbasic-floating-point-implementation-plan.md) ·
[Evidence](../development/fastbasic-floating-point.json)

FBC compiles floating-point sources on Exec and produces a self-contained
command that runs after the compiler exits. FBCI remains the smaller integer
compiler. Both use the current FB65 target `$4702`, ordinary Process ownership
and the same files/console/guest bridge. The six-byte numeric representation,
conversion/error rules and limitations are in the current reference.

## Implementation choices

The port retains the pinned FastBasic 4.7 and mini65 revisions. A reproducible
generator adapts mini65's Altirra math source to ca65, retaining its original
permission notice. The linked package keeps the original 2 KiB layout and
offset assertions, relocates calls/constants into the private runtime and adds
a private helper for the internal direct-page FLD0R path. ATN coefficients and
normalization/half constants are symbolic too; replacing public JSRs alone
would leave incorrect ROM dependencies.

Absolute,Y accesses to FR0/FR1 do not follow the guest D register. The adaptation
uses 65816 long-indirect access through five pointers at D `$70–7E`, initialized
to the correct instance's physical D page. Those 15 bytes fit an already
reserved page. General ZP allocation ends at `$D3`; math/conversion state owns
`$D4–FF`. The internal zero-page load helper uses the fifth pointer. Native
snapshot services write a fixed four-byte private buffer at `$0700`; no guest
pointer is passed to OS ROM.

Host literal conversion now collects decimal digits and matches the selected
AFP truncation rule. The donor's C++ double conversion rounded some literals
differently from the on-machine compiler. A focused case checks literal versus
VAL storage and FBC's saved output for `1.234567895`, represented as
`1.23456789`. Math-table constants retain the donor assembler's rounding rules.
Arithmetic and approximate functions follow the pinned private provider.

The 64-bytecode dispatch interval was insufficient for a math-heavy loop:
BREAK completion took five PAL ticks. A second quota checkpoints every two
completed FP operations at decimal-clear boundaries, preserving A/status/carry.
The normal and forced native-return cases each complete in two ticks while a
native peer progresses. Parser-line and memory-copy checkpoints remain.

The packaged screen oracle now waits for completed model writes, idle scroll
state and matching presentation generations. Its earlier predicate could
compare a newly written prime-counter model with an earlier physical row.
Physical cell/pixel comparisons remain exact; the change adds a stable
observation boundary.

## Memory and resource cost

Reserved bank-zero changes are **0 fixed, 0 root/kernel, 0 per public Task and
0 idle bytes** relative to the enabled integer/SDX profile, including guards,
alignment and unused capacity. The guarded two-page guest D pool remains 544
bytes. Native sessions remain 2,304 upper bytes and Image records 72 bytes.
Each aligned private bank still reserves 131,072 upper bytes including unused
alignment capacity; the 48-byte FP stack, snapshot and math code occupy that
existing bank. No new Task, guest slot, native stack or kernel service is added.

The final FBCI file is 6,032 bytes; FBC is 9,477 bytes. Their D allocations use
57 and 60 bytes respectively, within the 84-byte general linker capacity.
The remaining math D region and pointer capacity are charged to the full shared
page, not additional reservations. Linker heap starts are `$4800` and `$5500`;
actual available source space also accounts for frontend allocations.

Retaining an FBC Image costs 142,928 upper bytes for aligned bank backing,
session, Image and allocator-rounded file snapshot, before ordinary Process/DOS
and on-demand timer resources. FBCI costs 139,480 on the same basis. The text
demo emits 15,893 bytes across FBBIND/FBPROGRAM/FBSERVICE/FBFILES/FBSTATE,
excluding reused native modules and shared loader/Process edits. Its existing
SDX 12 KiB static arena remains unchanged. Per-build maps and stack observations
are retained in the evidence rather than inferred from these file sizes.

## Development acceptance

The evidence distinguishes actual pinned Exec/Altirra execution, seven
unmodified FP controls in mini65's simulated Atari OS, and a separate original
numeric program running under SDX with the actual pinned AltirraOS ROM math
and no emulator FP patch. That ROM control checks addition, square root,
degree-mode sine/arctangent, integer conversion and decimal VAL. Clean patched
sources reproduce both compiler hashes without reused host binaries. An old
integer native demo rejects compiler disk refresh before changing its system disk.

Focused optimized cases cover FP operators/functions, storage and arrays,
pointer-based procedure arguments, literal/VAL agreement, conversions, errors,
files, clock/random bounds, FBC compilation and saved-image admission/recovery.
Separate edge cases cover normalized range endpoints, underflow, overflow,
domain errors, signed INT limits and deterministic RND snapshots at unsigned
zero and UINT32_MAX. Those last two snapshots are explicitly test-only input
overrides; ordinary RND uses the real native per-invocation generator.

Raw and optimized probes insert a one-shot test-only SED/WAI trampoline into
the private IFP entry. A real VBI must retire and resume decimal arithmetic
correctly before the program can finish with the expected values. The injected
code is absent from compiler/runtime distributions. Two distinct FP guests,
a native peer, retained-image relaunch, third-slot rejection, MD5 and FBC
coexistence, cleanup and the forced native-return NMI case also pass.

The source-buffer case measures a start at `$5614` and 35,308 available bytes
for its recorded invocation. A 35,307-byte blank source compiles and runs;
exactly 35,308 and 35,309 bytes are rejected with 20/306, followed by successful
recovery. The frontend requires EOF within its BGET request and reports
`File error: 1` when the input fills it. This is a measured admission boundary,
not a general BASIC source-size guarantee. Separate write/Close injection checks
short transfers, first-cause retention, owned resources and full heap recovery.

The text and graphical package checks use clean ZIP extraction and physical
keyboard events to edit/save source in EDX, compile via arguments and prompts,
run by bare name and `.COM`, enter decimals, verify exact redirected bytes,
cancel a math loop and recover from errors. Both keep OF816, their documented
startup, matching media/ROM/notices, XEX and old/new CAR/raw BIN artifacts.
The corresponding source ZIP contains the complete modified sources and build
instructions; bulky build/test evidence remains outside the boot packages.

These development cases do not establish uniform accuracy bounds for arbitrary
transcendental inputs, exhaustive parser/output cancellation or pointer/focus
timing coverage, general guest interrupt qualification, or physical hardware
qualification. The integrated editor remains FB7.
