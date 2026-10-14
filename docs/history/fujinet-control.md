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
