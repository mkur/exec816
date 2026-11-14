/* SPDX-License-Identifier: MIT */
#ifndef EXEC816_GEM_RECT_H
#define EXEC816_GEM_RECT_H
#include <gem.h>
WORD *grect_to_array(const GRECT *rectangle,WORD *xy);
WORD rc_intersect(const GRECT *source,GRECT *destination);
void rc_union(const GRECT *source,GRECT *destination);
WORD wind_create_grect(WORD kind,const GRECT *rectangle);
WORD wind_open_grect(WORD handle,const GRECT *rectangle);
WORD wind_get_grect(WORD handle,WORD field,GRECT *rectangle);
WORD wind_set_grect(WORD handle,WORD field,const GRECT *rectangle);
WORD wind_calc_grect(WORD type,WORD kind,const GRECT *rectangle,GRECT *result);
#endif
