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
from collections import Counter
import hashlib
import json
import random

client_sock = "/home/pi/client"
e32_sock = "/run/e32.data"
e32_control = "/run/e32.control"
ctl_client = "/home/pi/ctl"

# run e32 as service in the background
os.system("sudo systemctl stop e32")
os.system("sudo systemctl daemon-reload")
os.system("sudo systemctl start e32")

# globals
serial_number = 10
neighbours = [serial_number] # [version, N1, N2, N3, ..., Nn]
new_hello = []
hello_sent = [-1, 0, 0, 0]
hello_offset = [-1, 0, 0, 0]
hello_received = [-1, 0, 0, 0]
hello_percentage = [-1, -1, -1, -1]

controller = 1
is_controller = True

routingTable = {}

hash_difference = False

lsdb = {}

current_adr = 0x1a # default (2.4kbps)
default_channel = 0x1a # default (2.4kbps)

joining_nodes = []

start_dijkstra = threading.Event()
stop_listen = threading.Event()
stop_hello = threading.Event()
go_rendez_vous = threading.Event()


def register_socket(s):
    """registers clients for e32.data socket"""

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
    """opens a client for e32.control socket"""

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
    """ get the settings, adjusts air data rate and changes it for the e32"""

    time.sleep(2)
    
    # get the raw settings
    bytes = get_settings()

    bytes_new = bytearray(bytes)  # make it mutable

    # change the air_data_rate
    bytes_new[3] = adr
    # bytes_new[0] = 0xc2 # C0: save on powerdown. C2 is bugged at the moment, it receives err 07.

    # change the settings
    ctl_sock.sendto(bytes_new, e32_control)
    (res, address) = ctl_sock.recvfrom(6)
    time.sleep(10)
    print("change setting response: ", res)

    # check new settings
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

def send_rendez_vous_hello():
    # send hello: [255, source, current air data rate]
    message = [255, 255, current_adr]
    print("rendez-vous hello:", bytearray(message))
    send(bytearray(message))

def advertise_default_channel():
    # send hello: [255, source, default_channel]
    message = [255, 255, default_channel]
    print("advertising default channel:", bytearray(message))
    send(bytearray(message))

def send_hello():
    """
    send Hello message
    Structure: [255, source, counter, beginning_of_hash]
    Timeout: 30s
    every 10th message is on rendez-vous channel at 0.3kbps 
    """
    counter = random.randint(1,9)
    while not stop_hello.is_set():
        
        # change to rendez-vous channel
        if (counter % 10) == 0 and not routingTable:

            print("changing to rendez-vous channel to advertise mesh channel")

            global stop_listen
            stop_listen.set()

            t.cancel()

            # get current adr
            current_adr = get_adr()
            print("current ADR: ", current_adr)
            time.sleep(5)

            # change air data rate to 300bps
            change_adr(0x18)

            stop_listen.clear()

            # time.sleep(5)

            # stay on rendez-vous for 2 mins to gather information if node wants to join
            for i in range(1,4):

                send_rendez_vous_hello()
                time.sleep(25)
            
            # go back to current air data rate and inform controller about joining nodes

            stop_listen.is_set()
            change_adr(current_adr)
            stop_listen.clear()

            newTimer()
            t.start()

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
    """changes the current channel and then starts sending hello messages"""

    global stop_listen
    global stop_hello

    stop_listen.set()

    change_adr(adr)
    
    stop_listen.clear()

    # start sending hellos and reset 5 min timer
    stop_hello.clear()
    print("restarting timer and hello messages")
    new_hello_thread()
    send_hello_msg.start()
    newTimer()
    t.start()

def increase_serialnumber():
    """Increments version of neighbour-list by 1"""
    global serial_number
    serial_number += 1

def send_LSAs():
    """sends all LSDB entries in LSA structure: [254, Source/Key, version, neighbour1, neighbour2, ...]"""
    
    for key, value in lsdb.items():

        message = [254, key, value[0]]
        message.extend(value[1:])
        print("sending", message)
        send(bytearray(message))
        time.sleep(3)

def request_LSA(target):
    """"Requests LSA at node that has different hash"""

    # send hello first (timeout = 30s) to make sure other node has entry

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

def update_rt():
    """runs Dijkstra to update the Routing Table"""

    time.sleep(60)

    global start_dijkstra

    while start_dijkstra.is_set():
        global routingTable
        threadLock.acquire()
        rt = dijkstra(lsdb)
        routingTable = rt
        threadLock.release()

        start_dijkstra.clear()

        for key in routingTable.keys():
            print("For Destination ", key, "the Next Hop is ", routingTable[key])
        
        time.sleep(180)

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

