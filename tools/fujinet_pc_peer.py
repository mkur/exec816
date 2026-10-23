"""Functional raw-SIO relay to a separate, isolated real FujiNet-PC process.

Altirra's existing custom-device TCP interface bridges complete SIO frames to
FujiNet's NetSIO UDP protocol. Responses use the target's observed bit period.
Host waits pause emulator advancement: this is functional firmware/media
integration evidence, not wall-clock or physical UART qualification.
"""
from collections import deque
from contextlib import AbstractContextManager
import json
import secrets
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time


SCRIPT='''option "name": "Exec816 real FujiNet-PC relay";
option "network": { port: @PORT@ };
Segment command: { size: 5 };
Segment payload: { size: 4096 };
Segment wire: { size: 4 };
Thread monitor;
Thread worker;
function void transfer() {
    int i=0;
    command.write_byte(0,$sio.recv_raw_byte());
    int cpb=$aux;
    i=1;
    while (i<5) { command.write_byte(i,$sio.recv_raw_byte());i=i+1; }
    $sio.wait_command_off();
    if (@UNMOUNTED@) return;
    int count=$network.send_message(1,cpb);
    cpb=wire.read_byte(0) | (wire.read_byte(1)<<8);
    int writing=0;
    if (count<0) { writing=0-count;count=1; }
    Thread.sleep(1600);
    i=0;
    while (i<count) {
        if (i==1) Thread.sleep(1600);
        $sio.send_raw_byte(payload.read_byte(i),cpb);i=i+1;
    }
    int cmd=command.read_byte(1);
    if ((writing>0 || cmd==$50 || cmd==$57 || cmd==$4f) && count==1 && payload.read_byte(0)==$41) {
        int size=256;
        if (writing>0) size=writing;
        else if (cmd==$4f) size=12;
        else if (command.read_byte(3)==0 && command.read_byte(2)<4) size=128;
        i=0;
        while (i<size+1) { payload.write_byte(i,$sio.recv_raw_byte());i=i+1; }
        count=$network.send_message(2,size+1);
        cpb=wire.read_byte(0) | (wire.read_byte(1)<<8);
        Thread.sleep(1600);
        i=0;
        while (i<count) {
            if (i==1) Thread.sleep(1600);
            $sio.send_raw_byte(payload.read_byte(i),cpb);i=i+1;
        }
    }
}
function void watch() {
    loop { $sio.wait_command();worker.run(transfer); }
}
event "cold_reset": function {
    $sio.enable_raw(true);worker.interrupt();monitor.run(watch);
};
'''


def checksum(data):
    total=0
    for value in data:
        total+=value;total=(total&255)+(total>>8)
    return total


