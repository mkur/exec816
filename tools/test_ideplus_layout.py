"""Small emitted raw/optimized IDE geometry/bridge probe."""
import json
from native_program import ROOT,build,compiler,execute,verify_machine
from os_boundary import emulator
from test_sio_device import PIN
if __name__=='__main__':
    t=compiler(ROOT/'build/actionc')
    for mode in ('raw','opt'):
        out=ROOT/'build/development/ideplus-ip1/layout'/mode
        out.mkdir(parents=True,exist_ok=True)
        p=build(t,ROOT/'tests/programs/ideplus_layout.act',out,optimize=mode=='opt',tasks=True)
        with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            runtime,_=execute(b,p,timeout=60,frame_limit=3000)
        (out/'results.json').write_text(json.dumps(dict(status='pass',build=p['build'],runtime=runtime,machine=machine),indent=2)+'\n')
        print('IDE geometry layout passed',mode,flush=True)
