"""Physical pointer stimuli for current profiles and frozen benchmark images."""


def scale(program):
    if 'desktop_mouse' in program['build']:
        if program['build']['desktop_mouse']['profile'] != 'off':
            raise ValueError('Adaptive movement has no constant scale')
        return 2
    # Older recorded images predate the desktop scale field; they used 1x.
    return program['build'].get('desktop_pointer_pixels_per_step', 1)


def coordinates(program, current, target):
    factor = scale(program)
    limits = (639, 239)
    result = [min(max(v, 0), limit) for v, limit in zip(target, limits)]
    if 'desktop_mouse' in program['build']:
        delta = [b-a for a,b in zip(current,result)]
        steps = [(d+1)//2 if d>=0 else -((-d+1)//2) for d in delta]
        return [max(0,min(limit,a+2*n)) for a,n,limit in zip(current,steps,limits)],steps
    result = [v if v == limit else v//factor*factor for v, limit in zip(result, limits)]
    steps = [(b+factor-1)//factor-(a+factor-1)//factor for a, b in zip(current, result)]
    return result, steps


def slow_schedule(bridge, program, current, target):
    if program['build'].get('desktop_mouse',{}).get('profile') == 'mild':
        # Isolated one/two-phase packets give one whole pixel per phase.
        # The long idle resets any half-pixel diagonal tail before the next.
        # These are positioning stimuli; fast/threshold traces run separately.
        result = [max(0,min(limit,v)) for v,limit in zip(target,(639,239))]
        remaining = [b-a for a,b in zip(current,result)]
        index = 0
        while any(remaining):
            packet = [max(-2,min(2,d)) for d in remaining]
            remaining = [d-n for d,n in zip(remaining,packet)]
            bridge._cmd_ok(f'MOUSE AT {70000+index*130000} {packet[0]*16} {packet[1]*16} -1')
            index += 1
        return result
    result, (dx, dy) = coordinates(program, current, target)
    index = 0
    while dx or dy:
        # At most eight phases per packet, paced within the supported envelope.
        sx, sy = max(-8, min(8, dx)), max(-8, min(8, dy))
        bridge._cmd_ok(f'MOUSE AT {2000+index*85000} {sx*16} {sy*16} -1')
        dx -= sx
        dy -= sy
        index += 1
    return result


def schedule(bridge, program, current, target):
    # Session preferences may differ from the immutable build default. Observe
    # the active transform; never alter target state to position the pointer.
    selected = next((d['address'] for d in program['image']['data']
                     if '_DESKMOUSE_SELECTEDPROFILE_' in d['name']), None)
    if selected is not None and 'desktop_mouse' in program['build']:
        profile = 'mild' if bridge.memdump(selected,1)[0] else 'off'
        program = {**program, 'build': {**program['build'], 'desktop_mouse':
            {**program['build']['desktop_mouse'], 'profile': profile}}}
    if program['build'].get('desktop_mouse',{}).get('profile') != 'mild':
        return slow_schedule(bridge,program,current,target)
    # Coarse physical travel, observing the cursor like a user, followed by
    # exact slow phases. Independent curve/capture tests check displacement;
    # this positioning helper never writes a guest position or event.
    from os_boundary import run_to
    at = lambda name: next(d['address'] for d in program['image']['data']
        if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    target = [max(0,min(limit,v)) for v,limit in zip(target,(639,239))]
    current = list(current)
    for _ in range(128):
        remaining = [b-a for a,b in zip(current,target)]
        if max(map(abs,remaining)) <= 16:
            return slow_schedule(bridge,program,current,target)
        packet = [(1 if d>0 else -1)*min(16,max(1,abs(d)//4)) if d else 0 for d in remaining]
        bridge._cmd_ok(f'MOUSE AT 2000 {packet[0]*16} {packet[1]*16} -1')
        condition = f'@frame>={bridge.eval_expr("@frame")+7}'
        marker = program['labels']['native_irq']
        bridge.bp_clear_all();bridge.bp_set(marker,condition=condition)
        run_to(bridge,marker,condition=condition,timeout=60,frame_limit=500)
        current = [int.from_bytes(bridge.memdump(at(n),2),'little') for n in ('cursorX','cursorY')]
    raise RuntimeError('Physical pointer positioning did not converge')


def fast_distance(program, steps):
    if program['build'].get('desktop_mouse',{}).get('profile') == 'mild':
        return 4*steps-3 if steps else 0
    return steps*scale(program)


def raw_record(bridge, program, capture, head):
    # Frozen pre-MA1 images use the old private record layout. This reader does
    # not install an old runtime implementation or change their recorded data.
    size = program['build']['memory']['input_storage']['POINTER_CAPTURE_BYTES']
    slots,stride = (32,24) if size == 1280 else (64,28)
    return bridge.memdump(capture+128+(head & (slots-1))*stride,stride)
