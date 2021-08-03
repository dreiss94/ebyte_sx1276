#!/usr/bin/python3

import socket
import sys
import os, os.path
from pathlib import Path
import time
import threading
from routing import myAddress as myAddress
from dijkstra import dijkstra
from typing import Dict, Any
import hashlib
import json

client_sock = "/home/pi/client"
e32_sock = "/run/e32.data"
e32_control = "/run/e32.control"
ctl_client = "/home/pi/ctl"

# fix socket permissions
os.system("sudo systemctl stop e32")
os.system("sudo systemctl daemon-reload")
os.system("sudo systemctl start e32")
# os.system("sudo chown -R pi " + e32_sock)
# os.system("sudo chmod -R u=rwx " + e32_sock)


serial_number = 10
neighbours = [serial_number] # [version, N1, N2, N3, ..., Nn]
hello_counter = [-1, 0, 0, 0]
hello_percentage = [-1, -1, -1, -1]

controller = -1

routingTable = {}

hash_difference = False

lsdb = {}

current_adr = 0x1a # default (2.4kbps)

joining_nodes = []

stop_event = threading.Event()


def register_socket(s):

    if os.path.exists(s):
        os.remove(s)

    csock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    csock.bind(s)

    print("registering socket", s)
    csock.sendto(b'', e32_sock)
    (msg, address) = csock.recvfrom(10)
    print("return code", msg[0])

    if msg[0] != 0:
        print("bad return code exiting")
        sys.exit(1)
    
    return csock

def open_ctl_socket():

    if os.path.exists(ctl_client):
        os.remove(ctl_client)
    
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client_socket.bind(ctl_client)

    return client_socket

def close_sock():
    """ close the socket and delete the file """
    global client_sock
    global sock_send
    global sock_listen
    global e32_control

    print("closing client socket", client_sock)

    sock_listen.close()
    sock_send.close()

    if os.path.exists(client_sock):
        os.remove(client_sock)
    if os.path.exists(client_sock+"1"):
        os.remove(client_sock+"1")

def set_adr(adr):
    """sets current_adr to adr"""
    global current_adr
    current_adr = adr

def get_adr() -> bytes:
    """get current air data rate setting"""
    ctl_sock.sendto(b's', e32_control)
    (bytes, address) = ctl_sock.recvfrom(6)
    print("get_adr received:", bytes)
    try:
        r = bytes[3]
    except:
        r = 26
    return r

def change_adr(adr):
    """ get the settings, change air data rate"""
    
    global sock_send
    global sock_listen

    time.sleep(2)

    bytes = get_settings()

    bytes_new = bytearray(bytes)  # make it mutable

    # change the air_data_rate
    bytes_new[3] = adr
    # bytes_new[0] = 0xc2

    # change the settings
    ctl_sock.sendto(bytes_new, e32_control)
    (res, address) = ctl_sock.recvfrom(6)
    time.sleep(10)
    print("change setting response: ", res)
    

    # close_sock()
    # time.sleep(2)
    # os.system("sudo systemctl stop e32")
    # os.system("sudo systemctl daemon-reload")
    # os.system("sudo systemctl start e32")
    # os.system("sudo chown -R pi " + e32_sock)
    # os.system("sudo chmod -R u=rwx " + e32_sock)

    # sock_listen = register_socket(client_sock)
    # sock_send = register_socket(client_sock+"1")
    
    # time.sleep(3)

    ctl_sock.sendto(b's', e32_control)
    (settings, address) = ctl_sock.recvfrom(6)
    print("settings are updated: ", settings)

    time.sleep(5)



def get_settings()-> bytes:
    """get settings value from the control socket"""
    ctl_sock.sendto(b's', e32_control)
    (bytes, address) = ctl_sock.recvfrom(6)
    print("get_settings received:", bytes)
    return bytes


def send(bytearray):
    """Sends a bytearray to the SEND socket"""
    threadLock.acquire()
    sock_send.sendto(bytearray, e32_sock)
    (bytes, address) = sock_send.recvfrom(10)
    print("return code", bytes[0])
    threadLock.release()
    
def send_hello():
    """
    send Hello message
    Structure: [255, source, counter, beginning_of_hash]
    Timeout: 30s
    every 10th message is on rendez-vous channel at 0.3kbps 
    """
    counter = 1
    while True:
        
        # change to rendez-vous channel
        if (counter % 10) == 0:

            print("changing to rendez-vous channel")

            global stop_event
            stop_event.is_set()

            # get current adr
            current_adr = get_adr()
            print("current ADR: ", current_adr)
            time.sleep(5)

            # change air data rate to 300bps
            change_adr(0x18)

            stop_event.clear()

            # time.sleep(5)

            # stay on rendez-vous for 2 mins to gather information if node wants to join
            for i in range(1,4):

                # send hello: [255, source, current air data rate]
                message = [255, 255, current_adr]
                print("rendez-vous hello:", bytearray(message))
                send(bytearray(message))
                time.sleep(25)
            
            # go back to current air data rate and inform controller about joining nodes

            stop_event.is_set()
            change_adr(current_adr)
            stop_event.clear()

        #     # TODO inform controller

            time.sleep(1)

        # normal Hello messages
        # [255, source, counter, beginning_of_hash]
        hash = dict_hash()[:1]

        message = [255, myAddress, counter]
        barr = bytearray(message)
        
        barr.extend(hash)

        print("sending hello", barr)
        send(barr)
        counter += 1
        time.sleep(30)


def send_hello_once():
    """
    send Hello message once
    Structure:  [255, source]
    """

    # [255, source, counter, beginning_of_hash]

    message = [255, myAddress]
    barr = bytearray(message)

    print("sending extra hello", barr)
    send(barr)

