'
' FastBasic - Fast basic interpreter for the Atari 8-bit computers
' Copyright (C) 2017-2025 Daniel Serpell
'
' This program is free software; you can redistribute it and/or modify
' it under the terms of the GNU General Public License as published by
' the Free Software Foundation, either version 2 of the License, or
' (at your option) any later version.
'
' This program is distributed in the hope that it will be useful,
' but WITHOUT ANY WARRANTY; without even the implied warranty of
' MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
' GNU General Public License for more details.
'
' You should have received a copy of the GNU General Public License along
' with this program.  If not, see <http://www.gnu.org/licenses/>
'
' In addition to the permissions in the GNU General Public License, the
' authors give you unlimited permission to link the compiled version of
' this file into combinations with other programs, and to distribute those
' combinations without any restriction coming from the use of this file.
' (The General Public License restrictions do apply in other respects; for
' example, they cover modification of the file, and distribution when not
' linked into a combine executable.)


' Exec816 on-machine FastBasic integer compiler. Donor parser/runtime remain 6502.
FileName$ = ""
dim MemStart(-1) byte
MemEnd = adr(MemStart)
dim NewPtr
ArgNumber = 0

proc FileError
  LastError=err()
  ? "File error: "; LastError
  ' Native cleanup closes channels while preserving this first failure.
  i = usr(@FB_ERROR, 1)
  end
endproc

proc InputFileName
  FileName$ = ""
  i = usr(@FB_ARGUMENT, ArgNumber)
  if i then FileName$ = $(i)
  if not len(FileName$)
    if ArgNumber=0
      ? "Source file: ";
    else
      ? "Output file: ";
    endif
    input FileName$
  endif
  inc ArgNumber
endproc

ArgNumber = 0
exec InputFileName
open #1, 4, 0, FileName$
if err() > 127 then exec FileError
bget #1, adr(MemStart), dpeek(@MEMTOP) - adr(MemStart)
if err() <> 136 then exec FileError
MemEnd = dpeek($358) + adr(MemStart)
close #1
if err() > 127 then exec FileError
' Compact CRLF while accepting LF, CR and the ATASCII documents from EDX.
r = adr(MemStart)
w = r
while r < MemEnd
  v = peek(r)
  inc r
  if v=13
    if r<MemEnd
      if peek(r)=10 then inc r
    endif
    v=$9B
  elif v=10
    v=$9B
  endif
  poke w,v
  inc w
wend
' A final EOL also makes empty and unterminated sources safe for the parser.
if w=adr(MemStart)
  poke w,$9B
  inc w
elif peek(w-1)<>$9B
  poke w,$9B
  inc w
endif
MemEnd=w
dpoke @@RELOC_OFFSET, @BYTECODE_ADDR - MemEnd
dpoke @@BUF_PTR, adr(MemStart)
if usr(@COMPILE_BUFFER, MemEnd)
  ? " at line "; dpeek(@@LINENUM); " column "; peek(@@BMAX)
  i = usr(@FB_ERROR, 2)
  end
endif
exec InputFileName
open #1, 8, 0, FileName$
if err() > 127 then exec FileError
bput #1, @COMP_HEAD_1, 16
if err() > 127 then exec FileError
bput #1, @__JUMPTAB_RUN__, @COMP_RT_SIZE
if err() > 127 then exec FileError
bput #1, MemEnd, NewPtr - MemEnd + 1
if err() > 127 then exec FileError
close #1
if err() > 127 then exec FileError
? "Compiled "; FileName$
