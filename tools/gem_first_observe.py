"""Independent liveness and scanout checks for the native GEM-first baseline."""
from native_program import require


def digit_pixels(raw, stride, width, height, x, y):
    """Counter's 48x8 digit damage, after the native scanout's 16-pixel margin."""
    require(width == 672 and height == 240 and len(raw) == stride*height,
            'Unexpected native scanout geometry')
    require(0 <= x <= 640-48 and 0 <= y <= height-8, 'Digit crop outside screen')
    return b''.join(raw[row*stride+(column+16)*4:row*stride+(column+16)*4+3]
                    for row in range(y, y+8) for column in range(x, x+48))


def progress(before, after, count=2):
    """Model progress alone cannot establish that an inactive client painted."""
    old, new = before['clients'][:count], after['clients'][:count]
    require(len(old) == len(new) == count, 'Missing Counter sample')
    for field in ('identity', 'base', 'id', 'window'):
        require(all(item[field] for item in old), 'Missing Counter '+field)
        require(len({item[field] for item in old}) == count, 'Counters share '+field)
    result = []
    for a, b in zip(old, new):
        require(all(a[key] == b[key] for key in ('identity', 'base', 'id', 'window')),
                'Counter identity changed between samples')
        require(b['count'] > a['count'], 'Counter stopped')
        require(b['paints'] > a['paints'], 'Counter paint stopped')
        require(b['digits_sha256'] != a['digits_sha256'], 'Counter digit pixels did not change')
        result.append(dict(identity=a['identity'], increments=b['count']-a['count'],
                           paints=b['paints']-a['paints']))
    return result
