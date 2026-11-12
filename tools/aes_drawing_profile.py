"""Exclusive caller CPU and physical-unit accounting for passive AES traces."""
from collections import defaultdict

from os_boundary import require


# Earlier groups take priority over their inclusive parents. The residual
# categories are named for their scope, not an inferred instruction purpose.
CATEGORIES = {
    'display_ownership': {'DisplayEnter', 'DisplayLeave'},
    'completion_poll': {'idle'},
    'upload': {'_VbxeUpload', '_VbxeTextUpload'},
    'submission_fence': {'VbxeOwnerSubmit', 'VbxeOwnerFence', 'VbxeOwnerRead',
        'VbxeOwnerWrite', 'start', 'fence_owner', 'drain', 'flush'},
    'command_build': {'blit_mask', 'blit_glyph', 'blit_glyph_run', 'glyph_record',
        'text_run', 'GemSolidFill', 'solid_record', 'blit_and', 'blit_or',
        'blit_xor', 'blit_fill'},
    'graphics_state': {'App_gsx_attr', 'App_gsx_fcolor', 'gsx_attr', 'gsx_fcolor',
        'GemVdiReset'},
    'primitive_renderer': {'App_WidgetFill', 'App_WidgetText', 'App_bb_fill',
        'App_gsx_box', 'App_gsx_tblt', 'GemWidgetFill', 'GemWidgetText',
        'GemWidgetStipple', 'vbxe_fill_rect', 'vbxe_glyph', 'vbxe_text_run',
        'vbxe_widget_text_run', 'vbxe_line_diag', 'draw_line'},
    'object_preparation': {'prepare_object', 'prepare_icon', 'App_prepare_draw',
        'ExecAESPrepareEdit', 'App_gr_just_to'},
    'object_callback_setup': {'draw', 'App_just_draw', 'just_draw',
        'App_draw_prepared', 'ExecAESPaintEdit', 'draw_icon',
        'ExecAESDrawEdit', 'App_ob_relxywh', 'App_gr_inside', 'App_gr_crack',
        'App_gr_just', 'App_expand_string', 'App_gsx_chkclip', 'App_r_set'},
    'cursor_overlay': {'pointer_erase', 'cursor_show', 'cursor_hide',
        'cursor_render', 'outline_toggle'},
    'borrow_glue': {'GemDrawingBorrow', 'drawing_borrow'},
    'aes_draw_other': {'ExecAESDraw', 'objc_draw'},
}
COUNTERS = ('DisplayEnter', 'DisplayLeave', 'GemDrawingBorrow', 'draw',
    'App_just_draw', 'prepare_object', 'App_prepare_draw', 'App_draw_prepared',
    'ExecAESPrepareEdit', 'prepare_icon', 'App_gsx_attr', 'App_WidgetFill', 'App_WidgetText',
    'GemSolidFill', 'solid_record', 'blit_mask', 'glyph_record',
    'VbxeOwnerSubmit', 'VbxeOwnerFence', '_VbxeUpload', '_VbxeTextUpload', 'idle')


def category(names):
    for name, members in CATEGORIES.items():
        if names & members:
            return name
    return 'unattributed'


def partition_cpu(timeline, spans, start, end):
    """Reconcile exclusive buckets against CPU charged to this Task only."""
    boundaries = defaultdict(list)
    boundaries[start]
    boundaries[end]
    for index, span in enumerate(spans):
        left, right = max(start, span['start']), min(end, span['end'])
        if left < right:
            boundaries[left].append((index, True))
            boundaries[right].append((index, False))
    active = set()
    totals = defaultdict(float)
    previous = start
    for tick in sorted(boundaries):
        if tick > previous:
            name = category({spans[i]['kind'] for i in active})
            totals[name] += timeline.measure(previous, tick)['charged_cpu_ms']
        for index, opening in boundaries[tick]:
            if opening:
                active.add(index)
            else:
                active.remove(index)
        previous = tick
    require(abs(sum(totals.values()) - timeline.measure(start, end)['charged_cpu_ms']) < 1e-6,
        'Drawing CPU buckets do not reconcile')
    return dict(totals)


def physical_units(timeline, spans, drawing):
    """Successful borrowed units; owned core excludes Enter and Leave."""
    def inside(scope, kind=None):
        return [s for s in spans if scope['start'] <= s['start'] < s['end'] <= scope['end']
            and (kind is None or s['kind'] == kind)]

    def one(scope, kind):
        rows = inside(scope, kind)
        require(len(rows) == 1, 'Expected one ' + kind + ' per borrowed unit')
        return rows[0]

    units = []
    borrows = sorted(inside(drawing, 'GemDrawingBorrow'), key=lambda s: s['start'])
    require(borrows, 'Missing physical drawing units')
    for index, borrow in enumerate(borrows):
        enter, leave, callback = (one(borrow, n) for n in ('DisplayEnter', 'DisplayLeave', 'draw'))
        require(enter['return_a'] == leave['return_a'] == borrow['return_a'] == 0,
            'Failed drawing ownership/borrow')
        require(enter['end'] <= callback['start'] < callback['end'] <= leave['start'],
            'Callback outside acquired drawing interval')
        require(not units or units[-1]['end'] <= borrow['start'], 'Overlapping borrows')
        nested = inside(borrow)
        units.append(dict(index=index, start=borrow['start'], end=borrow['end'],
            transaction=timeline.measure(enter['start'], leave['end']),
            owned_core=timeline.measure(enter['end'], leave['start']),
            callback=timeline.measure(callback['start'], callback['end']),
            exclusive_cpu_ms=partition_cpu(timeline, nested, borrow['start'], borrow['end']),
            counts={n:sum(s['kind'] == n for s in nested) for n in COUNTERS}))
    return units
