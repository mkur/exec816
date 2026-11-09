"""The one hosted APP runtime and its build-time typed main adapter."""
from pathlib import Path
from native_program import ROOT,require,sha256
from generate_c_runtime import ABI as RUNTIME_ABI,files

SOURCES=tuple(ROOT/'c/runtime'/name for name in (
    'allocation.c','arguments.c','files.c','stdio.c','library.c','lifecycle.c','scope.c'))
COMPILER_OPTIONS=['--no-cross-call','--no-interprocedural-cross-jump']


def prepare(output,sources,main_signature='void'):
    import json
    application_abi=json.loads((ROOT/'abi/c-program.json').read_text())
    require(application_abi['entry']==RUNTIME_ABI['entry'] and application_abi['runtime_version']==RUNTIME_ABI['version'],'Mismatched APP/runtime contract')
    require(main_signature in ('void','args'),'Choose main(void) or main(argc,argv)')
    for path,content in files().items():require(path.read_text()==content,'Stale C runtime interface: '+str(path))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    adapter=output/'runtime-main.c'
    declaration='int main(void);' if main_signature=='void' else 'int main(int,char **);'
    invocation='(void)argc;(void)argv;return main();' if main_signature=='void' else 'return main(argc,argv);'
    adapter.write_text('/* Generated typed APP main adapter; MIT. */\n'+declaration+'\n'+
        'int __exec_c_runtime_main(int argc,char **argv) { '+invocation+' }\n')
    sources=[*sources,*SOURCES,adapter]
    require(len(sources)==len(set(map(str,sources))),'Duplicate APP/runtime source')
    return sources,dict(version=RUNTIME_ABI['version'],entry=RUNTIME_ABI['entry'],
        main_signature=main_signature,compiler_options=COMPILER_OPTIONS,
        inputs={str(p):sha256(p) for p in (*SOURCES,ROOT/'c/runtime/internal.h',
            ROOT/'c/include/exec816/c-runtime.h',ROOT/'c/include/setjmp.h',adapter)})


def audit(output,image,sources):
    """Prove the selected owners, including archive overrides, from real placements."""
    import re
    from calypsi_image import object_symbols
    text=(Path(output)/'link.lst').read_text()
    pattern=(r"([^\n]+?) in section 'farcode'\s+placed at address ([a-f0-9]+)-([a-f0-9]+) "
             r"of size [a-f0-9]+\n\([^\n]*?unit (\d+) section index (\d+)\)")
    placements={(int(m[4]),int(m[5])):(int(m[2],16),int(m[3],16)+1)
                for m in re.finditer(pattern,text)}
    owners={}
    for name,unit in [('__exec_c_runtime_entry','scope.c'),('malloc','allocation.c'),
                      ('free','allocation.c'),('_Stub_open','files.c'),('_Stub_close','files.c'),
                      ('exit','scope.c'),('_Exit','scope.c'),('_Stub_assert','scope.c')]:
        if name not in image['symbols']:
            require(name in ('_Stub_open','exit','_Exit','_Stub_assert'),'Missing common runtime operation: '+name)
            continue
        index=list(sources).index(ROOT/'c/runtime'/unit)
        obj=Path(output)/(str(index)+'-'+Path(unit).stem+'.o')
        symbol=object_symbols(obj)[name]
        extent=placements.get((index,symbol['section']))
        require(extent and extent[0]<=image['symbols'][name]<extent[1],
                'Wrong C runtime owner: '+name)
        owners[name]=dict(source='c/runtime/'+unit,address=image['symbols'][name])
    require(not any(n.startswith(('__initialize_heap','__heap_start','__heap_end')) for n in image['symbols']),
            'Vendor default heap selected by APP')
    return owners
