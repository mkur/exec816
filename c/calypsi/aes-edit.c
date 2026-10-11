/* Caller-local single-line editing; shared draw scratch is DISPLAY-owned. */
#include "aes-private.h"
#include "application-hosted.h"

static OBJECT fieldObject;
static TEDINFO fieldTed;
static char fieldText[128];

static WORD formatted(WORD type) { return type==G_FTEXT || type==G_FBOXTEXT; }
static WORD length_limit(const OBJECT *object,const TEDINFO *ted)
{
    WORD limit=ted->te_txtlen-1;
    if (formatted(object->ob_type)) {
        const char *p=(const char *)(ULONG)ted->te_ptmplt;
        WORD slots=0;
        while (*p) { if (*p=='_') ++slots;++p; }
        if (limit>slots) limit=slots;
    }
    return limit;
}
/* GEM classes are ASCII here; upper-case classes fold before admission. */
static WORD accepted(char *value,const char *valid,WORD index)
{
    UBYTE c=(UBYTE)*value;
    WORD n=strlen(valid);
    char type=n ? valid[index<n ? index:n-1]:'X';
    WORD upper=type=='A' || type=='N' || type=='F' || type=='P' || type=='f' || type=='p' || type=='x';
    if (!strchr("9AaNnFfPpXx",type)) return 0;
    if (upper && c>='a' && c<='z') c-=32;
    if (type=='9' && !(c>='0' && c<='9')) return 0;
    if ((type=='A' || type=='a') && !(c==' ' || (c>='A' && c<='Z') || (c>='a' && c<='z'))) return 0;
    if ((type=='N' || type=='n') && !(c==' ' || (c>='0' && c<='9') || (c>='A' && c<='Z') || (c>='a' && c<='z'))) return 0;
    if (type=='F' || type=='f' || type=='P' || type=='p') {
        WORD ordinary=(c>='0' && c<='9') || (c>='A' && c<='Z') ||
            (c>='a' && c<='z') || c=='_';
        if (!ordinary && !(type=='F' && (c==':' || c=='?' || c=='*')) &&
            !((type=='P' || type=='p') && (c=='\\' || c==':' || c=='/')) &&
            !(type=='P' && (c=='.' || c=='?' || c=='*'))) return 0;
    }
    if (c<32 || c>126) return 0;
    *value=(char)c;return 1;
}

WORD objc_edit(OBJECT *tree,WORD object,WORD key,WORD *index,WORD kind)
{
    struct ExecAESContext *c=ExecAESContext();
    TEDINFO *ted=(TEDINFO *)(ULONG)tree[object].ob_spec;
    char *text=(char *)(ULONG)ted->te_ptext,ch=(char)key;
    WORD length,limit,okay;
    if (kind==ED_START) return 1;
    if (!c || !wind_update(BEG_UPDATE)) return 0;
    length=strlen(text);limit=length_limit(&tree[object],ted);
    if (kind==ED_INIT) { *index=length;c->editScroll=0; }
    else if (kind==ED_CHAR) {
        switch (key) {
        case 0x4b00:if (*index) --*index;break;
        case 0x4d00:if (*index<length) ++*index;break;
        case 0x4700:*index=0;break;
        case 0x4f00:*index=length;break;
        case 0x5300:case 0x537f:
            if (*index<length) memmove(text+*index,text+*index+1,length-*index);
            break;
        default:
            if ((key&255)==8) {
                if (*index) { --*index;memmove(text+*index,text+*index+1,length-*index); }
            } else if ((key&255)==27) { text[0]=0;*index=0; }
            else if (length<limit && accepted(&ch,(const char *)(ULONG)ted->te_pvalid,*index)) {
                memmove(text+*index+1,text+*index,length-*index+1);text[*index]=ch;++*index;
            }
        }
    }
    c->editTree=kind==ED_END ? 0:(ULONG)tree;c->editObject=object;c->editIndex=*index;
    okay=objc_draw(tree,object,0,c->view->work.left,c->view->work.top,
        c->view->work.right-c->view->work.left,c->view->work.bottom-c->view->work.top);
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}

/* Called inside the ordinary complete clipped object strip. The copied TED
 * and object keep formatting/justification in the extracted GEM renderer. */
void ExecAESDrawEdit(struct ExecAESContext *c,OBJECT *tree,WORD object,WORD x,WORD y)
{
    TEDINFO *ted=(TEDINFO *)(ULONG)tree[object].ob_spec;
    const char *source=(const char *)(ULONG)ted->te_ptext;
    const char *pattern=(const char *)(ULONG)ted->te_ptmplt;
    WORD length=strlen(source),count=0,raw=0,caret=0,start=0,width,height,left,top;
    WORD active=c->editTree==(ULONG)tree && c->editObject==object;
    WORD inset=ted->te_thickness>0 ? ted->te_thickness:0;
    GRECT paper;
    fieldObject=tree[object];fieldTed=*ted;
    width=fieldObject.ob_width-2*inset;height=fieldObject.ob_height-2*inset;
    if (formatted(fieldObject.ob_type)) {
        while (pattern[count] && count<63) {
            if (pattern[count]=='_') {
                if (raw==c->editIndex) caret=count;
                fieldText[count]=raw<length ? source[raw]:'_';++raw;
            } else fieldText[count]=pattern[count];
            ++count;
        }
        if (c->editIndex>=raw) caret=count;
    } else {
        WORD columns=width/8;
        if (columns>63) columns=63;
        if (columns<1) columns=1;
        if (active) {
            start=c->editScroll;
            if (c->editIndex<start) start=c->editIndex;
            if (c->editIndex>=start+columns) start=c->editIndex-columns+1;
            c->editScroll=start;caret=c->editIndex-start;
        }
        while (start+count<length && count<columns) { fieldText[count]=source[start+count];++count; }
    }
    fieldText[count]=0;
    fieldTed.te_ptext=(ULONG)fieldText;
    fieldObject.ob_spec=(ULONG)&fieldTed;
    fieldObject.ob_type=fieldObject.ob_type==G_FBOXTEXT ? G_BOXTEXT:
        fieldObject.ob_type==G_FTEXT ? G_TEXT:fieldObject.ob_type;
    r_set(&paper,x+inset,y+inset,width,height);
    WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,ted->te_color&15,&paper);
    just_draw(&fieldObject,0,x,y);
    if (active) {
        left=x+inset;top=y+inset+(height-8)/2;
        if (ted->te_just==TE_RIGHT) left+=width-count*8;
        else if (ted->te_just==TE_CNTR) left+=(width-count*8)/2;
        left+=caret*8;
        if (left>=x+fieldObject.ob_width-inset) left=x+fieldObject.ob_width-inset-1;
        r_set(&paper,left,top,1,8);
        WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,(ted->te_color>>8)&15,&paper);
    }
}
