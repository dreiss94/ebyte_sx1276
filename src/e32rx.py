#!/usr/bin/python3

import socket
import sys
import os, os.path
import time
import threading
from routing import myAddress as myAddress
from dijkstra import dijkstra
from typing import Dict, Any
import hashlib
import json

client_sock = "/home/pi/client"
e32_sock = "/run/e32.socket"

# fix socket permissions
os.system("sudo chown -R pi " + e32_sock)
os.system("sudo chmod -R u=rwx " + e32_sock)

neighbours = []

routingTable = {}

serial_number = 10

lsdb = {}

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
    
def send_hello() -> int:
    """
    send Hello message
    Structure: [255, source, counter, beginning_of_hash]
    Timeout: 10s
    """
    counter = 0
    while True:
        
        # [255, source, counter, beginning_of_hash]
        hash = dict_hash(lsdb)[:1]

        message = [255, myAddress, counter]
        barr = bytearray(message)
        
        barr.extend(hash)

        print("sending hello", barr)
        send(barr)
        time.sleep(10)
        counter += 1

def increase_serialnumber():
    global serial_number
    serial_number += 1

def request_LSA(target):
    """"Requests LSA at node that has different hash"""

    message = [253, myAddress, target] 
    barr = bytearray(message)
    
    print("requesting LSA", message)
    send(barr)


def construct_lsdb():
    """"builds Link State Database as a dictionary"""

    increase_serialnumber()
    lsdb[myAddress] = neighbours

    # send LSA
    message = [254, myAddress, 3] # Indentifier, Source, TTD, neighbour1, neighbour2, ...
    message.extend(neighbours)

    barr = bytearray(message)

    for i in range(5):
        print("sending", message)
        send(barr)
        time.sleep(10)


def dict_hash(dictionary: Dict[Any, Any]) -> bytes:
    """SHA1 hash of a dictionary."""
    dhash = hashlib.sha1()
    # We need to sort arguments
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.digest()

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
            # handle LSA [Indentifier, Source, TTD, neighbour1, neighbour2, ...]

            if source not in lsdb.keys() or lsdb[source] != message[3:]:
                lsdb[source] = message[3:]
                increase_serialnumber()
            
            if source != myAddress and message[2] > 0:
                message[2] -= 1
                print("repeating foreign LSA")
                send(bytearray(message))
            
            if not build_lsa.is_alive():
                build_lsa.start()

        elif identifier == 255:
            # handle hello messages [255, source, counter, hash]
            
            if source not in neighbours:
                increase_serialnumber()
                neighbours.append(source)
                print("neighbours updated:", neighbours)
            
            if message[3] != dict_hash(lsdb):
                request_LSA(source)
            
            # gather packets lost stats

        else:
            print("Message ", msg, " discarded because Im not next hop")


sock_listen = register_socket(client_sock)
sock_send = register_socket(client_sock+"1")

send_hello = threading.Thread(target=send_hello)
listen = threading.Thread(target=multi_hop)
build_lsa = threading.Thread(target=construct_lsdb)


threadLock = threading.Lock()

print("starting send_hello")
send_hello.start()
# time.sleep(20)


print("starting listen")
listen.start()

send_hello.join()
print("say_hi finished: list of neighbours is updated")
print("my ID", myAddress , "my Neighbours:", neighbours, "\n")

time.sleep(10)

print("starting to construct lsdb")
if build_lsa.is_alive(): pass
else:
    build_lsa.start()

build_lsa.join()
print("lsdb constructing finished: lsbd is updated")

print("LSDB:", lsdb)

time.sleep(10)

threadLock.acquire()
rt = dijkstra(lsdb)
routingTable = rt
threadLock.release()

for key in routingTable.keys():
    print("For Destination ", key, "the Next Hop is ", routingTable[key])








