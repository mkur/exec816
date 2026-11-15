"""Generate one native semaphore layout and ordinary/public operation bindings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = json.loads((ROOT/'abi/semaphores.json').read_text())
LABELS = {name+'Semaphore': 'semaphores_'+name.lower() for name in ('Init', 'Obtain', 'Attempt', 'Release')}


def constants():
    from generate_tasks import fields
    result = fields(ABI['record'], 'SEM')
    result.update(SEM_SIZE=ABI['record']['size'], SEM_ALIGNMENT=ABI['record']['alignment'])
    result.update({'SEM_SERVICE_'+name: value for name, value in ABI['services'].items()})
    for path in (ROOT/'abi').glob('*.json'):
        if path.name == 'semaphores.json':
            continue
        other = json.loads(path.read_text())
        used = set(other.get('services', {}).values()) | set(other.get('private_services', {}).values())
        if used & set(ABI['services'].values()):
            raise RuntimeError('Semaphore selector collision: '+path.name)
    return result


def public_api():
    return ('PUBLIC TYPE SignalSemaphore=[\n  CARD ARRAY ss_Private('+str(ABI['record']['size']//2)+')\n]\n'
            'PUBLIC CONST SEMAPHORE_SIZE='+str(ABI['record']['size'])+'\n')


def declarations():
    return ''.join('PUBLIC EXTERNAL '+('LONGINT FUNC ' if name == 'AttemptSemaphore' else 'PROC ')+
                   name+'(SignalSemaphore POINTER semaphore)\n' for name in ABI['imports'])


def generate(output):
    output = Path(output)
    values = constants()
    (output/'semaphore-abi.inc').write_text('; Generated from abi/semaphores.json.\n'+
        ''.join(f'{name} = ${value:x}\n' for name, value in values.items()))
    (output/'semaphore-types.inc').write_text('TYPE NativeSemaphore=[\n'+\
        ''.join(f'  {kind} {name}\n' for name, kind, _ in ABI['record']['fields'])+']\n')
    tasks = json.loads((ROOT/'abi/tasks.json').read_text())
    context = {name: offset for name, _, offset in tasks['context']['fields']}
    (output/'semaphore-action.inc').write_text('; Generated semaphore fixture constants.\n'+
        ''.join(f'CONST {name}=${value:x}\n' for name, value in values.items())+
        f'CONST SEM_OWNED_OFFSET={context["semaphoreOwned"]}\n')
    text = '; Generated semaphore native import stubs.\n.a16\n.i16\n'
    for name in ABI['imports']:
        label = LABELS[name]
        text += f'.export {label}, {label}_end\n{label}:\n'
        if name == 'InitSemaphore':
            # Ordinary leaf; the native ABI permits clobbering $80..$BF.
            text += ('    lda 4,s\n    sta $80\n    sep #$20\n    lda 6,s\n'
                     '    sta $82\n    rep #$20\n    lda #0\n'
                     f'    ldy #{ABI["record"]["size"]-2}\n:\n'
                     '    sta [$80],y\n    dey\n    dey\n    bpl :-\n')
        else:
            selector = name.removesuffix('Semaphore').upper()+'_SEMAPHORE'
            text += ('    lda 4,s\n    tax\n    sep #$20\n    lda 6,s\n'
                     '    rep #$20\n    and #$ff\n    ora #T_PROFILE_TAG\n'
                     f'    tay\n    lda #SEM_SERVICE_{selector}\n    cop $50\n')
        text += f'    rtl\n{label}_end:\n'
    (output/'semaphore-gateway.inc').write_text(text)
