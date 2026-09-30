#!/usr/bin/env python3
"""Produce independent fixtures by executing the original MyDOS 4.50 FMS.

Only the disposable boot disk is assembled on the host. Target volumes are
formatted, populated and read back through original MyDOS CIO, without Exec816.
"""
import json,struct,time
from pathlib import Path
from native_program import ROOT,command,require,sha256,verify_machine
from os_boundary import emulator
from test_sio_device import PIN

SOURCE=ROOT/'build/mydos-design'
ORIGINAL_URL='https://ftp.pigwa.net/stuff/collections/holmes%20cd/Holmes%201/ATR%20Programs/Disk%20Operating%20Systems/Mydos%204.50.atr'
ORIGINAL_SHA256='0c13eb9175975636e231be335341eb91fd143dc19e090efa995c09374ff313a1'

def original():
    path=SOURCE/'Mydos-4.50.atr'
    if not path.exists():
        import urllib.request
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(urllib.request.urlopen(ORIGINAL_URL,timeout=30).read())
    require(sha256(path)==ORIGINAL_SHA256,'Unpinned original MyDOS producer')
    return path

def blank(path,size,count):
    length=384+(count-3)*size;paras=length//16
    path.write_bytes(struct.pack('<HHHH',0x296,paras&65535,size,paras>>16)+bytes(8)+bytes(length))

