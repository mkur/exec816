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
uint16_t WidgetPaint(struct WidgetPacket *);
uint16_t WidgetInput(struct WidgetContext *,struct WidgetPacket *);
uint16_t WidgetSet(struct WidgetContext *,const struct WidgetTree *,struct WidgetPacket *);
uint16_t WidgetUpdate(struct WidgetContext *,const struct WidgetUpdate *,struct WidgetPacket *);
uint16_t WidgetRead(const struct WidgetContext *,struct WidgetSnapshot *,uint16_t);
uint16_t WidgetEligible(const struct WidgetContext *,uint16_t);
int16_t WidgetFirst(const struct WidgetContext *);
void WidgetDamage(struct WidgetPacket *,const struct WidgetContext *,int16_t);
void WidgetFocusDamage(struct WidgetPacket *,const struct WidgetContext *,int16_t);
extern struct WidgetContext *WidgetCurrent;
void WidgetFill(WORD mode,WORD style,WORD pattern,WORD colour,const GRECT *);
void WidgetText(WORD x,WORD y,const WORD *glyphs,WORD count,WORD mode,WORD colour);
#endif
