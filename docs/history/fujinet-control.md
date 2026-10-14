# FujiNet control implementation

[History index](README.md) · [Plan](../plans/fujinet-control-implementation-plan.md) ·
[SIO contract](../reference/device-io.md#siodevice)

## FN0 protocol and serial fixture

The selected control commands and fixed byte extents are generated from
[fujinet.json](../../abi/fujinet.json). Source URLs/hashes are pinned in
[fujinet-control.json](../../toolchain/fujinet-control.json). The execution peer
uses Altirra's existing custom-device serial interface; no emulator changes or
production driver shortcuts are required. It is a scripted protocol fixture,
not executable FujiNet firmware or physical-device qualification.

Development checks pass: 473 host tests, generated definitions and 161 optimized
native assertions covering slot/AUX arithmetic and a complete 128-byte patterned
read over the real serial path. Native stack/domain guards, final heap ownership
and OS restoration pass. The [development record](../development/fujinet-control.json)
retains the exact inputs and scope.

Production bank-zero reservation delta is fixed 0, per public Task 0 and private
idle 0, including guards, alignment and unused capacity. FN0 adds protocol
constants only; its payload storage belongs to the test fixture.

## FN1 raw transfers and unit exclusion

STANDARD19200 admits complete raw frames up to 512 bytes and defaults to a
bounded fifteen-second deadline. Legacy profiles retain their admission and
conversion paths. Sparse unit metadata adds `$70` at offset 240; the exclusive
open bit consumes existing unit-record padding. Neither the 256-byte upper
metadata reservation nor bank-zero reservations grow: fixed 0, per Task 0,
private idle 0, including guards/alignment/capacity.

474 host tests and 2,995 optimized native assertions pass. Real serial reads,
writes and readback cover 140/255/256/304/512-byte payloads across a CPU-bank
boundary; neighboring guards remain intact. Checks cover admission rejection,
deadline rounding/defaults, clock wrap, a three-second completion with another
runnable Task, clean device errors followed by another successful request,
shared/exclusive conflicts on control and disk units, reopen, final ownership
and shutdown restoration. The peer uses Altirra's normal frame/checksum handling;
its receive primitive already supplies the data ACK.
