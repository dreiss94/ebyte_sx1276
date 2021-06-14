#!/usr/bin/python3

import socket
import sys
import os, os.path
import time
import threading
from routing import myAddress as myAddress

client_sock = "/home/pi/client"
e32_sock = "/run/e32.socket"

# fix socket permissions
os.system("sudo chown -R pi " + e32_sock)
os.system("sudo chmod -R u=rwx " + e32_sock)

neighbours = []

routingTable = {}

lsdb = {"version" : 1}

def close_sock():
    global client_sock

    print("closing client socket")

    client_sock.close()

    if os.path.exists(client_sock):
      os.remove(client_sock)

def register_socket(s):

    if os.path.exists(s):
        os.remove(s)

    csock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    csock.bind(s)

    print("registering socket", e32_sock)
    csock.sendto(b'', e32_sock)
    (msg, address) = csock.recvfrom(10)

    if msg[0] != 0:
        print("bad return ode exiting")
        sys.exit(1)
    
    return csock

def send(bytearray):
    threadLock.acquire()
    sock_send.sendto(bytearray, e32_sock)
    (bytes, address) = sock_send.recvfrom(10)
    print("return code", bytes[0])
    threadLock.release()
    
def send_hello():

    message = [255, myAddress] # 255, source

    barr = bytearray(message)

    for i in range(5):
        print("sending", message)
        send(barr)
        time.sleep(5)
        
def send_lsa():

    lsdb["version"] = lsdb["version"] + 1

    message = [254, myAddress, lsdb["version"], 5] # Indentifier, Source, Version, TTD, neighbour1, neighbour2, ...
    message.extend(neighbours)

    barr = bytearray(message)

    for i in range(5):
        print("sending", message)
        send(barr)
        time.sleep(10)


def multi_hop():

    while True:
        # receive from the e32
        (msg, address) = sock_listen.recvfrom(59)
        print("received", len(msg), msg)
        
        try:
            message = [x for x in msg]
            identifier = message[0]
            source = message[1]
            
            # source = message[0]
            # identifier = message[2]
        except:
            pass
        
        if identifier == myAddress:

            # multi-hop
            try:
                destination = message[2]

                if destination == myAddress:
                    print("Message ", msg, " arrived at destination ", myAddress)
                else:
                    fwd_message = [routingTable[destination], source, destination]
                    barr = bytearray(fwd_message)

                    print("forwarding message", fwd_message)
                    sock_send.sendto(barr, e32_sock)
                    (bytes, address) = sock_send.recvfrom(10)
                    print("return code", bytes[0])
            
            except:
                pass
        
        
        elif identifier == 254:

            # handle LSA [Indentifier, Source, Version, TTD, neighbour1, neighbour2, ...]

            version = message[2]
            myversion = lsdb["version"]

            if myversion > version:
                pass

            elif myversion <= version:

                if version == myversion:

                    if source not in lsdb.keys():
                        lsdb[source] = message[4:]

                    elif lsdb[source] != message[4:]:
                        lsdb[source] = message[4:]
                
                else:
                    if build_lsa.is_alive():
                        if lsdb[source] != message[4:]:
                            lsdb[source] = message[4:]
                    else:
                        lsdb["version"] = myversion + 1
                        build_lsa.start()
            
            else:
                pass

            if source != myAddress and message[4] > 0 and version >= myversion:
                message[4] -= 1
                print("repeating foreign LSA")
                send(bytearray(message))
        




        elif identifier == 255:

            # handle hello messages [255, source]
            
            if source not in neighbours:
                neighbours.append(source)
                print("neighbours updated:", neighbours)

        else:
            print("Message ", msg, " discarded because Im not next hop")


sock_listen = register_socket(client_sock)
sock_send = register_socket(client_sock+"1")

send_hello = threading.Thread(target=send_hello)
listen = threading.Thread(target=multi_hop)
build_lsa = threading.Thread(target=send_lsa)

threadLock = threading.Lock()

print("starting send_hello")
send_hello.start()
print("starting listen")
listen.start()

send_hello.join()
print("say_hi finished: list of neighbours is updated")
print("my ID", myAddress , "my Neighbours:", neighbours, "\n")

time.sleep(10)

print("starting send_lsa")
if build_lsa.is_alive(): pass
else:
    lsdb["version"] = lsdb["version"] + 1
    build_lsa.start()

build_lsa.join()
print("send_lsa finished: lsbd is updated")

print("LSDB:", lsdb)





