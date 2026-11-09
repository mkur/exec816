/* SPDX-License-Identifier: MIT. Actual native archive engine/stdio ownership. */
#include "platform.h"
#include "internal.h"
#include <stdio.h>
#include <errno.h>
static unsigned int executions,read_failure,write_failure,close_failure,rename_failure;
static unsigned int close_hits,rename_hits,cancel_after,polls;
static BPTR failed_input;
static char archive[40],output[40];
static ARC_ENTRY *entries;
static char (*names)[ARC_NAMELEN];
static unsigned char bytes[2048];
#define CHECK(test,number) do {if (!(test)) return number;} while (0)
int GemArcPoll(void) { ExecYield();return cancel_after && ++polls>=cancel_after; }
void arc_progress(const char *name) { (void)name;ExecYield(); }
BPTR ExecCRTTestOpen(const char *name,LONG mode)
{
    BPTR file=Open(name,mode);
    if (strstr(name,"FAIL.DAT")) failed_input=file;
    return file;
}
LONG ExecCRTTestRead(BPTR file,void *data,LONG count)
{
    if (read_failure && file==failed_input) { SetIoErr(0x0000c219L);return -1; }
    return Read(file,data,count);
}
LONG ExecCRTTestWrite(BPTR file,const void *data,LONG count)
{
    if (write_failure) {
        LONG done=Write(file,data,1);
        write_failure=0;SetIoErr(0x0000c219L);return done;
    }
    return Write(file,data,count);
}
LONG ExecCRTTestClose(BPTR file)
{
    LONG result=Close(file);
    if (close_failure && --close_failure==0) {
        ++close_hits;SetIoErr(0x0000c219L);return 0;
    }
    return result;
}
LONG EXEC_CALL GemArcTestRename(CONST_STRPTR from,CONST_STRPTR to)
{
    if (rename_failure && --rename_failure==0) {
        ++rename_hits;SetIoErr(0x0000c219L);return 0;
    }
    return Rename(from,to);
}
__attribute__((section("exec_layout"))) const UWORD GemArcLayout[]={
    sizeof(ARC_ENTRY),offsetof(ARC_ENTRY,csize),sizeof(struct ARC_RECOVERY)};

static int verify(const char *path,unsigned int kind,ULONG expected)
{
    static const unsigned char old[]={111,108,100,0,255};
    static const unsigned char store[]={0,128,255,13,10,155};
    static const unsigned char pack[]={65,65,65,65,65,65,144,66};
    FILE *file=fopen(path,"rb");
    ULONG total=0;
    size_t got,i;
    int okay=1;
    if (!file) return 0;
    while ((got=fread(bytes,1,sizeof(bytes),file))!=0) {
        for (i=0;i<got;++i,++total) {
            unsigned char want=kind==0 ? old[total%5]:kind==1 ? store[total%6]:
                kind==2 ? pack[total%8]:kind==3 ? 'A':kind==6 ? (total ? 'B':'A'):
                (unsigned char)total;
            if (bytes[i]!=want) okay=0;
        }
    }
    if (ferror(file) || total!=expected) okay=0;
    if (fclose(file)) okay=0;
    return okay;
}
static int core(void)
{
    struct ExecCRuntimeHeapStats initial,after;
    uint16_t count,index;
    int result;
    const struct ARC_RECOVERY *recovery;
    uint16_t *prefix,*codes;
    uint8_t *suffix,*stack,*input,*out;
    uint32_t *hash;
    GemArcIOBegin();
    ExecCRuntimeHeapSnapshot(&initial);
    CHECK(initial.blocks==1,101);
    prefix=malloc(16384);suffix=malloc(8192);stack=malloc(8192);
    hash=malloc(20012);codes=malloc(10006);input=malloc(2048);out=malloc(2048);
    entries=malloc(sizeof(*entries)*512);names=malloc(sizeof(*names)*64);
    CHECK(prefix && suffix && stack && hash && codes && input && out && entries && names,102);
    arc_tables(prefix,suffix,stack,hash,codes);arc_buffers(input,out,2048);
    snprintf(archive,sizeof(archive),"RAM:A%06lX.ARC",(ULONG)FindTask(NULL)&0xffffffUL);
    snprintf(output,sizeof(output),"RAM:O%06lX.DAT",(ULONG)FindTask(NULL)&0xffffffUL);
    CHECK(arc_list("SYS:CORPUS.ARC",entries,512,&count)==0 && count==7,103);
    for (index=0;index<count;++index) {
        CHECK(arc_extract("SYS:CORPUS.ARC",&entries[index],output)==0,110+index);
        CHECK(verify(output,index,entries[index].osize),120+index);
        CHECK(!remove(output),130+index);
    }
    CHECK(!arc_new(archive),140);
    strcpy(names[0],"FAIL.DAT");
    CHECK(!arc_add(archive,"SYS:",names,1,entries,512),141);
    CHECK(!arc_list(archive,entries,512,&count) && count==1 && entries[0].osize==15360,142);
    read_failure=1;
    result=arc_add(archive,"SYS:",names,1,entries,512);
    read_failure=0;
    CHECK(result==ARC_E_READ && GemArcCause()==0x0000c219L,143);
    CHECK(!arc_list(archive,entries,512,&count) && count==1 && entries[0].osize==15360,144);
    write_failure=1;
    CHECK(arc_add(archive,"SYS:",names,1,entries,512)==ARC_E_WRITE,145);
    CHECK(GemArcCause()==0x0000c219L,146);
    close_failure=3;close_hits=0;
    CHECK(arc_add(archive,"SYS:",names,1,entries,512)==ARC_E_CLOSE && close_hits==1,147);
    recovery=arc_recovery();
    CHECK(recovery->uncertain_close && recovery->temp[0] && !remove(recovery->temp),148);
    rename_failure=2;rename_hits=0;
    CHECK(arc_add(archive,"SYS:",names,1,entries,512)==ARC_E_RENAME && rename_hits==1,149);
    recovery=arc_recovery();
    CHECK(recovery->original_moved && !recovery->published &&
        pf_exists(recovery->backup)==1 && pf_exists(recovery->temp)==1,150);
    CHECK(!rename(recovery->backup,archive) && !remove(recovery->temp),151);
    cancel_after=1;polls=0;
    CHECK(arc_add(archive,"SYS:",names,1,entries,512)==ARC_E_CANCEL,152);
    cancel_after=0;
    CHECK(!arc_list(archive,entries,512,&count) && count==1 && entries[0].osize==15360,153);
    CHECK(!arc_extract(archive,&entries[0],output) && verify(output,4,15360),154);
    CHECK(!remove(output) && !remove(archive),155);
    ExecCRuntimeHeapSnapshot(&after);
    CHECK(after.blocks==initial.blocks+9 && after.payload==initial.payload+84610UL,156);
    SetIoErr(0);
    return -321-executions++;
}
int main(void) { return core(); }
