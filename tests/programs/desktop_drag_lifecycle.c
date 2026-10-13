/* Host isolation of the actual desktop gesture code, with API outcomes supplied
 * by the fixture. Physical input, ABI and disk bytes have separate target tests. */
#include <assert.h>
#include <string.h>
#include "../../examples/gem-browser/desktop.h"
#include <exec816/aes.h>
static struct Desktop d;
static struct Browser a,b;
static struct FileEntry entries[2];
static OBJECT tree[24];
static WORD held,visual,writes,admitted,accept,hit,found,words[8];
static char destination[128];
static struct Browser *desktop_folder(struct Desktop *desk,WORD handle)
{ WORD i;for(i=0;i<DESKTOP_FOLDERS;++i) if(desk->folders[i] && desk->folders[i]->window==handle) return desk->folders[i];return 0; }
static void selection_status(struct Browser *folder) { strcpy(folder->status,"selection"); }
static WORD redraw(struct Browser *folder,const WORD *area) { (void)area;++folder->paints;return 1; }
static WORD selected_entry(const struct Browser *folder,UWORD entry) { return !!(folder->selection[entry>>3]&(1U<<(entry&7))); }
static WORD select_entry(struct Browser *folder,WORD entry,WORD mode)
{ (void)mode;memset(folder->selection,0,32);folder->selection[entry>>3]=1U<<(entry&7);folder->selectionCount=1;return 1; }
static void label(char *to,const char *from,WORD max) { strncpy(to,from,max);to[max]=0; }
static WORD job_same_directory(const char *x,const char *y) { return !strcmp(x,y); }
static WORD desktop_copy_admit(struct Browser *folder,const char *path,WORD directory)
{ assert(folder==&a && directory && !held && !visual);++admitted;strcpy(destination,path);return 1; }
WORD wind_get(WORD h,WORD f,WORD *x,WORD *y,WORD *w,WORD *height)
{ struct Browser *folder=desktop_folder(&d,h);(void)f;assert(folder);*x=folder->work[0];*y=folder->work[1];*w=folder->work[2];*height=folder->work[3];return 1; }
WORD wind_find(WORD x,WORD y) { (void)x;(void)y;return found; }
WORD wind_update(WORD code) { if(code==BEG_MCTRL) ++held;else if(code==END_MCTRL) --held;assert(held>=0);return 1; }
WORD ExecAESDragOutline(WORD h,WORD x,WORD y,WORD w,WORD height)
{ (void)x;(void)y;(void)w;(void)height;assert(held);visual=h!=0;return 1; }
UWORD ExecAESDiagnostic(void) { return AES_OK; }
WORD ExecAESInputWindow(WORD event) { (void)event;return 1; }
WORD objc_find(OBJECT *objects,WORD start,WORD depth,WORD x,WORD y)
{ (void)objects;(void)start;(void)depth;(void)x;(void)y;return hit; }
WORD appl_write(WORD id,WORD size,const WORD *message)
{ assert(id==d.id && size==16 && !held && !visual);++writes;memcpy(words,message,16);return accept; }
WORD FileJoin(char *out,WORD bytes,const char *path,const char *name)
{ if(strlen(path)+strlen(name)+2>(UWORD)bytes)return 0;strcpy(out,path);strcat(out,"/");strcat(out,name);return 1; }
#include "../../examples/gem-browser/desktop-drag.inc"
static void reset(void)
{
 memset(&d,0,sizeof(d));memset(&a,0,sizeof(a));memset(&b,0,sizeof(b));
 held=visual=writes=admitted=0;accept=1;hit=0;found=2;
 a.window=1;b.window=2;a.ready=b.ready=1;d.id=7;
 d.folders[0]=&a;d.folders[1]=&b;a.desktop=b.desktop=&d;
 a.work[2]=b.work[2]=200;a.work[3]=b.work[3]=160;
 a.entries=b.entries=entries;a.tree=b.tree=tree;a.count=b.count=1;a.visible=b.visible=1;
 strcpy(a.path,"SYS:");strcpy(b.path,"WORK:");entries[0].kind=0;strcpy(entries[0].name,"FILE.TXT");
 tree[BROWSER_ROW_FIRST].ob_width=80;tree[BROWSER_ROW_FIRST].ob_height=12;
 a.selection[0]=1;a.selectionCount=1;d.mx=50;d.my=80;
 d.drag.source=1;d.drag.target=2;strcpy(d.drag.destination,"WORK:");
}
static void tracking(void) { d.drag.phase=DRAG_TRACKING;d.drag.held=held=visual=1; }
int main(void)
{
 reset();tracking();assert(drag_post(&d));assert(d.drag.phase==DRAG_QUEUED && writes==1 && !admitted);
 assert(words[0]==DESKTOP_DROP && words[1]==7 && words[3]==2 && words[4]==1 && words[5]==50 && words[6]==80);
 assert(!desktop_drag_input(&d,MU_BUTTON));assert(desktop_drag_deliver(&d));
 assert(admitted==1 && !strcmp(destination,"WORK:") && !d.drag.phase);
 assert(desktop_drag_deliver(&d) && admitted==1);
 reset();tracking();assert(drag_post(&d));assert(desktop_drag_cancel(&d,0));
 assert(d.drag.phase==DRAG_CANCELLED && !d.drag.source && !d.drag.target);
 d.folders[0]=0;assert(!desktop_drag_input(&d,MU_BUTTON));assert(desktop_drag_deliver(&d) && !admitted && !d.drag.phase);
 reset();tracking();accept=0;assert(drag_post(&d));assert(!d.drag.phase && !admitted && !held && strstr(d.status,"queue full"));
 reset();tracking();d.down=1;d.kr=27;assert(!desktop_drag_input(&d,MU_KEYBD));
 assert(d.drag.phase==DRAG_RELEASE && !held && !visual);d.down=0;
 assert(!desktop_drag_input(&d,MU_BUTTON) && !d.drag.phase);
 hit=BROWSER_ROW_FIRST;d.down=1;assert(desktop_drag_input(&d,MU_BUTTON)==MU_BUTTON && d.drag.phase==DRAG_ARMED);
 reset();d.drag.phase=DRAG_ARMED;d.drag.pressX=20;d.drag.pressY=80;
 assert(!desktop_drag_input(&d,MU_BUTTON) && d.drag.phase==DRAG_QUEUED && !held);
 assert(desktop_drag_deliver(&d) && admitted==1);
 reset();tracking();found=0;assert(drag_target(&d) && !d.drag.target);
 assert(drag_post(&d) && !writes && !admitted && !held);
 reset();tracking();strcpy(b.path,a.path);assert(drag_target(&d) && !d.drag.target);
 reset();tracking();hit=BROWSER_ROW_FIRST;assert(drag_target(&d) && !d.drag.target);
 reset();tracking();hit=BROWSER_ROW_FIRST;entries[0].kind=1;
 assert(drag_target(&d) && d.drag.target==2 && !strcmp(d.drag.destination,"WORK:/FILE.TXT"));
 reset();tracking();a.selectionDirectories=1;d.drag.entry=0;d.down=1;
 assert(drag_start(&d) && d.drag.phase==DRAG_RELEASE && !held && !visual);
 return 0;
}
