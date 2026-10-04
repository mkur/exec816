"""Physical desktop mouse coordinates, including explicitly frozen 1x images."""


def scale(program):
    # Older recorded images predate the desktop scale field; they used 1x.
    return program['build'].get('desktop_pointer_pixels_per_step', 1)


def coordinates(program, current, target):
    factor = scale(program)
    limits = (639, 239)
    result = [min(max(v, 0), limit) for v, limit in zip(target, limits)]
    result = [v if v == limit else v//factor*factor for v, limit in zip(result, limits)]
    steps = [(b+factor-1)//factor-(a+factor-1)//factor for a, b in zip(current, result)]
    return result, steps


def schedule(bridge, program, current, target):
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
