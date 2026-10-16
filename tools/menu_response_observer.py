"""Host-only heading crossings and frame endpoints for the menu observer."""
from native_program import ROOT, require
from sio_transaction_trace import BASE_HZ


def crossing_markers(program):
    image = program['image']
    decoder = {'__name__': 'menu_decoder'}
    path = ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(), str(path), 'exec'), decoder)
    points = {}
    for routine, fields in (
            ('DESKINPUT_FRESH', [('DESKINPUT_CURSORX', 'pointer_x'),
                                 ('DESKINPUT_CURSORY', 'pointer_y')]),
            ('DESKMENU_HEADING', [('DESKMENU_PENDINGHEADING', 'heading_routed')])):
        r = next(r for r in image['routines'] if r['name'].startswith('M_'+routine+'_'))
        segments = []
        for s in image['segments']:
            lo = max(s['address'], r['address'])
            hi = min(s['address']+len(s['bytes']), r['address']+r['size'])
            if lo < hi:
                segments.append(dict(address=lo, executable=True,
                    bytes=s['bytes'][lo-s['address']:hi-s['address']]))
        listing = decoder['disassemble']({**image, 'version': 3, 'segments': segments})
        for field, name in fields:
            address = next(d['address'] for d in image['data']
                           if d['name'].startswith('M_'+field+'_'))
            stores = [line for line in listing.splitlines()
                      if line.endswith(f' STA ${address:06X}')]
            require(len(stores) == 1, 'Ambiguous menu observer store: '+field)
            require('8F ' in stores[0], 'Expected long accumulator store: '+field)
            points[int(stores[0][:6], 16)] = name
    return points


def heading_at(x, y, headings):
    return next((h['index'] for h in headings if h['enabled'] and
                 h['bounds'][0] <= x < h['bounds'][2] and
                 h['bounds'][1] <= y < h['bounds'][3]), None)


def pixels_match(got, want, area, masks=()):
    """Packed BGRA crop; mask only the current/previous 16x16 pointer image."""
    left, top, right, bottom = area
    width = right-left
    require(len(got) == len(want) == width*(bottom-top)*4, 'Menu crop size')
    for y in range(top, bottom):
        offset = (y-top)*width*4
        cuts = sorted((max(left, x & ~1), min(right, (x+15 | 1)+1))
                      for x, yy in masks if yy <= y < yy+16 and x < right and x+16 > left)
        begin = left
        for lo, hi in cuts + [(right, right)]:
            if lo > begin:
                a, b = offset+(begin-left)*4, offset+(lo-left)*4
                if got[a:b] != want[a:b]:
                    return False
            begin = max(begin, hi)
    return True


def endpoint(start, tick):
    return start+((tick-int(start)) & 0xffffffff)


def pointer_response(events, points, sample, start, end, worker):
    """Coordinates are fresh stores; routing can happen later through replay."""
    target = sample['heading']
    x, y = sample['initial_pointer']
    previous = heading_at(x, y, sample['headings'])
    crossings, routes, losses = [], [], []
    for tick, e in events:
        if not start <= tick <= end or int(e[9], 16) != worker:
            continue
        name = points.get(int(e[4], 16))
        a = int(e[5], 16)
        if name in ('pointer_x', 'pointer_y', 'heading_routed'):
            require(not int(e[11], 16) & 0x20, 'Menu coordinate store is not 16-bit')
        if name == 'pointer_x':
            x = a
        elif name == 'pointer_y':
            y = a
            hit = heading_at(x, y, sample['headings'])
            if hit != previous:
                crossings.append(dict(tick=tick, heading=hit, x=x, y=y))
            previous = hit
        elif name == 'heading_routed' and a == target:
            routes.append(tick)
        elif name == 'AESMOUSE_LOST':
            losses.append(tick)
    hits = [c['tick'] for c in crossings if c['heading'] == target]
    crossing = hits[0] if hits else None
    routed = next((t for t in routes if crossing is not None and t >= crossing), None)
    full = sample['complete_frame']
    first = endpoint(start, full['first_match'])
    last = endpoint(start, full['last_nonmatch'])
    valid = crossing is not None and routed is not None and len(hits) == 1 and not losses
    ms = lambda t: (t-start)*1000/BASE_HZ if t is not None else None
    return dict(available=valid, crossings=crossings, routed=routes, input_loss=losses,
        crossing_ms=ms(crossing), routing_ms=ms(routed),
        travel_ms=ms(crossing),
        crossing_to_routing_ms=(routed-crossing)*1000/BASE_HZ if valid else None,
        crossing_to_visible_ms=[max(0, last-crossing)*1000/BASE_HZ,
                                (first-crossing)*1000/BASE_HZ] if valid else None)
