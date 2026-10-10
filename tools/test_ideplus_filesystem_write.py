"""Persisted SDFS-512 mutations through real IDE PIO, with independent audits."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_filesystem_write import run
from ideplus_media import sdfs_image
from sdfs_reference import extract
from make_data_disk import make

CASES={'mutations':(17000,0,None,False),
       'bitmap-boundary':(17000,4090,0,True),
       'directory-boundary':(17000,0,None,False),
       'map-boundary':(512*255+7,0,None,True)}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--case',action='append',choices=CASES);a.add_argument('--output',type=Path,default=ROOT/'build/development/ideplus-ip4/filesystems');v=a.parse_args()
    out=v.output;out.mkdir(parents=True,exist_ok=True)
    fixture=out/'stage.atr';sdfs_image(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr',fixture,sectors=8193)
    t=compiler(ROOT/'build/actionc',release=True)
    cases=v.case or list(CASES)
    first=out/cases[0];first.mkdir(exist_ok=True)
    for name in cases:
        amount,hint,cache,file_only=CASES[name]
        dest=out/name;dest.mkdir(exist_ok=True)
        selected=fixture
        if name=='directory-boundary':
            tree=dest/'tree';extract(fixture,tree)
            # Seven root entries plus fourteen empty files: new row 22 begins
            # at byte 506 and straddles the 512-byte directory-sector boundary.
            for i in range(14):(tree/f'AAA{i:02d}.BIN').write_bytes(b'')
            selected=dest/'input.atr'
            make(selected,tree,binary_names=[p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_file()],sector_bytes=512,sectors=8193)
        result=run(t,dest,'opt','sdfs',512,amount,fast_media=True,from_build=first if name!=cases[0] or v.reuse else None,fixture=selected,hint=hint,cache_blocks=cache,file_only=file_only,device='ideplus.device')
        (dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print('IDE filesystem writes/audit passed',name,flush=True)
