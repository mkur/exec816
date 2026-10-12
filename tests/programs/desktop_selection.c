/* The real private selection helpers, exercised without a display or filesystem. */
#include "../../examples/gem-browser/browser.c"
static WORD unexpected;
WORD wind_update(WORD mode) { (void)mode;++unexpected;return 0; }
WORD wind_get(WORD handle,WORD field,WORD *a,WORD *b,WORD *c,WORD *d)
{
    (void)handle;(void)field;(void)a;(void)b;(void)c;(void)d;++unexpected;return 0;
}
WORD objc_draw(OBJECT *tree,WORD object,WORD depth,WORD x,WORD y,WORD w,WORD h)
{
    (void)tree;(void)object;(void)depth;(void)x;(void)y;(void)w;(void)h;++unexpected;return 0;
}
LONG EXEC_CALL IoErr(void) { ++unexpected;return 0; }
static struct Browser probeBrowser;
static struct FileEntry probeEntries[BROWSER_ENTRIES];
ULONG DesktopSelectionProbe(void)
{
    struct Browser *b=&probeBrowser;
    UWORD i;
    b->entries=probeEntries;b->count=BROWSER_ENTRIES;
    b->armedModifiers=0x5a5a;b->selected=-1;
    for (i=0;i<BROWSER_ENTRIES;++i) b->entries[i].kind=(i&1) ? -1:1;
    clear_selection(b);
    for (i=0;i<BROWSER_ENTRIES;++i) {
        mark_entry(b,i,1);
        if (b->selectionCount!=i+1 || !selected_entry(b,i)) return 1000+i;
    }
    if (b->selectionDirectories!=128 || b->armedModifiers!=0x5a5a || single_entry(b)!=-1) return 2000;
    for (i=0;i<sizeof(b->selection);++i) if (b->selection[i]!=255) return 2100+i;
    for (i=0;i<255;++i) mark_entry(b,i,0);
    if (single_entry(b)!=255 || b->selectionCount!=1 || b->selectionDirectories) return 2200;
    mark_entry(b,255,1);
    if (b->selectionCount!=1) return 2300;
    clear_selection(b);
    for (i=0;i<BROWSER_ENTRIES;++i) if (selected_entry(b,i)) return 2400+i;
    if (b->armedModifiers!=0x5a5a || b->selected!=-1) return 2700;
    if (unexpected) return 2800;
    return 0;
}
int main(void) { return 0; }
