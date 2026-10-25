#!/usr/bin/env python3
"""One resident guest lease, two retained contexts and ordinary native peers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import time

from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_runtime import PIN, ROM, BRIDGE
from sector_images import disk_image


def payload(service, phase=0, rawcon=False):
    # Only synthetic 6502 code, plus admitted guest-local mode veneers.
    # Four 16-bit counter wraps per phase ensure non-yielding computation.
    code = bytes.fromhex('e620d002e621d002e622a522c904d0f02020f0e623a9008522'
                         'e620d002e621d002e622a522c904d0f02040f04c3030')
    if rawcon:
        # Every 32 counter steps execute a changing put and a get. Keep the
        # ordinary loop/return invariants, including private DP and flags.
        code=(b'\x20\x00\xf7'+code[:25].replace(b'\xd0\xf0',b'\xd0\xed')+
              b'\x20\x00\xf7'+code[25:].replace(b'\xd0\xf0',b'\xd0\xed'))
    # Offset of the second loop is $3019; absolute final loop is immaterial.
    bank = bytearray(65536)
    bank[0x3000:0x3000+len(code)] = code
    for at, event in ((0xf020, 1), (0xf040, 2)):
        # PHP acts as RTI status above the original JSR return. The second PHP
        # matches the IRQ hook's extra status byte. Save hidden B in native mode.
        veneer = bytes.fromhex('08780818fbc23048da5a0b8b')+b'\xa9'+struct.pack('<H', event)
        veneer += b'\x5c'+service.to_bytes(3, 'little')
        bank[at:at+len(veneer)] = veneer
    # A test shim records any pending VBI that escaped the final restore.
    prefix = bytes.fromhex('0848af0478280f1a78288f1a782868284c0030')
    bank[0x2fe0:0x2fe0+len(prefix)] = prefix
    bank[0xf080:0xf088] = bytes.fromhex('ea38eafbea28ea40')
    if rawcon:
        helper=bytes.fromhex('0848a520291fd01a a55448a55548a90085548555a520'
                             '2080f62060f6688555688554682860'.replace(' ',''))
        bank[0xf700:0xf700+len(helper)]=helper
        for at,event in ((0xf660,43),(0xf680,44)):
            veneer=bytes.fromhex('08780818fbc23048da5a0b8b')+b'\xa9'+struct.pack('<H',event)
            veneer+=b'\x5c'+service.to_bytes(3,'little')
            bank[at:at+len(veneer)]=veneer
    if phase >= 8:
        bank[0xf080+(phase-8)*2] = 0xcb  # one-shot WAI, retired by the NMI hook
    return bytes(bank)


def fixture(out, smoke, phase=0, sio=False, profile="stock810", rawcon=False):
    (out/'sdxprobe.act').write_text('''MODULE SDXPROBE
PUBLIC EXTERNAL CARD FUNC Install()
PUBLIC EXTERNAL CARD FUNC Remove()
PUBLIC EXTERNAL CARD FUNC Acquire(CARD slot)
PUBLIC EXTERNAL PROC Enter(CARD slot)
PUBLIC EXTERNAL PROC Release()
PUBLIC EXTERNAL CARD FUNC Run(CARD slot)
PUBLIC EXTERNAL CARD FUNC Bind(CARD slot)
ENDMODULE
''')
    source = out/'probe.act'
    source.write_text('''MODULE SDXTASKPROBE
USE EXEC
USE EXECTASKS
USE EXECLISTS
USE TASKSTACKS
USE HEAPCORE
USE SDXPROBE
USE SDXABI
USE INPUT
USE EXECOS

INPUT.Lease mouse
INPUT.Config mouseConfig
EXEC.Task ARRAY workers(2)
PROC POINTER noFinalizer()
VOLATILE CARD ARRAY progress(2)
VOLATILE LONGCARD peer
BYTE ARRAY message=[83 68 88 155]
CARD checks
BYTE ARRAY snapshots(26)
CARD busySeen,romPeer

PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($f800+checks)
  FI
  checks==+1

RETURN

PROC Guest(CARD slot)
  CARD event,status,index

  IF slot=1 THEN
    Require(SDXPROBE.Acquire(slot)=0)
    busySeen==+1
  FI
  WHILE SDXPROBE.Acquire(slot)=0 DO
    EXEC.Yield()
  OD
  SDXPROBE.Enter(slot)
  LET frame=BYTE POINTER(ADDRESS(SDXABI.INITIAL_S))
  frame(SDXABI.FRAME_Y)=$a6
  frame(SDXABI.FRAME_X)=$5a
  frame(SDXABI.FRAME_A+1)=$ab

  event=SDXPROBE.Run(slot)
  Require(event=1)
  FOR index=1 TO 13 DO
    snapshots(slot*13+index-1)=frame(index)
  OD
  progress(slot)=1
  Require(EXECOS.Write(@message,4)=1)
  status=EXECTASKS.Sleep(4+slot*3)
  Require(status=0)
  FOR index=1 TO 13 DO
    Require(frame(index)=snapshots(slot*13+index-1))
  OD
  event=SDXPROBE.Run(slot)
  Require(event=2)
  FOR index=1 TO 13 DO
    snapshots(slot*13+index-1)=frame(index)
  OD
  SDXPROBE.Release()
  progress(slot)=2

RETURN

PROC First()

  Guest(0)

RETURN

PROC Second()

  Guest(1)

RETURN

PROC Prepare(EXEC.Task POINTER item CARD slot)

  item.tc_Node.ln_Type=EXEC.NT_TASK
  item.tc_SPLower=ADDRESS(TASKSTACKS.StackLower(slot))
  item.tc_SPUpper=ADDRESS(TASKSTACKS.StackUpper(slot))
  item.tc_SPReg=ADDRESS(TASKSTACKS.StackUpper(slot)-2)
  EXECLISTS.NewList(@item.tc_MemEntry)

RETURN

PROC Main()
  EXEC.Task POINTER added
  BYTE POINTER firstDp,secondDp
  CARD index

  ; The loader has retired before application entry. These diagnostic pages
  ; are outside all native stacks/DPs and below the VBXE aperture.
  firstDp=BYTE POINTER(ADDRESS($7e00))
  secondDp=BYTE POINTER(ADDRESS($7f00))
  FOR index=0 TO 255 DO
    firstDp(index)=BYTE(index)
    secondDp(index)=BYTE(index XOR $ff)
  OD
  FOR index=$20 TO $23 DO
    firstDp(index)=0
    secondDp(index)=0
  OD
  Require(SDXPROBE.Install()=0)
  Require(EXEC.AllocSignal(16)=16)
  mouseConfig.version=INPUT.VERSION
  mouseConfig.source=INPUT.SOURCE_POINTER
  mouseConfig.wakeMask=$10000
  mouseConfig.pointerProtocol=INPUT.POINTER_ST
  mouseConfig.pointerPort=INPUT.POINTER_PORT
  mouseConfig.maxX=200
  mouseConfig.maxY=200
  Require(INPUT.Acquire(@mouse,@mouseConfig)=INPUT.OK)
  Prepare(@workers(0),1)
  Prepare(@workers(1),2)
  EXEC.Forbid()
  added=EXEC.AddTask(@workers(0),@First,noFinalizer)
  Require(added=@workers(0))
  added=EXEC.AddTask(@workers(1),@Second,noFinalizer)
  Require(added=@workers(1))
  EXEC.Permit()
  WHILE workers(0).tc_State<>EXEC.TS_REMOVED
      OR workers(1).tc_State<>EXEC.TS_REMOVED DO
    peer==+1
    IF progress(0)=1 AND romPeer=0 THEN
      Require(EXECOS.Write(@message,4)=1)
      romPeer=1
    FI
  OD
  Require(progress(0)=2 AND progress(1)=2)
  Require(busySeen=1)
  Require(peer>0)
  FOR index=0 TO 255 DO
    IF index<$20 OR index>$23 THEN
      Require(firstDp(index)=BYTE(index))
      Require(secondDp(index)=BYTE(index XOR $ff))
    FI
  OD
  Require(firstDp($20)=0 AND firstDp($21)=0 AND firstDp($22)=4 AND firstDp($23)=1)
  Require(secondDp($20)=0 AND secondDp($21)=0 AND secondDp($22)=4 AND secondDp($23)=1)
  Require(INPUT.Release(@mouse)=INPUT.OK)
  EXEC.FreeSignal(16)
  Require(SDXPROBE.Remove()=0)

RETURN
ENDMODULE
''')
    if sio:
        text = source.read_text().replace('USE EXECOS', 'USE EXECOS\nUSE SIO\nUSE SIOCLIENT')
        # ROM CIO is explicitly unavailable while the native SIO device owns POKEY.
        text = text.replace('Require(EXECOS.Write(@message,4)=1)',
                            'Require(EXECOS.Write(@message,4)=$ff02)')
        text = text.replace('CARD checks', 'CARD checks,sectorsRead\nSIO.Session disk\nSIO.Transaction transfer\nBYTE ARRAY sector(128)')
        at = text.index('PROC Main()')
        text = text[:at]+'''PROC ReadSector()
  CARD index

  transfer.command=$52
  transfer.aux1=4+BYTE(sectorsRead & 3)
  transfer.direction=SIO.SIODIR_READ
  transfer.profile=SIO.SIO_PROFILE_STOCK810
  transfer.length=128
  transfer.data=sector
  Require(SIOCLIENT.Transfer(BYTE POINTER(@disk),BYTE POINTER(@transfer))=0)
  Require(transfer.actual=128)
  FOR index=0 TO 127 DO
    Require(sector(index)=(BYTE(index) XOR BYTE(CARD(transfer.aux1)*15)))
  OD

  sectorsRead==+1

RETURN

'''+text[at:]
        text = text.replace('  Prepare(@workers(0),1)\n  Prepare(@workers(1),2)',
                            '  Require(SIOCLIENT.Open(49,0,BYTE POINTER(@disk))=0)\n'
                            '  Prepare(@workers(0),2)\n  Prepare(@workers(1),3)')
        text = text.replace('OR workers(1).tc_State<>EXEC.TS_REMOVED DO',
                            'OR workers(1).tc_State<>EXEC.TS_REMOVED\n      OR sectorsRead<8 DO\n    ReadSector()')
        text = text.replace('  Require(INPUT.Release(@mouse)=INPUT.OK)',
                            '  SIOCLIENT.Close(BYTE POINTER(@disk))\n  Require(INPUT.Release(@mouse)=INPUT.OK)')
        source.write_text(text)
    if phase:
        text = source.read_text()
        start = text.index('  Require(EXEC.AllocSignal(16)=16)')
        end = text.index('  Prepare(@workers(0),1)', start)
        text = text[:start]+text[end:]
        text = text.replace('  Require(INPUT.Release(@mouse)=INPUT.OK)\n  EXEC.FreeSignal(16)\n', '')
        source.write_text(text)
    if smoke:
        text = source.read_text()
        start = text.index('  Require(EXEC.AllocSignal(16)=16)')
        end = text.index('  Require(SDXPROBE.Remove()=0)', start)
        text = text[:start]+'''  Require(SDXPROBE.Acquire(0)=1)
  SDXPROBE.Enter(0)
  LET frame=BYTE POINTER(ADDRESS(SDXABI.INITIAL_S))
  frame(SDXABI.FRAME_Y)=$a6
  frame(SDXABI.FRAME_X)=$5a
  frame(SDXABI.FRAME_A+1)=$ab
  Require(SDXPROBE.Run(0)=1)
  FOR index=1 TO 13 DO
    snapshots(index-1)=frame(index)
  OD
  SDXPROBE.Release()
  Require(firstDp($20)=0 AND firstDp($21)=0 AND firstDp($22)=4)
  progress(0)=1
'''+text[end:]
        source.write_text(text)
    if profile=="generic56k":
        source.write_text(source.read_text().replace("SIO_PROFILE_STOCK810","SIO_PROFILE_GENERIC57600"))
    if rawcon:
        text=source.read_text()
        at=text.index('PROC Guest(CARD slot)')
        text=text[:at]+'''PROC Word(BYTE POINTER bytes CARD offset,value)

  bytes(offset)=BYTE(value)
  bytes(offset+1)=BYTE(value RSH 8)

RETURN

PROC BindCells(CARD slot)
  CARD row

  LET binding=BYTE POINTER(ADDRESS(SDXABI.BINDING_BASE))
  Word(binding,SDXABI.BINDING_WIDTH,80)
  Word(binding,SDXABI.BINDING_HEIGHT,30)
  Word(binding,SDXABI.BINDING_SCREEN,$d000)
  binding(SDXABI.BINDING_SCREEN+2)=BYTE($30+slot)
  Word(binding,SDXABI.BINDING_FIRST,$e000)
  binding(SDXABI.BINDING_FIRST+2)=BYTE($30+slot)
  Word(binding,SDXABI.BINDING_END,$e020)
  binding(SDXABI.BINDING_END+2)=BYTE($30+slot)
  Word(binding,SDXABI.BINDING_PENDING,0)
  binding(SDXABI.BINDING_PENDING+2)=0
  FOR row=0 TO 29 DO
    Word(binding,SDXABI.BINDING_ROWS+row*2,row*80)
  OD
  Require(SDXPROBE.Bind(slot)=1)

RETURN

'''+text[at:]
        text=text.replace('  SDXPROBE.Enter(slot)', '  SDXPROBE.Enter(slot)\n  BindCells(slot)')
        text=text.replace('  Require(SDXPROBE.Install()=0)', '''  FOR index=0 TO 1 DO
    BEGIN
      LET context=BYTE POINTER(ADDRESS(SDXABI.CONTEXT_BASE+LONGCARD(index)*16))
      Word(context,SDXABI.FIELDS_BANK,$30+index)
      Word(context,SDXABI.FIELDS_ENTRY,$2fe0)
      Word(context,SDXABI.FIELDS_DP,$7e00+index*256)
    END
  OD''')
        text=text.replace('  Require(SDXPROBE.Remove()=0)', '')
        source.write_text(text)
    return source


def image_data(service, early=False, phase=0, rawcon=False):
    state = bytearray(0x8000)
    state[:0x4000] = ROM.read_bytes()
    state[0x7812] = int(early)
    for slot in range(2):
        base = 0x7a00+slot*16
        state[base+4:base+14] = struct.pack('<5H',0x1e0,0,0x30+slot,0x2fe0,0x7e00+slot*256)
    return ([] if rawcon else [(0x280000, bytes(state))])+[
        (0x300000, payload(service, phase,rawcon)), (0x310000, payload(service, phase,rawcon))]


def run(out, mode, early=False, phase=0, sio=False, trace=False, program=None, profile="stock810", rawcon=False):
    out.mkdir(parents=True, exist_ok=True)
    if program is None:
        source = fixture(out, mode == 'raw', phase, sio, profile,rawcon)
        toolchain = compiler(ROOT/'build/actionc', release=True)
        options = dict(optimize=mode == 'opt', tasks=True, task_capacity=12, console=False,
                       sdx_runtime_probe=not rawcon,sdx=rawcon, sdx_return_probe=phase)
        preliminary = build(toolchain, source, out/'bind', image_data=image_data(0, early, phase,rawcon), **options)
        service = preliminary['labels']['sdx_probe_service']
        program = build(toolchain, source, out, image_data=image_data(service, early, phase,rawcon), **options)
        require(program['labels']['sdx_probe_service'] == service, 'Unstable service binding')
    reserved = (program['labels']['sdx_probe_nmi_stub'], program['labels']['sdx_probe_stubs_end'])
    # E=1 nested-entry classification needs unambiguous PC offsets.
    require(reserved[1] <= 0x2fe0, 'Guest code overlaps bank-zero transition PC interval')
    require(sha256(ROM) == PIN['rom']['sha256'], 'ROM differs from pin')
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Emulator differs from pin')
    effective = bytearray(ROM.read_bytes())
    patches = []
    for address, name in ((0xfffa, 'sdx_probe_nmi_stub'), (0xfffe, 'sdx_probe_irq_stub')):
        offset = address-0xc000
        replacement = program['labels'][name].to_bytes(2, 'little')
        patches.append(dict(address=address, expected=effective[offset:offset+2].hex(), replacement=replacement.hex()))
        effective[offset:offset+2] = replacement

    if sio:
        disk_image(out/'sectors.atr')

    def installed(b):
        if sio:
            b.mount(0, str(out/'sectors.atr'))
        at = program['labels']['sdx_probe_installed']
        condition = f'@xpc=${at:x}'
        b.bp_set(at & 65535, condition=condition)
        run_to(b, at & 65535, frame_limit=120, timeout=10, condition=condition)
        require(b.memdump(0xc000, 0x1000) == effective[:0x1000], 'Task low ROM shadow differs')
        require(b.memdump(0xd800, 0x2800) == effective[0x1800:], 'Task high ROM shadow differs')
        b.bp_clear_all()
        if trace:
            b.profile_start()

    for name in ('EXEC816_LATENCY_TRACE', 'EXEC816_MASK_TRACE', 'EXEC816_LATENCY_PCS'):
        os.environ.pop(name, None)
    if trace:
        marks = {k: v for k, v in program['labels'].items()
                 if k.startswith(('sio_', 'native_', 'sdx_', 'signal_route'))}
        if rawcon:
            for name in ('pointer_port_read','pointer_sample','pointer_sample_return',
                         'timer_tick','timer_sample'):
                marks[name]=program['labels'][name]
            for bank in (0x30,0x31):
                for pc in (0xf661,0xf681,0xf087):
                    marks[f'cell_{bank:x}_{pc:x}']=bank*65536+pc
        os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_MASK_TRACE='1',
                          EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    machineout = out/('trace' if trace else 'replay')
    machineout.mkdir(exist_ok=True)
    with emulator(BRIDGE, ROM, machineout, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        if sio:
            b.config('diskemu', 'generic56k' if profile=='generic56k' else '810')
        machine = verify_machine(b, ROM, PIN)
        try:
            runtime, _ = execute(b, program, timeout=45, frame_limit=2000, before_run=installed)
        except Exception:
            print('SDX state:', b.memdump(0x287800, 16).hex(), 'CPU:', b.regs(),
                  'checks:', data(b, program['image'], 'checks'), flush=True)
            raise
        if trace:
            b.profile_stop()
        ownership(b, program, out)
        progress = data(b, program['image'], 'progress', True)
        peer = int.from_bytes(bytes(data(b, program['image'], 'peer')), 'little')
        checks = int.from_bytes(bytes(data(b, program['image'], 'checks')), 'little')
        state = b.memdump(0x287800, 34)
        contexts = b.memdump(0x287a00, 32)
        busy_seen=data(b,program['image'],'busySeen',True)[0]
        frames=bytes(data(b,program['image'],'snapshots'))
        (out/'contexts.bin').write_bytes(contexts)
        require(progress == ([1, 0] if mode == 'raw' else [2, 2]), 'Guest progress differs')
        if mode == 'opt':
            require(peer > 0, 'Native peer made no progress')
            if not phase:
                require(int.from_bytes(state[12:14], 'little') > 1000, 'Owned pointer IRQ path was not exercised')
        for slot in range(1 if mode == 'raw' else 2):
            at = slot*16
            expected = bytes([0x30+slot])+struct.pack('<4H', 0x7e00+slot*256, 0xa6, 0x5a, 0xab04)
            expected += bytes.fromhex('3733')+struct.pack('<H', 0x3013 if mode == 'raw' else 0x3032 if rawcon else 0x302c)
            require(frames[slot*13:(slot+1)*13] == expected, 'Guest register/status/JSR frame differs')
            require(contexts[at+4:at+6] == bytes.fromhex('e001'), 'Guest stack drifted')
        require(runtime['vbi_dispatches'] > 0, 'No ordinary VBI scheduling occurred')
        require(not early or state[16:18] == bytes([1, 0]), 'Forced E=1 entry NMI did not run')
        sectors_read = data(b, program['image'], 'sectorsRead', True)[0] if sio else 0
        if sio:
            require(sectors_read >= 8, 'Storage workload incomplete')
            require(int.from_bytes(state[28:30], 'little') > 0, 'No serial IRQ interrupted a guest')
            require(int.from_bytes(state[30:32], 'little') > 0, 'No owned IRQ deferred-work handoff')
        require(state[26:28] == bytes(2), 'Pending VBI escaped to guest instructions')
        if phase:
            require(int.from_bytes(state[24:26], 'little') == (1 if phase == 1 else 2),
                    'Forced restore boundary did not interrupt both guests exactly once')
            require(state[12:14] == bytes(2), 'An IRQ could hide late pending service')
            if phase < 10:
                require(int.from_bytes(state[20:22], 'little') >= (1 if phase == 1 else 2),
                        'Native partial-frame interception did not run')
        require(state[0] == 0 and state[2:6] == bytes(4), 'Guest ownership or deferred NMI leaked')
    result = dict(status='pass', tier='development', mode=mode, checks=checks,
                progress=progress, peer_iterations=peer, runtime=runtime, machine=machine,
                guest_nmis=int.from_bytes(state[10:12], 'little'),
                owned_irqs=int.from_bytes(state[12:14], 'little'),
                deferred_native_nmis=int.from_bytes(state[14:16], 'little'),
                early_entry_injection=early, return_boundary=phase, sio=sio, profile=profile, rawcon=rawcon, sectors_read=sectors_read,
                guest_serial_irqs=int.from_bytes(state[28:30], 'little'),
                owned_work_handoffs=int.from_bytes(state[30:32], 'little'),
                busy_rejections=busy_seen,
                forced_return_nmis=int.from_bytes(state[24:26], 'little'),
                intercepted_returns=int.from_bytes(state[20:22], 'little'),
                transition_pc_reservation=list(reserved),
                input_rom_sha256=sha256(ROM), effective_rom_sha256=hashlib.sha256(effective).hexdigest(),
                emulator_sha256=PIN['emulator']['sha256'], vector_patches=patches,
                source_sha256={str(path.relative_to(ROOT)):sha256(path) for path in (
                    Path(__file__), ROOT/'platform/altirraos/sdx-runtime-probe.s', ROOT/'platform/altirraos/sdx-rom-shadow.s')},
                build=program['build'], production_bank_zero_delta=dict(fixed=0, per_task=0),
                fixture_bank_zero_borrowed_bytes=512,
                scope=('Focused native Run ABI and guest service return' if mode == 'raw' else
                       'Sequential resident guests with real stock-810 reads and pointer IRQs' if sio else
                       'Sequential resident guests, native peer and forced VBI return boundary' if phase else
                       'Single guest lease, blocked service, busy rejection, native peer and pointer IRQs')
                       +'; no SDX binary or production slot allocator')

    if trace:
        from sio_adapter_trace import analyze
        from sio_transaction_trace import read_events
        timing = analyze(machineout/'emulator.log', marks, divisor=8 if profile=="generic56k" else 40)
        events = read_events(machineout/'emulator.log')
        if rawcon:
            from sio_transaction_trace import BASE_HZ,stats
            pending={};intervals=[];service_bank=None
            interrupts=[t for t,e in events if e[0]=='cpu' and int(e[4],16) in
                        tuple(marks[n] for n in ('native_nmi','sdx_probe_native_nmi',
                              'sdx_probe_nmi_stub','native_irq','sdx_probe_irq_stub'))]
            from bisect import bisect_left
            for tick,event in events:
                if event[0]!='cpu':continue
                pc=int(event[4],16);bank=pc>>16;low=pc&65535
                if pc==marks['sdx_probe_service']:
                    service_bank=0x30+(int(event[9],16)-0x7e00)//256
                if pc==marks['sdx_probe_cell_committed'] and service_bank in pending:
                    pending[service_bank][2]=True
                if bank not in (0x30,0x31):continue
                if low in (0xf661,0xf681):
                    # An IRQ sampled before SEI can return to that same PC.
                    # Its intermediate trampoline is not cell completion.
                    if bank not in pending:
                        pending[bank]=[tick,'get' if low==0xf661 else 'put',False]
                elif low==0xf087 and bank in pending and pending[bank][2]:
                    begin,kind,_=pending.pop(bank)
                    i=bisect_left(interrupts,begin)
                    interrupted=i<len(interrupts) and interrupts[i]<=tick
                    # Include the emulation RTI after its observation point.
                    intervals.append(dict(kind=kind,clocks=tick-begin+6/8,
                                          interrupted=interrupted))
            require(not pending and len(intervals)>1000,'Missing production cell observations')
            timing['cells']={kind:dict(count=sum(v['kind']==kind for v in intervals),
                uninterrupted=stats([v['clocks'] for v in intervals
                                     if v['kind']==kind and not v['interrupted']]),
                interrupted=stats([v['clocks'] for v in intervals
                                   if v['kind']==kind and v['interrupted']]))
                            for kind in ('get','put')}
            maximum=max(v['clocks']/BASE_HZ*1e6 for v in intervals if not v['interrupted'])
            timing['cell_masked_max_us']=maximum
            require(maximum<=50,'Fast-cell masked transition exceeds 50 us: '+str(maximum))
            reads=[t for t,e in events if e[0]=='cpu'
                   and int(e[4],16)==marks['pointer_port_read']]
            gaps=[b-a for a,b in zip(reads,reads[1:])]
            require(gaps and max(gaps)/BASE_HZ<.001,
                    'Pointer sampling gap exceeds 1 ms: '+str(stats(gaps)))
            timing['pointer_sample_gaps']=stats(gaps)
        timing['observations_sha256'] = hashlib.sha256(
            '\n'.join(' '.join(e) for _, e in events).encode()).hexdigest()
        (out/'timing.json').write_text(json.dumps(timing, indent=2)+'\n')
        require(timing['verdict'] == 'pass', 'SIO timing failed: '+str(timing['violations']))
        replay = run(out, mode, early, phase, sio, program=program,profile=profile,rawcon=rawcon)
        fields = ('checks', 'runtime', 'progress', 'peer_iterations', 'guest_nmis',
                  'owned_irqs', 'deferred_native_nmis', 'guest_serial_irqs',
                  'owned_work_handoffs', 'busy_rejections', 'intercepted_returns', 'sectors_read')
        for key in fields:
            require(result[key] == replay[key], 'Observer changed '+key)
        result['timing'] = {k: v for k, v in timing.items() if k not in ('tx_frames', 'rx_bytes')}
        result['trace_replay'] = dict(status='identical', xex_sha256=sha256(program['xex']))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/sdx-tasks')
    parser.add_argument('--early-entry', action='store_true')
    parser.add_argument('--profile',choices=('stock810','generic56k'),default='stock810')
    parser.add_argument('--sio', action='store_true')
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--rawcon', action='store_true',help='Exercise production bound cells alongside real SIO/pointer IRQs')
    parser.add_argument('--return-boundary', type=int, choices=range(1, 12), default=0)
    parser.add_argument('--case', choices=('opt', 'raw'), default='opt')
    args = parser.parse_args()
    require(not args.return_boundary or (args.case == 'opt' and not args.early_entry),
            'Return-boundary tests require optimized guests without the IRQ entry hold')
    require(not args.sio or (args.case == 'opt' and not args.return_boundary and not args.early_entry),
            'Storage checks require ordinary optimized guests')
    require(not args.trace or args.sio, 'Wire tracing requires --sio')
    require(not args.rawcon or (args.sio and args.case=='opt'), 'RAWCON IRQ checks require optimized --sio')
    out = args.output.resolve()
    result = dict(status='running')
    started = time.monotonic()
    try:
        result = run(out, args.case, args.early_entry, args.return_boundary, args.sio, args.trace,profile=args.profile,rawcon=args.rawcon)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        result['seconds'] = round(time.monotonic()-started, 3)
        out.mkdir(parents=True, exist_ok=True)
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('status', 'checks', 'progress', 'peer_iterations', 'guest_nmis', 'seconds')}))


if __name__ == '__main__':
    main()
