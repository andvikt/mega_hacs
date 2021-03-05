import struct

print(struct.unpack('!f', bytes.fromhex('435c028f'))[0])