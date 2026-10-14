"""A scripted serial peripheral fixture; not a FujiNet firmware emulator."""
from pathlib import Path


def make_peer(output, discovery=True, commands=False):
    """Use Altirra's existing custom-device SIO interface, with real wire frames."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'pattern.bin').write_bytes(bytes((i * 37 + 11) & 255 for i in range(512)))
    path = output / 'peer.atdevice'
    text = '''option "name": "Exec816 FujiNet protocol fixture";
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
'''
    if not discovery:
        begin = text.index('SIODevice discovery_probe:')
        end = text.index('SIODevice control_probe:')
        text = text[:begin] + text[end:]
    if commands:
        hosts = bytearray(256)
        hosts[0:3] = b'SD\0'
        hosts[32:45] = b'TNFS.EXAMPLE\0'
        disks = bytearray(304)
        for index in range(8):
            disks[index * 38] = 255
        disks[0:2] = bytes([0, 0x41])
        disks[2:13] = b'system.atr\0'
        paths = bytearray(2048)
        paths[:17] = b'/boot/system.atr\0'
        adapter = bytearray(140)
        adapter[33:46] = b'exec816-fuji\0'
        adapter[97:101] = bytes([192, 0, 2, 1])
        adapter[125:135] = b'fixture-1\0'
        rows = bytearray(1020)
        for index, name in enumerate((b'tools.atr\0', b'nested/\0', b'read me.atr\0', b'\x7f\x7f')):
            rows[index * 255:index * 255 + len(name)] = name
        for name, payload in (('hosts', hosts), ('disks', disks), ('paths', paths),
                              ('adapter', adapter), ('rows', rows)):
            (output / (name + '.bin')).write_bytes(payload)
        declarations = '\n'.join(f'Segment {name}: {{ source: "{name}.bin", size: {len(payload)} }};'
                                 for name, payload in (('hosts', hosts), ('disks', disks), ('paths', paths),
                                                       ('adapter', adapter), ('rows', rows)))
        (output / 'invalid.bin').write_bytes(b'x' * 256)
        text = declarations + '''
Segment invalid: { source: "invalid.bin", size: 256 };
Segment counters: { size: 16 };
int directory_index;
int directory_open;
int fault_mode;
''' + text
        extra = '''
    { id: $06, script: function {
      $sio.ack(); fault_mode = $aux1; $sio.complete();
    } },
    { id: $07, script: function {
      counters.write_byte(0, directory_open);
      $sio.ack(); $sio.complete(); $sio.send_frame(counters, 0, 16);
    } },
    { id: $09, script: function {
      $sio.ack(); $sio.error(); $sio.send_frame(pattern, 0, 128);
    } },
    { id: $fa, auto_transfer: [3] },
    { id: $e8, script: function {
      $sio.ack(); $sio.complete();
      if (fault_mode == 1) $sio.send_frame(invalid, 0, 140);
      else $sio.send_frame(adapter, 0, 140);
    } },
    { id: $f4, auto_transfer: { mode: "read", segment: hosts, offset: 0, length: 256 } },
    { id: $f2, auto_transfer: { mode: "read", segment: disks, offset: 0, length: 304 } },
    { id: $da, script: function {
      $sio.ack(); $sio.complete(); $sio.send_frame(paths, $aux1 * 256, 256);
    } },
    { id: $f9, script: function {
      $sio.ack();
      if ($aux1 < 2 && fault_mode != 9) $sio.complete(); else $sio.error();
    } },
    { id: $f7, script: function {
      $sio.ack(); $sio.recv_frame(256); directory_index = 0;
      directory_open = 1; $sio.complete();
    } },
    { id: $f6, script: function {
      $sio.ack();
      if (directory_open == 0 || fault_mode == 2) $sio.error();
      else {
        if (fault_mode == 3) $sio.delay(5400000);
        $sio.complete(); $sio.send_frame(rows, directory_index * 255, 255);
        if (directory_index < 3) directory_index += 1;
      }
    } },
    { id: $f5, script: function {
      $sio.ack(); directory_open = 0;
      counters.write_byte(1, counters.read_byte(1) + 1); $sio.complete();
    } },
'''
        at = text.index('commands: [', text.index('SIODevice control_probe:')) + len('commands: [')
        text = text[:at] + extra + text[at:]
    path.write_text(text)
    return path
