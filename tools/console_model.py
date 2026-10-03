"""Decode private retained storage for independent terminal/pixel oracles."""
from generate_console import constants
from native_program import require


def read_cells(read, instance):
    layout = constants()
    record = read(instance, layout['INSTANCE_SIZE'])
    def field(name, size=2):
        offset = layout['INSTANCE_'+name]
        return int.from_bytes(record[offset:offset+size], 'little')
    width, height = field('WIDTH'), field('HEIGHT')
    count, origin = field('COUNT'), field('CELLORIGIN')
    require(width > 0 and height > 0 and count == width*height and
            count <= layout['CELL_BYTES'] and origin < count and origin % width == 0,
            'Invalid retained console row layout')
    physical = read(field('CELLS', 3), count)
    require(len(physical) == count, 'Incomplete retained cell read')
    return physical[origin:]+physical[:origin]
