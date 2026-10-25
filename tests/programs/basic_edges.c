/* Uniform-row strips, offscreen tabs and an odd-position viewport. */
#define BasicPaintProbe UnusedPaintProbe
#define main UnusedPaintMain
#include "basic_paint.c"
#undef BasicPaintProbe
#undef main
LONG EXEC_CALL BasicPaintProbe(ULONG unused)
{
    ULONG baseline=AvailMem(MEMF_UPPER),fast;
    (void)unused;CHECK(!BasicDocumentInit(&e.document));
    e.rows=6;e.columns=16;e.app.cellw=e.app.cellh=8;
    e.app.work[0]=8;e.app.work[1]=4;e.app.work[2]=136;e.app.work[3]=64;
    CHECK(seed("'abcdefghijklmnopqrs\tXYZabcdefgh\n'abcdefghijklmnopqrs\tXYZabcdefgh"));
    CHECK(!e.motion.state.uniform[0]);
    e.left=8;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    e.left=16;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    e.left=8;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    e.left=0;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    CHECK(seed("\"abcdefghijklmnopqrstuvwx\""));CHECK(e.motion.state.uniform[0]==2);
    fast=e.motion.state.stripRows;e.left=1;BasicEditorDamage(&e,0,BASIC_LINES);
    CHECK(drain() && picture() && e.motion.state.stripRows>fast);
    CHECK(seed("\"abcdefghijklmnopqr\tstuvwx\""));CHECK(!e.motion.state.uniform[0]);
    e.left=8;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    CHECK(seed("PRINT \"abc\" + variable"));CHECK(!e.motion.state.uniform[0]);
    e.left=1;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    CHECK(seed("xxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxx"));
    fast=e.motion.state.stripRows;e.left=1;BasicEditorDamage(&e,0,BASIC_LINES);
    CHECK(drain() && picture() && e.motion.state.stripRows==fast+6);
    CHECK(!e.motion.state.applied && view.pixelsReady);
    reset_counts();e.left=0;BasicEditorDamage(&e,0,BASIC_LINES);
    CHECK(drain() && picture() && copies==1 && !e.motion.state.applied && view.pixelsReady);
    ++e.app.work[0];++e.app.work[1];full_visibility();BasicEditorDamage(&e,0,BASIC_LINES);
    CHECK(drain() && picture());reset_counts();
    e.left=1;BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture() && copies==1);
    CHECK(!invalid);BasicAssistanceDispose();BasicDocumentDispose(&e.document);
    CHECK(AvailMem(MEMF_UPPER)==baseline);return 0;
}
int main(void) { return 0; }
