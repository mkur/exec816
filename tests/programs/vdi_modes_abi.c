/* Small raw/optimized record and public VDI call-boundary probe. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/vdi-unit.h>
#include <exec816/vdi.h>
static volatile struct ExecVDIUnit unit;
static WORD glyphs[2]={'A',' '};
int main(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57],handle=1;
    WORD mode=2,reply=0,control[12]={32,0,0,1,0,0,0,0,0,0,0,0};
    VDIPB pb={control,&mode,NULL,&reply,NULL};
    unit.writeMode=MD_TRANS;unit.textColor=6;unit.count=2;unit.glyphs=glyphs;
    unit.x=-3;unit.y=11;
    if(unit.writeMode!=2 || unit.textColor!=6 || unit.count!=2 ||
       unit.glyphs!=glyphs || unit.x!=-3 || unit.y!=11)return 101;
    v_opnvwk(input,&handle,output);
    if(handle!=2 || ExecAESDiagnostic()!=AES_OK)return 102;
    if(vswr_mode(handle,MD_TRANS)!=2 || ExecAESDiagnostic()!=AES_OK)return 103;
    control[6]=handle;vdi_call(&pb);
    if(reply!=2 || control[4]!=1 || ExecAESDiagnostic()!=AES_OK)return 104;
    mode=3;reply=0x7777;vdi_call(&pb);
    if(reply!=0x7777 || control[4] || ExecAESDiagnostic()!=AES_UNSUPPORTED)return 105;
    if(vswr_mode(handle,0) || ExecAESDiagnostic()!=AES_UNSUPPORTED)return 106;
    if(ExecVDICopyRect(handle,0,0,0,0,0,0)!=EXEC_VDI_COPY_ERROR ||
       ExecAESDiagnostic()!=AES_IDENTITY)return 109;
    mode=MD_REPLACE;vdi_call(&pb);
    if(reply!=1 || control[4]!=1 || ExecAESDiagnostic()!=AES_OK)return 107;
    v_clsvwk(handle);
    if(ExecAESDiagnostic()!=AES_OK)return 108;
    return -321;
}
