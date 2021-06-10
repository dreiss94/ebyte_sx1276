#!/usr/bin/python3

import socket
import sys
import os, os.path
import time
from routing import lsdb as lsdb
from routing import routingTable as routingTable
from routing import myAddress as myAddress

e32_sock = "/run/e32.socket"
csock_file = "/tmp/client1"

if os.path.exists(csock_file):
  os.remove(csock_file)

csock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
csock.bind(csock_file)

print("registering socket", e32_sock)
csock.sendto(b'', e32_sock)
(msg, address) = csock.recvfrom(10)

if msg[0] != 0:
    print("bad return code exiting")
    sys.exit(1)

#print("registering")
#csock.sendto(b'', e32_sock)
#(bytes, address) = csock.recvfrom(10)
#print("return code", bytes[0])


destination = 255
nextHop     = 255

message = [myAddress, destination, nextHop] # Source, Destination, Identifier
#message = [myAddress, destination-250, nextHop-1, 0, 2] # Source, Version, Identifier, Neighbour1, Neighbour2


barr = bytearray(message)
try:
    while True:
        print("sending", message)
        csock.sendto(barr, e32_sock)
        (bytes, address) = csock.recvfrom(10)
        print("return code", bytes[0])
        time.sleep(10)

finally:
    csock.close()

    if os.path.exists(csock_file):
        os.remove(csock_file)
