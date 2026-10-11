"""Verify durable logical writes and every persisted neighbour/padding byte."""
import argparse,json
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from ideplus_media import pattern_fixture,put_sector
from test_cooperative import data
from test_heap_api import clean_ownership
from pathlib import Path


def observe_readbacks(out):
    """Count physical reads issued while the worker owns an accepted write."""
    source = ROOT/'lib/io/ideplusdriver.act'
    text = source.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE IDEWRITEPROBE\n', 1)
    for include in source.parent.glob('ideplus-*.inc'):
        text = text.replace('"'+include.name+'"', '"'+str(include)+'"')
    hook = 'BYTE FUNC ReadInto(LONGCARD sector BYTE POINTER destination BYTE count)\n  BYTE error,index\n'
    require(text.count(hook) == 1, 'Stale physical read observation hook')
    text = text.replace(hook, hook+'\n  IDEWRITEPROBE.Read()\n', 1)
    (out/'ideplusdriver.act').write_text(text)
    (out/'idewriteprobe.act').write_text('''MODULE IDEWRITEPROBE
USE IDEMETA
PUBLIC CARD readbacks

; The settled driver phase distinguishes explicit reads from write readbacks.
PUBLIC PROC Read()

  LET phase=BYTE POINTER(ADDRESS(IDEMETA.BUS+10))
  IF phase^=3 THEN
    readbacks==+1
  FI

RETURN
ENDMODULE
''')
    source = ROOT/'tests/programs/ideplus_write.act'
    target = out/source.name
    target.write_text(source.read_text())
    return target


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'build/development/ideplus-ip4/sectors');v=a.parse_args()
    out=v.output;out.mkdir(parents=True,exist_ok=True)
    p=read_build(out) if v.reuse else build(compiler(ROOT/'build/actionc',release=True),observe_readbacks(out),out,optimize=True,tasks=True,task_capacity=8,image_data=[(0x2dfff0,bytes([0xa5])*512)])
    for protected,failed in ((False,False),(True,False),(False,True)):
        dest=out/('failed-write' if failed else 'protected' if protected else 'writable');dest.mkdir(exist_ok=True)
        original,maps=pattern_fixture(readonly=protected);expected=bytearray(original);disk=dest/'ide.img';disk.write_bytes(original)
        if not protected and not failed:
            for mapping in maps:
                for sector,length,seed in [(0,512,0x6c),(1,512,0xa7)]:
                    payload=bytes((i^(i>>8)^seed^mapping['unit'])&255 for i in range(length))
                    put_sector(expected,mapping['start'],sector,payload)
        with ide_emulator(dest,disk,writable=not failed) as b:
            def before(b):
                for field,value in [('PROTECTED',protected),('EXPECTEDERROR',3 if failed else 0)]:
                    b.memload(next(d['address'] for d in p['image']['data'] if '_IDEPLUSWRITETEST_'+field+'_' in d['name']),bytes([value]))
            try:runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            except Exception:
                print('checks',data(b,p['image'],'checks',True),flush=True)
                print('controller',b.memdump(p['build']['memory']['ideplus_storage']['BASE']+640,32).hex(),flush=True);raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        require(disk.read_bytes()==expected,'Unexpected physical media change, neighbour or padding corruption')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks),indent=2)+'\n')
        print('IDE logical writes passed',dest.name,flush=True)
