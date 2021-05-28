#!/usr/bin/python3

import socket
import sys
import os, os.path
import time

def close_sock():
    global client_sock

    print("closing client socket")

    client_sock.close()

    if os.path.exists(client_sock):
      os.remove(client_sock)

client_sock = "/home/pi/client"
e32_sock = "/run/e32.socket"

if os.path.exists(client_sock):
      os.remove(client_sock)

csock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
csock.bind(client_sock)

print("registering socket", e32_sock)
csock.sendto(b'', e32_sock)
(msg, address) = csock.recvfrom(10)

if msg[0] != 0:
    print("bad return ode exiting")
    sys.exit(1)

# row = 0

# msg = b"listening"
# command = bytearray([2, row, 3, len(msg)])
# command = command + bytearray(msg)
# print("sending", len(command), bytes(command))
# csock.sendto(bytes(command), ssd1306_sock)
# (msg, address) = csock.recvfrom(2)
# if msg[1] != 0:
#     print("bad value", msg[1], "at", msg[0])

while True:
    # receive from the e32
    (msg, address) = csock.recvfrom(59)
    print("received", len(msg), msg)

    myAddress = 2

    message = [x for x in msg]
    source = message[0]
    destination = message[1]
    next_hop = message[2]


    

    if destination == myAddress:
        print("Message ", msg, " arrived at destination ", myAddress)
    if next_hop == myAddress:
        fwd_message = [source, destination, destination]
        barr = bytearray(fwd_message)

        print("forwarding message", fwd_message)
        csock.sendto(barr, e32_sock)
        (bytes, address) = csock.recvfrom(10)
        print("return code", bytes[0])

