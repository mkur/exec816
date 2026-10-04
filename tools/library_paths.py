"""Exec library search paths and owner-relative INCLUDE handling for source copies."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SUBSYSTEMS = ('exec', 'dos', 'fs', 'console', 'display', 'desktop', 'widgets', 'input', 'mydos', 'spartados', 'io')


def module_args(root=ROOT):
    """Append after generated/fixture paths so their module overrides win."""
    return [arg for name in SUBSYSTEMS for arg in ('--module-path', root/'lib'/name)]


def library_file(name, root=ROOT):
    """Resolve a unique library basename; never silently choose a duplicate."""
    if Path(name).name != name:
        raise ValueError('Expected library basename: '+str(name))
    matches = [root/'lib'/group/name for group in SUBSYSTEMS
               if (root/'lib'/group/name).is_file()]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one library file for {name}, found {len(matches)}')
    return matches[0]


def library_relative(name):
    return library_file(name).relative_to(ROOT).as_posix()


def read_source(path, includes=None):
    """Copy Action source without changing where its static includes resolve.

    Explicit basename overrides select generated includes. Other existing
    includes become absolute; unresolved generated names remain relative to
    the output directory. Nested includes retain their own source owner.
    """
    path = Path(path)
    overrides = includes or {}

    def include(match):
        name = match[2]
        target = overrides.get(Path(name).name)
        if target is None:
            target = path.parent/name
            if not target.is_file():
                return match[0]
        return match[1]+'"'+str(Path(target).resolve())+'"'

    source = path.read_text().replace('\r\n', '\n')
    return re.sub(r'(?mi)^([ \t]*INCLUDE[ \t]+)"([^"\n]+)"', include, source)


def record_input_paths(record):
    """Compare evidence from previous layouts with current path spellings.

    Return a copy, leaving historical records and their Git/blob provenance
    untouched. Only path keys change; hashes and freshness checks do not.
    Reject aliases that would overwrite evidence, even with identical hashes.
    """
    # Removed implementations still occur in immutable qualification records.
    paths = {'lib/task-sio.inc':'lib/io/task-sio.inc',
             'lib/mydosfiletypes.act':'lib/mydos/mydosfiletypes.act',
             'lib/fsmydos.act':'lib/mydos/fsmydos.act',
             'lib/mydosnames.act':'lib/mydos/mydosnames.act'}
    for path in (ROOT/'examples/shell').iterdir():
        if path.is_file() and path.suffix in ('.act', '.inc'):
            paths['examples/'+path.name] = path.relative_to(ROOT).as_posix()
    for group in SUBSYSTEMS:
        for path in (ROOT/'lib'/group).iterdir():
            if path.is_file() and path.suffix in ('.act', '.inc'):
                key = 'lib/'+path.name
                if key in paths:
                    raise RuntimeError('Duplicate library basename: '+path.name)
                paths[key] = path.relative_to(ROOT).as_posix()

    def visit(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                key = paths.get(key, key)
                if key in result:
                    raise RuntimeError('Duplicate record input path: '+key)
                result[key] = visit(item)
            return result
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    return visit(record)
