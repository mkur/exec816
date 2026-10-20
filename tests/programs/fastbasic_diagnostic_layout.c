/* SPDX-License-Identifier: MIT */
#include <stddef.h>
#include <exec816/fastbasic-diagnostic.h>
UWORD DiagnosticChecks;
static struct ExecFastBasicDiagnostic d;
#define CHECK(x) do { if (!(x)) return __LINE__; ++DiagnosticChecks; } while (0)
LONG DiagnosticProbe(void)
{
    CHECK(sizeof(d)==224);
    CHECK(offsetof(struct ExecFastBasicDiagnostic,job)==8);
    CHECK(offsetof(struct ExecFastBasicDiagnostic,native_cause)==16);
    CHECK(offsetof(struct ExecFastBasicDiagnostic,line)==20);
    CHECK(offsetof(struct ExecFastBasicDiagnostic,source)==32);
    CHECK(offsetof(struct ExecFastBasicDiagnostic,message)==160);
    d.magic[0]='F';d.magic[1]='B';d.magic[2]='D';d.magic[3]='1';
    d.version=1;d.bytes=224;d.job=0x12345678UL;d.stage=2;
    d.native_cause=306;d.line=2;d.byte_column=9;
    d.source_bytes=5;d.source[0]='R';d.source[1]='A';d.source[2]='M';
    d.source[3]=':';d.source[4]='S';d.message_bytes=1;d.message[0]='X';
    CHECK(ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:S"));
    CHECK(!ExecFastBasicDiagnosticMatches(&d,223,0x12345678UL,"RAM:S"));
    CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345679UL,"RAM:S"));
    CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:T"));
    CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:SX"));
    d.source[5]='X';CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:S"));d.source[5]=0;
    d.message_bytes=64;CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:S"));d.message_bytes=1;
    d.reserved=1;CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:S"));d.reserved=0;
    d.stage=0;CHECK(!ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:S"));d.stage=4;
    CHECK(ExecFastBasicDiagnosticMatches(&d,224,0x12345678UL,"RAM:S"));
    return 0;
}
int main(void) { return (int)DiagnosticProbe(); }
