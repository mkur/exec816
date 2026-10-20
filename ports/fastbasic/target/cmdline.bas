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
SourceName$ = ""
DiagnosticName$ = ""
JobName$ = ""
LastError=0
dim Diagnostic(9)
dim MemStart(-1) byte
MemEnd = adr(MemStart)
dim NewPtr
ArgNumber = 0

proc FileError
  Diagnostic(1)=LastError
  if len(DiagnosticName$) then i = usr(@FB_ERROR, 1)
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
SourceName$=FileName$
i=usr(@FB_ARGUMENT, 2)
if i then DiagnosticName$=$(i)
i=usr(@FB_ARGUMENT, 3)
if i then JobName$=$(i)
Diagnostic(0)=1
Diagnostic(1)=0
Diagnostic(2)=@@LINENUM
Diagnostic(3)=@@BMAX
Diagnostic(4)=@COMP_DIAG_ERROR
Diagnostic(5)=@FB_DIAG_MESSAGES
Diagnostic(6)=adr(SourceName$)
Diagnostic(7)=adr(DiagnosticName$)
Diagnostic(8)=adr(JobName$)
if len(DiagnosticName$) or len(JobName$)
  i=usr(@FB_DIAGNOSTIC, adr(Diagnostic))
endif
open #1, 4, 0, FileName$
LastError=err()
if LastError > 127 then exec FileError
bget #1, adr(MemStart), dpeek(@MEMTOP) - adr(MemStart)
LastError=err()
if LastError <> 136 then exec FileError
MemEnd = dpeek($358) + adr(MemStart)
close #1
LastError=err()
if LastError > 127 then exec FileError
' Compact CRLF while accepting LF, CR and the ATASCII documents from EDX.
r = adr(MemStart)
w = r
SourceLine=1
SourceColumn=0
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
  if v=$9B
    inc SourceLine
    SourceColumn=0
  else
    if SourceColumn=255 or (v<>9 and (v<32 or v>126))
      Diagnostic(0)=2
      Diagnostic(1)=256
      if SourceColumn=255 then Diagnostic(1)=257
      dpoke @@LINENUM,SourceLine
      poke @@BMAX,SourceColumn
      ? "Invalid source at line ";SourceLine;" column ";SourceColumn
      i=usr(@FB_ERROR,2)
      end
    endif
    inc SourceColumn
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
Diagnostic(0)=2
if usr(@COMPILE_BUFFER, MemEnd)
  ? " at line "; dpeek(@@LINENUM); " column "; peek(@@BMAX)
  i = usr(@FB_ERROR, 2)
  end
endif
exec InputFileName
Diagnostic(0)=3
open #1, 8, 0, FileName$
LastError=err()
if LastError > 127 then exec FileError
bput #1, @COMP_HEAD_1, 16
LastError=err()
if LastError > 127 then exec FileError
bput #1, @__JUMPTAB_RUN__, @COMP_RT_SIZE
LastError=err()
if LastError > 127 then exec FileError
bput #1, MemEnd, NewPtr - MemEnd + 1
LastError=err()
if LastError > 127 then exec FileError
close #1
LastError=err()
if LastError > 127 then exec FileError
Diagnostic(0)=4
Diagnostic(1)=0
? "Compiled "; FileName$
