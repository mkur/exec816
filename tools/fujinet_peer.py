"""A scripted serial peripheral fixture; not a FujiNet firmware emulator."""
from pathlib import Path


def make_peer(output):
    """Use Altirra's existing custom-device SIO interface, with real wire frames."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'pattern.bin').write_bytes(bytes((i * 37 + 11) & 255 for i in range(512)))
    path = output / 'peer.atdevice'
    path.write_text('''option "name": "Exec816 FujiNet protocol fixture";
Segment pattern: { source: "pattern.bin", size: 512 };
Segment echo: { size: 512 };
SIODevice discovery_probe: {
  device_id: $31,
  commands: [
    { id: $52, auto_transfer: { mode: "read", segment: pattern, offset: 0, length: 128 } }
  ]
};
SIODevice control_probe: {
  device_id: $70,
  commands: [
    { id: $01, script: function {
      $sio.ack(); $sio.complete(); $sio.send_frame(pattern, 0, $aux);
    } },
    { id: $02, script: function {
      $sio.ack(); $sio.recv_frame($aux); echo.copy(0, $sio_frame, 0, $aux);
      $sio.complete();
    } },
    { id: $03, script: function {
      $sio.ack(); $sio.complete(); $sio.send_frame(echo, 0, $aux);
    } },
    { id: $04, script: function {
      $sio.ack(); $sio.delay(5400000); $sio.complete();
    } },
    { id: $05, script: function { $sio.ack(); $sio.error(); } }
  ]
};
''')
    return path
