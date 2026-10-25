/* Emitted painter oracle: real editor code, independently reconstructed pixels. */
#include "../../examples/gem-basic/editor.h"
#include "../../examples/gem-basic/assist-ui.h"
#include "../../examples/gem-basic/assist.h"
#include <exec816/aes.h>
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#define WIDTH 160
#define HEIGHT 80
#define CHECK(x) do { if (!(x)) return __LINE__; ++BasicPaintChecks; } while (0)
volatile UWORD BasicPaintChecks;
volatile ULONG BasicPaintStats[80];
volatile UWORD BasicPaintSizes[]={sizeof(struct BasicRefresh),BASIC_REFRESH_BYTES,
                                sizeof(((struct BasicEditor *)0)->refresh)};
static struct BasicEditor e;
static UBYTE pixels[WIDTH*HEIGHT],expected[WIDTH*HEIGHT],visited[WIDTH*HEIGHT],lexical[256];
static UBYTE *target=pixels;
static WORD rectangles[12][4],count=1,index,clip[4],pen=1,fill,locked,diagnostic;
static WORD invalid,failDraw,failEnd,failVisible,recording=1,reportCount;
static ULONG clears,textCells,statusCells,updates,empty,painted,textCalls;
static WORD max(WORD a,WORD b) { return a>b ? a:b; }
static WORD min(WORD a,WORD b) { return a<b ? a:b; }
static WORD visible_pixel(WORD x,WORD y)
{
    UWORD i;
    for (i=0;i<count;++i) if (x>=rectangles[i][0] && x<rectangles[i][0]+rectangles[i][2] &&
        y>=rectangles[i][1] && y<rectangles[i][1]+rectangles[i][3]) return 1;
    return 0;
}
static void dot(WORD x,WORD y,UBYTE color)
{
    if (x<clip[0] || x>clip[2] || y<clip[1] || y>clip[3] || x<0 || x>=WIDTH || y<0 || y>=HEIGHT) return;
    if (recording && (!locked || !visible_pixel(x,y))) { invalid=1;return; }
    target[y*WIDTH+x]=color;if (recording) { visited[y*WIDTH+x]=1;++painted; }
}
static void glyph(WORD x,WORD y,UBYTE c,UBYTE color)
{
    WORD a,b;
    for (b=0;b<8;++b) for (a=0;a<8;++a)
        dot(x+a,y+b,c!=' ' && (b==1 || b==6 || a==1+(c+b)%6) ? color:0);
}
WORD wind_get(WORD window,WORD field,WORD *a,WORD *b,WORD *c,WORD *d)
{
    (void)window;
    if (failVisible) { failVisible=0;return 0; }
    if (field==WF_FIRSTXYWH) index=0;else if (field==WF_NEXTXYWH) ++index;else { invalid=1;return 0; }
    if (index<count) { *a=rectangles[index][0];*b=rectangles[index][1];*c=rectangles[index][2];*d=rectangles[index][3]; }
    else *a=*b=*c=*d=0;
    return 1;
}
WORD wind_set(WORD w,WORD f,WORD a,WORD b,WORD c,WORD d)
{ (void)w;(void)f;(void)a;(void)b;(void)c;(void)d;invalid=1;return 0; }
WORD form_center(OBJECT *tree,WORD *x,WORD *y,WORD *w,WORD *h)
{ (void)tree;(void)x;(void)y;(void)w;(void)h;invalid=1;return 0; }
WORD form_dial(WORD mode,WORD a,WORD b,WORD c,WORD d,WORD x,WORD y,WORD w,WORD h)
{ (void)mode;(void)a;(void)b;(void)c;(void)d;(void)x;(void)y;(void)w;(void)h;invalid=1;return 0; }
WORD form_do(OBJECT *tree,WORD start) { (void)tree;(void)start;invalid=1;return -1; }
WORD ExecAESBeginUpdate(WORD window)
{
    (void)window;if (locked) { invalid=1;return 0; }
    locked=1;diagnostic=0;painted=0;reportCount=0;memset(visited,0,sizeof(visited));++updates;return 1;
}
WORD wind_update(WORD code)
{
    if (code!=END_UPDATE || !locked) { invalid=1;return 0; }
    locked=0;if (!painted) ++empty;
    if (failEnd) { failEnd=0;return 0; }return 1;
}
UWORD ExecAESDiagnostic(void) { return diagnostic; }
WORD ExecAESPainted(WORD window,WORD x,WORD y,WORD width,WORD height)
{
    WORD a,b;(void)window;
    if (++reportCount>AES_PAINT_REPORTS) { invalid=1;return 0; }
    for (b=y;b<y+height;++b) for (a=x;a<x+width;++a)
        if (visible_pixel(a,b) && !visited[b*WIDTH+a]) { invalid=1;return 0; }
    return !diagnostic;
}
WORD ExecAESPaintedChanges(WORD window) { (void)window;return !diagnostic; }
void vs_clip(WORD vdi,WORD enabled,const WORD *p)
{ (void)vdi;(void)enabled;memcpy(clip,p,sizeof(clip)); }
WORD vst_color(WORD vdi,WORD value) { (void)vdi;pen=value;return value; }
WORD vsf_color(WORD vdi,WORD value) { (void)vdi;fill=value;return value; }
void v_bar(WORD vdi,const WORD *p)
{
    WORD x,y;(void)vdi;
    if (recording && p[2]-p[0]>=e.columns*8-1 && p[1]<e.app.work[1]+e.rows*8) ++clears;
    for (y=p[1];y<=p[3];++y) for (x=p[0];x<=p[2];++x) dot(x,y,fill);
}
void v_gtext(WORD vdi,WORD x,WORD y,const char *text)
{
    (void)vdi;
    if (recording) ++textCalls;
    if (failDraw) { failDraw=0;diagnostic=AES_DISPLAY_ERROR;return; }
    while (*text) {
        glyph(x,y-6,*text++,pen);
        if (recording && x<=clip[2] && x+7>=clip[0]) {
            ++textCells;if (y-6>=e.app.work[1]+e.rows*8) ++statusCells;
        }
        x+=8;
    }
}
static void full_visibility(void)
{ count=1;memcpy(rectangles[0],e.app.work,8); }
static WORD drain(void)
{
    UWORD turns=0;ULONG before;
    while (e.dirty && ++turns<200) {
        if (BasicAssistanceWork(&e)) BasicAssistanceStep(&e);
        before=e.refresh.state.glyphs;
        if (!BasicEditorPaint(&e) || e.refresh.state.glyphs-before>96) return 0;
    }
    return !e.dirty && !locked && !invalid;
}
static void reset_counts(void) { clears=textCells=statusCells=updates=empty=textCalls=0; }
/* Rebuild the complete viewport from source offsets, independent of the cache. */
static WORD picture(void)
{
    UWORD row,line,i;ULONG offset,column,next,lo=min(e.caret,e.anchor),hi=max(e.caret,e.anchor),at,a,z;
    WORD x=e.app.work[0]+4,y=e.app.work[1],px,py;UBYTE c;
    recording=0;target=expected;memset(expected,0,sizeof(expected));
    clip[0]=clip[1]=0;clip[2]=WIDTH-1;clip[3]=HEIGHT-1;
    for (row=0;row<e.rows;++row) {
        line=BasicAssistanceLine(&e,row);column=0;
        if (line<e.document.lines) {
            BasicLexLine(&e.document,line,lexical);offset=e.document.line[line];i=0;
            while (offset<e.document.bytes && (c=BasicByte(&e.document,offset++))!=10) {
                next=c==9 ? (column+8)&~7UL:column+1;
                while (column<next) { if (column>=e.left && column<e.left+e.columns)
                    glyph(x+(column-e.left)*8,y+row*8,c==9 ? ' ':c,lexical[i]);++column; }
                ++i;
            }
            if (lo<hi && lo<e.document.line[line+1] && hi>e.document.line[line]) {
                at=max(lo,e.document.line[line]);a=BasicColumn(&e.document,at);
                at=min(hi,e.document.line[line+1]);if (at>e.document.line[line] && BasicByte(&e.document,at-1)==10) --at;
                z=BasicColumn(&e.document,at)+(hi>at);
                for (column=a;column<z;++column) if (column>=e.left && column<e.left+e.columns)
                    for (i=0;i<8;++i) dot(x+(column-e.left)*8+i,y+row*8+7,3);
            }
            if (line==BasicLine(&e.document,e.caret)) {
                column=BasicColumn(&e.document,e.caret);
                if (column>=e.left && column<e.left+e.columns) for (i=0;i<8;++i) dot(x+(column-e.left)*8,y+row*8+i,1);
            }
        }
    }
    for (i=0;i<e.columns;++i) {
        c=i==0 ? (BasicDirty(&e.document) ? '*':' '):i>1 && i-2<strlen(e.status) ? e.status[i-2]:' ';
        glyph(x+i*8,y+e.rows*8+4,c,1);
    }
    recording=1;target=pixels;
    for (py=e.app.work[1];py<e.app.work[1]+e.app.work[3];++py)
        for (px=e.app.work[0];px<e.app.work[0]+e.app.work[2];++px)
            if (visible_pixel(px,py) && pixels[py*WIDTH+px]!=expected[py*WIDTH+px]) return 0;
    return 1;
}
static WORD seed(const char *text)
{
    if (BasicReplace(&e.document,0,e.document.bytes,(const UBYTE *)text,strlen(text))) return 0;
    e.caret=e.anchor=e.first=e.left=0;e.document.saved=e.document.generation;
    memset(&e.refresh,0,sizeof(e.refresh));memset(pixels,0xcc,sizeof(pixels));
    strcpy(e.status,"Ready");BasicAssistanceInit(&e);full_visibility();BasicEditorDamage(&e,0,BASIC_LINES);
    return drain() && picture();
}
static void sample(UWORD index,ULONG turns,ULONG glyphs)
{
    volatile ULONG *v=BasicPaintStats+index*8;
    v[0]=textCells-statusCells;v[1]=statusCells;v[2]=updates;v[3]=empty;
    v[4]=e.paintTurns-turns;v[5]=e.refresh.state.glyphs-glyphs;
    v[6]=textCalls;v[7]=clears;
}

