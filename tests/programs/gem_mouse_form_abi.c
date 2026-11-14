#include <gem.h>

volatile UWORD FormChecks;
volatile WORD FormWords[37];
static MFORM form;
#define CHECK(test) do { ++FormChecks; if (!(test)) return __LINE__; } while (0)

LONG FormProbe(void)
{
    UWORD i;
    for (i=0;i<37;++i) FormWords[i]=(WORD)(0x8100+i);
    for (i=0;i<37;++i) ((WORD *)&form)[i]=FormWords[i];
    CHECK(sizeof(MFORM)==74);
    CHECK((UWORD)form.mf_xhot==0x8100 && (UWORD)form.mf_yhot==0x8101);
    CHECK((UWORD)form.mf_nplanes==0x8102);
    CHECK((UWORD)form.mf_bg==0x8103 && (UWORD)form.mf_fg==0x8104);
    for (i=0;i<16;++i) {
        CHECK((UWORD)form.mf_mask[i]==0x8105+i);
        CHECK((UWORD)form.mf_data[i]==0x8115+i);
        form.mf_mask[i]=(WORD)(0xffffU-i);
        form.mf_data[i]=(WORD)(0x8000U>>i);
    }
    for (i=0;i<37;++i) FormWords[i]=((WORD *)&form)[i];
    for (i=0;i<16;++i) {
        CHECK((UWORD)FormWords[5+i]==0xffffU-i);
        CHECK((UWORD)FormWords[21+i]==(0x8000U>>i));
    }
    return 0;
}
int main(void) { return 0; }
