"""Build the source-audited synthetic commands admitted during P3/P4.

Native runtime selection checks the complete serialized record file and patch
bytes. The pinned real application catalog is generated separately.
"""
import hashlib
import struct
import subprocess
import zlib
from pathlib import Path

from generate_memory import ROOT


def stream(sites):
    result=bytearray(b'\xfe\x01')
    previous=0
    for site in sorted(sites):
        delta=site-previous
        while delta>250:
            result.append(255)
            delta-=250
        result.append(delta)
        previous=site
    return bytes(result)+b'\xfc'


def assemble(output, name):
    output=Path(output)
    source=ROOT/'compat/sdx/probes'/f'{name}.s'
    config=output/f'{name}.cfg'
    config.write_text('MEMORY { RAM: start=0, size=$9000, file=%O; }\n'
                      'SEGMENTS { CODE: load=RAM,type=ro,align=$100; }\n')
    subprocess.run(['ca65','-I',str(source.parent),'-o',str(output/f'{name}.o'),str(source)],check=True)
    subprocess.run(['ld65','-C',str(config),'-Ln',str(output/f'{name}.lbl'),
                    '-o',str(output/f'{name}.bin'),str(output/f'{name}.o')],check=True)
    labels={line.split()[2].lstrip('.'):int(line.split()[1],16)
            for line in (output/f'{name}.lbl').read_text().splitlines()}
    code=(output/f'{name}.bin').read_bytes()
    raw=bytearray(struct.pack('<HBBHH',0xfffe,1,0,0,len(code))+code)
    raw+=struct.pack('<HBH',0xfffc,1,labels['MAIN'])+b'MAIN    '
    local=[v for k,v in labels.items() if k.startswith('reloc_')]
    if local:
        fix=stream(local)
        raw+=struct.pack('<HBH',0xfffd,1,len(fix))+fix
    imports={}
    for key,at in labels.items():
        if key.startswith('import_'):
            imports.setdefault(key[len('import_'):].rsplit('_',1)[0],[]).append(at)
    for symbol,sites in sorted(imports.items()):
        fix=stream(sites)
        raw+=struct.pack('<H',0xfffb)+symbol.encode().ljust(8,b' ')+struct.pack('<H',len(fix))+fix
    (output/f'{name}.com').write_bytes(raw)
    return dict(name=name,bytes=bytes(raw),patch=labels.get('patch_irq'),
                sha256=hashlib.sha256(raw).hexdigest(),crc32=zlib.crc32(raw),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                direct_page_sites=sorted(v for k,v in labels.items() if k.startswith('dp_arg_')))


def generate(output, names=('process','services','fail','options','console','rethrow')):
    fixtures=[assemble(output,n) for n in names]
    text='''; Generated exact-identity development and pinned MD5 admission.
MODULE SDXADMISSION
USE SDXCRC32
USE SDXFILE
USE SDXPATCH
USE SDXABI
USE SDXMD5
USE SDXARC

PUBLIC BYTE FUNC Select(BYTE POINTER bytes LONGCARD length)
  LONGCARD crc

  IF length=0 OR length>$ffff THEN
    RETURN(0)
  FI
  crc=SDXCRC32.Update(bytes,CARD(length),$ffffffff) XOR $ffffffff
'''
    for index,item in enumerate(fixtures,1):
        text+=f'  IF length={len(item["bytes"])} AND crc=${item["crc32"]:08x} THEN\n    RETURN({index})\n  FI\n'
    text+='\n  IF SDXMD5.Select(length,crc)<>0 THEN\n    RETURN(SDXMD5.PROFILE)\n  FI\n\nRETURN(SDXARC.Select(length,crc))\n\n'
    text+='PUBLIC CARD FUNC Entry(SDXFILE.Layout POINTER plan BYTE profile)\n\n'
    text+='  IF profile=SDXMD5.PROFILE THEN\n    RETURN(SDXMD5.Entry(plan))\n  FI\n\n'
    text+='  IF profile=SDXARC.PROFILE THEN\n    RETURN(SDXARC.Entry(plan))\n  FI\n\n'
    text+='RETURN(SDXFILE.Symbol(plan,BYTE POINTER("MAIN    ")+1))\n\n'
    text+='PUBLIC CARD FUNC Patch(SDXFILE.Layout POINTER plan BYTE profile)\n'
    text+='  SDXPATCH.Patch patch\n  SDXFILE.Block POINTER block\n  BYTE before,after\n\n'
    text+='  IF profile=SDXMD5.PROFILE THEN\n    RETURN(SDXMD5.Patch(plan))\n  FI\n'
    text+='  IF profile=SDXARC.PROFILE THEN\n    RETURN(SDXARC.Patch(plan))\n  FI\n'
    text+='  block=SDXFILE.Find(plan,1)\n  IF block=NULL THEN\n    RETURN(1)\n  FI\n'
    for index,item in enumerate(fixtures,1):
        text+=f'  IF profile={index} THEN\n'
        if item['patch'] is not None:
            text+=f'''    before=$78
    after=$ea
    patch.offset=block.placed+{item['patch']}
    patch.length=1
    patch.expected=@before
    patch.replacement=@after
    RETURN(SDXPATCH.Apply(plan.bank,@patch,1))
'''
        else:
            text+='    RETURN(0)\n'
        text+='  FI\n'
    text+='\nRETURN(1)\n\nPUBLIC BYTE FUNC DirectPage(BYTE profile CARD site)\n\n'
    for index,item in enumerate(fixtures,1):
        for site in item['direct_page_sites']:
            text+=f'  IF profile={index} AND site=SDXABI.GUEST_START+${site:x} THEN\n    RETURN(1)\n  FI\n'
    text+='  IF profile=SDXMD5.PROFILE THEN\n    RETURN(SDXMD5.DirectPage(site))\n  FI\n  IF profile=SDXARC.PROFILE THEN\n    RETURN(SDXARC.DirectPage(site))\n  FI\n\nRETURN(0)\n\nENDMODULE\n'
    (Path(output)/'sdxadmission.act').write_text(text)
    return [{k:v for k,v in item.items() if k!='bytes'} for item in fixtures]
