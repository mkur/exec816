/* SPDX-License-Identifier: GPL-3.0-only
 * Canonical physical names with a retained ordinary directory lock.
 */
#include "qed-path.h"
#include <stdlib.h>
#include <string.h>
static unsigned char fold(unsigned char ch)
{return ch>='a' && ch<='z' ? ch-32:ch;}
int QedPathEqual(const char *a,const char *b)
{
    while(*a && fold(*a)==fold(*b)){a++;b++;}
    return fold(*a)==fold(*b);
}
void QedPathRelease(struct QedPath *owner)
{
    LONG cause=IoErr();BPTR parent=owner->parent;owner->parent=0;
    if(parent)UnLock(parent);
    SetIoErr(cause);
}
/* Only the precise leaf-not-found result is absence. Query locks never escape. */
int QedPathInfo(const char *name,struct FileInfoBlock *info)
{
    BPTR lock=Lock(name,SHARED_LOCK);LONG cause,result;
    if(!lock)return IoErr()==ERROR_OBJECT_NOT_FOUND ? 0:-1;
    result=Examine(lock,info);cause=IoErr();UnLock(lock);SetIoErr(cause);
    return result ? 1:-1;
}
int QedPathSibling(const struct QedPath *owner,const char *leaf,char *result)
{
    unsigned length=(unsigned)strlen(leaf);
    if((unsigned long)owner->prefix+length>255UL){SetIoErr(ERROR_LINE_TOO_LONG);return 0;}
    memcpy(result,owner->name,owner->prefix);strcpy(result+owner->prefix,leaf);return 1;
}
static int valid_leaf(const char *leaf)
{
    unsigned stem=0,extension=0;int dotted=0;unsigned char ch;
    if(*leaf>='0' && *leaf<='9')return 0;
    while((ch=*leaf++)!=0){
        if(ch=='.'){if(dotted || !stem)return 0;dotted=1;continue;}
        if(!((ch>='0' && ch<='9') || (ch>=64 && ch<=90) || (ch>=95 && ch<=122)))return 0;
        if(dotted){if(++extension>3)return 0;}else if(++stem>8)return 0;
    }
    return stem && (!dotted || extension);
}
int QedPathPrepare(struct QedPath *owner,const char *path,int siblings)
{
    char *parent;const char *leaf,*p;struct FileInfoBlock *info;
    LONG cause=0;unsigned prefix,length,i;int result=0;
    QedPathRelease(owner);owner->name[0]=0;owner->prefix=0;
    length=(unsigned)strlen(path);
    if(!length || length>255){SetIoErr(ERROR_BAD_ARGUMENTS);return 0;}
    leaf=path;for(p=path;*p;p++)if(*p==':' || *p=='/')leaf=p+1;
    if(!valid_leaf(leaf)){SetIoErr(ERROR_INVALID_COMPONENT_NAME);return 0;}
    parent=malloc(256);info=malloc(sizeof(*info));
    if(!parent || !info){cause=ERROR_NO_FREE_STORE;goto done;}
    prefix=(unsigned)(leaf-path);
    memcpy(parent,path,prefix);parent[prefix]=0;
    if(prefix && parent[prefix-1]=='/')parent[prefix-1]=0;
    owner->parent=Lock(parent,SHARED_LOCK);
    if(!owner->parent){cause=IoErr();goto done;}
    if(!Examine(owner->parent,info)){cause=IoErr();goto done;}
    if(info->fib_DirEntryType!=ST_ROOT && info->fib_DirEntryType!=ST_USERDIR){cause=ERROR_OBJECT_WRONG_TYPE;goto done;}
    if(!NameFromLock(owner->parent,owner->name,256)){cause=IoErr();goto done;}
    prefix=(unsigned)strlen(owner->name);
    if(prefix && owner->name[prefix-1]!=':'){
        if(prefix==255){cause=ERROR_LINE_TOO_LONG;goto done;}
        owner->name[prefix++]='/';owner->name[prefix]=0;
    }
    owner->prefix=prefix;
    if((unsigned long)prefix+strlen(leaf)>255UL || (siblings && (unsigned long)prefix+12UL>255UL)){
        cause=ERROR_LINE_TOO_LONG;goto done;
    }
    for(i=0;leaf[i];i++)owner->name[prefix+i]=fold(leaf[i]);
    owner->name[prefix+i]=0;result=1;
done:
    free(parent);free(info);
    if(!result)QedPathRelease(owner);
    SetIoErr(cause);return result;
}
