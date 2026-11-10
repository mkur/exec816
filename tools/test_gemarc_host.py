#!/usr/bin/env python3
"""Independent ARC byte oracles and checked-engine failure regressions."""
import argparse,ctypes as C,hashlib,json,shutil,struct,subprocess
from pathlib import Path
from native_program import ROOT,require,sha256
from prepare_gemarc import prepare,CACHE


class Entry(C.Structure):
    _fields_=[('name',C.c_char*13),('method',C.c_uint8),('sel',C.c_uint8),
        ('date',C.c_uint16),('time',C.c_uint16),('crc',C.c_uint16),
        ('csize',C.c_uint32),('osize',C.c_uint32),('data',C.c_uint32)]
class Recovery(C.Structure):
    _fields_=[('temp',C.c_char*256),('backup',C.c_char*256),
        ('original_moved',C.c_uint8),('published',C.c_uint8),('uncertain_close',C.c_uint8)]
Names=(C.c_char*13)*64


def crc(data):
    value=0
    for byte in data:
        value^=byte
        for _ in range(8):value=(value>>1)^((0xa001) if value&1 else 0)
    return value


def member(name,method,data,plain,bad_crc=False):
    raw=name.encode().ljust(13,b'\0')
    header=b'\x1a'+bytes([method])+raw+struct.pack('<IHHH',len(data),0,0,crc(plain)^bad_crc)
    return header+(b'' if method==1 else struct.pack('<I',len(plain)))+data


