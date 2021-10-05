#!/usr/bin/python3

import socket
import sys
import os, os.path
from pathlib import Path
import numpy
import time
import threading

from numpy.core.records import array
from routing import myAddress as myAddress
from dijkstra import dijkstra, NUMBER_OF_NODES
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
n_time = [-1]
new_hello = []
hello_sent = numpy.full(NUMBER_OF_NODES+1, 0)
hello_offset = numpy.full(NUMBER_OF_NODES+1, 0)
hello_received = numpy.full(NUMBER_OF_NODES+1, 0)
hello_percentage = numpy.full(NUMBER_OF_NODES+1, 0)

stats = numpy.full([NUMBER_OF_NODES, NUMBER_OF_NODES], 0)

controller = 0 # BIN is the controller
HELLO_TIMEOUT = 60

routingTable = {}

hash_difference = False

lsdb = {}

current_adr = 0x19 # default (2.4kbps)
default_channel = 0x19 # 0x1a is default (2.4kbps) # here, its lowered

joining_nodes = []
counter = 0

start_dijkstra = False
stop_listen = threading.Event()
stop_hello = threading.Event()
stop_checking = threading.Event()



counter_LSA = 0
counter_LSR = 0

stop_increasing = False

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

def send_hello(advertising: bool):
    """
    send Hello message
    Structure: [255, source, counter, beginning_of_hash]
    Timeout: 30s
    if advertising == TRUE
        every 10th message is on rendez-vous channel at 0.3kbps 
    """
    counter = random.randint(1,9)
    start = counter
    while not stop_hello.is_set():
        
        if advertising:
            # change to rendez-vous channel
            if (counter % 10) == 0 and bool(routingTable):

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

                # stay on rendez-vous for 1 min to gather information if node wants to join
                for i in range(2):

                    send_rendez_vous_hello()
                    time.sleep(10)
                
                # go back to current air data rate and inform controller about joining nodes

                stop_listen.is_set()
                change_adr(current_adr)
                stop_listen.clear()

                new_Timer()
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
        print(f"\nNode {myAddress} has sent \t {counter - start} hello \t {counter_LSA} LSA \t {counter_LSR} LSR packets.\n")

        if myAddress == controller:
            # analyze stats
            #if (counter - start) % ((NUMBER_OF_NODES*2)+1) == 0:
            if (counter - start) % 9 == 0:
                analyse_stats()

        time.sleep(HELLO_TIMEOUT)


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
    time.sleep(random.randint(0,HELLO_TIMEOUT))
    stop_hello.clear()
    print("restarting timer and hello messages")
    new_hello_thread(True)
    send_hello_msg.start()
    new_Timer()
    t.start()

def increase_serialnumber():
    """Increments version of neighbour-list by 1"""
    global serial_number
    serial_number += 1

def send_LSAs():
    """sends all LSDB entries in LSA structure: [254, Source/Key, version, neighbour1, neighbour2, ...]"""
    global counter_LSA
    for key, value in lsdb.items():

        message = [254, key, value[0]]
        message.extend(value[1:])
        print("sending LSA", message)
        send(bytearray(message))
        time.sleep(random.randint(0,3))
        counter_LSA += 1
        print(f"\nNode {myAddress} has sent {counter_LSA} LSA packets.\n")

def request_LSA(target):
    """"Requests LSA at node that has different hash"""

    # send hello first (timeout = 30s) to make sure other node has entry

    global counter_LSR
    # time.sleep(5)

    message = [253, myAddress, target] 
    barr = bytearray(message)
    
    print("requesting LSA, sending LSR", message)
    send(barr)

    counter_LSR += 1
    print(f"\nNode {myAddress} has sent {counter_LSR} LSR packets")

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

    global start_dijkstra
    if start_dijkstra:

        global routingTable
        threadLock.acquire()
        rt = dijkstra(lsdb)
        routingTable = rt
        threadLock.release()

        for key in routingTable.keys():
            print("For Destination ", key, "the Next Hop is ", routingTable[key])
        start_dijkstra = False

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

def sendto_controller(index):
    """
    send packets received ratios to controller in multi-hop manner
    if node is controller, it updates the stats and recalculates the state of the mesh
    """
    if myAddress != controller:
        next_hop = routingTable[controller]
        # [next-hop, source, destination, payload]
        msg = [next_hop, myAddress, controller, neighbours[index], int(round(hello_percentage[index]))]
        barr = bytearray(msg)
        print("Sending stats to controller", msg)
        for i in range(2):
            send(barr)
            time.sleep(random.randint(0,5))
    else:
        # update controller statistics
        stats[myAddress] = hello_percentage[1:]
        # analyse_stats()
        print(stats)

