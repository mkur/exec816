"""Coverage analysis for frozen native-preview background traces."""
from native_program import require

CLIENT = (39, 45, 183, 101)
DAMAGE = [(40, 46, 70, 56), (56, 52, 82, 64), (32, 99, 44, 108),
          (38, 32, 98, 40), (176, 97, 190, 107)]
def pixel_set(bounds):
    left, top, right, bottom = bounds
    return {(x, y) for y in range(top, bottom) for x in range(left, right)}


def check_fills(rows):
    client = pixel_set(CLIENT)
    first = rows[1]['fills']
    backgrounds = [f for f in first if f['pen'] == 3]
    require(backgrounds, 'Missing empty-client background')
    require(set().union(*(pixel_set(f['bounds']) for f in backgrounds)) == client,
            'Client background does not cover every pixel')
    require(sum(len(pixel_set(f['bounds'])) for f in backgrounds) == len(client),
            'Duplicate empty-client background pass')
    require(all(not (pixel_set(f['bounds']) & client) for f in first if f['pen'] != 3),
            'Frame background overwrites client pixels')
    allowed = set().union(*(pixel_set(r) for r in DAMAGE))
    require(rows[5]['fills'], 'Missing sparse repair')
    require(all(pixel_set(f['bounds']) <= allowed for f in rows[5]['fills']),
            'Sparse fill escaped its damage clips')


