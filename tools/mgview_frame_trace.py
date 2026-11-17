"""Passive selected-frame raster detail; consumes unchanged cached machine code."""
from collections import Counter,defaultdict
import struct

from native_program import require


GROUPS={
    'batch_control':'draw_FrameBatch widget_batch',
    'callback_control':'fragment',
    'scratch_clear':'fill',
    'traversal':'App_ob_offset App_everyobj',
    'object_callback':'frame_object',
    'object_preparation':'App_prepare_draw ob_sst App_gr_crack',
    'object_raster':'App_draw_prepared App_gr_box App_gr_rect App_gsx_box',
    'object_adapter':'App_WidgetFill App_bb_fill App_gsx_attr App_gsx_fcolor App_gsx_chkclip App_gr_inside',
    'solid_encoding':'GemSolidFill GemSolidRows solid_record',
    'pattern_encoding':'GemWidgetStipple',
    'mask_encoding':'blit_mask blit_and blit_fill',
    'queue':'drain flush fence_owner',
    'upload':'_VbxeUpload',
    'driver_submission':'submit',
    'overlays':'GemDrawingPrepare pointer_erase',
}


def partition(rows,timeline,start,end,kinds):
    """Assign each CPU interval to the innermost selected routine exactly once."""
    edges=defaultdict(list);edges[start];edges[end]
    for index,row in enumerate(rows):
        left=max(start,row['start']);right=min(end,row['end'])
        if left<right:
            edges[left].append((index,True));edges[right].append((index,False))
    active=set();previous=start;costs=Counter()
    for tick,changes in sorted(edges.items()):
        inner=max(active,key=lambda i:(rows[i]['start'],-rows[i]['end'])) if active else None
        group=kinds.get(rows[inner]['kind'],'unselected') if inner is not None else 'unselected'
        costs[group]+=timeline.measure(previous,tick)['charged_cpu_ms']
        for index,entering in changes:
            if entering:active.add(index)
            else:active.remove(index)
        previous=tick
    measured=timeline.measure(start,end)
    require(abs(sum(costs.values())-measured['charged_cpu_ms'])<1e-6,'Frame CPU partition does not reconcile')
    return dict(costs)


def analyze(rows,timeline):
    from mgview_slider_trace import GROUPS as SLIDER_GROUPS
    kinds={name:group for group,names in {**SLIDER_GROUPS,**GROUPS}.items() for name in names.split()}
    paints=[r for r in rows if r['kind']=='AESFRAME_PAINT']
    result=[]
    for paint in paints:
        start,end=paint['start'],paint['end']
        selected=[r for r in rows if start<=r['start']<r['end']<=end]
        functions=defaultdict(list)
        for row in selected:functions[row['kind']].append(row)
        callbacks=[]
        for callback in sorted(functions['fragment'],key=lambda r:r['start']):
            objects=[r for r in functions['frame_object'] if callback['start']<=r['start']<r['end']<=callback['end']]
            clears=[r for r in functions['fill'] if callback['start']<=r['start']<r['end']<=callback['end']]
            callbacks.append(dict(measured=timeline.measure(callback['start'],callback['end']),
                object_ids=[r['argument'] for r in sorted(objects,key=lambda r:r['start'])],
                clears=[dict(r,**timeline.measure(r['start'],r['end'])) for r in clears]))
        batches=functions['widget_batch'];fragments=functions['fragment']
        stages=[]
        for batch in batches:
            inside=sorted((r for r in fragments if batch['start']<=r['start']<r['end']<=batch['end']),key=lambda r:r['start'])
            require(len(inside)==1,'Expected one complete callback per widget batch')
            callback=inside[0]
            stages.extend([
                dict(kind='scratch_setup',start=batch['start'],end=callback['start']),
                dict(kind='scratch_callback',start=callback['start'],end=callback['end']),
                dict(kind='scratch_publication_and_fence',start=callback['end'],end=batch['end'])])
        for stage in stages:stage.update(timeline.measure(stage['start'],stage['end']))
        routines={name:dict(calls=len(calls),**{key:sum(r[key] for r in calls)
            for key in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')}) for name,calls in functions.items()}
        masks=[dict(charged_cpu_ms=mask['charged_cpu_ms']) for mask in functions['blit_mask']]
        submitted=sum(r['argument'] for r in functions['VbxeOwnerSubmit'])
        solid=len(functions['solid_record'])
        result.append(dict(measured=timeline.measure(start,end),exclusive_cpu_ms=partition(selected,timeline,start,end,kinds),
            stages=stages,callbacks=callbacks,routines=routines,
            raw_submission_record_counts=[r['argument'] for r in functions['VbxeOwnerSubmit']],
            mask_calls=masks,
            record_accounting=dict(solid=solid,mask_and_other=submitted-solid,submitted=submitted),
            spans=selected))
    require(result,'No completed frame paint in slider scope')
    return result


def geometry(bridge,program,app_window):
    """Read the complete stored frame at the ready checkpoint, before tracing."""
    from generate_desktop import layout as desktop_layout
    from generate_gem_objects import layout as gem_layout
    d=desktop_layout();g=gem_layout()
    number=lambda address,size=2:int.from_bytes(bridge.memdump(address,size),'little')
    service_var=next(r['address'] for r in program['image']['data'] if '_DESKSTATE_SERVICE_' in r['name'])
    service=number(service_var,3);handle=number(app_window)
    record=0
    for slot in range(6):
        candidate=number(service+d['Service']['fields']['windows']+slot*3,3)
        if candidate and number(candidate+d['Window']['fields']['gui'])==handle:
            record=candidate;break
    require(record,'Missing ready window frame')
    frame=bridge.memdump(record+d['Window']['fields']['frame'],g['Frame']['size'])
    fields=g['Frame']['fields'];objects={}
    for obj in (0,9,10,13,14):
        raw=frame[fields['tree']+obj*24:fields['tree']+(obj+1)*24]
        objects[str(obj)]=dict(zip(('next','head','tail','type','flags','state','spec','x','y','width','height'),struct.unpack('<3h3HI4h',raw)))
    return dict(handle=handle,objects=objects,
        rectangles={n:list(struct.unpack_from('<4h',frame,fields[n])) for n in ('current','work')},
        sliders={n:struct.unpack_from('<h',frame,fields[n])[0] for n in ('hslide','vslide','hsize','vsize')})
