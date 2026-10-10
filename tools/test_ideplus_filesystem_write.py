"""Run the existing filesystem mutation oracle through real IDE PIO."""
import json,sys
from native_program import ROOT,compiler
from test_filesystem_write import run
if __name__=='__main__':
    out=ROOT/'build/development/ideplus-ip4/filesystems';out.mkdir(parents=True,exist_ok=True)
    t=compiler(ROOT/'build/actionc',release=True)
    first=out/'mydos';first.mkdir(exist_ok=True)
    for fs,amount in [('mydos',257),('sdfs',17000)]:
        dest=out/fs;dest.mkdir(exist_ok=True)
        reuse=first if fs=='sdfs' or '--reuse' in sys.argv else None
        result=run(t,dest,'opt',fs,256,amount,fast_media=True,from_build=reuse,device='ideplus.device')
        (dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print('IDE filesystem writes/audit passed',fs,flush=True)
