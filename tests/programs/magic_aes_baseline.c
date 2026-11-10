/* Development workload. Production Counter drawing is included unchanged. */
#include "../../examples/gem-counter/counter.c"
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <proto/exec.h>

#define SAMPLES 8
#define WARMUPS 2
#define COVERS 3
#define OBJECTS 33

ULONG MagicService;
volatile UWORD MagicPhase,MagicGo,MagicChecks,MagicFailures,MagicFirstFailure;
volatile UWORD MagicObjectsCount,MagicExposureCount,MagicVisibleCount;
WORD MagicMoveBounds[4]={32,24,480,184};
WORD MagicExposureRects[8][4];
OBJECT MagicObjects[OBJECTS];
struct Counter MagicCounter;
static const struct CounterConfig config={"MagiC baseline",32,24,480,184,4,3};
static WORD covers[COVERS],coverWork[COVERS][4],message[8];
static WORD kindNow;

static WORD checked(WORD okay,WORD line)
{
    ++MagicChecks;
    if (!okay) {
        ++MagicFailures;
        if (!MagicFirstFailure) MagicFirstFailure=line;
    }
    return okay;
}
#define REQUIRE(x) do { if (!checked((x)!=0,__LINE__)) return 0; } while (0)

static void checkpoint(UWORD phase)
{
    MagicPhase=phase;
    while (MagicGo!=phase) ExecYield();
}

static WORD work(void)
{
    return wind_get(MagicCounter.window,WF_WORKXYWH,&MagicCounter.work[0],
        &MagicCounter.work[1],&MagicCounter.work[2],&MagicCounter.work[3]);
}

static WORD paint_cover(WORD index)
{
    WORD p[4]={0,0,0,0},x,y,w,h;
    REQUIRE(wind_update(BEG_UPDATE));
    REQUIRE(wind_get(covers[index],WF_WORKXYWH,&coverWork[index][0],
        &coverWork[index][1],&coverWork[index][2],&coverWork[index][3]));
    REQUIRE(wind_get(covers[index],WF_FIRSTXYWH,&x,&y,&w,&h));
    while (w>0 && h>0) {
        p[0]=x;p[1]=y;p[2]=x+w-1;p[3]=y+h-1;
        vs_clip(MagicCounter.vdi,1,p);
        vsf_color(MagicCounter.vdi,7);
        v_bar(MagicCounter.vdi,p);
        REQUIRE(wind_get(covers[index],WF_NEXTXYWH,&x,&y,&w,&h));
    }
    vs_clip(MagicCounter.vdi,0,p);
    REQUIRE(wind_update(END_UPDATE));
    return 1;
}

static WORD draw_objects(void)
{
    WORD x,y,w,h,p[4]={0,0,0,0};
    REQUIRE(wind_update(BEG_UPDATE));
    REQUIRE(work());
    REQUIRE(wind_get(MagicCounter.window,WF_FIRSTXYWH,&x,&y,&w,&h));
    MagicVisibleCount=0;
    while (w>0 && h>0) {
        ++MagicVisibleCount;
        p[0]=x;p[1]=y;p[2]=x+w-1;p[3]=y+h-1;
        vs_clip(MagicCounter.vdi,1,p);
        REQUIRE(objc_draw(MagicObjects,0,MAX_DEPTH,x,y,w,h));
        REQUIRE(wind_get(MagicCounter.window,WF_NEXTXYWH,&x,&y,&w,&h));
    }
    vs_clip(MagicCounter.vdi,0,p);
    REQUIRE(wind_update(END_UPDATE));
    return 1;
}

static WORD drain_messages(void)
{
    WORD events,mx,my,mb,ks,kr,br,i,n=0;
    do {
        events=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,
            message,0,0,&mx,&my,&mb,&ks,&kr,&br);
        REQUIRE(events);
        if (events & MU_MESAG) {
            REQUIRE(++n<64);
            if (message[0]==WM_REDRAW) {
                if (message[3]==MagicCounter.window) {
                    if (kindNow==6 && MagicExposureCount<8) {
                        for (i=0;i<4;++i)
                            MagicExposureRects[MagicExposureCount][i]=message[4+i];
                        ++MagicExposureCount;
                    }
                    REQUIRE(redraw(&MagicCounter,&message[4]));
                } else {
                    for (i=0;i<COVERS;++i)
                        if (message[3]==covers[i]) REQUIRE(paint_cover(i));
                }
            }
        }
    } while (events & MU_MESAG);
    return 1;
}

/* This public fixture boundary is observed at emitted entry/caller return.
 * Setup and host checkpoints are outside the samples; helper checks remain. */
WORD MagicBaselineProbe(WORD kind)
{
    WORD mx,my,mb,ks,kr,br;
    kindNow=kind;
    if (kind<3) return draw_objects();
    if (kind==3 || kind==4) {
        REQUIRE(work());
        return redraw(&MagicCounter,MagicCounter.work);
    }
    if (kind==5) {
        ++MagicCounter.count;
        return redraw(&MagicCounter,NULL);
    }
    if (kind==6) return drain_messages();
    if (kind==7) {
        REQUIRE(wind_set(MagicCounter.window,WF_CURRXYWH,MagicMoveBounds[0],
            MagicMoveBounds[1],MagicMoveBounds[2],MagicMoveBounds[3]));
        REQUIRE(work());
        return redraw(&MagicCounter,MagicCounter.work);
    }
    return evnt_multi(MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,
        message,0,0,&mx,&my,&mb,&ks,&kr,&br)==MU_TIMER;
}

