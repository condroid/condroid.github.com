#!/usr/bin/python
import os
import os.path
print("input filename")
filename=raw_input()
print("filename is"+filename) 
oldmd = file(filename,"r")
newmd = file(filename+".bak","w")
flag =0
for line in oldmd:
	if "```" in line:
		flag = 1-flag
		newmd.write("\n")
	elif flag:
		newmd.write("\t"+line)	
	else:
		newmd.write(line)

oldmd.close()
newmd.close()
os.remove(filename)
os.rename(filename+".bak",filename)
