"""Current production QED identities and supported-delivery inventory."""
import json
import re
from pathlib import Path

from analysis_artifact import reject_analysis
from c_program import ABI
from check_qed_baseline import provider_identity
from native_program import ROOT, require, sha256

PORT = ROOT/'ports/gem4xe/apps/qed'
REQUIREMENTS = {'launch', 'document', 'text', 'editing', 'search', 'files',
                'appearance', 'settings', 'coexistence'}


def read(path):
    return json.loads(path.read_text())


def checked(path, expected):
    require(path.is_file() and sha256(path) == expected, 'Changed QED input: '+str(path))


def production(directory, provider):
    """Check the complete linked inputs before staging or claiming reuse."""
    directory = directory.resolve()
    layout = read(directory/'layout.json')
    require(layout['status'] == 'executable-development' and layout['complete_link'] and
            layout['abi'] == ABI and not layout['image']['provenance']['analysis_only'],
            'Use current executable production QED')
    require(not any('/tests/programs/' in name for name in layout['build_inputs']), 'QED fixture is not production')
    checked(directory/'program.app', layout['app']['sha256'])
    reject_analysis((directory/'program.app').read_bytes())
    for name, expected in layout['build_inputs'].items():
        checked(Path(name), expected)
    sources = read(directory/'inputs/sources.json')
    require(sources['patches'] == {p.name: sha256(p) for p in (PORT/'patches').glob('*.patch')},
            'Changed QED source patch set')
    require(sources['source_manifest_sha256'] == sha256(PORT/'inputs.json'), 'Changed QED source pins')
    for name, expected in sources['native_inputs'].items():
        checked(ROOT/name, expected)
    resource = read(directory/'inputs/resource/resource.json')
    checked(directory/'inputs/resource/QED.RSC', resource['resource_sha256'])
    checked(directory/'inputs/source/qed/src/qed.h', resource['header_sha256'])
    checked(PORT/'resource-selection.json', resource['selection_sha256'])
    checked(ROOT/'tools/build_qed_resource.py', resource['generator_sha256'])
    original = Path(layout['resident_provider']['path'])
    checked(original, layout['resident_provider']['sha256'])
    identity = provider_identity(read(original))
    require(provider_identity(read(provider)) == identity, 'QED/provider identity differs')
    for tool in layout['image']['provenance']['tools'].values():
        checked(Path(tool['path']), tool['sha256'])
    runtime = layout['image']['provenance']['runtime']
    checked(Path(runtime['path']), runtime['sha256'])
    return layout, identity


def inventory(directory, provider, policy=None):
    layout, identity = production(directory, provider)
    policy = policy or read(PORT/'delivery.json')
    require(set(policy['requirements']) == REQUIREMENTS, 'Incomplete QED scope map')
    require(all(v.get('scope_row') and v.get('implementation') and v.get('evidence')
                for v in policy['requirements'].values()), 'Missing QED scope evidence')
    require(set(policy['grants']) == {'qed', 'cflib', 'native', 'bindings', 'runtime'} and
            all(policy['grants'].values()), 'Missing QED component grant')
    app = read(directory/'app.json')
    inputs = list(app['inputs'])
    overrides = list(layout['image']['provenance']['runtime_source_overrides']['prepared_sources'])
    compiled = inputs+overrides
    units = []
    for row in layout['link_units']:
        name = Path(row['source']).name
        match = re.match(r'(\d+)-.*\.o$', name)
        if row['archive']:
            component, source = 'runtime', row['archive']+':'+name
        elif name.endswith('-asm.o'):
            component, source = 'bindings', 'c/calypsi/image-info.s or generated import assembly'
        else:
            require(match is not None and int(match[1]) < len(compiled), 'Unclassified QED link unit: '+name)
            source = compiled[int(match[1])]
            component = ('qed' if '/source/qed/' in source else 'cflib' if '/source/cflib/' in source
                         else 'native' if '/apps/qed/native/' in source else 'runtime')
        units.append(dict(object=name, source=source, component=component, sections=row['sections'],
                          grant=policy['grants'][component]))
    native = {str(p.relative_to(ROOT)): dict(sha256=sha256(p),
              notice=p.read_text(errors='replace').splitlines()[0])
              for p in sorted((PORT/'native').glob('*')) if p.is_file()}
    return dict(schema_version=1, status='pass', tier='development', qualification=False,
        distribution_ready=False, unresolved=policy['unresolved'], requirements=policy['requirements'],
        limits=policy['limits'], deferrals=policy['deferrals'], link_units=units,
        native_files=native, source_pins=layout['inputs']['sources'], provider_identity=identity,
        app_sha256=layout['app']['sha256'], resource_sha256=read(directory/'inputs/resource/resource.json')['resource_sha256'],
        layout_sha256=sha256(directory/'layout.json'), policy_sha256=sha256(PORT/'delivery.json'),
        auditor_sha256=sha256(Path(__file__)),
        bank_zero_delta=dict(fixed=0, per_public_task=0, private_idle=0))


def require_distribution(record):
    require(not record['unresolved'], 'Unresolved QED grants: '+', '.join(record['unresolved']))
    require(set(record['requirements']) == REQUIREMENTS and
            all(v['status'] == 'pass' for v in record['requirements'].values()), 'Incomplete QED delivery requirements')
