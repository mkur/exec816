"""Persisted SDFS-512 mutations through real IDE PIO, with independent audits."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_filesystem_write import run
from ideplus_media import sdfs_image

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'build/development/ideplus-ip4/filesystems');v=a.parse_args()
    out=v.output;out.mkdir(parents=True,exist_ok=True)
    fixture=out/'stage.atr';sdfs_image(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr',fixture,sectors=8193)
    t=compiler(ROOT/'build/actionc',release=True)
    first=out/'mutations';first.mkdir(exist_ok=True)
    for name,hint,cache,file_only in [('mutations',0,None,False),('bitmap-boundary',4090,0,True)]:
        dest=out/name;dest.mkdir(exist_ok=True)
        result=run(t,dest,'opt','sdfs',512,17000,fast_media=True,from_build=first if name!='mutations' or v.reuse else None,fixture=fixture,hint=hint,cache_blocks=cache,file_only=file_only,device='ideplus.device')
        (dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print('IDE filesystem writes/audit passed',name,flush=True)
