;
; FastBasic - Fast basic interpreter for the Atari 8-bit computers
; Copyright (C) 2017-2025 Daniel Serpell
;
; This program is free software; you can redistribute it and/or modify
; it under the terms of the GNU General Public License as published by
; the Free Software Foundation, either version 2 of the License, or
; (at your option) any later version.
;
; This program is distributed in the hope that it will be useful,
; but WITHOUT ANY WARRANTY; without even the implied warranty of
; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
; GNU General Public License for more details.
;
; You should have received a copy of the GNU General Public License along
; with this program.  If not, see <http://www.gnu.org/licenses/>
;

; Compiled header written from the IDE
; ------------------------------------

; Exec816 FastBasic profile. Addresses name the invocation's private bank.
.include "fastbasic.inc"
.import start, bytecode_start
.import __CODE_RUN__, __CODE_SIZE__, __RUNTIME_RUN__, __RUNTIME_SIZE__, __DATA_SIZE__
.import __JUMPTAB_RUN__
.export COMP_HEAD_1, COMP_HEAD_2, COMP_RT_SIZE, BYTECODE_ADDR
BYTECODE_ADDR = __RUNTIME_RUN__ + __RUNTIME_SIZE__ + __DATA_SIZE__
COMP_RT_SIZE = BYTECODE_ADDR - FB_LOAD
.segment "PREHEAD"
COMP_HEAD_1:
.byte "FB65"
.word FB_VERSION, FB_TARGET
COMP_HEAD_2:
.word FB_LOAD, __CODE_RUN__+__CODE_SIZE__
.word start, FB_LIMIT
