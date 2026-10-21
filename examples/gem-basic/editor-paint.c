/* SPDX-License-Identifier: MIT */
#include "editor.h"
#include "assist-ui.h"
#include "assist.h"
#include <exec816/aes.h>
#include <string.h>

static WORD min(WORD a,WORD b) { return a<b ? a:b; }
static WORD max(WORD a,WORD b) { return a>b ? a:b; }

static void row_text(struct BasicEditor *e,UWORD line)
{
    ULONG at,col=0,next;UWORD i=0;UBYTE c;
    memset(e->row,' ',e->columns);e->row[e->columns]=0;
    if (line>=e->document.lines) return;
    at=e->document.line[line];
    while (at<e->document.bytes && i<e->columns) {
        c=BasicByte(&e->document,at++);if (c==10) break;
        next=c==9 ? (col+8)&~7UL:col+1;
        while (col<next) { if (col>=e->left) e->row[i++]=c==9 ? ' ':c;++col;if (i==e->columns) break; }
    }
}

WORD BasicEditorPaint(struct BasicEditor *e)
{
    struct BasicApp *a=&e->app;WORD r[4],clip[4],bar[4],i,y,end,okay=1;
    ULONG lo=e->anchor<e->caret ? e->anchor:e->caret,hi=e->anchor>e->caret ? e->anchor:e->caret;
    ULONG start,finish,at;UWORD line;
    end=min(e->damageEnd,e->damageFirst+4);
    if (end==e->damageEnd && end-e->damageFirst==4) --end;
    y=a->work[1]+e->damageFirst*a->cellh;
    if (!ExecAESBeginUpdate(a->window)) return 0;
    if (!wind_get(a->window,WF_FIRSTXYWH,&r[0],&r[1],&r[2],&r[3])) okay=0;
    while (okay && r[2] && r[3]) {
        clip[0]=max(a->work[0],r[0]);clip[1]=max(y,r[1]);
        clip[2]=min(a->work[0]+a->work[2],r[0]+r[2])-1;
        clip[3]=min(a->work[1]+end*a->cellh,r[1]+r[3])-1;
        if (clip[0]<=clip[2] && clip[1]<=clip[3]) {
            vs_clip(a->vdi,1,clip);vsf_color(a->vdi,0);v_bar(a->vdi,clip);vst_color(a->vdi,1);
            for (i=e->damageFirst;i<end;++i) {
                line=BasicAssistanceLine(e,i);row_text(e,line);
                BasicAssistanceColors(e,line,e->colors);
                {
                    UWORD column=0,stop;char saved;
                    while (column<e->columns) {
                        stop=column+1;while (stop<e->columns && e->colors[stop]==e->colors[column]) ++stop;
                        saved=e->row[stop];e->row[stop]=0;vst_color(a->vdi,e->colors[column]);
                        v_gtext(a->vdi,a->work[0]+4+column*a->cellw,a->work[1]+i*a->cellh+6,e->row+column);
                        e->row[stop]=saved;column=stop;
                    }
                }
                if (line<e->document.lines && lo<hi && lo<e->document.line[line+1] && hi>e->document.line[line]) {
                    at=lo>e->document.line[line] ? lo:e->document.line[line];start=BasicColumn(&e->document,at);
                    at=hi<e->document.line[line+1] ? hi:e->document.line[line+1];
                    if (at>e->document.line[line] && at<=e->document.bytes && BasicByte(&e->document,at-1)==10) --at;
                    finish=BasicColumn(&e->document,at);if (hi>at) ++finish;
                    bar[0]=a->work[0]+4+max(0,(WORD)start-e->left)*a->cellw;
                    bar[2]=a->work[0]+3+min(e->columns,(WORD)finish-e->left)*a->cellw;
                    bar[1]=a->work[1]+i*a->cellh+7;bar[3]=bar[1];
                    if (bar[0]<=bar[2]) { vsf_color(a->vdi,3);v_bar(a->vdi,bar); }
                }
                if (line==BasicLine(&e->document,e->caret)) {
                    start=BasicColumn(&e->document,e->caret);
                    if (start>=e->left && start<e->left+e->columns) {
                        bar[0]=bar[2]=a->work[0]+4+(start-e->left)*a->cellw;
                        bar[1]=a->work[1]+i*a->cellh;bar[3]=bar[1]+a->cellh-1;
                        vsf_color(a->vdi,1);v_bar(a->vdi,bar);
                    }
                }
            }
            okay=ExecAESDiagnostic()==AES_OK;
        }
        if (end==e->damageEnd) {
            clip[0]=max(a->work[0],r[0]);clip[1]=max(a->work[1]+e->rows*a->cellh,r[1]);
            clip[2]=min(a->work[0]+a->work[2],r[0]+r[2])-1;
            clip[3]=min(a->work[1]+a->work[3],r[1]+r[3])-1;
            if (clip[0]<=clip[2] && clip[1]<=clip[3]) {
                vs_clip(a->vdi,1,clip);vsf_color(a->vdi,0);v_bar(a->vdi,clip);vst_color(a->vdi,1);
                memset(e->row,' ',e->columns);e->row[e->columns]=0;
                e->row[0]=BasicDirty(&e->document) ? '*':' ';
                if (e->columns>2) {
                    UWORD n=strlen(e->status);if (n>e->columns-2) n=e->columns-2;
                    memcpy(e->row+2,e->status,n);
                }
                v_gtext(a->vdi,a->work[0]+4,a->work[1]+e->rows*a->cellh+10,e->row);
                if (!ExecAESPainted(a->window,clip[0],clip[1],clip[2]-clip[0]+1,clip[3]-clip[1]+1)) okay=0;
            }
        }
        if (!wind_get(a->window,WF_NEXTXYWH,&r[0],&r[1],&r[2],&r[3])) okay=0;
    }
    if (okay) okay=ExecAESPainted(a->window,a->work[0],y,a->work[2],(end-e->damageFirst)*a->cellh);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) { e->damageFirst=end;e->dirty=end<e->damageEnd;++e->paintTurns; }
    return okay;
}
