# Shared serial IRQ adapter

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/device-io.md) and [history index](README.md).

Status: slice 1 of the [signal implementation plan](../plans/signals-wait-implementation-plan.md).
The shared [assembly include](../../platform/altirraos/serial-irq.inc) supplies
bounded serial routing and ownership operations. It is exercised by the
[two-context fixture](../../probes/sio-irq/probe.s), before public signals or the
production scheduler are connected. The original latency proof remains intact.

## Entry and ownership contract

The adapter macros use caller-bound symbols, with explicit long addressing for
state. State can reside in upper RAM. Claim/release require native E=0, M=1,
I=1 and a protected registration transaction; they preserve X/Y, D, DBR and S,
and clobber A/P. Claim returns carry clear on success, set if already owned or
an OS activation is busy. Rejection changes neither OS nor saved ownership.
The caller must exclude ROM SIO for the entire claim, not just check it once.

Claim saves serial enable bits `$38`, CRITIC and VSEROR, installs the registered
bank-zero emulation callback, sets CRITIC and disables serial sources. Only
then may the owner configure POKEY and enable its bound source. The adapter
currently routes transmit-data-needed (`$10`); it does not claim receive or
transmit-complete handling is implemented. A binding must remain stable until
its source is disabled, handlers have retired, and release completes.

Release follows device quiescence, restores VSEROR and the previous CRITIC,
and merges the saved serial enable bits with the current unrelated enable
bits. Repeated release is harmless. Device register configuration and native
vector installation/restoration belong to the enclosing platform activation;
this helper does not save an entire POKEY audio configuration. The disposable
fixture restores its SKCTL shadow/hardware, IRQ mask and callback/native vectors.
Normal completion waits for the last transmitted byte; abort may discard it.

CRITIC postpones stage-two VBI work. Stage one, including the clock and OS
timer one, continues. Tests verify deferred VBI callbacks do not run during the
claim, resume after release when the old CRITIC was zero, and stay suppressed
when its old value was nonzero. Arbitrary ROM SIO calls during a claim are
unsupported; a future driver must enforce that exclusion at its OS boundary.

## Native and emulation paths

The native route starts after the caller saves the complete interrupted frame,
with M=1, X=0, I=1. It checks ownership and the intersection of IRQST and the OS
IRQ-enable shadow. It acknowledges serial-ready by clearing/re-enabling that
hardware enable bit without changing the shadow, then calls a bounded posting
routine. Other enabled pending sources, including a simultaneous timer source,
continue through the existing ROM adapter before safe return. Unowned IRQs
always use that adapter. No scheduler or compiler scratch is borrowed here.

The post callback is a same-bank JSR, adds two stack bytes, and returns with
M=1/I=1 and D/DBR/S preserved; A/X/Y may be clobbered. The route has no loops.
Its serial-only path executes 19 instructions including JSR and the final JMP,
but excluding the callback and enclosing save/restore. The check after posting
adds bounded coexistence work to the original proof.

ROM VBI can enable IRQs in emulation mode. These interrupts bypass the native
vector and use VSEROR, so a qualified emulation callback is also required.
ROM has saved A and acknowledged the source. The callback enters E=1, M=X=1,
I=1, D=DBR=0, posts without switching, then PLA/RTI retires the ROM handler.
Its notification helper preserves X/Y and all domain/stack state. JSR adds two
bytes to the existing OS frame. It uses no caller direct-page scratch.

The enclosing adapter may switch only after all OS/IRQ activations retire and
the saved task's I is clear. NMI can interrupt a native posting transaction,
but the protected activation prevents it from inspecting or dispatching partial
state. The fixture retains full A/B/X/Y/P/D/DBR/S/PC/PBR frames and chains other
COP signatures; Exec remains COP `$50`, the OS COP `$00` remains available.
All-M/X coverage of the integrated signal gateway belongs to later slices.

## Measurement and limits

The [explicit platform pin](../../toolchain/altirra-sio-irq.json) selects the same
ROM and emulator as the existing pins, with 8× PAL CPU and fast ROM. It leaves
the existing 1× profiles unchanged. The [qualification record](../qualification/serial-irq.json)
records actual DMA, VBI, machine settings, source/image hashes, ownership checks,
hardware refill timing and uninstrumented replay. Serial acceleration is off.

The accepted workload is a minimal worker plus busy/idle background, scoped
CRITIC, no active OS software-timer callback, and no additional hardware timer
IRQs. The divisor produces 126.675 kbaud and a 78.942 µs byte deadline. The
matrix includes a 65,535-byte stream and three initial phases. Across the six
accepted traced cases, 98,303 bytes pass with a worst refill of **71.612 µs**,
leaving **7.330 µs** of observed margin. A separate
hardware-timer case verifies concurrent-source service and ownership integrity;
it misses the serial deadline and is explicitly outside timing qualification.
The long-masking negative control must also fail. Functional success alone does
not constitute a serial timing pass.

Public signals, upper-RAM execution, general scheduler load, RX/turnaround,
physical devices and complete SIO/DOS remain unqualified by this fixture.

## Storage and reproduction

Production bank-zero reservation: **unchanged, delta 0 bytes**. The opt-in fixture
uses the same reservations as the original proof: 4,096 code + 256 state + 240
shared OS-stack bytes, and two contexts each with 288 DP/guard and 1,568
stack/guard bytes, totaling **8,304 bytes**. This counts unused reservation
capacity. Adapter-owned state is five logical bytes (active, saved mask, saved
CRITIC, saved VSEROR); the busy flag is supplied by the OS owner. It fits the
existing fixture state reservation and may live in upper RAM in production.
No additional context, DP or stack reservation is introduced.

Prepare the observer and pinned emulator as described in the
[original proof](sio-latency-poc.md#storage-and-reproduction), then run:

```sh
python3 tools/test_serial_irq.py --output build/sio-irq/qualification
```

Use `--case NAME` for focused reruns. Abort and replay use the uninstrumented
pinned emulator. The other cases use the previously qualified passive observer.
The runner rejects different ROM/emulator hashes and a different resolved
machine profile. These are assembly tests; raw/optimized NIR does not apply.
