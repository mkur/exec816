/* Presenter-owned widget state. GPL-3.0-only. No kernel or hardware ownership. */
#ifndef EXEC_AES_WIDGETS_H
#define EXEC_AES_WIDGETS_H
#include "aes-hosted.h"
#pragma pack(push, 2)
struct WidgetContext {
    uint32_t epoch,revision;
    uint16_t count,textBytes,background,width,height;
    int16_t focus,armed;
    uint16_t pressed;
    OBJECT objects[WIDGET_OBJECTS];
    char text[WIDGET_TEXT_BYTES];
    int16_t parent[WIDGET_OBJECTS];
    uint16_t order[WIDGET_OBJECTS];
    GRECT bounds[WIDGET_OBJECTS];
};
#pragma pack(pop)
uint16_t WidgetValidate(struct WidgetContext *,const struct WidgetTree *,uint16_t,uint16_t,uint16_t);
int16_t WidgetHit(struct WidgetContext *,int16_t,int16_t);
void WidgetDrawObject(struct WidgetContext *,uint16_t,int16_t,int16_t);
uint16_t WidgetVisible(const struct WidgetContext *,uint16_t);
extern struct WidgetContext *WidgetCurrent;
void WidgetFill(WORD mode,WORD style,WORD pattern,WORD colour,const GRECT *);
void WidgetText(WORD x,WORD y,const WORD *glyphs,WORD count,WORD mode,WORD colour);
#endif
