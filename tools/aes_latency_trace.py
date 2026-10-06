"""Passive AES call/deadline boundaries, checked against emitted instructions.

A reply boundary is the call to public ReplyMsg (before its bounded publication
transaction). Client completion is the binding's checked-result epilogue.
"""
import re
from collections import defaultdict
from native_program import require
from sio_transaction_trace import BASE_HZ
from measure_desktop import distribution


def routine(program, name):
    r=next(r for r in program['image']['routines'] if r['name'].startswith('M_'+name+'_'))
    raw=bytearray(r['size'])
    for s in program['image']['segments']:
        lo=max(s['address'],r['address']);hi=min(s['address']+len(s['bytes']),r['address']+r['size'])
        if lo<hi:raw[lo-r['address']:hi-r['address']]=bytes(s['bytes'][lo-s['address']:hi-s['address']])
    return r['address'],bytes(raw)


def c_listing(program, name, stem):
    paths=list((program['output'].parent/'drawing').glob('*-'+stem+'.lst'))
    require(len(paths)==1, 'Missing C listing '+stem)
    text=paths[0].read_text().replace('\r\n','\n')
    require(text.count(name+':')==1, 'Missing or ambiguous C routine '+name)
    return text.split(name+':',1)[1].split('.section ',1)[0]


def caller_markers(program, foreign):
    sy=foreign['symbols'];out={}
    text=c_listing(program,'evnt_timer','aes')
    require('evnt_timer' in sy, 'Missing public timer entry')
    out['direct_timer_begin']=sy['evnt_timer']
    epilogue=text.rsplit('}',1)[1]
    end=re.search(r'\\ ([0-9a-f]{6}) [0-9a-f.]+\s+',epilogue)
    require(end is not None, 'Missing public timer epilogue')
    out['direct_timer_end']=sy['evnt_timer']+int(end[1],16)
    text=c_listing(program,'ExecAESTimerSend','aes-events')
    require('ExecAESTimerSend' in sy,'Missing caller alarm submission')
    # Read values at their actual 64-bit request-field stores, independent of
    # Calypsi's register-versus-stack choice for the C arguments.
    for field,offset_value in (('high',26),('low',30)):
        add=re.search(r'\\ [0-9a-f]{6} [0-9a-f.]+\s+adc\s+##'+str(offset_value)+r'\b',text)
        require(add is not None,'Missing caller deadline field '+field)
        stores=re.findall(r'\\ ([0-9a-f]{6}) (?:87|97)[0-9a-f.]+\s+sta\s+\[',text[add.end():])[:2]
        require(len(stores)==2,'Missing wide caller deadline store '+field)
        for half,at in zip(('lo','hi'),stores):
            out['direct_deadline_'+field+'_'+half]=sy['ExecAESTimerSend']+int(at,16)
    # The existing public C I/O bridge copies four full-width arguments to
    # native stack storage. Observe a=request before SendIO can complete.
    entry=sy['_IOCall']
    raw=next(bytes(s['bytes'][entry-s['address']:entry-s['address']+100])
        for s in foreign['segments'] if s['address']<=entry<s['address']+len(s['bytes']))
    needle=bytes.fromhex('a00000b7808305c8c8b7808307')
    require(raw.count(needle)==1,'Unknown public C I/O bridge argument copy')
    at=raw.index(needle)
    out.update(io_begin=entry,io_request_low=entry+at+5,io_request_high=entry+at+11)
    return out