LONG EXEC_CALL BasicPaintProbe(ULONG unused)
{
    ULONG baseline=AvailMem(MEMF_UPPER),before,turns,glyphs;UWORD i,row;UBYTE saved;
    (void)unused;CHECK(BasicPaintSizes[2]==5120);CHECK(BasicPaintSizes[0]<=BasicPaintSizes[1]);
    CHECK(!BasicDocumentInit(&e.document));e.rows=6;e.columns=16;e.app.cellw=e.app.cellh=8;
    e.app.work[0]=8;e.app.work[1]=4;e.app.work[2]=136;e.app.work[3]=64;
    CHECK(seed("alpha1\nbeta22\ngamma3\ndelta4\nepsil5\nzeta66"));
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,13,0) && drain() && picture());sample(0,turns,glyphs);
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,8,0) && drain() && picture());sample(1,turns,glyphs);
    CHECK(seed("alpha1\nbeta22\ngamma3\ndelta4\nepsil5\nzeta66"));
    e.caret=e.anchor=e.document.line[3];BasicEditorReveal(&e);BasicEditorRows(&e,0,1);
    CHECK(drain() && picture());
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,13,0) && drain() && picture());sample(2,turns,glyphs);
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,8,0) && drain() && picture());sample(3,turns,glyphs);
    CHECK(seed("alpha1\nbeta22\ngamma3\ndelta4\nepsil5\nzeta66"));
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,'q',0) && drain() && picture());sample(4,turns,glyphs);
    CHECK(seed("alpha1\nbeta22\ngamma3\ndelta4\nepsil5\nzeta66"));
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    e.first=1;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());sample(5,turns,glyphs);
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    e.first=0;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());sample(6,turns,glyphs);
    CHECK(seed("abcdefghijklmnopqrstuvwx\nabcdefghijklmnopqrstuvwx\nabcdefghijklmnopqrstuvwx"));
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    e.left=1;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());sample(7,turns,glyphs);
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    e.left=0;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());sample(8,turns,glyphs);
    CHECK(seed(""));turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,13,0) && drain() && picture());sample(9,turns,glyphs);
    CHECK(seed(""));reset_counts();
    CHECK(!BasicEditorKey(&e,'a',0) && drain() && picture());
    CHECK(!clears && textCells==3 && statusCells==1 && updates==1 && !empty);
    reset_counts();CHECK(!BasicEditorKey(&e,'b',0) && drain() && picture());
    CHECK(!clears && textCells==2 && !statusCells && updates==1 && !empty);
    reset_counts();CHECK(!BasicEditorKey(&e,0x4b00,0) && drain() && picture());
    CHECK(textCells==2 && !statusCells && !empty && !clears);
    reset_counts();CHECK(!BasicEditorKey(&e,0x4b00,1) && drain() && picture());
    CHECK(!statusCells && !empty && !clears);
    CHECK(!BasicEditorKey(&e,'x',0) && drain() && picture());
    reset_counts();
    CHECK(!BasicEditorKey(&e,8,0) && drain() && picture());
    CHECK(textCells==2 && !statusCells && !empty && !clears);
    CHECK(!BasicEditorKey(&e,26,4) && drain() && picture());
    CHECK(!BasicEditorKey(&e,25,4) && drain() && picture());
    CHECK(seed("abcdefghijklmnopqrstuvwx"));e.caret=e.anchor=24;BasicEditorReveal(&e);
    CHECK(e.left==9 && drain() && picture());
    CHECK(!BasicEditorKey(&e,'z',0) && drain() && picture());
    BasicEditorExpose(&e,8,4,136,64);CHECK(BasicEditorPaint(&e));
    e.columns=12;e.app.work[2]=104;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    e.columns=16;e.app.work[2]=136;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    CHECK(seed("PRIN"));e.caret=e.anchor=4;BasicEditorReveal(&e);CHECK(drain());
    CHECK(!BasicEditorKey(&e,'T',0) && drain() && picture());CHECK((e.refresh.state.attributes[0][0]&15)==4);
    CHECK(seed("\"abc\"\txyz\nsecond\nthird"));e.caret=e.anchor=4;BasicEditorReveal(&e);CHECK(drain());
    CHECK(!BasicEditorKey(&e,127,0) && drain() && picture());
    CHECK(!BasicEditorKey(&e,13,0) && drain() && picture());
    /* Replacing a newline with Return can change two rows without changing
     * the line count. Both rows must be compared. */
    CHECK(seed("one\nTwo\nthree"));e.anchor=1;e.caret=5;
    CHECK(!BasicEditorKey(&e,13,0) && drain() && picture());
    CHECK(seed("' note\nPRINT 1\nPROC X\n  ? \"ok\"\nENDPROC\n"));
    for (i=0;BasicAssistanceWork(&e) && i<100;++i) BasicAssistanceStep(&e);
    e.caret=e.anchor=e.document.line[2];BasicEditorReveal(&e);CHECK(drain());
    BasicAssistanceRequest(BASIC_ASSIST_FOLD);CHECK(BasicAssistanceStep(&e)==1);
    CHECK(drain());CHECK(picture());
    BasicEditorStatus(&e,"A longer message");CHECK(drain() && picture());
    reset_counts();BasicEditorStatus(&e,"A longer message");CHECK(drain() && !updates && !textCells);
    BasicEditorStatus(&e,"Short");CHECK(drain() && picture());
    e.document.saved=e.document.generation;BasicEditorStatus(&e,e.status);CHECK(drain() && picture());
    /* Exposure must reconstruct identical logical cells. */
    memset(pixels,0xcc,sizeof(pixels));BasicEditorExpose(&e,8,4,136,64);CHECK(drain() && picture());
    /* Partial glyph clipping, including selection/caret, must preserve other pixels. */
    rectangles[0][2]=27;count=2;rectangles[1][0]=63;rectangles[1][1]=4;rectangles[1][2]=81;rectangles[1][3]=64;
    memset(pixels,0xcc,sizeof(pixels));BasicEditorExpose(&e,8,4,136,64);CHECK(drain() && picture());
    CHECK(pixels[5*WIDTH+50]==0xcc);
    full_visibility();BasicEditorExpose(&e,8,4,136,64);CHECK(drain() && picture());
    /* Multiple visible fragments require journal rollover without widened claims. */
    count=10;for (i=0;i<count;++i) { rectangles[i][0]=8+i*13;rectangles[i][1]=4;rectangles[i][2]=12;rectangles[i][3]=64; }
    memset(pixels,0xcc,sizeof(pixels));BasicEditorExpose(&e,8,4,136,64);CHECK(drain() && picture());
    full_visibility();BasicEditorExpose(&e,8,4,136,64);CHECK(drain() && picture());
    /* New input during a large repair merges with outstanding work. */
    BasicEditorDamage(&e,0,BASIC_LINES);CHECK(BasicEditorPaint(&e));
    CHECK(!BasicEditorKey(&e,'q',0) && drain() && picture());
    count=0;before=updates;BasicEditorStatus(&e,"Hidden update");CHECK(drain());
    CHECK(updates-before==1);before=updates;CHECK(BasicEditorPaint(&e) && updates==before);
    full_visibility();memset(pixels,0xcc,sizeof(pixels));BasicEditorExpose(&e,8,4,136,64);CHECK(drain() && picture());
    /* Failed drawing or publication cannot consume the pending prefix. */
    CHECK(!BasicEditorKey(&e,'r',0));row=BasicAssistanceRow(&e,BasicLine(&e.document,e.caret));
    saved=e.refresh.state.first[row];failDraw=1;
    CHECK(!BasicEditorPaint(&e) && !locked && e.refresh.state.first[row]<=saved && e.dirty);
    CHECK(drain() && picture());
    CHECK(!BasicEditorKey(&e,'t',0));failVisible=1;CHECK(!BasicEditorPaint(&e) && e.dirty && !locked);
    CHECK(drain() && picture());
    CHECK(!BasicEditorKey(&e,'s',0));failEnd=1;CHECK(!BasicEditorPaint(&e) && e.dirty);
    CHECK(drain() && picture());
    reset_counts();CHECK(BasicEditorPaint(&e) && !updates && !textCells && !clears);
    CHECK(!invalid);BasicAssistanceDispose();BasicDocumentDispose(&e.document);CHECK(AvailMem(MEMF_UPPER)==baseline);
    return 0;
}
int main(void) { return 0; }
