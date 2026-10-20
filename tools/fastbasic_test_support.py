"""Reuse an unchanged emitted native fixture with freshly built guest inputs."""
from native_program import require, ROOT, sha256


def guest_inputs(program, previous_source, current_source, payloads):
    for group in ('fastbasic_inputs','sdx_inputs','sdx_runtime_probe_inputs',
                  'platform_inputs','console_inputs','task_inputs','banked_inputs'):
        for name,digest in program['build'].get(group,{}).items():
            # Guest source changes are the purpose of this mode. Native
            # implementation/ABI changes require a fresh emitted fixture.
            if name.startswith(('lib/','abi/','platform/','config/','toolchain/')):
                require((ROOT/name).is_file() and sha256(ROOT/name)==digest,
                        'Native input changed; rebuild fixture: '+name)
    def code(text):
        return '\n'.join(line for line in text.splitlines()
                         if line.strip() and not line.lstrip().startswith(';'))
    require(code(previous_source)==code(current_source),
            'Native fixture changed; rebuild instead of --reuse-native')
    for address, raw in payloads:
        segment=next((item for item in program['image']['segments'] if item['address']==address),None)
        require(segment is not None and len(segment['bytes'])==len(raw),
                'Guest input extent changed; rebuild native fixture')

    def install(bridge):
        # execute calls this at the paused bootstrap, before Task execution.
        for address, raw in payloads:
            bridge.memload(address,raw)
    return install
