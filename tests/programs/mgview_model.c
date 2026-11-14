/* SPDX-License-Identifier: GPL-3.0-only
 * Exercise the actual imported static parser, not a replacement loader model. */
#include "mgwind.c"

UWORD MGViewChecks;
#define CHECK(value) do { ++MGViewChecks; if(!(value))return __LINE__; } while(0)
static WORD callback_seen;
static void probe_draw(WINDOW *window,GRECT *rectangle)
{
    callback_seen=window->handle+rectangle->g_w;
}

LONG EXEC_CALL MGViewProbe(void)
{
    unsigned char data[]="a\r\nb\nc\rd\r";
    unsigned char tabs[]={'a','\t',0,'b'};
    unsigned char output[9];
    unsigned char *lines[4];
    long count,width,length;
    WORD tab;
    WINDOW window={0};
    GRECT a={1,2,10,12},b={5,6,10,12};
    CHECK(memchr2(data,0)==NULL);
    CHECK(memchr2(data,sizeof(data)-1)==data+1);
    get_line_column_count(data,sizeof(data)-1,&count,&width,8);
    CHECK(count==4 && width==1);
    init_line_ptrs(data,sizeof(data)-1,lines);
    CHECK(lines[0]==data && lines[1]==data+3 && lines[2]==data+5 && lines[3]==data+7);
    window.user_file=data;window.user_fsize=sizeof(data)-1;
    window.user_lines=lines;window.vscroll.n=count;
    CHECK(get_line(&window,3,&length)==data+7 && length==1);
    CHECK(get_line(&window,4,&length)==NULL && length==0);
    get_line_column_count(data,0,&count,&width,8);
    CHECK(count==0 && width==0);
    for(tab=0;tab<=9;++tab){
        length=expand_line(tabs,4,tab,output,8);
        CHECK(length<=8 && output[0]=='a');
        CHECK(expand_line(tabs,4,tab,NULL,1)>=length);
    }
    CHECK(expand_line(tabs,4,8,output,2)==2 && output[1]==' ');
    window.draw=probe_draw;window.handle=7;window.draw(&window,&a);
    CHECK(callback_seen==17);
    CHECK(rc_intersect(&a,&b) && b.g_x==5 && b.g_y==6 && b.g_w==6 && b.g_h==8);
    return 0;
}
int main(void){return 0;}
