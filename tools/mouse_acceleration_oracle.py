"""Independent rational model of the MA2 pointer contract (no generated tables)."""
from fractions import Fraction
from math import trunc

AXIS = (4,4,4,4,4,4,4,4,3,2,2,Fraction(3,2),Fraction(3,2),1,1,1,1)
DIAGONAL = (4,4,4,4,4,4,4,4,4,3,2,2,Fraction(3,2),Fraction(3,2),1,1,1)


class Pointer:
    def __init__(self, x=320, y=120, profile='mild'):
        self.position = [x,y]
        self.remainder = [Fraction(0),Fraction(0)]
        self.profile = profile

    def take(self, dx, dy, info, kind=2):
        if kind == 4 or info & 31 == 16:
            self.remainder = [Fraction(0),Fraction(0)]
        if kind != 4:
            gain = 2 if self.profile == 'off' else (DIAGONAL if info & 32 else AXIS)[info & 31]
            for axis, (delta, limit) in enumerate(zip((dx,dy),(639,239))):
                if not delta:
                    continue
                exact = delta*gain+self.remainder[axis]
                movement = trunc(exact)
                self.remainder[axis] = exact-movement
                self.position[axis] += movement
                if self.position[axis] <= 0 and (self.position[axis] < 0 or self.remainder[axis] < 0):
                    self.position[axis] = 0
                    self.remainder[axis] = Fraction(0)
                if self.position[axis] >= limit and (self.position[axis] > limit or self.remainder[axis] > 0):
                    self.position[axis] = limit
                    self.remainder[axis] = Fraction(0)
        return tuple(self.position)


def cases():
    """Include paired partitions, fractional tails, resets, clipping and buttons."""
    result = []
    def scenario(profile, initial, events):
        pointer = Pointer(*initial, profile)
        for i,(dx,dy,info,kind) in enumerate(events):
            result.append((int(i == 0),int(profile == 'mild'),*initial,dx,dy,info,kind,*pointer.take(dx,dy,info,kind)))
        return pointer
    for profile in ('off','mild'):
        for info in [*range(17),*(32+i for i in range(17))]:
            for sign in (-1,1):
                dy = sign if info & 32 else 0
                split = scenario(profile,(320,120),[(sign,dy,info,2)]*17+[(0,0,0,3)])
                merged = scenario(profile,(320,120),[(sign*17,dy*17,info,2),(0,0,0,3)])
                assert split.position == merged.position and split.remainder == merged.remainder
        for initial in ((0,0),(639,239),(1,1),(638,238),(320,120)):
            scenario(profile,initial,[(64,64,32,2),(1,1,43,2),(-1,-1,48,2),
                (-64,-64,32,2),(-64,-64,32,2),(-64,-64,32,2),(1,1,48,2),
                (1,1,43,2),(0,0,0,3),(0,0,0,4),(1,1,43,2),
                (-1,-1,48,2),(0,0,16,2)])
        # Remainders survive timing changes but expire at pauses/reversal/loss.
        scenario(profile,(320,120),[(1,0,11,2),(0,0,0,3),(1,0,12,2),
            (-1,0,16,2),(-1,0,11,2),(0,0,16,2),(-1,0,11,2),
            (0,0,0,4),(1,0,11,2),(1,0,11,2)])
    return result
