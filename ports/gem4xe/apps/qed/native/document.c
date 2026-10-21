/* SPDX-License-Identifier: GPL-3.0-only
 * Detached donor LINE ownership. No live document changes before commit.
 */
#include "qed-document.h"
#include "qed-path.h"
#include "qed-files.h"
#include "clipbrd.h"
#include "memory.h"
#include "text.h"
#include "window.h"
#include "edit.h"
#include "rsc.h"
#include <limits.h>

static RING candidate;
static struct QedPath candidate_path;
static char *read_buffer,*line_buffer;
static short descriptor=-1,line_length,convention;
static bool pending_cr,ready,unnamed;
static LONG cause,source_bytes;

LONG QedDocumentError(void){return cause;}
const char *QedDocumentName(void){return candidate_path.name;}
RINGP QedDocumentRing(void){return &candidate;}
static void buffers_free(void)
{
    free(read_buffer);free(line_buffer);read_buffer=line_buffer=NULL;
}
void QedDocumentCancel(void)
{
    LONG saved=cause;
    if(descriptor>=0){short fd=descriptor;descriptor=-1;if(Fclose(fd)<0 && !saved)saved=IoErr();}
    QedPathRelease(&candidate_path);
    buffers_free();kill_textring(&candidate);qed_ring_empty(&candidate);
    ready=FALSE;cause=saved;SetIoErr(cause);
}
static bool failed(LONG error)
{
    cause=error;QedDocumentCancel();return FALSE;
}
static bool append_line(void)
{
    LINEP line;
    if(candidate.lines==LONG_MAX)return failed(ERROR_BAD_NUMBER);
    line=new_col(line_buffer,line_length);
    if(!line)return failed(ERROR_NO_FREE_STORE);
    col_append(&candidate,line);line_length=0;return TRUE;
}
bool QedDocumentBegin(const char *path)
{
    LONG fd;
    QedDocumentCancel();cause=source_bytes=0;line_length=0;pending_cr=FALSE;
    convention=-1;unnamed=path==NULL;
    if(unnamed){
        const char *name=rsc_string(NAMENLOS);LINEP empty;
        if(strlen(name)>=sizeof(candidate_path.name))return failed(ERROR_BAD_ARGUMENTS);
        strcpy(candidate_path.name,name);empty=new_col("",0);
        if(!empty)return failed(ERROR_NO_FREE_STORE);
        col_append(&candidate,empty);ready=TRUE;return TRUE;
    }
    if(!*path || strlen(path)>=sizeof(candidate_path.name))return failed(ERROR_BAD_ARGUMENTS);
    if(!QedPathPrepare(&candidate_path,path,0))return failed(IoErr());
    read_buffer=malloc(4096);line_buffer=malloc(MAX_LINE_LEN+1);
    if(!read_buffer || !line_buffer)return failed(ERROR_NO_FREE_STORE);
    fd=Fopen(candidate_path.name,0);if(fd<0)return failed(IoErr());
    descriptor=(short)fd;return TRUE;
}
short QedDocumentPoll(void)
{
    LONG bytes;unsigned short i;unsigned char ch;short ending,fd;
    if(ready)return 1;
    if(descriptor<0)return -1;
    bytes=Fread(descriptor,4096L,read_buffer);
    if(bytes<0 || IoErr()){failed(IoErr());return -1;}
    if(bytes>4096 || bytes>LONG_MAX-source_bytes){failed(ERROR_BAD_NUMBER);return -1;}
    source_bytes+=bytes;
    if(!bytes){
        if(pending_cr){failed(ERROR_BAD_ARGUMENTS);return -1;}
        if(!append_line())return -1;
        fd=descriptor;descriptor=-1;
        if(Fclose(fd)<0){failed(IoErr());return -1;}
        candidate.ending=convention==lns_tos?lns_tos:lns_unix;
        buffers_free();ready=TRUE;return 1;
    }
    for(i=0;i<(unsigned short)bytes;i++){
        ch=(unsigned char)read_buffer[i];ending=-1;
        if(pending_cr){
            pending_cr=FALSE;
            if(ch!=10){failed(ERROR_BAD_ARGUMENTS);return -1;}
            ending=lns_tos;
        }else if(ch==13){pending_cr=TRUE;continue;}
        else if(ch==10)ending=lns_unix;
        else{
            if(!ch || line_length==MAX_LINE_LEN){failed(ERROR_BAD_ARGUMENTS);return -1;}
            line_buffer[line_length++]=ch;continue;
        }
        if(convention>=0 && convention!=ending){failed(ERROR_BAD_ARGUMENTS);return -1;}
        convention=ending;if(!append_line())return -1;
    }
    return 0;
}
void QedDocumentCommit(TEXTP text)
{
    RING old;WINDOWP window=get_window(text->link);
    QedPointerCancel();clr_undo();qed_ring_empty(&old);
    qed_ring_take(&old,&text->text);qed_ring_take(&text->text,&candidate);ready=FALSE;
    text->cursor_line=FIRST(&text->text);text->xpos=0;text->ypos=0;text->moved=0;
    text->p1=text->p2=NULL;text->z1=text->z2=-1;text->x1=text->x2=0;
    text->blink=text->block=text->block_dir=text->up_down=text->blk_mark_mode=FALSE;
    text->cursor=TRUE;text->desire_x=0;text->readonly=FALSE;text->file_date_time=-1;
    text->max_line=NULL;text->info_str[0]=0;text->asave=0;
    set_text_name(text,candidate_path.name,unnamed);
    window->doc.x=window->doc.y=0;kill_textring(&old);
    window->flags&=~WI_CHANGED;set_wtitle(window,text->filename);
    QedPathRelease(&candidate_path);
    make_chg(text->link,TOTAL_CHANGE,0);
}