def corpus():
    plain=bytes(range(256))*180
    packed=b'A\x90\x06\x90\0B'
    squeezed=struct.pack('<Hhh',1,-66,-257)+b'\0\x01'
    def unix(data,bits):
        result=subprocess.run(['/usr/bin/compress','-c','-f','-b',str(bits)],input=data,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
        require(result[:2]==b'\x1f\x9d' and result[2]&31==bits,'Unexpected Unix compress format')
        return result[3:]
    rle=plain.replace(b'\x90',b'\x90\0')
    clear=(65|(256<<9)).to_bytes(9,'little')+bytes([66,0])
    return [('OLD.DAT',1,b'old\x00\xff',b'old\x00\xff'),
        ('STORE.DAT',2,b'\0\x80\xff\r\n\x9b',b'\0\x80\xff\r\n\x9b'),
        ('PACK.DAT',3,packed,b'A'*6+b'\x90B'),
        ('SQUEEZE.DAT',4,squeezed,b'A'*8),
        ('CRUNCH.DAT',8,b'\x0c'+unix(rle,12),plain),
        ('SQUASH.DAT',9,unix(plain,13),plain),
        ('CLEAR.DAT',9,clear,b'AB')]


def library(out,source,current_header,original=False):
    out.mkdir(parents=True,exist_ok=True)
    compiler=shutil.which('clang');require(compiler,'Install a host C compiler')
    flags=['-O2','-fPIC','-I'+str(source),'-DEXEC_GEMARC_HOST=1']
    io_source=ROOT/'ports/gem4xe/apps/gemarc/native/io.c'
    # Compile the same stream adapter against the port header in both cases.
    paths=[('arcfile',source/'arcfile.c',[]),('arccodec',source/'arccodec.c',[]),
        ('io',io_source,['-I'+str(current_header),
            '-Dfopen=GemArcHostOpen','-Dfread=GemArcHostRead','-Dfwrite=GemArcHostWrite',
            '-Dfclose=GemArcHostClose','-Drename=GemArcHostRename']),
        ('shim',ROOT/'tests/programs/gemarc_host_support.c',[])]
    for name,path,extra in paths:
        subprocess.run([compiler,*extra,*flags,'-c',str(path),'-o',str(out/(name+'.o'))],check=True)
    binary=out/'gemarc.dylib'
    subprocess.run([compiler,'-shared','-o',str(binary),*[str(out/(n+'.o')) for n,_,_ in paths]],check=True)
    lib=C.CDLL(str(binary));lib.GemArcHostBegin()
    lib.arc_list.argtypes=[C.c_char_p,C.POINTER(Entry),C.c_uint16,C.POINTER(C.c_uint16)]
    lib.arc_extract.argtypes=[C.c_char_p,C.POINTER(Entry),C.c_char_p]
    lib.arc_add.argtypes=[C.c_char_p]+([C.c_char_p] if original else [])+[
        C.c_char_p,C.POINTER(C.c_char*13),C.c_uint16,C.POINTER(Entry),C.c_uint16]
    if not original:lib.arc_recovery.restype=C.POINTER(Recovery)
    return lib,dict(compiler=compiler,compiler_sha256=sha256(Path(compiler)),library_sha256=sha256(binary),
        sources={str(p):sha256(p) for _,p,_ in paths})


def check(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    prepare(out/'prepared');source=out/'prepared/source/src/apps'
    # The adapter includes the current port header even when reproducing the
    # original engine's two failures; do not alter the verified original cache.
    lib,inputs=library(out/'engine',source,source)
    old,old_inputs=library(out/'original',CACHE/'src/apps',source,True)
    table=(Entry*512)();count=C.c_uint16();names=Names()
    b=lambda p:str(p).encode()
    def fault(library,read=0,write=0,close=0,rename=0,cancel=0):
        library.GemArcHostFault(read,write,close,rename,cancel)
    def add(library,path,folder,items,original=False):
        for i,name in enumerate(items):names[i].value=name.encode()
        return library.arc_add(b(path),*([b(folder/'FIXED.TMP')] if original else []),
            b(str(folder)+'/'),names,len(items),table,512)
    record=dict(status='running',tier='development',qualification=False,scope='Portable archive policy and independent byte oracles; native execution is a separate gate',inputs=inputs,original_inputs=old_inputs,cases=[])
    try:
        fixtures=corpus();archive=out/'INPUT.ARC'
        archive.write_bytes(b''.join(member(*item) for item in fixtures)+b'\x1a\0')
        require(lib.arc_list(b(archive),table,512,C.byref(count))==0 and count.value==len(fixtures),'Input listing failed')
        extracted=out/'extracted';extracted.mkdir(exist_ok=True)
        for index,(name,method,data,plain) in enumerate(fixtures):
            target=extracted/name
            if target.exists():target.unlink()
            result=lib.arc_extract(b(archive),C.byref(table[index]),b(target))
            require(result==0 and target.read_bytes()==plain,'Decode mismatch: '+name+' '+str(result))
        oracle=out/'unar-input';oracle.mkdir(exist_ok=True)
        subprocess.run([shutil.which('unar'),'-q','-f','-o',str(oracle),str(archive)],check=True)
        for name,_,_,plain in fixtures:
            candidates=list(oracle.rglob(name));require(len(candidates)==1 and candidates[0].read_bytes()==plain,'Independent input oracle differs: '+name)
        record['cases'].append(dict(name='methods-1-2-3-4-8-9-and-clear',members=len(fixtures),input_sha256=sha256(archive)))
        folder=out/'work';folder.mkdir(exist_ok=True);destination=folder/'RESULT.ARC'
        original_bytes=member('READERR.DAT',2,b'original',b'original')+b'\x1a\0'
        (folder/'READERR.DAT').write_bytes(b'replacement')
        for engine,is_old in [(old,True),(lib,False)]:
            destination.write_bytes(original_bytes);(folder/'FIXED.TMP').unlink(missing_ok=True)
            fault(engine,read=1);result=add(engine,destination,folder,['READERR.DAT'],is_old);fault(engine)
            require((result==0 and destination.read_bytes()!=original_bytes) if is_old else
                    (result==16 and destination.read_bytes()==original_bytes),'Read error regression')
            record['cases'].append(dict(name='source-read-failure',original_engine=is_old,result=result,original_preserved=destination.read_bytes()==original_bytes))
            destination.write_bytes(original_bytes);(folder/'FIXED.TMP').unlink(missing_ok=True)
            fault(engine,rename=1 if is_old else 2);result=add(engine,destination,folder,['READERR.DAT'],is_old);fault(engine)
            if is_old:require(result!=0 and not destination.exists(),'Original rename failure was not reproduced')
            else:
                state=engine.arc_recovery().contents
                require(result==18 and state.original_moved and not state.published and
                    Path(state.backup.decode()).read_bytes()==original_bytes and Path(state.temp.decode()).exists(),
                    'Publication did not retain both copies')
            record['cases'].append(dict(name='publication-rename-failure',original_engine=is_old,result=result,recoverable_original=not is_old))
        for kind,values in [('short-write',dict(write=1)),('close',dict(close=3)),('cancel',dict(cancel=1))]:
            destination.write_bytes(original_bytes)
            (folder/'READERR.DAT').write_bytes(bytes(range(256))*60)
            fault(lib,**values);result=add(lib,destination,folder,['READERR.DAT']);fault(lib)
            require(result!=0 and destination.read_bytes()==original_bytes,'Failure published data: '+kind)
            record['cases'].append(dict(name=kind,result=result,original_preserved=True))
        bad=folder/'BAD.ARC';bad.write_bytes(member('BAD.DAT',2,b'bad',b'bad',True)+b'\x1a\0')
        target=folder/'BAD.DAT';target.write_bytes(b'keep')
        require(lib.arc_list(b(bad),table,512,C.byref(count))==0,'Bad-CRC fixture failed listing')
        require(lib.arc_extract(b(bad),C.byref(table[0]),b(target))==3 and target.read_bytes()==b'keep','CRC failure damaged destination')
        (folder/'EMPTY.DAT').write_bytes(b'');(folder/'DATA.DAT').write_bytes(bytes(range(256))*150)
        destination.unlink(missing_ok=True);require(add(lib,destination,folder,['EMPTY.DAT','DATA.DAT'])==0,'Archive creation failed')
        oracle=out/'unar-output';oracle.mkdir(exist_ok=True)
        subprocess.run([shutil.which('unar'),'-q','-f','-o',str(oracle),str(destination)],check=True)
        for name in ['EMPTY.DAT','DATA.DAT']:
            candidates=list(oracle.rglob(name));require(len(candidates)==1 and candidates[0].read_bytes()==(folder/name).read_bytes(),'Created archive oracle differs')
        record['cases'].append(dict(name='create-and-independent-extract',sha256=sha256(destination)))
        # Header/batch limits and unsupported methods are checked before output.
        for count_limit,expected in [(512,0),(513,15)]:
            archive.write_bytes(b''.join(member('E%07d.DAT'%i,2,b'',b'') for i in range(count_limit))+b'\x1a\0')
            result=lib.arc_list(b(archive),table,512,C.byref(count))
            require(result==expected,'Member limit differs: '+str(result))
        for method in (5,6,7):
            archive.write_bytes(member('UNSUP.DAT',method,b'abc',b'abc')+b'\x1a\0')
            require(lib.arc_list(b(archive),table,512,C.byref(count))==0,'Unsupported-method listing')
            target.write_bytes(b'keep')
            require(lib.arc_extract(b(archive),C.byref(table[0]),b(target))!=0 and target.read_bytes()==b'keep','Unsupported method published output')
        full=member('CUT.DAT',2,b'0123456789',b'0123456789')+b'\x1a\0'
        for end in (1,2,10,28,len(full)-3):
            archive.write_bytes(full[:end])
            require(lib.arc_list(b(archive),table,512,C.byref(count))!=0,'Truncated archive accepted')
        leaf=(C.c_char*13)();lib.arc_member_name(b'longfilename.extension',leaf)
        require(leaf.value==b'LONGFILE.EXT','Native 8.3 normalization differs: '+repr(leaf.value))
        (folder/'DUPE.DAT').write_bytes(b'data')
        require(add(lib,destination,folder,['DUPE.DAT','dupe.dat'])!=0,'Duplicate canonical input accepted')
        record['cases'].append(dict(name='limits-truncation-methods-5-6-7-and-8.3',member_limit=512,batch_limit=64))
        record.update(status='pass',unar=dict(path=shutil.which('unar'),sha256=sha256(Path(shutil.which('unar')))))
    except Exception as error:record.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    check(parser.parse_args().output)
