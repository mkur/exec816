dim A(4), B(3) byte
for I=0 to 4
  A(I)=I*I
next
? A(0)+A(1)+A(2)+A(3)+A(4)
X=1234
Y=17
? X*Y
? X/Y
? X MOD Y
S$="ABC"
S$=+"def"
? S$[2,4]
? VAL(" -123")
proc Say
  ? "PROCEDURE"
endproc
exec Say
dim Copy(8) byte
for I=0 to 7
  Copy(I)=I+10
next
-move adr(Copy),adr(Copy)+1,7
move adr(Copy)+1,adr(Copy),7
? Copy(0)+Copy(6)
? DPEEK($FF)
