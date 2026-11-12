/* SPDX-License-Identifier: MIT
 * Conventional GEM entry points backed by the independent TOS/libc SDK.
 * This is the subset needed by the shared sample, not a general GEM SDK. */
#include <gem.h>
#include <tos/aes.h>
#include <tos/vdi.h>
#include <tos/xgemdos.h>
#include <string.h>

_Static_assert(sizeof(WORD)==2 && sizeof(LONG)==4, "GEM scalar ABI");
_Static_assert(sizeof(OBJECT)==24, "GEM object ABI");
_Static_assert(__builtin_offsetof(OBJECT,ob_spec)==12, "GEM object pointer offset");
_Static_assert(sizeof(VDIPB)==sizeof(struct vdi_pb), "SDK VDI parameter block");

static struct aes context;
WORD appl_init(void) { return aes_appl_init(&context); }
WORD appl_exit(void) { return aes_appl_exit(&context); }
WORD graf_handle(WORD *a,WORD *b,WORD *c,WORD *d) {return aes_graf_handle__(&context,a,b,c,d);}
WORD wind_create(WORD k,WORD x,WORD y,WORD w,WORD h) {return aes_wind_create__(&context,k,x,y,w,h);}
WORD wind_open(WORD k,WORD x,WORD y,WORD w,WORD h) {return aes_wind_open__(&context,k,x,y,w,h);}
WORD wind_close(WORD h) {return aes_wind_close(&context,h);}
WORD wind_delete(WORD h) {return aes_wind_delete(&context,h);}
WORD wind_get(WORD h,WORD f,WORD *a,WORD *b,WORD *c,WORD *d) {return aes_wind_get(&context,h,f,a,b,c,d);}
WORD wind_set(WORD h,WORD f,WORD a,WORD b,WORD c,WORD d) {return aes_wind_set(&context,h,f,a,b,c,d);}
WORD wind_set_str(WORD h,WORD f,const char *s)
{
    uintptr_t p=(uintptr_t)s;
    return wind_set(h,f,(UWORD)(p>>16),(UWORD)p,0,0);
}
WORD wind_update(WORD c) {return aes_wind_update(&context,c);}
WORD evnt_multi(WORD f,WORD bc,WORD bm,WORD bs,WORD f1,WORD x1,WORD y1,WORD w1,WORD h1,
 WORD f2,WORD x2,WORD y2,WORD w2,WORD h2,WORD *msg,WORD lo,WORD hi,
 WORD *mx,WORD *my,WORD *mb,WORD *ks,WORD *kr,WORD *br)
{
    return aes_evnt_multi(&context,f,bc,bm,bs,f1,x1,y1,w1,h1,f2,x2,y2,w2,h2,
        msg,lo,hi,mx,my,mb,ks,kr,br);
}
WORD objc_draw(OBJECT *t,WORD s,WORD d,WORD x,WORD y,WORD w,WORD h)
{return aes_objc_draw(&context,(struct aes_object *)t,s,d,x,y,w,h);}
WORD wind_calc(WORD type,WORD kind,WORD x,WORD y,WORD w,WORD h,
 WORD *ox,WORD *oy,WORD *ow,WORD *oh)
{return aes_wind_calc(&context,type,kind,x,y,w,h,ox,oy,ow,oh);}
WORD menu_bar(OBJECT *t,WORD on)
{return aes_menu_bar(&context,(struct aes_object *)t,on);}
WORD menu_ienable(OBJECT *t,WORD item,WORD on)
{return aes_menu_ienable(&context,(struct aes_object *)t,item,on);}
WORD menu_tnormal(OBJECT *t,WORD item,WORD on)
{return aes_menu_tnormal(&context,(struct aes_object *)t,item,on);}
void reference_mouse(WORD mode) {aes_graf_mouse(&context,mode,NULL);}
WORD fsel_exinput(char *path,char *file,WORD *button,const char *title)
{
    struct aes_control control={91,0,2,3,0};
    const void *addresses[]={path,file,title};
    struct aes_pb p=context.pb;
    p.control=&control;
    p.addr_in=(const struct aes_addr_in *)addresses;
    xgemdos_aes(&p);
    *button=context.int_out.n[1];
    return context.int_out.n[0];
}

static WORD ctl[12],in[256],pts[16],out[256],pout[16];
static VDIPB pb={ctl,in,pts,out,pout};
void vdi_call(VDIPB *p) {xgemdos_vdi((struct vdi_pb *)p);}
static void vdi(WORD handle,WORD op,WORD points,WORD words,WORD sub)
{
    ctl[0]=op;ctl[1]=points;ctl[2]=0;ctl[3]=words;
    ctl[4]=0;ctl[5]=sub;ctl[6]=handle;
    vdi_call(&pb);
}

WORD reference_font[4];
void v_opnvwk(WORD *wi,WORD *h,WORD *wo)
{
    WORD height;
    memcpy(in,wi,11*sizeof(WORD));
    vdi(*h,100,0,11,0);
    *h=ctl[6];
    memcpy(wo,out,45*sizeof(WORD));
    memcpy(wo+45,pout,12*sizeof(WORD));
    /* Counter expects an 8x8 cell. VDI requested height is not cell height. */
    for (height=1;height<=16;++height) {
        pts[0]=0;pts[1]=height;
        vdi(*h,12,1,0,0);
        if (pout[2]==8 && pout[3]==8) break;
    }
    memcpy(reference_font,pout,4*sizeof(WORD));
}
void v_clsvwk(WORD h) {vdi(h,101,0,0,0);}
void vs_clip(WORD h,WORD on,const WORD *p) {in[0]=on;memcpy(pts,p,8);vdi(h,129,2,1,0);}
void v_bar(WORD h,const WORD *p) {memcpy(pts,p,8);vdi(h,11,2,0,1);}
void v_gtext(WORD h,WORD x,WORD y,const char *s)
{
    WORD n=0;
    pts[0]=x;pts[1]=y;
    while (n<256 && s[n]) {in[n]=(unsigned char)s[n];++n;}
    vdi(h,8,1,n,0);
}
WORD vsf_color(WORD h,WORD c) {in[0]=c;vdi(h,25,0,1,0);return out[0];}
WORD vst_color(WORD h,WORD c) {in[0]=c;vdi(h,22,0,1,0);return out[0];}
WORD vswr_mode(WORD h,WORD c) {in[0]=c;vdi(h,32,0,1,0);return out[0];}
WORD vsf_interior(WORD h,WORD c) {in[0]=c;vdi(h,23,0,1,0);return out[0];}
