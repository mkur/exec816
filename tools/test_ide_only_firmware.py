"""Exercise the real BIOS menu and XEX loader; no direct-XEX loading hook."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from os_boundary import run_to
from test_ideplus import ide_emulator,PIN
from test_of816 import screen_text

def directories(bundle,out):
    """Use the real BIOS loader to read both partitions without launching code."""
    out.mkdir(parents=True,exist_ok=True)
    media=bundle/'ideplus.img';initial=media.read_bytes()
    with ide_emulator(out,media,writable=False,history=True) as b:
        b.cold_reset();b.consol(start=True)
        for _ in range(8):b.frame(50);b.pause()
        b.consol()
        def key(name):
            b._cmd_ok('KEY '+name+' down');b.frame(4);b.pause()
            b._cmd_ok('KEY '+name+' up');b.frame(4);b.pause()
        for name in ('B','1','RETURN','L'):key(name)
        b.frame(250);b.pause()
        system=screen_text(b.memdump(b.peek16(88),960))
        require('STORY' in system,'BIOS did not list SYS')
        b.screenshot(str(out/'sys.png'))
        key('2');b.frame(250);b.pause()
        work=screen_text(b.memdump(b.peek16(88),960))
        require('README' in work,'BIOS did not list WORK')
        require('STORY' not in work,'BIOS remained on SYS instead of WORK')
        b.screenshot(str(out/'work.png'))
    require(media.read_bytes()==initial,'BIOS directory reads changed media')
    result=dict(status='pass',tier='development',pin=PIN,media_sha256=sha256(media),
                scope='Real BIOS SYS/WORK directory reads; no executable launch',
                sys=system,work=work)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('BIOS SYS/WORK directory reads passed',flush=True)
    return result


def run(bundle,out):
    """Launch SYS:EXEC816.XEX with real keys and the pinned BIOS file loader."""
    import shutil
    import test_demo
    from test_of816 import check_loading_paused,check_loading_complete,check_boot_guards
    from test_ide_only_demo import Walkthrough,extract
    from serial_watch import install
    out.mkdir(parents=True,exist_ok=True)
    root=extract(bundle,out/'extracted')
    case=out/'demo'
    shutil.copytree(bundle,case,dirs_exist_ok=True)
    boot=json.loads((bundle/'of816/of816.json').read_text())
    result=dict(status='running',tier='development',pin=PIN,id5='open',
                media_sha256=sha256(root/'ideplus.img'),
                scope='Real BIOS menu executable load, OF816 INITAD pause/autoboot, kernel and IDE shell')
    stage='BIOS menu'
    def bootstrap(b,p):
        nonlocal stage
        try:
            b.cold_reset();b.consol(start=True)
            for _ in range(8):b.frame(50);b.pause()
            b.consol()
            def key(name):
                b._cmd_ok('KEY '+name+' down');b.frame(4);b.pause()
                b._cmd_ok('KEY '+name+' up');b.frame(4);b.pause()
            for name in ('B','1','RETURN'):key(name)
            menu=screen_text(b.memdump(b.peek16(88),960))
            require('Boot drive: D1:' in menu,'Wrong BIOS boot unit')
            result['serial']=install(b)
            stage='SYS directory'
            key('L');b.frame(250);b.pause()
            listing=screen_text(b.memdump(b.peek16(88),960))
            require('EXEC816 XEX' in listing,'BIOS did not list EXEC816.XEX')
            result['listing']=listing
            b.screenshot(str(out/'directory.png'))
            # Formatter emits C, S, WORK then EXEC816.XEX. Physical Atari down
            # keys move the selection; Return invokes the firmware loader.
            for _ in range(3):
                b._cmd_ok('KEY CTRL down');key('EQUALS');b._cmd_ok('KEY CTRL up')
            b.screenshot(str(out/'selected.png'))
            stage='XEX load to OF816 INITAD'
            b.bp_set(boot['labels']['of_start'])
            key('RETURN')
            run_to(b,boot['labels']['of_start'],6000,180)
            result['memlo_at_initad']=b.peek16(0x2e7)
            b.bp_clear_all();b._cmd_ok('KEY ALL up')
            settings=check_loading_paused(b,boot,p)
            stage='OF816 autoboot'
            b.bp_set(boot['labels']['of_autoboot'])
            run_to(b,boot['labels']['of_autoboot'],1000,30)
            b.bp_clear_all();begin=b.eval_expr('@frame')
            b.bp_set(boot['labels']['of_handoff'])
            run_to(b,boot['labels']['of_handoff'],300,15)
            result['autoboot_frames']=b.eval_expr('@frame')-begin
            require(249<=result['autoboot_frames']<=251,'Five-second autoboot changed')
            check_boot_guards(b,boot['layout'])
            check_loading_paused(b,boot,p)
            stage='Resumed kernel payload load'
            b.bp_clear_all();b.bp_set(p['labels']['loader_start'])
            run_to(b,p['labels']['loader_start'],6000,180)
            check_loading_complete(b,boot,p,settings)
            stage='Kernel handoff'
            b.bp_clear_all();b.bp_set(p['labels']['start'])
            run_to(b,p['labels']['start'],1000,30)
            b.bp_clear_all()
            stage='IDE shell'
        except Exception as error:
            result['failure_context']=dict(stage=stage,registers=b.regs(),memlo=b.peek16(0x2e7),
                error=str(error),dcb=b.memdump(0x300,16).hex(),screen=screen_text(b.memdump(b.peek16(88),960)))
            b.screenshot(str(out/'failed.png'))
            raise
    try:
        result['shell']=test_demo.run(case,boot_smoke=True,bootstrap=bootstrap,
            media_path=root/'ideplus.img',distribution_root=root,integration=Walkthrough())
        result.update(status='pass',id5='closed',stage='IDE shell and EXIT',
                      reason='Actual BIOS XEX loader reached OF816, resumed loading and ran IDE commands.')
    except Exception as error:
        result.update(status='incompatible',id5='open',stage=stage,reason=str(error))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Firmware menu:',result['status'],result['reason'],flush=True)
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,default=ROOT/'build/development/ide-only/demo')
    a.add_argument('--output',type=Path,default=ROOT/'build/development/ide-only/id5-firmware')
    a.add_argument('--directories-only',action='store_true')
    v=a.parse_args()
    (directories if v.directories_only else run)(v.bundle.resolve(),v.output.resolve())