def analyse_stats():
    """go through stats to determine state of mesh"""

    global counter
    global stop_increasing
    global lsdb

    print(f"analysing LSDB: checking if every entry has ingoing and outgoing edge..")

    increase = True


    # if stop_increasing == False:
    keys = lsdb.keys()
    if len(keys) < NUMBER_OF_NODES:
        increase = False
        decrease_speed()
    else:
        values = lsdb.values()
        vals = []
        for e in values:
            vals.extend(e)
        
        for i in keys:
            if i not in vals:
                increase = False
                # counter = 1
                decrease_speed()
                break

        if increase == True and stop_increasing == False:
            # counter = 1
            increase_speed()
        else:
            #stay
            print("staying on same channel")
            pass

        # if len(LSDB.keys()) == NUMBER_OF_NODES and :
        #     increase_speed()
        
        # elif len(LSDB.keys()) < NUMBER_OF_NODES:
        #     stop_increasing = True
        #     decrease_speed()


    # if counter >= NUMBER_OF_NODES:
    #     sum = 0
    #     count = 0
    #     for x in stats:
    #         for y in x:
    #             if y != 0:
    #                 # take percentage into consideration
    #                 sum += y
    #                 count += 1
        
    #     print(f"The average percentage is: {(sum/count)}")
    #     print(f"The number of single connections is: {(count)}")
    #     print(f"The number of connections is: {(count/2)}")
        
    #     if count > 2*(NUMBER_OF_NODES-1):
    #         print(f"count {count} > 2*nodes {(2*(NUMBER_OF_NODES-1))}, therefore increasing the speed")
    #         increase_speed()
        
    #     if count < 2*(NUMBER_OF_NODES-1):
    #         print(f"count {count} < 2*nodes {(2*(NUMBER_OF_NODES-1))}, therefore decreasing the speed")
    #         decrease_speed()


def send_new_adr(adr, bool):

    global stats
    stats = numpy.full([NUMBER_OF_NODES, NUMBER_OF_NODES], 0)

    # send first to further nodes
    for i in routingTable.keys():
        next_hop = routingTable[i]
        if i != routingTable[i]:
            # [next-hop, source, destination, payload]
            msg = [next_hop, myAddress, i, adr]
            barr = bytearray(msg)
            print(f"Sending adr to node {i}: msg")
            send(barr)
            time.sleep(1)
            if bool:
                print(f"Sending adr to node {i}: msg")
                send(barr)
                time.sleep(1)

        
    for i in routingTable.keys():
        next_hop = routingTable[i]
        if i == routingTable[i]:
            # [next-hop, source, destination, payload]
            msg = [next_hop, myAddress, i, adr]
            barr = bytearray(msg)
            print(f"Sending adr to node {i}: msg")
            send(barr)
            time.sleep(1)
            if bool:
                print(f"Sending adr to node {i}: msg")
                send(barr)
                time.sleep(1)

def increase_speed():
    print("advertise increased channel")

    adr = get_adr()
    time.sleep(3)
    
    if adr <= 28:

        adr += 1

        global routingTable

        send_new_adr(adr, False)
            
        global stop_listen
        global stop_hello
        global lsdb
        global neighbours
        global n_time
        global counter_LSA
        global counter_LSR

        counter_LSR = 0
        counter_LSR = 0

        stop_listen.set()
        stop_hello.set()
        set_adr(adr)
        t.cancel()

        lsdb.clear()
        neighbours.clear()
        neighbours.append(serial_number)
        routingTable.clear()
        n_time = [-1]


        time.sleep(5)

        # change air data rate to payload
        change_adr(adr)

        time.sleep(5)

        stop_listen.clear()
        # stop_hello.clear()

        # start sending hellos and reset 5 min timer
        time.sleep(random.randint(0,HELLO_TIMEOUT))
        stop_hello.clear()
        print("restarting timer and hello messages")
        new_hello_thread(True)
        send_hello_msg.start()
        new_Timer()
        t.start()

        time.sleep(2)

    else:
        print("Maximum air data rate is reached")

    
    #controller change speed


