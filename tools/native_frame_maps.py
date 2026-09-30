"""Check v3 frame-map bounds; typed liveness proofs remain compiler-owned."""
from os_boundary import require
from native_abi import FIELDS, POINTERS

SCALAR_START = FIELDS["scratch"]["offset"] + 32
SCALAR_END = FIELDS["scratch"]["offset"] + FIELDS["scratch"]["size"] - 2


def natural(value, label):
    require(type(value) is int and value >= 0, 'Invalid frame-map ' + label)
    return value


def validate(routines):
    require(isinstance(routines, list), 'Invalid routine maps')
    ids = set()
    for routine in routines:
        required = {'id', 'fixed_frame', 'spill_bytes', 'arguments', 'objects',
                    'temporaries', 'calls', 'local_stack_peak', 'whole_task_stack_bound'}
        require(isinstance(routine, dict) and required <= routine.keys(), 'Incomplete v3 routine map')
        identity = natural(routine['id'], 'routine identity')
        require(identity not in ids, 'Duplicate routine map')
        ids.add(identity)
        frame = natural(routine['fixed_frame'], 'fixed frame')
        require(frame <= 254 and frame % 2 == 0 and
                natural(routine['spill_bytes'], 'spill extent') <= frame and
                routine['whole_task_stack_bound'] is None, 'Invalid fixed frame')
        for field in ('arguments', 'objects', 'temporaries', 'calls'):
            require(isinstance(routine[field], list), 'Invalid frame-map ' + field)
        for argument in routine['arguments']:
            require(isinstance(argument, dict) and
                    {'offset', 'body_displacement', 'size'} <= argument.keys(), 'Invalid incoming map')
            offset = natural(argument['offset'], 'incoming offset')
            size = natural(argument['size'], 'incoming size')
            displacement = natural(argument['body_displacement'], 'incoming displacement')
            require(size > 0 and displacement == frame + 4 + offset and
                    displacement + size <= 256, 'Invalid incoming displacement')
        extents = []
        for obj in routine['objects']:
            require(isinstance(obj, dict) and {'displacement', 'size'} <= obj.keys(), 'Invalid frame object')
            extents.append((obj['displacement'], obj['size']))
        temps, dp_width = set(), None
        for temp in routine['temporaries']:
            require(isinstance(temp, dict) and set(temp) == {'id', 'size', 'home'}, 'Invalid v3 temporary')
            identity = natural(temp['id'], 'temporary identity')
            size = natural(temp['size'], 'temporary size')
            require(identity not in temps and 1 <= size <= 4, 'Invalid temporary identity/width')
            temps.add(identity)
            home = temp['home']
            require(isinstance(home, dict), 'Invalid temporary home')
            if home.get('kind') == 'stack':
                require(set(home) == {'kind', 'displacement'}, 'Invalid stack home')
                extents.append((home['displacement'], size))
            else:
                require(home.get('kind') == 'direct_page' and set(home) == {'kind', 'offset'},
                        'Invalid direct-page home')
                offset = natural(home['offset'], 'direct-page offset')
                # Pointer CFGs keep complete three-byte slots and use remaining
                # resident bytes for byte temporaries. Word allocation is separate.
                resident_pointer = (SCALAR_START <= offset <= SCALAR_END - 1 and
                                    (offset - SCALAR_START) % 3 == 0)
                pointer = size == 3 and (offset in POINTERS or resident_pointer)
                scalar = size == 2 and SCALAR_START <= offset <= SCALAR_END and offset % 2 == 0
                byte = size == 1 and SCALAR_START <= offset <= SCALAR_END + 1
                dp_class = 3 if byte else size
                require((pointer or scalar or byte) and not routine['calls'] and
                        dp_width in (None, dp_class), 'Invalid direct-page temporary map')
                dp_width = dp_class
        resident_pointers = [t['home']['offset'] for t in routine['temporaries']
                             if t['size'] == 3 and t['home']['kind'] == 'direct_page']
        for temp in routine['temporaries']:
            if temp['size'] == 1 and temp['home']['kind'] == 'direct_page':
                offset = temp['home']['offset']
                require(not any(start <= offset < start + 3 for start in resident_pointers),
                        'Byte resident overlaps complete pointer slot')
        # Temporary homes may overlap when their typed live ranges do not.
        # The final map cannot establish that proof; the compiler verifies it.
        for offset, size in extents:
            offset = natural(offset, 'stack displacement')
            size = natural(size, 'stack extent')
            require(offset > 0 and size > 0 and offset + size <= frame + 1,
                    'Frame-map extent exceeds allocation')
        peak = 0
        for call in routine['calls']:
            require(isinstance(call, dict) and set(call) == {'outgoing', 'transfer_peak'}, 'Invalid call map')
            outgoing = natural(call['outgoing'], 'outgoing extent')
            transfer = natural(call['transfer_peak'], 'call transfer')
            require(0 < outgoing <= 255 and outgoing % 2 == 1 and transfer in (3, 6), 'Invalid call extent')
            peak = max(peak, outgoing + transfer)
        require(natural(routine['local_stack_peak'], 'local peak') == frame + peak,
                'Invalid local stack accounting')
