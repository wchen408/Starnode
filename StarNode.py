#!/usr/bin/env python
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 0:
    print("This script requires Python version 3.0")
    sys.exit(1)

import threading
import subprocess
import socket
import sys
import json
import queue
import logging
import time
import fcntl
import struct
from enum import IntEnum

class packetType(IntEnum):
	ACK = 0
	DATA = 1
	BDATA = 2
	KNOCKKNOCK = 3
	KNOCKRPLY = 4 
	RTTSUM = 5
	TERMINATE = 6


class StarNode:

	def __init__(self, name, port, hostPOC, portPOC, maxNode):

		#populate instance variables
		self.name = name

		#obtain IP of this node
		# self.ip = socket.gethostbyname(socket.gethostname())
		self.ip = socket.gethostbyname(socket.gethostname())
		self.port = port
		self.hub = self.name
		self.nameKey = self.ip + str(self.port)


		#POC variable instantiation
		self.hostPOC = hostPOC
		self.portPOC = portPOC
		self.ipPOC = None
		self.namePOC = None
		self.nameKeyPOC = None

		#instantiate critical data structures, mutex locks, condition variables, logger
		self.dsSetup()

		self.peersLock.acquire() 
		self.peers[self.nameKey] = {"name": self.name, "host": self.ip, "port": self.port, "RTT": 0, "RTTSUM": sys.maxsize}
		if (hostPOC != None and portPOC != None):
			self.ipPOC = socket.gethostbyname(hostPOC)
			self.namePOC = "POC"
			self.nameKeyPOC = self.ipPOC + str(self.portPOC)
			self.peers[self.ipPOC + str(self.portPOC)] = {"name": "POC", "host": self.ipPOC, "port": portPOC, "RTT": sys.maxsize, "RTTSUM": sys.maxsize}
		self.peersLock.release()

		#instantiate socket handler
		self.socketSetup();

		#create threadworkers
		self.listenerThread = threading.Thread(target=self.listener, name="listenerThread")
		self.listenerThread.start()
		self.senderThread = threading.Thread(target=self.sender, name="senderThread")
		self.senderThread.start()
		

		#threading.Thread(target=self.countingDown, args=(self.probingMaxAttempts,)).start()
		self.countingDown(self.probingMaxAttempts)

	'''
	Threadworker that listens to the socket to for any incoming packet and perform actions correspondingly. 
	{ACK: Delete Entry from the Resend Stack} 
	{BDATA, DATA, VOTE, RTTSUM: Reply ACK to the sender} 
	{RTTSUM:    }
	'''
	def listener(self):
		self.logger.debug("Listener worker started.")
		while True:
			packet, addr = self.s_id.recvfrom(64000)
			#inflate packet from ASCII
			packet = packet.decode()
			packet = json.loads(packet)	

			# if senderHost == self.hostPOC:
			# 	self.peers[senderName] = self.peers.pop(self.namePOC)
			# 	self.namePOC = senderName

			senderName = packet["srcName"]
			senderHost = packet["srcHost"] 
			senderPort = packet["srcPort"] 
			rType = packet["TYPE"] 
			rHash = packet["hash"] 
			rPayload = packet["payload"] 
			#key used to index into self.peers
			srcKey = senderHost + str(senderPort)



			self.peersLock.acquire()

			#update the name of POC if haven't already
			if self.namePOC == "POC" and srcKey == self.nameKeyPOC:
				self.namePOC = senderName
				self.peers[srcKey]["name"] = senderName

			if rType == packetType.TERMINATE:
				self.peers[srcKey]["RTT"] = sys.maxsize
				self.peersLock.release()
				break
			else:
				'''
				updates the peer vector based on the incoming packet. 
				If the sender is previously unknown, it will be added to the vector. 
				Otherwise, the incoming packet is an ACK, update the peer vector to account for the most recent RTT to this peer. 
				'''

				if (rType == packetType.ACK):
					self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(rType), rHash, rPayload, senderName)
					self.waitAckLock.acquire()

					# In the case of receiving duplicate ACK packets
					try:
						# cancel the timer object
						self.waitAckPackets[rPayload]["timer"].cancel()
						# update RTT of the peer
						oldRTT = self.peers[srcKey]["RTT"]
						timeNow = time.time()
						self.peers[srcKey]["RTT"] = timeNow - self.waitAckPackets[rPayload]["LST"]

						# pop off entry from the self.waitAckPackets
						del self.waitAckPackets[rPayload]

						# notify the network if the node if previously dead
						if oldRTT == sys.maxsize:
							self.logger.info("Node %s joined the network", senderName)
							self.peerscv.notify()
					except:
						self.logger.warning("Attmpted to cancel packet %d failed", rPayload)

					self.waitAckLock.release()
				else:

					if srcKey not in self.peers.keys():
						self.peers[srcKey] = {"name": senderName, "host": senderHost, "port": senderPort, "RTT": sys.maxsize-1, "RTTSUM": sys.maxsize}
						self.logger.info("Node %s joined the network", senderName)
						self.peerscv.notify()
						#send a dummy packet right away to measure RTT
						self.sendTo(packetType.KNOCKKNOCK, None, senderName)

					#reply ACK via sendTo()
					self.sendTo(packetType.ACK, rHash, senderName)
					
					if rType == packetType.DATA:
						self.logger.info("Received [%s] from %s.",rPayload, senderName)
					elif rType == packetType.BDATA:
						self.broadcast(rPayload)
					elif rType == packetType.KNOCKKNOCK:
						self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(rType), rHash, rPayload, senderName)
						#Introduce the network to the node knocked on the door
						exisiting_nodesnports = {}
						newnode = {}
						newnode[srcKey] = {"name": senderName, "port": senderPort, "host": senderHost}
						for each in self.peers.keys():
							if self.peers[each]["RTT"] != sys.maxsize and each != self.nameKey:
								self.sendTo(packetType.KNOCKRPLY, newnode, self.peers[each]["name"])
								exisiting_nodesnports[each] = {"name": self.peers[each]["name"], "port": self.peers[each]["port"], "host": self.peers[each]["host"]}
						self.sendTo(packetType.KNOCKRPLY, exisiting_nodesnports, senderName)
					elif rType == packetType.KNOCKRPLY:
						self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(rType), rHash, rPayload, senderName)
						for newNeighbour in rPayload.keys():
							if newNeighbour not in self.peers.keys():
								self.logger.info("Node %s joined the network.", rPayload[newNeighbour]["name"])
								self.peerscv.notify()
								self.peers[newNeighbour] = {"name": rPayload[newNeighbour]["name"], "host": rPayload[newNeighbour]["host"], "port": rPayload[newNeighbour]["port"], "RTT": sys.maxsize-1, "RTTSUM": sys.maxsize}
					elif rType == packetType.RTTSUM:
						self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(rType), rHash, rPayload, senderName)
						self.peers[srcKey]["RTTSUM"] = rPayload

				#perform according to types
			self.peersLock.release()
		self.logger.debug("Listener exiting")

	'''Creates packet and pushes into waitMsgQ, notify senderThread.'''
	def sendTo(self, packtype, payload, recipient):
		#populate an packet
		packet = {"TYPE": packtype, "srcName": self.name, "srcHost": self.ip, \
		"srcPort": self.port, "payload": payload, "hash":hash(time.time())}

		#acquire mutex lock and push to the queue
		self.waitMsgLock.acquire()
		self.waitMsgQ.put((packet, recipient))
		self.waitMsgcv.notify()
		self.waitMsgLock.release()

	def pushTowaitMsgQ(self, packet, recipient):
		#acquire mutex lock and push to the queue
		self.waitMsgLock.acquire()
		self.waitMsgQ.put((packet, recipient))
		self.waitMsgcv.notify()
		self.waitMsgLock.release()

	'''Threadworker that sends out packet. For every type except for ACK, push the packet into the waitAckPackets '''
	def sender(self):

		self.logger.debug("Sender worker started.")

		while True:
			#waitMsgcv already bound waitMsgLock as the underlying lock
			#check queue is not empty to prevent suprious wake-up
			self.waitMsgLock.acquire()
			self.waitMsgcv.wait_for(lambda: not self.waitMsgQ.empty())

			#Acquire lock for modification of self.waitAckPackets
			self.waitAckLock.acquire()

			while not self.waitMsgQ.empty():
				packet, recipient = self.waitMsgQ.get()

				#retrieve recipient address
				dst_ipaddr = None
				dst_port = None
				recipientKey = None
				for each in self.peers.keys():
					if self.peers[each]["name"] == recipient:
						dst_ipaddr = self.peers[each]["host"]
						dst_port = self.peers[each]["port"]
						recipientKey = each

				#serialize packet dictionary to jason
				packet_json = json.dumps(packet)

				sHash = packet["hash"]
				sName = packet["srcName"]
				sType = packet["TYPE"]

				timeNow = time.time()
				if sType == packetType.ACK or sType == packetType.TERMINATE:
					self.s_id.sendto(packet_json.encode('ASCII'), (dst_ipaddr, dst_port))
					self.logger.debug("Send: %s %s to %s", packetType(sType), sHash, recipient)
					if sType == packetType.TERMINATE:
						self.logger.debug("Sender exiting")
						return 0

				else:
					if sHash not in self.waitAckPackets.keys():
						# if the packet has not been previously transmitted, create new entry
						# and add to the self.waitAckPackets
						timer = threading.Timer(self.ack_TIMEOUT, self.pushTowaitMsgQ, args=[packet, recipient])
						self.waitAckPackets[sHash] = {"packet":packet, "RTA": self.maxResend, "LST": timeNow, "timer": timer}
						timer.start()

						 #transmission
						self.s_id.sendto(packet_json.encode('ASCII'), (dst_ipaddr, dst_port))
						self.logger.debug("Send: %s %s to %s at attempt 1", packetType(sType), sHash, recipient)
					else:
						if self.waitAckPackets[sHash]["RTA"] == 0:
							# if the packet has been transmitted for self.maxResend + 1 times
							# and still no ACK is received, the intended recipient is dead.
							# 1. mark recipient as dead in self.peers 2. remove entry from dict
							self.peersLock.acquire()
							if self.peers[recipientKey]["RTT"] != sys.maxsize:
								self.logger.info("Node %s exited the network", recipient)
							self.peers[recipientKey]["RTT"] = sys.maxsize
							self.peers[recipientKey]["RTTSUM"] = sys.maxsize
							self.peersLock.release()

							#remove entry from self.waitAckPackets
							del self.waitAckPackets[sHash]
						else:
							# if the packet is eligible for retransmission: 1. update LST 2. decrement RTA 3. set new timer
							timer = threading.Timer(self.ack_TIMEOUT, self.pushTowaitMsgQ, args=[packet, recipient])
							self.waitAckPackets[sHash]["RTA"] = self.waitAckPackets[sHash]["RTA"] - 1
							self.waitAckPackets[sHash]["LST"] = timeNow
							self.waitAckPackets[sHash]["timer"] = timer
							timer.start()

							#transmission
							self.s_id.sendto(packet_json.encode('ASCII'), (dst_ipaddr, dst_port))
							self.logger.debug("Send: %s %s to %s at attempt %d", packetType(sType), sHash, recipient, self.maxResend - self.waitAckPackets[sHash]["RTA"] + 1)		
			self.waitAckLock.release()
			self.waitMsgLock.release()

	'''Broadcast messge to all known active node in the network'''
	def broadcast(self, message):
		for peer in self.peers.keys():
			self.sendTo(packetType.DATA, message, self.peers[peer]["name"])


	'''ThreadHandler to interact with user'''
	def console_interaction(self):

		if not self.isCountingDown:

			user_input = input("Starnode Command: ")
			commands = user_input.split()
			if len(commands) > 0: 
				if "disconnect" in commands[0].lower():
					self.logger.critical("Node Exiting...")
					return self.__exit__()
				else:
					if "send" in commands[0].lower():
						self.sendTo(packetType.BDATA, " ".join(commands[1:]), self.hub)
					elif "show-status" in commands[0].lower():
						status = "Node %s with RTTSUM: %f\
							\n		# of active peer(s) in the network: %d \
							\n		peers: %s \
							\n 		Hub: {%s}" % \
							(self.name, self.peers[self.nameKey]["RTTSUM"], \
							 self.activeCount, self.activepeers, \
							  self.hub)
						print(status)

					elif "show-log" in commands[0].lower():
						f = open(self.logfile, 'r')
						for line in f:
							print(line)
						f.close()
					else:
						self.logger.info("Invalid argument")			
			
			return self.console_interaction()


	'''socket setup returns the socket handler'''		
	def socketSetup(self):
		self.s_id = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		if (self.s_id.bind((self.ip, self.port)) == -1):
			self.logger.critical("socket setup failed.")
			sys.exit(1)
		else:
			self.logger.debug("socket created successfully at port %d", self.port)

	'''setup critical datastructures'''
	def dsSetup(self):
		'''
		Shared DS.
		A Vector, maintained by a dict of dict, of all Nodes in the network as well as their RTTSums.
		The key to each entry is the hostname of the peer.
		This vector should be consistent across every node in the network, hub of the network is the node with minimum RTTSum. 
		Mutex lock need to be acquired when making changes to the hashmap. 
		'''
		self.peers = dict()
		self.peersLock = threading.Lock()
		self.peerscv = threading.Condition(self.peersLock)

		'''
		Shared DS.
		A vector of sent-out packets that haven't received ACK from their recipients yet. 
		Each entry in the dictionary can be retrieved via the hash of the packet and contains four fields:
		packet: the unserialized packet object
		RTA:Remaining Transmit Attempts. When RTA = 0 and still no ACK received, recipient is deemed dead
		LST:Last Sent Time, when an ACK is received, this field is used by listener to calculate RTT 
		timer: a threading.timer object that calls SendTo() function when ack_TIMEOUT is up
		'''
		self.ack_TIMEOUT = 1
		self.maxResend = 2
		self.waitAckPackets = dict()
		self.waitAckLock = threading.Lock()

		'''
		Shared DS.
		A queue of packetJsons waiting to be sent out. 
		New packet will be pushed into the Queue by sendToThread.
		senderThread will be notified and waited up whenever a new packet is pushed into the Queue.
		senderThread will send out all packets in the queue during each wait-up and go back to sleep.
		'''
		self.waitMsgQ = queue.Queue()
		self.waitMsgLock = threading.Lock()
		self.waitMsgcv = threading.Condition(self.waitMsgLock)

		'''
		Instantiate a logger 
		'''
		self.logger = logging.getLogger(__name__)

		self.logfile = self.name + '_' + time.strftime("%Y-%m-%d_%H%M%S", time.localtime()) + '.log'
		logging.basicConfig(format='%(asctime)s %(levelname)-2s %(message)s', \
			datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG
			, filename=self.logfile, filemode='w')

		console_handler = logging.StreamHandler()

		console_handler.setFormatter(logging.Formatter('\x1b[1K\x1b[99D%(asctime)s %(levelname)-2s %(message)s', \
			datefmt='%Y-%m-%d %H:%M:%S'))
		console_handler.setLevel(logging.DEBUG)
		self.logger.addHandler(console_handler)
		

		'''heartbeat interval'''
		self.hbInterval = 10
		self.probingMaxAttempts = 5
		self.activeCount = 0 
		self.activepeers = []

		'''Exiting'''
		# isCountingDown is flagged on when either countingDown or probingPOC 
		# function is triggered
		self.isCountingDown = False

	'''
	When no peer nodes is active in the network, this node will start probing POC
	If connection could not be established with POC after self.maxAttempts, program terminates
	'''
	def countingDown(self, remainingAttempts):

		self.isCountingDown = True

		# if dormant heartbeat timer exist, cancel the timer to prevent duplication
		try:
			self.heartbeatTimer.cancel()
		except:
			None

		if remainingAttempts == 0:
			self.logger.critical("Could not established connection with other nodes. Exiting...")
			return self.__exit__()

		if self.hostPOC != None:
			self.logger.warning("Attempt to contact POC with %d more tries",remainingAttempts)
			self.sendTo(packetType.KNOCKKNOCK, None, self.namePOC)
		else:
			self.logger.warning("Exiting in %d seconds if no peers emerge",
			 (self.maxResend + 2) * self.ack_TIMEOUT * remainingAttempts)

		anyActivePeer = False
		self.peersLock.acquire()
		self.peerscv.wait(timeout= (self.maxResend + 2) * self.ack_TIMEOUT)
		for peer in self.peers.keys():
			if peer != self.nameKey and self.peers[peer]["RTT"] != sys.maxsize:
				anyActivePeer = True
				break
		self.peersLock.release()

		if anyActivePeer:
			self.isCountingDown = False
			#threading.Thread(target=self.console_interaction).start()
			return self.nextHeartbeat()
		else:
			return self.countingDown(remainingAttempts-1)

	'''
	Assuming all machines that the starnode network run on have the same time
	Calculate the next heartbeat (RTTSUM) exchange time in the network to be
	the least multiple of self.hbInterval > Current Unix Timestamp
	'''
	def nextHeartbeat(self):
		nextHB = self.hbInterval - int(time.time()) % self.hbInterval
		self.heartbeatTimer = threading.Timer(nextHB, self.heartbeat)
		self.heartbeatTimer.start()


	'''Recalculate RTTSUM and heartbeat to the peers in the network'''
	def heartbeat(self):
		# if not self.isCountingDown:

		#recalculate RTT
		self.activeCount = 0
		self.activepeers = []
		self.peersLock.acquire()
		self.peers[self.nameKey]["RTTSUM"] = 0
		for peer in self.peers.keys():
			if peer != self.nameKey and self.peers[peer]["RTT"] != sys.maxsize:
				self.activeCount = self.activeCount + 1
				self.activepeers.append(self.peers[peer]["name"])
				self.peers[self.nameKey]["RTTSUM"] += self.peers[peer]["RTT"]

		# if no active peer, revert self.name's RTTSUM to infinity
		self.peers[self.nameKey]["RTTSUM"] = sys.maxsize if self.activeCount == 0 else self.peers[self.nameKey]["RTTSUM"]
		
		self.peersLock.release()

		#periodic handshake with peers
		for peer in self.peers.keys():
			if peer != self.nameKey:
				self.sendTo(packetType.RTTSUM, self.peers[self.nameKey]["RTTSUM"], self.peers[peer]["name"])


		if self.activeCount == 0:
			self.countingDown(self.probingMaxAttempts)
		else:
			#timer will create a new thread to call heartbeat function for a given time interval
			#sleep to account for delay, lost packet durig RTT exchange before hub re-selection
			# self.selectHubnCheckTimer = threading.Timer(self.hbInterval-1, self.selectHubnCheck)
			# self.selectHubnCheckTimer.start()
			self.selectHubnCheckTimer = threading.Timer((self.maxResend + 1) * self.ack_TIMEOUT, self.selectHubnCheck)
			self.selectHubnCheckTimer.start()			

			#sleep because of periodic heartbeat
			self.heartbeatTimer = threading.Timer(self.hbInterval, self.heartbeat)
			self.heartbeatTimer.start()


	'''Reselect hub'''
	def selectHubnCheck(self):

		# if not self.isCountingDown:

		## Reselect the hub of the network
		minimumRTT = sys.maxsize
		for peer in self.peers.keys():
			if self.peers[peer]["RTTSUM"] < minimumRTT:
				minimumRTT = self.peers[peer]["RTTSUM"]
				self.hub = self.peers[peer]["name"]

		self.logger.info("Heartbeat from %s:\
		\n				# of active peer(s) in the network: %d \
		\n				peers: %s \
		\n 				Hub: {%s}", \
		self.name, self.activeCount, self.activepeers, self.hub)


	def __exit__(self):
		self.sendTo(packetType.TERMINATE, None, self.name)
		self.listenerThread.join()
		self.senderThread.join()
		#print(threading.enumerate())
		#print(self.waitAckPackets)
		try:
			self.heartbeatTimer.cancel()
			self.selectHubnCheckTimer.cancel()
		except:
			None

		for packet in self.waitAckPackets:
			self.waitAckPackets[packet]["timer"].cancel()