def send_ack():
    """
    send Hello message once
    Structure: [255, 255, 255, Source]
    """
    # send ack to hello in rendez-vous channel
    # [255, 255, Source]
    message = [255, 255, 255, myAddress]
    barr = bytearray(message)

    print("sending ack", barr)
    send(barr)

def join_mesh(adr):
    stop_event.is_set()

    change_adr(adr)
    
    stop_event.clear()

    # start sending hellos
    global send_hello
    send_hello.start()

def increase_serialnumber():
    """Increments version of neighbour-list by 1"""
    global serial_number
    serial_number += 1

def request_LSA(target):
    """"Requests LSA at node that has different hash"""

    # send hello first (timeout = 30s) to make sure other node has entry
    time.sleep(5)

    send_hello_once()

    time.sleep(5)

    message = [253, myAddress, target] 
    barr = bytearray(message)
    
    print("requesting LSA", message)
    send(barr)

def update_own_lsdb_entry():
    """
    updates entry in LSDB: key == myAddress
    lsdb{address: [version, neighb1, neighb2, ... neighbN]}
    """

    global lsdb

    neighbours[0] = serial_number

    lsdb[myAddress] = neighbours
    print(lsdb)

def lsdb_set_lsa(lsa):
    """
    Sets lsa to Link State Database
    LSA: [Indentifier, Source/Key, version, neighbour1, neighbour2, ...]
    lsdb{address: [version, neighb1, neighb2, ... neighbN]}
    """

    global lsdb

    value = lsa[2:]

    lsdb[lsa[1]] = value
    print(lsdb)

def dict_hash() -> bytes:
    """SHA1 hash of dictionary LSDB."""
    dhash = hashlib.sha1()
    # We need to sort arguments
    global lsdb
    encoded = json.dumps(lsdb, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.digest()

def elect_controller() -> int:
    """
    elects controller with highest ID in LSDB
    returns ID
    """
    try:
        controller = max(lsdb.keys())
    except:
        controller = -1
    return controller

def send_controller():
    """
    send packets received ratios to controller in multi-hop manner
    """

    next_hop = routingTable[controller]
    for i in range(1, len(neighbours)):
        # [next-hop,source, destination, payload]
        msg = [next_hop, myAddress, controller, neighbours[i], hello_percentage[i]]
        barr = bytearray(msg)    
        print("Sending stats to controller", msg)
        send(barr)
        time.sleep(3)


def listen():

    while not stop_event.is_set():
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
        
        
        elif identifier == 253:
            # handle LSA request: send all entries in LSDB
            time.sleep(1)
            print("answering LSA Request")

            for key, value in lsdb.items():

                message = [254, key, value[0]]
                message.extend(value[1:])
                print("sending", message)
                send(bytearray(message))
                time.sleep(3)


        elif identifier == 254:
            # handle LSA [Indentifier, Source/Key, version, neighbour1, neighbour2, ...]

            if source != myAddress:
                # only gather information about foreign nodes

                if source not in lsdb.keys() or lsdb[source][0] < message[2]:
                    lsdb_set_lsa(message)


        elif identifier == 255:
            # handle hello messages [255, source, counter, hash]

            if source == 255:

                if message[2] == 255:
                    # handle rendez-vous ack [255, 255, 255, Source]
                    global joining_nodes
                    joining_nodes.append(message[3])

                
                else:
                    # handle rendezvous hello [255, 255, current_adr]
                    print("received hello on rendezvous")
                    
                    # save channel and let channel advertiser know, that I want to join
                    set_adr(message[2])
                    time.sleep(2)
                    # send_ack()
                    time.sleep(2)

                    # join mesh
                    join_mesh(current_adr)

            else:
                global neighbours
                if source not in neighbours:  
                    increase_serialnumber()
                    neighbours.append(source)
                    print("neighbours updated:", neighbours)
                    # update own LSDB enty
                    update_own_lsdb_entry()
                    # lsdb_set_entry(myAddress, serial_number, neighbours)
                    # lsdb_set_entry(source, serial_number, neighbours)
                
                
                if len(message) > 3:
                    print("myhash", int.from_bytes(dict_hash()[:1], "big"), "vs", message[3], "other hash")
                    if int.from_bytes(dict_hash()[:1], "big") != message[3]:
                        request_LSA(source)
                    
                    # gather packets lost stats
                    index = neighbours.index(source)
                    # update hello_counter
                    global hello_counter
                    hello_counter[index] += 1
                    # update hello_received
                    global hello_percentage
                    hello_percentage[index] = 100 * hello_counter[index] / message[2]

        else:
            print("Message ", msg, " discarded because Im not next hop")


sock_listen = register_socket(client_sock)
sock_send = register_socket(client_sock+"1")
ctl_sock = open_ctl_socket()

send_hello = threading.Thread(target=send_hello, daemon = True)
listen = threading.Thread(target=listen, daemon = True)
# build_lsa = threading.Thread(target=construct_lsdb)


threadLock = threading.Lock()

print("starting send_hello")
send_hello.start()

time.sleep(3)

print("starting listen")
listen.start()


time.sleep(180)



# for i in range(3):
#     print("LSDB:", lsdb)
#     time.sleep(60)

# time.sleep(180)

# cleanup
sock_listen.close()
sock_send.close()

if os.path.exists(client_sock):
    os.remove(client_sock)

if os.path.exists(client_sock+"1"):
    os.remove(client_sock+"1")


os.system("sudo systemctl stop e32")

sys.exit()


# threadLock.acquire()
# rt = dijkstra(lsdb)
# routingTable = rt
# threadLock.release()

# for key in routingTable.keys():
#     print("For Destination ", key, "the Next Hop is ", routingTable[key])







