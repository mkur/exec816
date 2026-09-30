# Native word-address selection

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

The compiler pin advances from `70d59b96906e6c1f8a5688dadf1274a1dbda5770`
to `27119ab2804e795b0bbb067c269826b934271754`. The fix lives in actionc;
Exec816's Action! source, ABI v2 and stack-check setting are unchanged.

The selector recognizes an unsigned 16-bit value widened to an address and
used once by a byte/word memory access. It omits the intermediate pointer homes
before allocating the frame, and keeps the address in X. Representation-only
casts and an adjacent direct scalar payload load are allowed. Shared pointers,
signed widening, calls, volatile accesses and unrelated intervening operations
retain the conservative path. This is typed instruction selection, without
routine-name matching or an emitted-byte peephole.

For `ADDRESS(saved+8)`, the addition still wraps at 16 bits before widening.
The following long indexed access retains linear word transfers across a bank
boundary. Both the ordinary image and relocated o65 paths use these semantics.

## Result helpers

Both optimized `EXECPOLICY.Result` and `TASKPOLICY.Result` change from
**65 bytes / 35 instructions / an
8-byte frame** to **14 bytes / 7 instructions / no frame**:

```asm
LDA $04,S
CLC
ADC #$0008
TAX
LDA $06,S
STA $000000,X
RTL
```

X is already caller-clobbered under native ABI v2. The routine uses no pointer
scratch, stack reservation, entry reservation guard or frame teardown.
Removing its empty-frame guard follows the existing compiler contract; other
stack reservations remain checked.

Reserved bank-zero delta: **0 fixed / 0 per Task**, including guards, alignment
and unused capacity. Reducing the invocation frame does not change stack-pool
reservations.

## Development validation

- 332 compiler emission unit tests passed; one optional test remained ignored.
- All 31 native image emission integration tests passed; focused address tests
  also cover signed/shared/volatile/call fallbacks and image round trips.
- Raw/optimized emitted-code tests passed for byte/word loads and stores,
  addition/subtraction wrap, access widths and order, bank crossings, adjacent
  byte comparisons, relocated o65, and LF/CRLF source equivalence.
- IRQ/task switches and IRQ plus NMI passed at every reached instruction of
  the helper in both Tasks, with the IRQ dispatcher calling the same helper.
  This covers 70 raw and 14 optimized Task/instruction sites, including X live
  between address formation and the store, plus stack/domain guards.
- Existing byte-consumer and stack-fault runtime targets passed (five tests).
- Exec816's 236 host tests passed.
- Hosted Task `core-raw` and `core-opt` passed on the pinned PAL 800XL/65C816
  profile, including Task results, VBI dispatch, OS calls, restoration and
  stack/domain guards. Both real Result helpers emit identical 14-byte code.
- Cooperative-policy `locks-raw` and `locks-opt` passed on the
  [64 KiB profile](../../toolchain/altirra.json), using the same pinned ROM and
  IRQ bridge. Reports are in `build/cooperative-tests/`.

The hosted Task test's cleanup assertion also needed correction: self-removal
clears a context and then sets `caller.pending` to request a switch. It must
allow that Boolean flag in a retired slot while still requiring cleared
binding, nesting, finalizer and deadline fields. The previous compiler's saved
OF816 demo results show the same pending flag; kernel behavior is unchanged.

Runtime qualification used the pinned VM base
`56ddc5c5de41f0e7294e87c440869550eaf53292` plus the committed status-timing
correction. Local evidence is under `build/development/word-addresses/` and
the compiler runtime test runner's qualification directory. These development
checks do not replace full release qualification. The demo distribution has
not been rebuilt for this compiler pin.

Hosted Task checks used [the 1 MiB platform pin](../../toolchain/altirra-1m.json):
AltirraOS 3.44/65C816 ROM SHA-256
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`
and IRQ bridge SHA-256
`0439dfeb77d9bd54e5b136e9f3df14675e508ef0d2a30dc5c301e9a7116ff929`.
