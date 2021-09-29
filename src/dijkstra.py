#!/usr/bin/python3

# Driver Code for implementing Dijkstra's algorithm
import socket
import sys
import pickle
import os, os.path
import numpy as np
from routing import myAddress

NUMBER_OF_NODES = 3

def get_adjacency_matrix(lsdb):
	"""converts LSDB to adjacency matrix"""
	
	# LSDB = {
	# 	0 : [version, 1],
	# 	1 : [version, 0]}

	k = list(lsdb.keys())

	M = np.full([NUMBER_OF_NODES, NUMBER_OF_NODES], 999)

	for i in k:
		n = lsdb[i][1:]
		for j in n:
			#M[i,j] = 1
			M[j,i] = 1
			M[i,i] = 0

	return M

def dijkstra(lsdb):
	"""calculates shortest path in Dijkstra manner
	output:
	routing_table = {
		destination : next_hop}"""

	G = get_adjacency_matrix(lsdb)
	print("Adj Matrix:\n", G)
	
	destination_nexthop = {}

	# set source to myAdress and destination = every other node
	source = myAddress
	destinations = list(lsdb.keys())
	# destinations.remove("version")
	destinations.remove(myAddress)

	for destination in destinations:
		S = set()
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
					
			#print(u, "Is the minimum distance")
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
			
		destination_nexthop[destination] = route[0]

		# print("route:", route) # Display the route
		# print("path:", pi) # Display the path vector
		# print("distance from source:", d) # Display the distance of each node from source

	return destination_nexthop

# d = {0: [10, 1], 1: [10, 0, 1], 2: [10, 1]}
# d = {0: [10, 2], 2: [10, 0]}
# d = {0: [10, 1], 1: [10, 0]}
# print(d)

# m = get_adjacency_matrix(d)
# print(m)

# rt = dijkstra(d)

# for key in rt.keys():
#             print("For Destination ", key, "the Next Hop is ", rt[key])


