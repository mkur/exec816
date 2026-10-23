/* Ordinary independent client: repaint progress and public GEM policy messages. */
#include <gem.h>
#include <exec816/aes.h>

volatile UWORD QedPeerPaints,QedPeerCommand,QedPeerCalls;
volatile WORD QedPeerDestination,QedPeerHandle,QedPeerBounds[4];
static WORD handle,window;
static WORD paint(void)
{
    WORD x,y,w,h,box[4];
    if(!ExecAESBeginUpdate(window))return 0;
    if(!wind_get(window,WF_WORKXYWH,&x,&y,&w,&h)){
        wind_update(END_UPDATE);return 0;
    }
    box[0]=x;box[1]=y;box[2]=x+w-1;box[3]=y+h-1;
    vs_clip(handle,0,box);vsf_color(handle,3);v_bar(handle,box);
    vswr_mode(handle,MD_TRANS);vst_color(handle,1);
    v_gtext(handle,x+8,y+14,"Peer");vswr_mode(handle,MD_REPLACE);
    if(!ExecAESPainted(window,x,y,w,h) || !wind_update(END_UPDATE))return 0;
    ++QedPeerPaints;return 1;
}
int main(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57],message[8];
    WORD mx,my,buttons,qualifiers,key,clicks,events,command,i;
    if(appl_init()<0)return 101;
    handle=1;v_opnvwk(input,&handle,output);
    if(handle!=2)return 102;
    window=wind_create(NAME|CLOSER|MOVER,0,60,224,112);
    if(window<=0 || !wind_set_str(window,WF_NAME,"QED peer") ||
       !wind_open(window,0,60,224,112))return 103;
    for(;;){
        events=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,
            0,0,0,0,0,0,0,0,0,0,message,100,0,
            &mx,&my,&buttons,&qualifiers,&key,&clicks);
        if(!events)return 104;
        if(events&MU_MESAG){
            if(message[0]==WM_CLOSED)break;
            if(message[0]==WM_TOPPED && !wind_set(window,WF_TOP,0,0,0,0))return 105;
        }
        if(!paint())return 106;
        command=QedPeerCommand;
        if(command){
            QedPeerCommand=0;
            if(command==2){if(!wind_set(window,WF_TOP,0,0,0,0))return 107;}
            else{
                message[0]=command==1?WM_MOVED:(command==4?WM_SIZED:WM_CLOSED);
                message[1]=appl_init();message[2]=0;message[3]=QedPeerHandle;
                for(i=0;i<4;i++)message[4+i]=QedPeerBounds[i];
                if(!appl_write(QedPeerDestination,16,message))return 108;
            }
            ++QedPeerCalls;
        }
    }
    if(!wind_close(window) || !wind_delete(window))return 109;
    v_clsvwk(handle);return appl_exit()?0:110;
}
