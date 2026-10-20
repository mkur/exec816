T=TIME
pause 1
? TIME-T>0
for I=0 to 19
  X=RAND(17)
  if X<0 OR X>=17 then ? "BAD RANDOM"
next
? "RANDOM RANGE"
