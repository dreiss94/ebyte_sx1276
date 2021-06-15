#!/usr/bin/python3

# Driver Code for implementing Dijkstra's algorithm
import socket
import sys
import pickle
import os, os.path
import numpy as np
from routing import myAddress


def get_adjacency_matrix(lsdb):
	
	# LSDB = {"version" : int,
	# 	0 : [1],
	# 	1 : [0]}

	keys = list(lsdb.keys())
	k = keys[1:]

	M = np.full([len(k), len(k)], 999)

	for i in k:
		n = lsdb[i]
		for j in n:
			M[i,j] = 1
			M[j,i] = 1
			M[i,i] = 0

	return M

def Dijkstra(G):
	
	destination_nexthop = {}

	S = set()
		
	source = int(input("give source"))
	destination = int(input("give destination")) 
	Q =[] # empty queue

	for i in range(len(G)):
		Q.append(i)
		
	d = [] # initialize d values
	pi =[] # initialize pi values
	for i in range(len(G)):
		d.append(0)
		pi.append(0)

	for i in range(len(G)):
		if(i == source):
			d[i]= 0
		else:
			d[i]= 999
	for i in range(len(G)):
		pi[i]= 9000
	S.add(source)

	# While items still exist in Q
	while (len(Q)!= 0):
		
		# Find the minimum distance x from
		# source of all nodes in Q
		x = min(d[q] for q in Q)
		u = 0
		for q in Q:
			if(d[q]== x):
				
				# Find the node u in Q with minimum
				# distance x from source
				u = q
				
		print(u, "Is the minimum distance")
		Q.remove(u) # removed the minimum vertex
		S.add(u)
		adj =[]
		for y in range(len(G)):
			
			# find adjacent vertices to minimum vertex
			if(y != u and G[u][y]!= 999):	
				adj.append(y)
				
		# For each adjacent vertex, perform the update
		# of distance and pi vectors		
		for v in adj:		
			if(d[v]>(d[u]+G[u][v])):
				d[v]= d[u]+G[u][v]
				pi[v]= u # update adjacents distance and pi
	route =[]
	x = destination

	# If destination is source, then pi[x]= 9000.
	if(pi[x]== 9000):
		print(source)
	else:
		
		# Find the path from destination to source
		while(pi[x]!= 9000):
			route.append(x)
			x = pi[x]
		route.reverse()
		
		
	print("route:", route) # Display the route
	print("path:", pi) # Display the path vector
	print("distance from source:", d) # Display the distance of each node from source

	'''We will now send the calculated minimal route to the terminal
	# representing 'source'. From the source terminal, the 'route' list
	# will be sent to the next hop en route to the final destination.

	# At each intermediate terminal, the router removes its own identity
	from the list and sends the rest of the route to the next router.
	This continues until the final router is reached.'''

	sendingroute = pickle.dumps(route)
	sockets =[0, 1, 2]

	return destination_nexthop
