import json 
import base64
import os

f = open ("small.svg", "rb" )
data = base64.encodebytes(f.read())
f.close()
data = data.decode("ascii")
packet = {"data": data}
jpacket = json.dumps(packet)


print("len(json_obj): ", len(jpacket))
unpacked = json.loads(jpacket)
unpacked = unpacked["data"].encode("ascii")
unpacked = base64.decodebytes(unpacked)

nf = open("newsvg.svg", "wb")
nf.write(unpacked)
nf.close()
