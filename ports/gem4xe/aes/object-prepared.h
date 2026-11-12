/* Private decoded GEM object. Values/glyphs belong to one caller. */
#ifndef EXEC_OBJECT_PREPARED_H
#define EXEC_OBJECT_PREPARED_H
struct ObjectPrepared {
    WORD valid,state,type,thickness,inset,border,ink,pattern,paper,mode;
    WORD ted,font,length;
    GRECT bounds,text;
    WORD glyphs[64];
};
void prepare_draw(struct ObjectPrepared *,OBJECT *,WORD,WORD,WORD);
void draw_prepared(const struct ObjectPrepared *);
WORD gr_just_to(WORD *,WORD,WORD,const char *,WORD,WORD,GRECT *);
#endif