def boot_disk(path,payload):
    base=original().read_bytes()
    disk=bytearray(16+720*128);disk[:16]=struct.pack('<HHH',0x296,5760,128)+bytes(10)
    first=93
    disk[16:16+(first-1)*128]=base[16:16+(first-1)*128]
    sector=lambda n:16+(n-1)*128
    directory=sector(361);disk[directory:directory+32]=base[directory:directory+32]
    count=(len(payload)+124)//125
    require(first+count<360,'Producer overlaps boot directory')
    for i in range(count):
        data=payload[i*125:(i+1)*125];at=sector(first+i);following=first+1+i if i+1<count else 0
        disk[at:at+len(data)]=data;disk[at+125:at+128]=bytes([(2<<2)|(following>>8),following&255,len(data)])
    disk[directory+32:directory+48]=bytes([0x42])+struct.pack('<HH',count,first)+b'AUTORUN SYS'
    vtoc=sector(360);disk[vtoc:vtoc+5]=bytes([2])+struct.pack('<HH',707,707-(first-4)-count)
    for n in range(first+count,720):
        if not 360<=n<=368:disk[vtoc+10+n//8]|=0x80>>(n&7)
    path.write_bytes(disk)

def jobs(size):
    entries=[dict(op=34,name='D2:TOOLS'),dict(op=34,name='D2:TOOLS:SUB')]
    entries += [dict(op=3,name='D2:TOOLS:SUB:DATA.BIN',size=777,seed=0x53,flags=0),dict(op=3,name='D2:EMPTY',size=0,seed=0,flags=0),dict(op=3,name='D2:TEXT.TXT',size=259,seed=0x22,flags=0),dict(op=3,name='D2:LOCKED.BIN',size=17,seed=0x9b,flags=32),dict(op=3,name='D2:EXT.BIN',size=600,seed=0x31,flags=4)]
    entries += [dict(op=3,name='D2:CASE.TXT',size=9,seed=0x11,flags=0),dict(op=3,name='D2:case.txt',size=11,seed=0x12,flags=0),dict(op=3,name='D2:A@_`.BIN',size=5,seed=0x13,flags=0)]
    if size==256:
        entries += [dict(op=3,name='D2:HOLE.BIN',size=253*8,seed=0x61,flags=4),dict(op=3,name='D2:PAD.BIN',size=253*1100,seed=0xa7,flags=4),dict(op=33,name='D2:HOLE.BIN'),dict(op=3,name='D2:LARGE.BIN',size=70003,seed=0x81,flags=4)]
    # Fill all 64 root entries; the nested directory is independent.
    used=10 if size==256 else 8
    entries += [dict(op=3,name=f'D2:F{i:02}.BIN',size=i%5,seed=i,flags=0) for i in range(64-used)]
    return entries

def assemble(out,size,count):
    entries=jobs(size)
    table=[];names=[]
    for i,j in enumerate(entries):
        table += [f'.word name{i}',f'.byte {j["op"]},{j.get("flags",0)},{j.get("seed",0)}',f'.word {j.get("size",0)//1024},{j.get("size",0)%1024}']
        names.append(f'name{i}: .byte '+','.join(str(c) for c in j['name'].encode()+b'\0'))
    source='''.setcpu "6502"
.segment "CODE"
.export start,done,failed,result,job_index,phase
CIO=$e456
IOCB=$350
start:
    cld
    ldx #$ff
    txs
    cli
    lda #0
    sta job_index
    sta result
    sta phase
    ; Format only the target filesystem. AUX2 bit 7 suppresses physical format,
    ; as implemented by the original MDOS2.ASM FORMAT routine.
    lda #<diskname
    sta IOCB+4
    lda #>diskname
    sta IOCB+5
    lda #254
    sta IOCB+2
    lda #COUNTLO
    sta IOCB+10
    lda #COUNTHI
    sta IOCB+11
    jsr call
    lda #<table
    sta entry
    lda #>table
    sta entry+1
next_job:
    ldy #0
copy_job:
    lda (entry),y
    sta job,y
    iny
    cpy #9
    bne copy_job
    lda job
    sta IOCB+4
    lda job+1
    sta IOCB+5
    lda job+2
    sta IOCB+2
    lda #8
    sta IOCB+10
    lda job+3
    sta IOCB+11
    jsr call
    lda job+2
    cmp #3
    bne advance
    ; Every created file is closed, then read and verified through original CIO.
    lda #11
    sta operation
    jsr transfer
    jsr close
    lda job
    sta IOCB+4
    lda job+1
    sta IOCB+5
    lda #3
    sta IOCB+2
    lda #4
    sta IOCB+10
    jsr call
    lda #7
    sta operation
    jsr transfer
    jsr close
advance:
    inc job_index
    lda job_index
    cmp #JOBS
    beq complete
    clc
    lda entry
    adc #9
    sta entry
    bcc next_job
    inc entry+1
    jmp next_job
complete:
    lda #1
    sta result
done:
    jmp done
call:
    inc phase
    ldx #$10
    jsr CIO
    tya
    bmi failed
    rts
close:
    lda #12
    sta IOCB+2
    jmp call
failed:
    sty result
    jmp failed
transfer:
    lda job+5
    sta chunks
    lda job+6
    sta chunks+1
chunks_loop:
    lda chunks
    ora chunks+1
    beq tail
    lda #0
    sta length
    lda #4
    sta length+1
    jsr chunk
    lda chunks
    bne :+
    dec chunks+1
:
    dec chunks
    jmp chunks_loop
tail:
    lda job+7
    sta length
    lda job+8
    sta length+1
    ora length
    beq empty
    jmp chunk
empty:
    rts
chunk:
    lda #<buffer
    sta pointer
    sta IOCB+4
    lda #>buffer
    sta pointer+1
    sta IOCB+5
    ldx #4
    ldy #0
fill:
    tya
    eor job+4
    sta (pointer),y
    iny
    bne fill
    inc pointer+1
    dex
    bne fill
    lda operation
    sta IOCB+2
    lda length
    sta IOCB+8
    lda length+1
    sta IOCB+9
    jsr call
    lda operation
    cmp #7
    bne empty
    lda #<buffer
    sta pointer
    lda #>buffer
    sta pointer+1
    ldy #0
verify:
    tya
    eor job+4
    cmp (pointer),y
    bne mismatch
    iny
    bne :+
    inc pointer+1
:
    lda length
    bne :+
    dec length+1
:
    dec length
    lda length
    ora length+1
    bne verify
    rts
mismatch:
    ldy #$ff
    jmp failed
entry=$80
pointer=$82
job: .res 9
chunks: .res 2
length: .res 2
operation: .byte 0
result: .byte 0
job_index: .byte 0
phase: .byte 0
diskname: .byte "D2:",0
table:
TABLE
NAMES
buffer=$9000
'''.replace('COUNTLO',str(count&255)).replace('COUNTHI',str((count>>8)|128)).replace('JOBS',str(len(entries))).replace('TABLE','\n'.join(table)).replace('NAMES','\n'.join(names))
    (out/'producer.s').write_text(source)
    (out/'producer.cfg').write_text('MEMORY { RAM: start=$6000,size=$3000,file=%O; } SEGMENTS { CODE: load=RAM,type=ro; }\n')
    command(['ca65','-o',out/'producer.o',out/'producer.s']);command(['ld65','-C',out/'producer.cfg','-o',out/'producer.bin','-Ln',out/'producer.lbl',out/'producer.o'])
    labels={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in (out/'producer.lbl').read_text().splitlines()}
    binary=(out/'producer.bin').read_bytes();payload=struct.pack('<HHH',65535,0x6000,0x6000+len(binary)-1)+binary+struct.pack('<HHH',0x2e0,0x2e1,labels['start'])
    return payload,labels,entries

def produce(out,size,count):
    out.mkdir(parents=True,exist_ok=True)
    payload,labels,entries=assemble(out,size,count)
    boot=out/'boot.atr';target=out/'volume.atr';boot_disk(boot,payload);blank(target,size,count)
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.config('siopatch','on');b.config('diskemu','fastest')
        b.mount(1,str(target));b.bp_set(labels['done']);b.bp_set(labels['failed']);b.boot(str(boot))
        deadline=time.monotonic()+240
        b.resume()
        while time.monotonic()<deadline:
            regs=b.regs();pc=int(regs['PC'].lstrip('$'),16)
            if pc in (labels['done'],labels['failed']):break
            if b.eval_expr('@frame')>12000:break
            time.sleep(0.02)
        b.pause()
        result=b.peek(labels['result'])[0];job=b.peek(labels['job_index'])[0];phase=b.peek(labels['phase'])[0]
        print('producer',size,'PC',regs['PC'],'result',result,'job',job,'phase',phase,'Y',regs['Y'],'IOCB',b.memdump(0x350,16).hex(),flush=True)
        require(pc==labels['done'] and result==1,'Original MyDOS producer did not complete')
        # The pinned disk interface auto-flushes after 1.75 seconds of host
        # inactivity, on a 500-ms timer. Eject itself does not flush dirty data.
        # Keep the attachment alive beyond that timer before reading its bytes.
        time.sleep(3)
        b.regs()
        b._cmd_ok('EJECT drive=1')
    return dict(status='pass',machine=machine,profile=PIN,overrides={'siopatch':'on','diskemu':'fastest'},emulator_sha256=sha256(ROOT/'build/altirra-sio-multi/AltirraBridgeServer'),sector_bytes=size,sectors=count,media_sha256=sha256(target),boot_sha256=sha256(boot),producer_sha256=sha256(out/'producer.bin'),jobs=entries,original_sha256=sha256(original()))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--size',type=int,choices=(128,256),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=produce(a.output.resolve(),a.size,720 if a.size==128 else 2000)
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
