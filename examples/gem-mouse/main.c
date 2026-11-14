/* SPDX-License-Identifier: MIT */
#include <gem.h>
#include <exec816/aes.h>

/* Observed by the development harness; the application uses ordinary GEM. */
struct MouseProbe {
    volatile UWORD ready,done,checks,failures;
    volatile ULONG rounds;
    volatile UWORD painting;
    WORD id;
    WORD work[4];
    WORD input[11],output[57],message[8];
} GEMMouse;
static MFORM custom={7,7,1,0,2,
    {0xffff,0xffff,0xffff,0xffff,0xffff,0xffff,0xffff,0xffff,
     0xffff,0xffff,0xffff,0xffff,0xffff,0xffff,0xffff,0xffff},
    {0x8001,0x4002,0x2004,0x1008,0x0810,0x0420,0x0240,0x0180,
     0x0180,0x0240,0x0420,0x0810,0x1008,0x2004,0x4002,0x8001}};

static WORD check(WORD okay)
{
    ++GEMMouse.checks;
    if (!okay) ++GEMMouse.failures;
    return okay;
}

/* One UPDATE covers visible enumeration, copy and exposed-strip repair.
 * The source and destination both stay inside each visible fragment. */
static WORD scroll(WORD window,WORD vdi)
{
    WORD x,y,w,h,l,t,r,b,clip[4]={0},pxy[8],okay;
    MFDB screen={0};
    if (!check(wind_update(BEG_UPDATE))) return 0;
    if (!check(wind_update(BEG_MCTRL))) { wind_update(END_UPDATE); return 0; }
    okay=check(graf_mouse((WORD)(M_FORCE|(GEMMouse.rounds&7)),NULL));
    okay=check(graf_mouse(M_SAVE,NULL)) && okay;
    okay=check(graf_mouse(M_OFF,NULL)) && okay;
    GEMMouse.painting=2;
    v_hide_c(vdi);v_show_c(vdi,1);
    okay=check(wind_get(window,WF_WORKXYWH,&GEMMouse.work[0],&GEMMouse.work[1],
        &GEMMouse.work[2],&GEMMouse.work[3])) && okay;
    okay=check(wind_get(window,WF_FIRSTXYWH,&x,&y,&w,&h)) && okay;
    while (okay && w && h) {
        l=x>GEMMouse.work[0] ? x:GEMMouse.work[0];
        t=y>GEMMouse.work[1] ? y:GEMMouse.work[1];
        r=x+w;b=y+h;
        if (r>GEMMouse.work[0]+GEMMouse.work[2]) r=GEMMouse.work[0]+GEMMouse.work[2];
        if (b>GEMMouse.work[1]+GEMMouse.work[3]) b=GEMMouse.work[1]+GEMMouse.work[3];
        if (l<r && t<b) {
            clip[0]=l;clip[1]=t;clip[2]=r-1;clip[3]=b-1;
            vs_clip(vdi,1,clip);vsf_color(vdi,4);v_bar(vdi,clip);
            if (b-t>8) {
                clip[3]=t+7;vsf_color(vdi,3);v_bar(vdi,clip);
                pxy[0]=l;pxy[1]=t;pxy[2]=r-1;pxy[3]=b-9;
                pxy[4]=l;pxy[5]=t+8;pxy[6]=r-1;pxy[7]=b-1;
                vro_cpyfm(vdi,S_ONLY,pxy,&screen,&screen);
                vsf_color(vdi,(WORD)((GEMMouse.rounds+2)&15));v_bar(vdi,clip);
            }
        }
        okay=check(wind_get(window,WF_NEXTXYWH,&x,&y,&w,&h)) && okay;
    }
    vs_clip(vdi,0,clip);
    okay=check(ExecAESDiagnostic()==AES_OK) && okay;
    okay=check(graf_mouse(M_ON,NULL)) && okay;
    GEMMouse.painting=0;
    okay=check(graf_mouse(M_PREVIOUS,NULL)) && okay;
    okay=check(graf_mouse(M_RESTORE,NULL)) && okay;
    if (GEMMouse.rounds==7) {
        okay=check(graf_mouse(USER_DEF,&custom)) && okay;
        vsc_form(vdi,(const WORD *)&custom);
        okay=check(ExecAESDiagnostic()==AES_OK) && okay;
        okay=check(graf_mouse(M_RESTORE,NULL)) && okay;
    }
    okay=check(wind_update(END_MCTRL)) && okay;
    okay=check(wind_update(END_UPDATE)) && okay;
    return okay;
}

int main(void)
{
    WORD window=-1,vdi=0,opened=0,i,a,b,c,d,mx,my,mb,ks,key,clicks,events,quit=0;
    WORD x,y,buttons,qualifiers;
    GEMMouse.id=appl_init();
    if (!check(GEMMouse.id>0)) return 1;
    if (!check(graf_mouse(M_OFF,NULL)) || !check(graf_mouse(M_ON,NULL))) goto finish;
    vdi=graf_handle(&a,&b,&c,&d);
    for (i=0;i<10;++i) GEMMouse.input[i]=1;
    GEMMouse.input[10]=2;v_opnvwk(GEMMouse.input,&vdi,GEMMouse.output);
    if (!check(vdi>0)) goto finish;
    window=wind_create(NAME|CLOSER|MOVER,480,32,144,96);
    if (!check(window>0)) goto finish;
    if (!check(wind_set_str(window,WF_NAME,"Mouse forms"))) goto finish;
    if (!check(wind_open(window,480,32,144,96))) goto finish;
    opened=1;GEMMouse.ready=1;
    check(graf_mkstate(&x,&y,&buttons,&qualifiers));
    vq_mouse(vdi,&buttons,&a,&b);check(a>=0 && a<640 && b>=0 && b<240);
    while (!quit && GEMMouse.rounds<16) {
        events=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,
            0,0,0,0,0,0,0,0,0,0,GEMMouse.message,250,0,&mx,&my,&mb,&ks,&key,&clicks);
        if (!check(events!=0)) break;
        if (events&MU_MESAG) {
            if (GEMMouse.message[0]==WM_CLOSED) quit=1;
            else if (GEMMouse.message[0]==WM_TOPPED)
                check(wind_set(window,WF_TOP,0,0,0,0));
            else if (GEMMouse.message[0]==WM_MOVED)
                check(wind_set(window,WF_CURRXYWH,GEMMouse.message[4],GEMMouse.message[5],
                    GEMMouse.message[6],GEMMouse.message[7]));
        }
        if (!quit && ((events&MU_TIMER) ||
            ((events&MU_MESAG) && GEMMouse.message[0]==WM_REDRAW))) {
            if (!scroll(window,vdi)) break;
            if (events&MU_TIMER) ++GEMMouse.rounds;
        }
    }
finish:
    GEMMouse.ready=0;
    if (opened) check(wind_close(window));
    if (window>0) check(wind_delete(window));
    if (vdi) v_clsvwk(vdi);
    check(appl_exit());GEMMouse.done=1;
    return GEMMouse.failures ? 1:0;
}