def decrease_speed():
    global stop_increasing
    stop_increasing = True
    print("advertise decreased channel")
    
    adr = get_adr()
    time.sleep(3)
    
    if adr >= 25:
        
        adr -= 1

        global routingTable

        send_new_adr(adr, True)
        
        global stop_listen
        global stop_hello
        global lsdb
        global neighbours
        global counter_LSA
        global counter_LSR

        counter_LSR = 0
        counter_LSR = 0

        stop_listen.set()
        stop_hello.set()
        set_adr(adr)

        lsdb.clear()
        neighbours.clear()
        neighbours.append(serial_number)
        routingTable.clear()

        time.sleep(5)

        # change air data rate to payload
        change_adr(adr)

        time.sleep(5)

        stop_listen.clear()
        # stop_hello.clear()

        # start sending hellos and reset 5 min timer
        time.sleep(random.randint(0,HELLO_TIMEOUT))
        stop_hello.clear()
        print("restarting timer and hello messages")
        new_hello_thread(True)
        send_hello_msg.start()
        new_Timer()
        t.start()

        time.sleep(2)
        
        
        


    else:
        print("Lowest air data rate is reached, consider building mesh on rendez vous channel")





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


def new_Timer():
    """creates a new gobal timer with countdown 5 min,
    when countdown finishes, node goes to rendez-vous channel"""
    global t
    t = threading.Timer(300.0, go_to_rendez_vous)

def check_neighbours():
    while not stop_checking.is_set():
        global neighbours
        if bool(neighbours[1:]):
            threadLock.acquire()
            global n_time
            indices_to_delete = []
            now = time.time()

            # check if last registered hello is older than 5 mins
            for t in n_time[1:]:
                diff = now-t
                if diff > 300:
                    indices_to_delete.append(n_time.index(t))
            indices_to_delete.reverse()
            for e in indices_to_delete:
                try:
                    del n_time[e]
                    del neighbours[e]
                except:
                    pass
                update_own_lsdb_entry()
                increase_serialnumber()
                
            threadLock.release()
        time.sleep(55)

def new_hello_thread(advertising: bool):
    """creates new send_hello_msg thread"""
    global send_hello_msg
    send_hello_msg = threading.Thread(target=send_hello, args=(advertising,), daemon = True)

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
                payload = message[3:]

                if destination == myAddress:
                    if len(payload) == 1:
                        # handle increasing or decreasing adr
                        
                        global stop_hello
                        global lsdb
                        global neighbours
                        global n_time
                        global counter_LSA
                        global counter_LSR

                        if current_adr != payload:

                            counter_LSR = 0
                            counter_LSR = 0

                            stop_listen.set()
                            stop_hello.set()
                            set_adr(message[3])
                            t.cancel()

                            time.sleep(10)

                            lsdb.clear()
                            neighbours.clear()
                            neighbours.append(serial_number)
                            routingTable.clear()
                            n_time = [-1]

                            time.sleep(5)

                            # change air data rate to payload
                            change_adr(message[3])

                            time.sleep(5)

                            stop_listen.clear()
                            # stop_hello.clear()

                            # start sending hellos and reset 5 min timer
                            time.sleep(random.randint(0,HELLO_TIMEOUT))
                            stop_hello.clear()
                            print("restarting timer and hello messages")
                            new_hello_thread(True)
                            send_hello_msg.start()
                            new_Timer()
                            t.start()

                            time.sleep(2)

                    elif len(payload) > 1:
                        print(f"Message {msg} arrived at destination {myAddress} with payload: {payload}\nStats are updated:")
                        stats[source, message[3]] = message[4]
                        print(stats)
                    
                else:
                    fwd_message = [routingTable[destination], source, destination]
                    fwd_message.extend(payload)
                    barr = bytearray(fwd_message)

                    print("forwarding message", fwd_message)
                    sock_send.sendto(barr, e32_sock)
                    (bytes, address) = sock_send.recvfrom(10)
                    print("return code", bytes[0])
            
            except:
                pass
        
        
        elif identifier == 253:
            if myAddress == message[2]:
                # handle LSA request: send all entries in LSDB
                print("answering LSA Request")
                if message[2] == myAddress:
                    time.sleep(1)
                    send_LSAs()


        

        elif identifier == 254:
            # handle LSA [Indentifier, Source/Key, version, neighbour1, neighbour2, ...]

            

            if source != myAddress:
                # only gather information about foreign nodes

                if source not in lsdb.keys() or lsdb[source][0] < message[2]:
                    if source == 16:
                        pass
                    else:
                        lsdb_set_lsa(message)
                        global start_dijkstra
                        time.sleep(3)
                        if bool(neighbours[1:]):
                            start_dijkstra = True
                            update_rt()


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
                
                global new_hello
                global hello_received
                global hello_sent
                global hello_offset
                

                t.cancel()
                new_Timer()
                t.start()

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
                        n_time.append(time.time())
                        print("neighbours updated:", neighbours)
                        start_dijkstra = True
                        # update own LSDB enty
                        update_own_lsdb_entry()
                        # reset counter for statistics
                        hello_offset[neighbours.index(source)] = message[2]
                
                
                elif len(message) > 3:
                    print("myhash", int.from_bytes(dict_hash()[:1], "big"), "vs", message[3], "other hash")
                    if int.from_bytes(dict_hash()[:1], "big") != message[3]:
                        #send_LSAs()
                        time.sleep(random.randint(0,2))
                        request_LSA(source)
                        # if not update_routing_table.is_alive():
                        #     update_routing_table.start()
                        #     start_dijkstra.set()
                        # else:
                        #     time.sleep(60)
                        #     start_dijkstra.set()
                    else:
                        update_rt()
                    
                    index = neighbours.index(source)

                    # update time
                    n_time[index] = time.time()
                        
                    # gather packets lost stats
                    # update hello_counter
                    hello_received[index] += 1
                    # update hello_percentage
                    global hello_percentage
                    hello_percentage[index] = 100 * hello_received[index] / (message[2] - hello_offset[index])

                    print(f"hello received: {hello_received}")
                    if message[2] >= 250:
                        # reset hello received counter (and hello_offset) to 0 if the received counter is 250
                        hello_received[index] = 0
                        hello_offset[index] = 0
                    
                    if (hello_received[index] % 3) == 0:
                        if bool(routingTable):
                            try:
                                sendto_controller(index)
                            except:
                                pass
        else:
            print("Message ", msg, " discarded because Im not next hop")