class FujiNetPC(AbstractContextManager):
    def __init__(self,output,media,firmware,readonly=False,mounts=None,configuration_menu=False,hsio_index=8,
                 fault=None,fault_query=1):
        self.output,self.media,self.firmware=map(Path,(output,media,firmware))
        self.stop=threading.Event();self.condition=threading.Condition();self.received=deque()
        self.peer=None;self.connected=threading.Event();self.error=None;self.commands=[];self.sequence=0
        self.readonly=readonly
        self.configuration_menu=configuration_menu
        self.hsio_index=hsio_index
        self.peripheral_baud=19200
        self.response_baud=19200
        self.baud_changes=[]
        self.fault,self.fault_query=fault,fault_query
        self.query_count=0
        self.fault_events=[]
        self.write_count=0
        self.sector_sizes={48+drive:256 for drive,_,_ in (mounts or [(1,self.media,readonly)])}
        self.mounts=mounts or [(1,self.media,readonly)]
        if len({drive for drive,_,_ in self.mounts})!=len(self.mounts):
            raise ValueError('Duplicate FujiNet drive')
        for drive,path,_ in self.mounts:
            if drive not in range(1,9) or Path(path).resolve().parent!=self.media.resolve().parent:
                raise ValueError('FujiNet test mounts require D1..D8 in one media directory')

    def __enter__(self):
        self.output.mkdir(parents=True,exist_ok=True)
        self.udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.udp.bind(('127.0.0.1',0));self.udp.settimeout(.1)
        while True:
            self.tcp=socket.socket()
            try:
                self.tcp.bind(('127.0.0.1',20480+secrets.randbelow(24576)))
                break
            except OSError:self.tcp.close()
        self.tcp.listen(1);self.tcp.settimeout(.1)
        self.script=self.output/'peer.atdevice'
        unmounted=' && '.join(f'command.read_byte(0)!=${48+drive:x}' for drive,_,_ in self.mounts)
        if self.configuration_menu:unmounted+=' && command.read_byte(0)!=$70'
        self.script.write_text(SCRIPT.replace('@PORT@',str(self.tcp.getsockname()[1])).replace('@UNMOUNTED@',unmounted))
        config=self.output/'fnconfig.ini'
        config.write_text(f'[General]\ndevicename=Exec816-test\nhsioindex={self.hsio_index}\nconfigenabled={int(self.configuration_menu)}\nstatus_wait_enabled=0\n'
            '[WiFi]\nenabled=1\n[Host1]\ntype=SD\nname=SD\n'
            +''.join(f'[Mount{drive}]\nhostslot=1\npath=/{Path(path).name}\nmode={"r" if ro else "w"}\n'
                     for drive,path,ro in self.mounts)+
            f'[BOIP]\nenabled=1\nhost=127.0.0.1\nport={self.udp.getsockname()[1]}\n')
        self.log=(self.output/'firmware.log').open('w')
        self.threads=[threading.Thread(target=self.receive,daemon=True),threading.Thread(target=self.serve,daemon=True)]
        for thread in self.threads:thread.start()
        self.process=subprocess.Popen([str(self.firmware),'-c',str(config),'-s',str(self.media.parent)],
            cwd=self.firmware.parent,stdout=self.log,stderr=self.log)
        if not self.connected.wait(10):
            self.__exit__(None,None,None);raise RuntimeError('FujiNet-PC did not connect to isolated NetSIO hub')
        return self

    def send(self,data):
        if self.peer:self.udp.sendto(data,self.peer)

    def receive(self):
        while not self.stop.is_set():
            try:data,self.peer=self.udp.recvfrom(2048)
            except socket.timeout:continue
            except OSError:return
            if data[0]==0xc2:self.send(b'\xc3')
            elif data[0]==0xc4:self.send(b'\xc5')
            elif data[0] in (0xc1,0xc6):
                self.send(b'\xc7\xff')
                if data[0]==0xc1:
                    self.send(b'\x80'+struct.pack('<I',19200));self.connected.set()
            elif data[0]==0x81 and len(data)>=6 and data[2]==1:
                # Command-off sync carries the ACK and expected write size.
                # NetSIO deliberately defers WRITE ACK until this handshake.
                with self.condition:
                    self.write_count=int.from_bytes(data[4:6],'little')
                    self.received.append((data[3],self.peripheral_baud));self.condition.notify_all()
            elif data[0]==0x80 and len(data)>=5:
                self.peripheral_baud=int.from_bytes(data[1:5],'little')
                self.baud_changes.append(self.peripheral_baud)
            elif data[0] in (1,2):
                with self.condition:
                    self.received.extend((b,self.peripheral_baud) for b in
                                         (data[1:] if data[0]==2 else data[1:2]));self.condition.notify_all()

    def take(self,count,timeout=3):
        deadline=time.monotonic()+timeout
        with self.condition:
            while len(self.received)<count:
                left=deadline-time.monotonic()
                if left<=0:raise RuntimeError(f'FujiNet-PC response timeout ({len(self.received)}/{count})')
                self.condition.wait(min(left,.1))
            values=[self.received.popleft() for _ in range(count)]
            if values:self.response_baud=values[0][1]
            return bytes(b for b,_ in values)

    def recv_exact(self,count):
        result=b''
        while len(result)<count:
            try:chunk=self.connection.recv(count-len(result))
            except socket.timeout:
                if self.stop.is_set():raise EOFError()
                continue
            if not chunk:raise EOFError()
            result+=chunk
        return result

    def read_segment(self,index,size):
        self.connection.sendall(struct.pack('<BBII',6,index,0,size))
        return self.recv_exact(size)

    def reply(self,data):
        result=len(data)
        if isinstance(data,tuple):data,result=data
        period={19200:94,57600:30}.get(self.response_baud,round(1773447.5/self.response_baud))
        self.connection.sendall(struct.pack('<BBII',7,2,0,4)+struct.pack('<I',period)+
                                struct.pack('<BBII',7,1,0,len(data))+data+
                                struct.pack('<Bi',1,result))

    def transfer(self,kind,value):
        if kind==1:
            command=self.read_segment(0,5)
            if checksum(command[:4])!=command[4]:raise RuntimeError('Bad target SIO command checksum')
            with self.condition:self.received.clear();self.write_count=0
            baud=57600 if value<50 else 19200
            peripheral_baud=self.peripheral_baud
            self.send(b'\x80'+struct.pack('<I',baud))
            # NetSIO carries the command-line edges separately from bytes.
            # Leave a host scheduling turn for the firmware to observe ON;
            # a zero-time ON/data/OFF burst can be drained before bus dispatch.
            self.send(b'\x11');time.sleep(.002)
            # NetSIO's XOR corruption is a no-op when both baud rates have
            # identical low bytes (19200 and 57600 do). Model the invalid wire
            # frame explicitly so the real firmware's recovery policy runs.
            mismatch=abs(baud-peripheral_baud)>peripheral_baud*.1
            frame=command[:-1]+bytes([command[-1]^1]) if mismatch else command
            self.send(b'\x02'+frame+b'\0');time.sleep(.002)
            self.sequence=(self.sequence+1)&255
            self.send(bytes([0x18,self.sequence]))
            self.commands.append(dict(device=command[0],command=command[1],aux=int.from_bytes(command[2:4],'little'),bit_cycles=value,
                                      host_baud=baud,peripheral_baud=peripheral_baud,rate_mismatch=mismatch))
            try:ack=self.take(1)
            except RuntimeError:
                # CONFIG may deliberately ignore initial disk STATUS polls.
                # Leave the target to take its ordinary wire timeout/retry.
                self.commands[-1]['no_response']=True
                return b''
            if command[0]==0x70:
                if ack!=b'A':return ack
                if self.write_count:
                    if self.write_count>4096:raise RuntimeError('FujiNet control payload too large')
                    return ack,1-self.write_count
                completion=self.take(1)
                if completion!=b'C':return ack+completion
                # COMPLETE follows construction of control replies. NetSIO
                # sends the following data/checksum as a block; collect that
                # already-produced frame without prescribing a command table.
                time.sleep(.05)
                with self.condition:
                    body=bytes(b for b,_ in self.received);self.received.clear()
                if body and checksum(body[:-1])!=body[-1]:raise RuntimeError('Bad FujiNet control checksum')
                return ack+completion+body
            if ack!=b'A' or command[1] in (0x50,0x57,0x4f):return ack
            completion=self.take(1)
            if completion!=b'C':return ack+completion
            size={0x53:4,0x4e:12,0x3f:1}.get(command[1],128 if int.from_bytes(command[2:4],'little')<4
                else self.sector_sizes.get(command[0],256))
            body=self.take(size+1)
            if checksum(body[:-1])!=body[-1]:raise RuntimeError('Bad FujiNet-PC read checksum')
            if command[1]==0x3f:
                # Firmware publishes its new rate after writing this reply.
                # Deliver that asynchronous notification before emulation can
                # issue the next command; retain the reply's original rate.
                time.sleep(.01)
                self.query_count+=1
            eligible=(command[1]==0x3f and self.query_count==self.fault_query and
                      self.fault in ('query-lost','query-checksum')) or (
                      command[1]==0x52 and baud==57600 and self.query_count>=self.fault_query and
                      self.fault in ('read-checksum','terminal-error','read-error','nak','disconnect','partial-data','chain-self','chain-zero','chain-count'))
            if eligible and not self.fault_events:
                self.fault_events.append(dict(fault=self.fault,command=command.hex(),queries=self.query_count))
                if self.fault in ('query-lost','disconnect'):return b''
                if self.fault in ('query-checksum','read-checksum'):body=body[:-1]+bytes([body[-1]^1])
                if self.fault=='terminal-error':return ack+b'E'
                if self.fault=='read-error':completion=b'E'
                if self.fault=='nak':return b'N'
                if self.fault=='partial-data':return ack+completion+body[:12]
                if self.fault.startswith('chain-'):
                    data=bytearray(body[:-1])
                    if self.fault=='chain-self':data[253:255]=bytes([command[3],command[2]])
                    if self.fault=='chain-zero':data[253:255]=b'\0\0'
                    if self.fault=='chain-count':data[255]=0
                    body=bytes(data)+bytes([checksum(data)])
            if command[1]==0x53:self.sector_sizes[command[0]]=256 if body[0]&0x20 else 128
            return ack+completion+body
        body=self.read_segment(1,value)
        if checksum(body[:-1])!=body[-1]:raise RuntimeError('Bad target SIO write checksum')
        self.send(b'\x02'+body+b'\0')
        return self.take(2)

    def serve(self):
        try:
            while not self.stop.is_set():
                try:self.connection,_=self.tcp.accept();break
                except socket.timeout:continue
            else:return
            self.connection.settimeout(.2)
            while not self.stop.is_set():
                frame=self.recv_exact(17);command,address,value,_=struct.unpack('<BIIQ',frame)
                if command==7:
                    response=self.transfer(address,value)
                    if self.commands:self.commands[-1]['response_baud']=self.response_baud
                    self.reply(response)
                elif command!=8:self.connection.sendall(struct.pack('<BI',1,0))
        except EOFError:
            pass
        except OSError:
            # The emulator closes this socket when its normal test context
            # exits. Transfer/protocol failures above still record their cause.
            pass
        except Exception as error:
            self.error=str(error)
            try:self.connection.close()
            except OSError:pass

    def __exit__(self,*args):
        self.stop.set()
        for endpoint in (getattr(self,'connection',None),self.tcp,self.udp):
            if endpoint:
                try:endpoint.close()
                except OSError:pass
        if hasattr(self,'process'):
            self.process.terminate()
            try:self.process.wait(5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(5)
        for thread in self.threads:thread.join(1)
        self.log.close()
        (self.output/'relay.json').write_text(json.dumps(dict(error=self.error,commands=self.commands,baud_changes=self.baud_changes,fault_events=self.fault_events,
            scope='Real FujiNet-PC/NetSIO media operations through raw-SIO custom-device relay; no wall-clock or physical UART qualification'),indent=2)+'\n')