def markers(program, foreign):
    sy=foreign['symbols'];out={}
    text=next((program['output'].parent/'drawing').glob('*-aes.lst')).read_text()
    text=text.split('submit:',1)[1].split('.section ',1)[0]
    offset=lambda pattern:int(re.search(pattern,text)[1],16)
    # Calypsi's linked symbol table may expose only one of equal-named static
    # functions from different translation units (VBXE also has a submit).
    # Resolve the binding by its emitted instruction prefix, never that name.
    prefix={}
    for line in text.splitlines():
        match=re.search(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+',line)
        if not match:continue
        address=int(match[1],16)
        for index in range(0,len(match[2]),2):
            prefix[address+index//2]=match[2][index:index+2]
    require(all(i in prefix for i in range(32)),'Incomplete binding prefix')
    pattern=b''.join(b'.' if prefix[i]=='..' else re.escape(bytes.fromhex(prefix[i])) for i in range(32))
    locations=[segment['address']+m.start() for segment in foreign['segments'] if segment['executable']
        for m in re.finditer(pattern,bytes(segment['bytes']),re.S)]
    require(len(locations)==1,'Ambiguous linked AES binding')
    entry=locations[0]
    out['submit']=entry
    pointer_setup=text.split('struct AESRequest *r = &c->request;',1)[1].split('struct Message *reply;',1)[0]
    stores=re.findall(r'\\ ([0-9a-f]{6}) 83[0-9a-f]{2}\s+sta\s+\d+,s',pointer_setup)
    require(len(stores)==2,'Unknown binding pointer setup')
    out['c_low'],out['c_high']=(entry+int(at,16) for at in stores)
    out['send']=entry+offset(r'\\ ([0-9a-f]{6}) 22[.]+\s+jsl\s+long:PutMsg')
    out['client']=entry+int(re.findall(r'\\ ([0-9a-f]{6}) a8\s+tay',text)[-1],16)
    for name,key in (('AESCORE_DISPATCH','service'),('AESSTATE_REPLY','reply')):
        base,raw=routine(program,name)
        pairs=list(re.finditer(rb'\xa3(.)\x85\x80\xa3(.)\x85\x81',raw,re.S))
        if key=='service':
            # Dispatch also loads the service pointer. Anchor the request on
            # its message-length read, not the first pointer in the routine.
            pairs=[pair for pair in pairs if raw[pair.end():pair.end()+3]==bytes.fromhex('a00e00')]
        require(pairs and pairs[0][2][0]==pairs[0][1][0]+1,'Unknown native pointer load '+name)
        at=pairs[0].start()
        out[key+'_low']=base+at+2;out[key+'_high']=base+at+6
        if key=='reply':
            call=b'\x22'+program['labels']['ports_reply_msg'].to_bytes(3,'little')
            require(raw.count(call)==1,'Ambiguous AES reply boundary')
            out['reply']=base+raw.index(call)
    out.update(caller_markers(program,foreign))
    base,raw=routine(program,'AESTIMER_TARGET')
    for field,offset_value in (('deadline_high',26),('deadline_low',30)):
        needle=b'\xa0'+offset_value.to_bytes(2,'little')+b'\x97\x80\xa3'
        require(raw.count(needle)==1,'Unknown alarm deadline stores')
        at=raw.index(needle)
        require(raw[at+7:at+11]==bytes.fromhex('c8c89780'),'Unknown wide alarm store')
        out[field+'_lo']=base+at+3;out[field+'_hi']=base+at+9
    listing=(program['output']/'hosted.lst').read_text()
    local=lambda name:int(re.search(r'(?m)^([0-9A-F]{6})r \d+\s+'+name+r':',listing)[1],16)
    native_base=program['labels']['native_timer_work']-local('native_timer_work')
    out['device_due']=native_base+local('timer_expiry_due')
    # Request is already in A/X at this native ReplyMsg call.
    lines=listing.split('timer_expiry_reply:',1)[1].split('timer_expiry_done:',1)[0]
    out['device_reply']=native_base+int(re.search(r'(?m)^([0-9A-F]{6})r .*jsl exec_reply_msg_native',lines)[1],16)
    out['clock_tick']=program['labels']['native_vbi_clock']
    return out


def analyze(events, marks, final_clock, window=None):
    names={pc:name for name,pc in marks.items()}
    active={};by_pointer={};parts={};ticks={};clock=0;alarm_high=alarm_low=0
    due=None;reply_pointer=None;device=None;rows=[];alarms=[]
    direct={};direct_parts=defaultdict(dict);io={};caller_alarms={}
    for time,event in events:
        if event[0]!='cpu':continue
        name=names.get(int(event[4],16))
        if name is None:continue
        a=int(event[5],16);dp=int(event[9],16)
        if name=='clock_tick':
            clock+=1;ticks[clock]=time
        elif name=='direct_timer_begin':
            require(dp not in direct and dp not in active,'Overlapping public timer call')
            direct[dp]=dict(start=time,operation=24,dp=dp,transport='direct')
        elif name=='direct_timer_end':
            require(dp in direct,'Public timer returned without entry')
            row=direct.pop(dp);row['client']=time;rows.append(row)
        elif name.startswith('direct_deadline_'):
            direct_parts[dp][name.removeprefix('direct_deadline_')]=a
        elif name=='io_begin':
            io[dp]=dict(operation=a)
        elif name=='io_request_low':
            io[dp]['pointer']=a
        elif name=='io_request_high':
            call=io[dp];call['pointer']|=a<<16
            if call['operation']==5 and dp in direct:
                values=direct_parts[dp]
                require(all(k in values for k in ('low_lo','low_hi','high_lo','high_hi')),
                        'Missing caller alarm deadline')
                deadline=(values['high_lo'] | values['high_hi']<<16)<<32
                deadline|=values['low_lo'] | values['low_hi']<<16
                caller_alarms[call['pointer']]=dict(deadline=deadline,row=direct[dp])
                direct[dp]['alarm']=call['pointer']
        elif name=='submit':
            require(dp not in active,'Overlapping private AES call')
            active[dp]=dict(start=time,operation=a,dp=dp,transport='rpc')
        elif name=='c_low':active[dp]['pointer']=a
        elif name=='c_high':
            row=active[dp];row['pointer']|=a<<16
            require(row['pointer'] not in by_pointer,'Binding reused before reply collection')
            by_pointer[row['pointer']]=row
        elif name=='send':active[dp]['send']=time
        elif name in ('service_low','reply_low'):parts[name]=a
        elif name in ('service_high','reply_high'):
            key=name.split('_')[0];pointer=parts[key+'_low'] | (a<<8)
            require(pointer in by_pointer,'Unknown AES request in service')
            if key=='service':by_pointer[pointer]['service']=time
            else:reply_pointer=pointer
        elif name=='reply':
            row=by_pointer[reply_pointer]
            require('reply' not in row,'Double AES reply')
            row['reply']=time
            if device is not None and row['operation'] in (24,25):
                row['previous_device_reply']=device
        elif name=='client':
            row=active.pop(dp)
            require('reply' in row,'AES client returned without observed reply')
            row['client']=time;rows.append(row);del by_pointer[row['pointer']]
        elif name.startswith('deadline_'):
            parts[name]=a
            if name.endswith('_hi'):
                value=parts[name[:-2]+'lo'] | (a<<16)
                if name.startswith('deadline_high'):alarm_high=value
                else:alarm_low=value
        elif name=='device_due':
            require(due is None,'Overlapping native expiry decisions')
            due=dict(due=time)
        elif name=='device_reply':
            require(due is not None,'Timer reply without expiry decision')
            pointer=a | (int(event[6],16)<<16)
            caller=caller_alarms.pop(pointer,None)
            deadline=caller['deadline'] if caller else (alarm_high<<32)|alarm_low
            require(deadline in ticks,'Alarm expired before its observed VBI deadline')
            due.update(pointer=pointer,deadline=deadline,deadline_clock=ticks[deadline],reply=time)
            if caller:
                require('device_reply' not in caller['row'],'Duplicate caller alarm expiry')
                caller['row']['device_reply']=time
                due['client_dp']=caller['row']['dp']
            alarms.append(due);due=None;device=time
    require(not active and not by_pointer and not direct,'Uncollected AES calls in complete trace')
    require(clock==final_clock,'VBI trace does not match the device clock')
    if window is not None:
        rows=[r for r in rows if window[0]<=r['start']<=r['client']<=window[1]]
        alarms=[a for a in alarms if window[0]<=a['deadline_clock']<=a['reply']<=window[1]]
    require(len(rows)>=6 and alarms,'Empty AES call or expiry trace')
    groups=defaultdict(list)
    for row in rows:
        groups[str(row['operation'])].append(row)
    ms=lambda value:value/BASE_HZ*1000
    def metrics(items):
        if items[0]['transport']=='direct':
            require(all(row['transport']=='direct' for row in items),'Mixed execution paths for one operation')
            return dict(transport='direct',public_call=distribution([ms(row['client']-row['start']) for row in items]),
                device_reply_to_client=distribution([ms(row['client']-row['device_reply']) for row in items if 'device_reply' in row]))
        return {label:distribution([ms(row[end]-row[start]) for row in items])
                for label,start,end in (('binding_setup','start','send'),('submit_to_service','send','service'),
                    ('service_to_reply','service','reply'),('reply_to_client','reply','client'),('total','start','client'))}
    # Associate only timer calls whose service admission predates this alarm's
    # terminal reply. Immediate/queued-message completions are excluded.
    device_to_aes=[ms(row['reply']-row['previous_device_reply']) for row in rows
        if row['transport']=='rpc' and row['operation']==24 and 'previous_device_reply' in row
        and row['service']<row['previous_device_reply']<=row['reply']]
    return dict(calls=len(rows),window=window,operations={key:metrics(value) for key,value in groups.items()},
        expiry_count=len(alarms),clock_ticks=clock,
        deadline_to_device_reply=distribution([ms(a['reply']-a['deadline_clock']) for a in alarms]),
        expiry_decision_to_device_reply=distribution([ms(a['reply']-a['due']) for a in alarms]),
        device_reply_to_aes_reply=distribution(device_to_aes),
        scope='RPC uses the historical submit-to-checked-epilogue interval. Direct timers use public wrapper entry to result epilogue, including context lookup; compare these as distinct metrics. Caller deadlines and native expiry replies are matched by exact request pointer and client DP. VBI rounding is excluded from deadline latency.',
        records=rows,alarms=alarms)
