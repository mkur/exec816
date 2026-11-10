"""Coverage oracle for the three windows closed by the matched AES fixture."""
from os_boundary import require


def check_exposure_rectangles(rectangles,work):
    """Allow conservative coalescing, while requiring every exposure repair."""
    source=[(work[0]+x,work[1]+8,32,48) for x in (32,80,352)]
    allowed={(a[0],a[1],b[0]+b[2]-a[0],a[3])
             for i,a in enumerate(source) for b in source[i:]}
    rows=[tuple(r) for r in rectangles]
    require(1<=len(rows)<=3 and len(set(rows))==len(rows),
            'Unbounded or duplicate exposure redraws')
    require(all(r in allowed for r in rows),'Unexpected exposure redraw geometry')
    require(all(any(r[0]<=s[0] and r[0]+r[2]>=s[0]+s[2] for r in rows) for s in source),
            'Exposure redraws omit newly exposed pixels')
