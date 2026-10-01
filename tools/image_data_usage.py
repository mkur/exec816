"""Measure emitted data against the range recorded for that build."""


def used(image, memory):
    arena = memory.get('image_data')
    if arena is not None:
        low, high = arena['address'], arena['address']+arena['size']
    else:
        # Historical report inputs retain their original near arena geometry.
        low, high = memory['profile']['image_near']
    return sum(len(s['bytes']) for s in image['segments'] if low <= s['address'] < high) + sum(
        s['size'] for s in image['zero_fill'] if low <= s['address'] < high)