static void object_tree(WORD kind)
{
    WORD i,count=kind==0 ? 5:kind==1 ? 33:9;
    for (i=0;i<OBJECTS;++i) {
        MagicObjects[i].ob_next=NIL;
        MagicObjects[i].ob_head=NIL;
        MagicObjects[i].ob_tail=NIL;
        MagicObjects[i].ob_type=G_BOX;
        MagicObjects[i].ob_flags=0;
        MagicObjects[i].ob_state=0;
        MagicObjects[i].ob_spec=0x1173UL;
        MagicObjects[i].ob_x=0;MagicObjects[i].ob_y=0;
        MagicObjects[i].ob_width=24;MagicObjects[i].ob_height=12;
    }
    MagicObjectsCount=count;
    MagicObjects[0].ob_x=MagicCounter.work[0]+8;
    MagicObjects[0].ob_y=MagicCounter.work[1]+8;
    MagicObjects[0].ob_width=320;MagicObjects[0].ob_height=128;
    MagicObjects[0].ob_head=1;MagicObjects[0].ob_tail=count-1;
    for (i=1;i<count;++i) {
        MagicObjects[i].ob_spec=0x1170UL+(ULONG)(i%6);
        MagicObjects[i].ob_next=i+1==count ? 0:i+1;
        MagicObjects[i].ob_x=8+((i-1)%8)*38;
        MagicObjects[i].ob_y=8+((i-1)/8)*28;
        if (kind==2) {
            MagicObjects[i-1].ob_head=i;MagicObjects[i-1].ob_tail=i;
            MagicObjects[i].ob_next=i-1;
            MagicObjects[i].ob_x=3;MagicObjects[i].ob_y=3;
            MagicObjects[i].ob_width=320-i*8;
            MagicObjects[i].ob_height=128-i*8;
        }
    }
    MagicObjects[count-1].ob_flags=LASTOB;
}

static WORD open_covers(void)
{
    WORD i,x;
    for (i=0;i<COVERS;++i) {
        x=MagicCounter.work[0]+(i==0 ? 32:i==1 ? 80:352);
        REQUIRE(wind_open(covers[i],x,MagicCounter.work[1]+8,32,48));
        REQUIRE(paint_cover(i));
    }
    kindNow=4;
    REQUIRE(drain_messages());
    return 1;
}

static WORD samples(WORD kind)
{
    WORD i;
    for (i=0;i<WARMUPS+SAMPLES;++i) {
        /* Like WM_MOVED, provide requested geometry to the application.
         * Alternate two explicit, even-X placements outside the timed call. */
        if (kind==7) MagicMoveBounds[0]^=16;
        REQUIRE(MagicBaselineProbe(kind));
    }
    checkpoint(kind+1);
    return 1;
}

WORD MagicRun(void)
{
    ULONG available=AvailMem(0);
    WORD i,j,handle=1,input[11],output[57];
    REQUIRE(ExecAESAttach((struct MsgPort *)MagicService));
    MagicCounter.config=&config;
    MagicCounter.id=appl_init();REQUIRE(MagicCounter.id>0);
    for (i=0;i<11;++i) input[i]=1;
    input[6]=4;input[9]=3;input[10]=2;
    v_opnvwk(input,&handle,output);REQUIRE(handle>0);MagicCounter.vdi=handle;
    MagicCounter.window=wind_create(NAME|CLOSER|MOVER,32,24,480,184);
    REQUIRE(MagicCounter.window>0);
    REQUIRE(wind_set_str(MagicCounter.window,WF_NAME,config.title));
    REQUIRE(wind_open(MagicCounter.window,32,24,480,184));
    REQUIRE(work());MagicCounter.count=123456UL;
    REQUIRE(redraw(&MagicCounter,MagicCounter.work));
    REQUIRE(drain_messages());
    for (i=0;i<3;++i) {
        object_tree(i);
        REQUIRE(samples(i));
    }
    REQUIRE(samples(3));
    for (i=0;i<COVERS;++i) {
        covers[i]=wind_create(NAME|CLOSER|MOVER,0,0,32,48);
        REQUIRE(covers[i]>0);
        REQUIRE(wind_set_str(covers[i],WF_NAME,"Occluder"));
    }
    REQUIRE(open_covers());
    REQUIRE(samples(4));
    REQUIRE(samples(5));
    for (j=0;j<3;++j) {
        if (j) REQUIRE(open_covers());
        for (i=0;i<COVERS;++i) REQUIRE(wind_close(covers[i]));
        /* Let the presenter publish exposure while this owner is delayed.
         * Host settlement is outside the measured message/repair operation. */
        checkpoint(70+j);
        kindNow=6;MagicExposureCount=0;
        REQUIRE(MagicBaselineProbe(6));
        checkpoint(80+j);
    }
    REQUIRE(samples(7));
    REQUIRE(samples(8));
    for (i=0;i<COVERS;++i) REQUIRE(wind_delete(covers[i]));
    v_clsvwk(handle);
    REQUIRE(wind_close(MagicCounter.window));
    REQUIRE(wind_delete(MagicCounter.window));
    REQUIRE(ExecAESDetach());
    REQUIRE(AvailMem(0)==available);
    return 1;
}
