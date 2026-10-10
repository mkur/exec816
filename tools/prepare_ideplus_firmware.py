"""Convert the pinned vendor BIOS21.COM updater's literal banks to an Altirra ROM."""
import argparse,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COM_SHA='1adcbe6d28f5dd7aacf7a0fda7fa68a14a2ac870825572c41222dbebc7a2d739'
ROM_SHA='00ee56b1cd8bc5283a6561f87beea1e8c1bfe09453a4bafbed24889bbf0e4039'
def convert(source):
    payload=source.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=COM_SHA: raise ValueError('Unpinned BIOS21.COM')
    memory=bytearray(65536);cursor=2
    if payload[:2]!=b'\xff\xff': raise ValueError('Not an Atari executable')
    while cursor<len(payload):
        start,end=struct.unpack_from('<HH',payload,cursor);cursor+=4
        amount=end-start+1
        if end<start or cursor+amount>len(payload):raise ValueError('Invalid updater segment')
        memory[start:end+1]=payload[cursor:cursor+amount];cursor+=amount
    rom=bytearray([255])*131072
    for bank in range(15):rom[bank*2048:bank*2048+1536]=memory[0x2eae+bank*1536:0x2eae+(bank+1)*1536]
    if hashlib.sha256(rom).hexdigest()!=ROM_SHA: raise ValueError('BIOS ROM hash differs')
    return rom
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('updater',type=Path);p.add_argument('--output',type=Path,default=ROOT/'build/firmware/ideplus-bios-2.1.rom');a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(convert(a.updater));print(a.output)
