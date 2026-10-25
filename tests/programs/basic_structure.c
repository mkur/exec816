/* Reuse the independent pixel device; keep this cohort within its own bound. */
#define BasicPaintProbe UnusedPaintProbe
#define main UnusedPaintMain
#include "basic_paint.c"
#undef BasicPaintProbe
#undef main
static UBYTE sourceBytes[512];
static WORD source_is(const char *wanted)
{
    UWORD size=strlen(wanted);
    if (e.document.bytes!=size) return 0;
    BasicCopy(&e.document,0,sourceBytes,size);
    return !memcmp(sourceBytes,wanted,size);
}
LONG EXEC_CALL BasicPaintProbe(ULONG unused)
{
    ULONG baseline=AvailMem(MEMF_UPPER),turns,glyphs;UWORD line;
    const char *plain="alpha1\nbeta22\ngamma3\ndelta4\nepsil5\nzeta66";
    const char *longRows="abcdefghijklmnopqrstuvwx\nsecond-long-abcdefghijkl\nthird-long-abcdefghijkl\nfourth-long-abcdefghijkl\nfifth-long-abcdefghijkl\nsixth-long-abcdefghijkl\nseventh-long-abcdefghijkl";
    (void)unused;CHECK(!BasicDocumentInit(&e.document));
    e.rows=6;e.columns=16;e.app.cellw=e.app.cellh=8;
    e.app.work[0]=8;e.app.work[1]=4;e.app.work[2]=136;e.app.work[3]=64;
    CHECK(seed(plain));e.caret=e.anchor=3;BasicEditorReveal(&e);CHECK(drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,13,0) && drain() && picture() && copies==1);
    CHECK(source_is("alp\nha1\nbeta22\ngamma3\ndelta4\nepsil5\nzeta66"));
    reset_counts();CHECK(!BasicEditorKey(&e,8,0) && drain() && picture() && copies==1 && source_is(plain));
    CHECK(seed("  PRINT\t\"abc\"\nsecond\nthird\nfour\nfive\nsix\nseven\n"));
    e.caret=e.anchor=8;BasicEditorReveal(&e);CHECK(drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,13,0) && drain() && picture() && copies==1);
    CHECK(!BasicEditorKey(&e,0x4700,0) && drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,8,0) && drain() && picture() && copies==1);
    CHECK(!BasicEditorKey(&e,26,4) && drain() && picture());
    CHECK(!BasicEditorKey(&e,26,4) && drain() && picture() &&
        source_is("  PRINT\t\"abc\"\nsecond\nthird\nfour\nfive\nsix\nseven\n"));
    CHECK(!BasicEditorKey(&e,25,4) && drain() && picture());
    CHECK(!BasicEditorKey(&e,25,4) && drain() && picture());
    CHECK(seed(plain));e.anchor=e.document.line[1];e.caret=e.document.line[3];
    BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,8,0) && drain() && picture() && copies==1);
    CHECK(source_is("alpha1\ndelta4\nepsil5\nzeta66"));
    CHECK(seed(plain));e.anchor=e.document.line[1];e.caret=e.document.line[3];
    BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,13,0) && drain() && picture() && copies==1);
    CHECK(source_is("alpha1\n\ndelta4\nepsil5\nzeta66"));
    CHECK(seed("one\ntwo\nthree\nfour\nfive\nsix\n"));
    e.caret=e.anchor=e.document.line[3]+4;BasicEditorReveal(&e);BasicEditorRows(&e,0,1);CHECK(drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,13,0) && drain() && picture() && copies==1);
    reset_counts();CHECK(!BasicEditorKey(&e,8,0) && drain() && picture() && copies==1);
    CHECK(source_is("one\ntwo\nthree\nfour\nfive\nsix\n"));
    CHECK(seed(longRows));e.caret=e.anchor=20;e.left=10;
    BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    turns=e.paintTurns;glyphs=e.refresh.state.glyphs;reset_counts();
    CHECK(!BasicEditorKey(&e,13,0) && drain() && picture() && copies==1);sample(0,turns,glyphs);
    reset_counts();CHECK(!BasicEditorKey(&e,8,0) && drain() && picture() && copies==1 && source_is(longRows));
    CHECK(seed(plain));e.anchor=1;e.caret=e.document.line[1]+1;
    BasicEditorDamage(&e,0,BASIC_LINES);CHECK(drain() && picture());
    reset_counts();CHECK(!BasicEditorKey(&e,13,0) && drain() && picture() && !copies);
    /* A second edit before presentation must discard the old row mapping. */
    CHECK(seed(plain));CHECK(!BasicEditorKey(&e,13,0));
    CHECK(!BasicEditorKey(&e,'q',0) && drain() && picture());
    /* Delete at a newline uses the same mapping as Backspace. */
    CHECK(seed(plain));line=2;e.caret=e.anchor=e.document.line[line+1]-1;
    BasicEditorReveal(&e);BasicEditorRows(&e,0,1);CHECK(drain() && picture());reset_counts();
    CHECK(!BasicEditorKey(&e,127,0) && drain() && picture() && copies==1);
    CHECK(source_is("alpha1\nbeta22\ngamma3delta4\nepsil5\nzeta66"));
    CHECK(!invalid);BasicAssistanceDispose();BasicDocumentDispose(&e.document);
    CHECK(AvailMem(MEMF_UPPER)==baseline);return 0;
}
int main(void) { return 0; }
