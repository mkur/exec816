"""Physical settings and independent scanout checks on the packaged desktop."""
from native_program import require


def exercise(s,sy,click,move):
    b=s.b;panel=sy['GEMPanel'];counter=sy['GEMCounter']
    at=lambda module,name:next(d['address'] for d in s.p['image']['data']
                               if '_'+module+'_'+name.upper()+'_' in d['name'])
    active=at('DESKMOUSE','selectedProfile');chosen=at('DESKMOUSE','requestedProfile')
    state=lambda i:s.number(panel+178+i*24+10,2)
    staged=lambda:s.number(panel+400,2)
    applied=lambda:s.number(panel+402,2)
    actions=lambda:s.number(panel+10,4)
    def key(name,shift=False):
        if shift:b._cmd_ok('KEY SHIFT down')
        b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up')
        if shift:b._cmd_ok('KEY SHIFT up')
        s.frames(65)
    def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(45)
    def pixels(label):
        move(632,232);s.frames(50);s.cells('settings-'+label)
    def step(expected):
        x=s.number(at('DESKINPUT','cursorX'),2);y=s.number(at('DESKINPUT','cursorY'),2)
        b._cmd_ok('MOUSE AT 70000 16 0 -1');s.frames(12)
        actual=[s.number(at('DESKINPUT',name),2) for name in ('cursorX','cursorY')]
        require(actual==[x+expected,y],'Physical motion does not use applied profile: '+str(actual))
        s.saved['pointer']=actual
    count=s.number(counter+14,4)
    click(552,136);key('RETURN')
    click(456,136)
    require(staged()==0 and applied()==1 and s.number(active,1)==1,'Radio selection changed active mouse profile')
    pixels('pending-off')
    click(456,176)
    require(applied()==0 and s.number(active,1)==0 and state(6)==0,'Apply Off failed')
    step(2);pixels('active-off')
    click(456,104)
    require(staged()==1 and applied()==0 and s.number(active,1)==0 and state(2)==0,'Defaults was not staged')
    click(552,176)
    require(staged()==0 and state(4)==1 and state(5)==0 and state(7)==0,'Cancel did not restore applied Off')
    pixels('cancel')
    old=actions();click(550,104)
    require(actions()==old,'Mouse label is interactive')
    move(456,104);edge(1);move(390,220);edge(0)
    require(actions()==old and state(2)==0,'Outside release committed Defaults')
    move(456,104);edge(1);key('ESC');edge(0)
    require(actions()==old and state(2)==0,'Escape committed Defaults')
    key('TAB');require(s.number(panel+392,2)==4,'Tab failed to skip the label')
    key('TAB');key('SPACE')
    require(staged()==1 and applied()==0,'Keyboard radio did not stage Mild')
    key('TAB',True);require(s.number(panel+392,2)==4,'Shift-Tab focus')
    # Apply by keyboard during a held content press. The response acknowledges
    # the preference, while this physical gesture retains its original gain.
    move(456,104);edge(1);key('RETURN')
    require(applied()==1 and s.number(chosen,1)==1 and s.number(active,1)==0,'Held profile did not defer')
    step(2);edge(0)
    require(s.number(active,1)==1,'Profile did not activate after release')
    step(1);pixels('keyboard-mild')
    for i in range(6):
        click(456 if i%2==0 else 552,136);key('RETURN')
        expected=i%2
        require(applied()==expected and s.number(active,1)==expected and state(6)==0,'Repeated apply')
    pixels('repeated-apply')
    # Deliberately retain a nondefault preference across image retirement.
    click(456,136);key('RETURN')
    click(96,32);s.command('CAT STORY.TXT')
    click(592,56);pixels('shell-scroll-exposure')
    require(s.number(counter+14,4)>count,'Counter stopped while changing settings')
    s.saved['panel_settings']=dict(staging=True,cancel=True,defaults=True,
        keyboard=True,outside_release=True,escape=True,held_profile_deferral=True,
        physical_off_step=2,physical_mild_step=1,repeated_applies=6,
        independent_pixels=6,shell_output=True,counter_progress=True,reopen_profile=0)
    print('Panel settings, physical gain and redraw checks passed',flush=True)
