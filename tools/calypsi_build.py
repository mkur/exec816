"""Shared checked Calypsi emission; Exec's native builder still owns packaging."""
from pathlib import Path
import shutil

from calypsi_image import check_layout, read_image
from generate_calypsi import expected_layout, files
from native_program import ROOT, command, require, sha256


def emit(output, sources, assembly, task_entries, optimize=True, roots=(),
         includes=(), definitions=None, probes=(), source_optimization=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    tools = {}
    for name in ('cc65816', 'as65816', 'ln65816'):
        path = shutil.which(name)
        require(path is not None, 'Calypsi tool not installed: '+name)
        path = Path(path).resolve()
        version = command([path, '--version']).strip()
        require(version.endswith('version 5.18'), 'This C binding is checked with Calypsi 5.18')
        tools[name] = dict(path=str(path), version=version, sha256=sha256(path))
    for path, content in files().items():
        require(path.read_text() == content, 'Stale C binding: '+str(path))
    runtime = Path(tools['cc65816']['path']).parent.parent/'lib/clib-lc-hd.a'
    require(runtime.is_file(), 'Missing Calypsi large-code/huge-data runtime')
    flags = ['--code-model=large', '--data-model=huge', '-O2' if optimize else '-O0']
    include_args = [part for path in (ROOT/'c/include', ROOT/'platform/altirraos', output, *includes) for part in ('-I', path)]
    if ROOT/'platform/altirraos/vbxe-map.s' in assembly:
        probes=(*probes,(ROOT/'c/calypsi/vbxe-upload-layout.c',[
            ('VbxeUpload size',6),('VbxeUpload records',0),('VbxeUpload count',4),
            ('VbxeTextUpload size',25),('VbxeTextUpload text',0),('VbxeTextUpload font',4),
            ('VbxeTextUpload destination',8),('VbxeTextUpload count',12),
            ('VbxeTextUpload ink',14),('VbxeTextUpload paper',15),
            ('VbxeTextUpload fillDestination',16),('VbxeTextUpload fillBytes',20),
            ('VbxeTextUpload fillRows',22),('VbxeTextUpload fillValue',24)]))
    checked = {}
    for number, (source, expected) in enumerate(((ROOT/'c/calypsi/layout-check.c', expected_layout()), *probes)):
        obj = output/f'layout-{number}.o'
        command([tools['cc65816']['path'], *flags, '-c', *include_args, '-o', obj, source])
        checked.update(check_layout(obj, expected))
    objects = []
    for number, source in enumerate(sources):
        obj = output/f'{number}-{source.stem}.o'
        extra = (definitions or {}).get(source.name, ())
        source_flags = [*flags[:-1], '-O2' if (source_optimization or {}).get(source.name, optimize) else '-O0']
        command([tools['cc65816']['path'], *source_flags, *extra, '-c', *include_args,
                 '--list-file', obj.with_suffix('.lst'), '-o', obj, source])
        objects.append(obj)
    for number, source in enumerate(assembly):
        obj = output/f'{number}-{source.stem}-asm.o'
        command([tools['as65816']['path'], '-I', ROOT/'c/calypsi', '-o', obj, source])
        objects.append(obj)
    elf = output/'program.elf'
    root_args = [part for name in (*task_entries, '__exec_image_info', *roots)
                 for part in ('--root-symbol', name)]
    command([tools['ln65816']['path'], '--hosted', '--program-root', 'main', '--program-start', 'main',
             *root_args, '--no-data-init-table-section', '--no-automatic-placement-rules',
             '--list-file', output/'link.lst', '-o', elf, *objects, ROOT/'c/calypsi/layout.scm'])
    foreign = read_image(elf, task_entries)
    foreign['provenance']['platform_internal_inputs'] = {
        'platform/altirraos/vbxe-internal.h': sha256(ROOT/'platform/altirraos/vbxe-internal.h')}
    foreign['provenance'].update(tools=tools, linker_layout_sha256=sha256(ROOT/'c/calypsi/layout.scm'), runtime=dict(path=str(runtime), sha256=sha256(runtime)),
                                 compiler_flags=flags, source_options=definitions or {},
                                 source_optimization=source_optimization or {}, checked_layout=checked,
                                 link_objects=[str(p) for p in objects])
    if ROOT/'platform/altirraos/vbxe-map.s' in assembly:
        foreign['provenance']['upload_inputs']={str(p.relative_to(ROOT)):sha256(p) for p in (
            ROOT/'c/include/hardware/vbxe-upload.h',ROOT/'c/calypsi/vbxe-upload-layout.c',
            ROOT/'platform/altirraos/vbxe-map.s',Path(__file__).resolve())}
    return foreign
