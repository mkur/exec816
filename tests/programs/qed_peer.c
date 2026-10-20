/* An ordinary independently loaded GEM client for QED exposure checks. */
#include <gem.h>
#include <exec816/aes.h>

static WORD handle,window;
static WORD paint(void)
{
    WORD x,y,w,h,box[4];
    if(!wind_update(BEG_UPDATE))return 0;
    if(!wind_get(window,WF_WORKXYWH,&x,&y,&w,&h)){
        wind_update(END_UPDATE);return 0;
    }
    box[0]=x;box[1]=y;box[2]=x+w-1;box[3]=y+h-1;
    vs_clip(handle,0,box);vsf_color(handle,3);v_bar(handle,box);
    vswr_mode(handle,MD_TRANS);vst_color(handle,1);
    v_gtext(handle,x+8,y+14,"Peer");vswr_mode(handle,MD_REPLACE);
    return wind_update(END_UPDATE);
}

int main(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57],message[8];
    if(appl_init()<0)return 101;
    handle=1;v_opnvwk(input,&handle,output);
    if(handle!=2)return 102;
    window=wind_create(NAME|CLOSER|MOVER,0,60,224,112);
    if(window<=0)return 103;
    if(!wind_set_str(window,WF_NAME,"QED peer"))return 104;
    if(!wind_open(window,0,60,224,112))return 105;
    for(;;){
        if(!evnt_mesag(message))return 106;
        if(message[0]==WM_CLOSED)break;
        if(message[0]==WM_TOPPED && !wind_set(window,WF_TOP,0,0,0,0))return 110;
        if(message[0]==WM_REDRAW && !paint())return 107;
    }
    if(!wind_close(window) || !wind_delete(window))return 108;
    v_clsvwk(handle);
    return appl_exit()?0:109;
}