if __name__ == "__main__":

    # initial setup
    # register send/receive clients
    # open control socket
    sock_listen = register_socket(client_sock)
    sock_send = register_socket(client_sock+"1")
    ctl_sock = open_ctl_socket()

    # create threads for listening, check if neighbours are alive, updating routing table
    listen = threading.Thread(target=listen, daemon = True)
    neighbours_check = threading.Thread(target=check_neighbours, daemon = True)
    update_routing_table = threading.Thread(target=update_rt, daemon= True)

    # create Timer to enable going to rv-channel after 5 mins of not receiving anything
    new_Timer()

    threadLock = threading.Lock()


    scenario = 3
    
    if scenario == 1:
        # SCENARIO 1: Initializing the mesh
        # nodes are scattered accross multiple channels, where they do not detect neighbours
        # nodes go to rendez-vous channel to see if other nodes are around
        # controller decides on channel to build the mesh and advertises it
        # all nodes go to advertised channel and initialize mesh

        # create hello thread without advertising
        new_hello_thread(False)

    
    elif scenario == 2:
        
        # SCENARIO 2: nodes joining the mesh
        # mesh exists on given channel
        # new nodes wait on rendez-vous channel
        # nodes from the mesh will come on rendez-vous channel to advertise channel of the mesh
        
        # create hello thread with advertising
        new_hello_thread(True)
    

    elif scenario == 3:
        # SCENARIO 3: Reliable mesh
        # controller decides on air data rate based on packets received ratio from all nodes
        # nodes forward statistics to controller

        # create hello thread without advertising
        new_hello_thread(False)

    else:
        new_hello_thread(False)

    print("starting listen")
    listen.start()

    time.sleep(3)

    print("starting send_hello")
    send_hello_msg.start()

    neighbours_check.start()
    update_routing_table.start()

    if scenario == 1 or scenario == 3:
        # start Timer
        t.start()

    
    time.sleep(7200)




    # cleanup

    stop_hello.set()
    stop_listen.set()

    time.sleep(5)


    sock_listen.close()
    sock_send.close()

    if os.path.exists(client_sock):
        os.remove(client_sock)

    if os.path.exists(client_sock+"1"):
        os.remove(client_sock+"1")


    os.system("sudo systemctl stop e32")

    sys.exit()

