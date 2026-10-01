/* Private renderer boundary. Exec types stay in separate translation units. */
#ifndef EXEC816_HOSTED_VDI_H
#define EXEC816_HOSTED_VDI_H
#include <stdint.h>
#include "vdi/vdidev.h"

uint16_t GemVdiBind(const VDIDEV *device);
uint16_t GemVdiValidate(uint16_t op, uint16_t sub, uint16_t pairs,
                       uint16_t words, const int16_t *points, const int16_t *ints);
uint16_t GemVdiDispatch(uint16_t op, uint16_t sub, uint16_t handle,
                       uint16_t pairs, uint16_t words,
                       const int16_t *points, const int16_t *ints);
extern const VDIDEV hosted_vbxe_device;
#endif
