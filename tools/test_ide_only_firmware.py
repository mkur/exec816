"""Record the real BIOS menu's IDE admission; no direct-XEX loading hook."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from os_boundary import run_to
from test_ideplus import ide_emulator,PIN
from test_of816 import screen_text


def run(bundle,out):
    out.mkdir(parents=True,exist_ok=True)
    media=bundle/'ideplus.img'
    initial=media.read_bytes()
    result=dict(tier='development',pin=PIN,media_sha256=sha256(media),
                scope='Cold reset, BIOS START menu, boot unit 1, executable loader')
    with ide_emulator(out,media,writable=False,history=True) as b:
        b.cold_reset();b.consol(start=True)
        for _ in range(8):b.frame(50);b.pause()
        b.consol()
        def key(name):
            b._cmd_ok('KEY '+name+' down');b.frame(4);b.pause()
            b._cmd_ok('KEY '+name+' up');b.frame(4);b.pause()
        key('B');key('1');key('RETURN')
        menu=screen_text(b.memdump(b.peek16(88),960))
        require('Boot drive: D1:' in menu,'BIOS boot unit was not set')
        result['menu']=menu
        b.bp_set(0xd805)
        b._cmd_ok('KEY L down')
        run_to(b,0xd805,400,60)
        entry=b.regs();dcb=b.memdump(0x300,16)
        require(dcb[:3]==bytes.fromhex('310153'),'Unexpected BIOS request')
        result['entry']=dict(registers=entry,dcb=dcb.hex(),memlo=b.peek16(0x2e7),
                             pbi=b.memdump(0x247,3).hex())
        # BIOS is running in emulation mode, with its return in page one.
        stack=0x100+int(entry['S'].lstrip('$'),16)
        require(stack<=0x1fd,'Unexpected BIOS stack context')
        returned=b.peek16(stack+1)+1
        b.bp_clear_all();b.bp_set(returned)
        run_to(b,returned,400,60)
        registers=b.regs()
        result['returned']=dict(registers=registers,carry=int(registers['P'][1:],16)&1,
                                dcb=b.memdump(0x300,16).hex())
        (out/'handler-history.json').write_text(json.dumps(b.history(100),indent=2)+'\n')
        if result['returned']['carry']==0:
            result.update(status='incompatible',id5='open',
                reason='BIOS PBI handler declines unit 1 STATUS; OS would fall back to serial SIO. Stopped before fallback.',
                loading_started=False,loader_memlo=None)
        else:
            # A changed pin/layout needs the full callback and handoff check;
            # admission alone cannot establish a successful firmware boot.
            result.update(status='admitted-unverified',id5='open',loading_started=False,
                          reason='IDE STATUS claimed; full XEX/INITAD/RUNAD handoff still required.')
        b.screenshot(str(out/'menu.png'))
    require(media.read_bytes()==initial,'Read-only firmware experiment changed media')
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Firmware menu:',result['status'],result['reason'],flush=True)
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,default=ROOT/'build/development/ide-only/demo')
    a.add_argument('--output',type=Path,default=ROOT/'build/development/ide-only/id5-firmware')
    v=a.parse_args();run(v.bundle.resolve(),v.output.resolve())