def sendto_controller():
    """
    send packets received ratios to controller in multi-hop manner
    """

    next_hop = routingTable[controller]
    for i in range(1, len(neighbours)):
        # [next-hop, source, destination, payload]
        msg = [next_hop, myAddress, controller, neighbours[i], hello_percentage[i]]
        barr = bytearray(msg)
        print("Sending stats to controller", msg)
        send(barr)
        time.sleep(3)

def go_to_rendez_vous():
    """switches to rendez-vous channel when no hello messages are received for 5 minutes"""
    print("No messages received in 5 minutes: changing to rendez-vous channel")

    global stop_listen
    global stop_hello

    stop_listen.set()
    stop_hello.set()
    set_adr(0x18)
    # change air data rate to 300bps
    change_adr(0x18)

    stop_listen.clear()
    # stop_hello.clear()

    time.sleep(2)
    
    # advertise default channel if this node is controller
    if controller == myAddress:
        for i in range(1,4):
            advertise_default_channel()
            time.sleep(30)
        print("Joining default channel")
        join_mesh(default_channel)


def newTimer():
    """creates a new gobal timer with countdown 5 min,
    when countdown finishes, node goes to rendez-vous channel"""
    global t
    t = threading.Timer(300.0, go_to_rendez_vous)

def new_hello_thread():
    """creates new send_hello_msg thread"""
    global send_hello_msg
    send_hello_msg = threading.Thread(target=send_hello, daemon = True)

def listen():

    while not stop_listen.is_set():
        # receive from the e32
        (msg, address) = sock_listen.recvfrom(59)
        print("received", len(msg), msg)
        
        try:
            message = [x for x in msg]
            identifier = message[0]
            source = message[1]
            
        except:
            pass
        
        if identifier == myAddress:
            # multi-hop
            try:
                destination = message[2]

                if destination == myAddress:
                    print(f"Message {msg} arrived at destination {myAddress} with payload: {message[3:]}")
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

            send_LSAs()


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

                
                elif message[2]  == 0x18:
                    print("received hello on rendez vous, 0x18")
                
                elif message[2] == 0x19 or message[2] == 0x1a or message[2] == 0x1b or message[2] == 0x1c or message[2] == 0x1d:
                    # handle rendezvous hello [255, 255, current_adr]
                    print("received hello on rendezvous, changing settings")
                    
                    # save channel and let channel advertiser know, that I want to join
                    set_adr(message[2])
                    time.sleep(2)
                    send_ack()
                    time.sleep(2)

                    # join mesh
                    join_mesh(current_adr)

            else:
                # standard hello message [255, source, counter, hash]
                global neighbours
                global new_hello
                global hello_received
                global hello_sent
                global hello_offset
                # print("reset timer and start again")
                t.cancel()
                newTimer()
                t.start()
                # print("timer started")
                if source not in neighbours:
                    new_hello.append(source)
                    c = Counter(new_hello)
                    print(c)

                    # add node to neighbours after 3 hellos are received.
                    if c[source] >= 3:
                        while source in new_hello: new_hello.remove(source)
                        print(new_hello)

                        increase_serialnumber()
                        neighbours.append(source)
                        print("neighbours updated:", neighbours)
                        # update own LSDB enty
                        update_own_lsdb_entry()
                        # reset counter for statistics
                        hello_offset[neighbours.index(source)] = message[2]
                
                
                elif len(message) > 3:
                    print("myhash", int.from_bytes(dict_hash()[:1], "big"), "vs", message[3], "other hash")
                    if int.from_bytes(dict_hash()[:1], "big") != message[3]:
                        send_LSAs()
                        time.sleep(5)
                        request_LSA(source)
                        if not update_routing_table.is_alive():
                            update_routing_table.start()
                            start_dijkstra.set()
                        else:
                            time.sleep(60)
                            start_dijkstra.set()
                        
                    # gather packets lost stats
                    index = neighbours.index(source)
                    # update hello_counter
                    hello_received[index] += 1
                    # update hello_percentage
                    global hello_percentage
                    hello_percentage[index] = 100 * hello_received[index] / (message[2] - hello_offset[index])

        else:
            print("Message ", msg, " discarded because Im not next hop")


sock_listen = register_socket(client_sock)
sock_send = register_socket(client_sock+"1")
ctl_sock = open_ctl_socket()

new_hello_thread()
listen = threading.Thread(target=listen, daemon = True)
update_routing_table = threading.Thread(target=update_rt, daemon= True)

#go_to_rendez_vous = threading.Thread(target=go_to_rendez_vous, daemon = True)
newTimer()

threadLock = threading.Lock()

print("starting listen")
listen.start()

time.sleep(3)


print("starting send_hello")
send_hello_msg.start()

t.start()

# while True:
#     time.sleep(15)
#     for thread in threading.enumerate(): 
#         print(thread.name)

time.sleep(600)



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











