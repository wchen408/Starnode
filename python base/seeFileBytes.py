import os


f = open ("checking.jpeg", 'wb')
b = open("beauty.jpeg", 'rb')

for byte in b:
    print(byte, end='')
    f.write(byte)

f.close()
b.close()
