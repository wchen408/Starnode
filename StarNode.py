#!/usr/bin/env python
import sys

if sys.version_info[0] != 3 or sys.version_info[1] < 0:
    print("This script requires Python version 3.0")
    sys.exit(1)

import threading
import socket
import sys
import json
import queue
import logging
import time
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

	def __init__(self, hostname, port, hostPOC, portPOC, maxNode):

		#instantiate critical data structures, mutex locks, condition variables, logger
		self.dsSetup()

		#populate instance variables
		self.hostname = hostname
		self.port = port
		self.hub = self.hostname
		self.hostPOC = hostPOC
		self.portPOC = portPOC

		self.peersLock.acquire()
		self.peers[self.hostname] = {"port": self.port, "RTT": 0, "RTTSUM": sys.maxsize}
		if (hostPOC != None and portPOC != None):
			self.peers[hostPOC] = {"port": portPOC, "RTT": sys.maxsize, "RTTSUM": sys.maxsize}
		self.peersLock.release()

		#instantiate socket handler
		self.socketSetup();

		#create threadworkers
		self.listenerThread = threading.Thread(target=self.listener, name="listenerThread")
		self.listenerThread.start()
		self.senderThread = threading.Thread(target=self.sender, name="senderThread")
		self.senderThread.start()

		threading.Thread(target=self.countingDown, args=(self.probingMaxAttempts,)).start()
		#self.countingDown(self.probingMaxAttempts)

	'''
	Threadworker that listens to the socket to for any incoming packet and perform actions correspondingly. 
	{ACK: Delete Entry from the Resend Stack} 
	{BDATA, DATA, VOTE, RTTSUM: Reply ACK to the sender} 
	{VOTE:     } 
	{RTTSUM:    }
	'''
	def listener(self):
		self.logger.debug("Listener worker started.")
		while True:
			packet, addr = self.s_id.recvfrom(64000)
			#inflate packet from ASCII
			packet = packet.decode()
			packet = json.loads(packet)	

			self.peersLock.acquire()
			if packet["TYPE"] == packetType.TERMINATE:
				self.peerscv.notify()
				self.peersLock.release()
				break
			else:
				'''
				updates the peer vector based on the incoming packet. 
				If the sender is previously unknown, it will be added to the vector. 
				Otherwise, the incoming packet is an ACK, update the peer vector to account for the most recent RTT to this peer. 
				'''

				##TODO add try&except statement to handle duplicate ACK packets
				if (packet["TYPE"] == packetType.ACK):
					self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(packet["TYPE"]), packet["hash"], packet["payload"], packet["srcHost"])
					self.waitAckLock.acquire()
					# cancel the timer object
					self.waitAckPackets[packet["payload"]]["timer"].cancel()
					# update RTT of the peer
					oldRTT = self.peers[packet["srcHost"]]["RTT"]
					timeNow = time.time()
					self.peers[packet["srcHost"]]["RTT"] = timeNow - self.waitAckPackets[packet["payload"]]["LST"]
					# pop off entry from the self.waitAckPackets
					del self.waitAckPackets[packet["payload"]]
					# notify the network if the node if previously dead
					if oldRTT == sys.maxsize:
						self.logger.info("Node %s joined the network", packet["srcHost"])
						self.peerscv.notify()
					self.waitAckLock.release()
				else:
					#reply ACK via sendTo()
					self.sendTo(packetType.ACK, packet["hash"], packet["srcHost"])

					if packet["srcHost"] not in self.peers:
						self.peers[packet["srcHost"]] = {"port": packet["srcPort"], "RTT": sys.maxsize-1, "RTTSUM": sys.maxsize}
						self.logger.info("Node %s joined the network", packet["srcHost"])
						self.peerscv.notify()
						#send a dummy packet right away to measure RTT
						self.sendTo(packetType.KNOCKKNOCK, None, packet["srcHost"])
					
					if packet["TYPE"] == packetType.DATA:
						self.logger.info("Received %s %d with payload=[%s] from %s", packetType(packet["TYPE"]), packet["hash"], packet["payload"], packet["srcHost"])
					elif packet["TYPE"] == packetType.BDATA:
						self.logger.info("Received %s %d with payload=[%s] from %s", packetType(packet["TYPE"]), packet["hash"], packet["payload"], packet["srcHost"])
					elif packet["TYPE"] == packetType.KNOCKKNOCK:
						self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(packet["TYPE"]), packet["hash"], packet["payload"], packet["srcHost"])
						#Introduce the network to the node knocked on the door
						nodesnports = {}
						for each in self.peers:
							self.sendTo(packetType.KNOCKRPLY, {packet["srcHost"]:packet["srcPort"]}, each)
							nodesnports[each] = self.peers[each]["port"]
						self.sendTo(packetType.KNOCKRPLY, nodesnports, packet["srcHost"])
					elif packet["TYPE"] == packetType.KNOCKRPLY:
						self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(packet["TYPE"]), packet["hash"], packet["payload"], packet["srcHost"])
						for newNeighbour in packet["payload"].keys():
							if newNeighbour not in self.peers:
								self.logger.info("Node %s joined the network", newNeighbour)
								self.peers[newNeighbour] = {"port": packet["payload"][newNeighbour], "RTT": sys.maxsize-1, "RTTSUM": sys.maxsize}
					elif packet["TYPE"] == packetType.RTTSUM:
						self.logger.debug("Received %s %d with payload=[%s] from %s", packetType(packet["TYPE"]), packet["hash"], packet["payload"], packet["srcHost"])
						self.peers[packet["srcHost"]]["RTTSUM"] = packet["payload"]

				#perform according to types
			self.peersLock.release()
		self.logger.debug("Listener exiting")

	'''Creates packet and pushes into waitMsgQ, notify senderThread.'''
	def sendTo(self, type, payload, recipient):
		#populate an packet
		packet = {"TYPE": type, "srcHost": self.hostname, \
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
				dst_ipaddr = socket.gethostbyname(recipient)
				dst_port = self.peers[recipient]["port"]

				#serialize packet dictionary to jason
				packet_json = json.dumps(packet)

				timeNow = time.time()
				if packet["TYPE"] == packetType.ACK or packet["TYPE"] == packetType.TERMINATE:
					self.s_id.sendto(packet_json.encode('ASCII'), (dst_ipaddr, dst_port))
					self.logger.debug("Send: %s %s to %s", packetType(packet["TYPE"]), packet["hash"], recipient)
					if packet["TYPE"] == packetType.TERMINATE:
						self.logger.debug("Sender exiting")
						return 0

				else:
					if packet["hash"] not in self.waitAckPackets.keys():
						# if the packet has not been previously transmitted, create new entry
						# and add to the self.waitAckPackets
						timer = threading.Timer(self.ack_TIMEOUT, self.pushTowaitMsgQ, args=[packet, recipient])
						self.waitAckPackets[packet["hash"]] = {"packet":packet, "RTA": self.maxResend, "LST": timeNow, "timer": timer}
						timer.start()
						 #transmission
						self.s_id.sendto(packet_json.encode('ASCII'), (dst_ipaddr, dst_port))
						self.logger.debug("Send: %s %s to %s at attempt 1", packetType(packet["TYPE"]), packet["hash"], recipient)
					else:
						if self.waitAckPackets[packet["hash"]]["RTA"] == 0:
							# if the packet has been transmitted for self.maxResend + 1 times
							# and still no ACK is received, the intended recipient is dead.
							# 1. mark recipient as dead in self.peers 2. remove entry from dict
							self.peersLock.acquire()
							if self.peers[recipient]["RTT"] != sys.maxsize:
								self.logger.info("Node %s exited the network", recipient)
							self.peers[recipient]["RTT"] = sys.maxsize
							self.peers[recipient]["RTTSUM"] = sys.maxsize
							self.peerscv.notify()
							self.peersLock.release()

							#remove entry from self.waitAckPackets
							del self.waitAckPackets[packet["hash"]]
						else:
							# if the packet is eligible for retransmission: 1. update LST 2. decrement RTA 3. set new timer
							timer = threading.Timer(self.ack_TIMEOUT, self.pushTowaitMsgQ, args=[packet, recipient])
							self.waitAckPackets[packet["hash"]]["RTA"] = self.waitAckPackets[packet["hash"]]["RTA"] - 1
							self.waitAckPackets[packet["hash"]]["LST"] = timeNow
							self.waitAckPackets[packet["hash"]]["timer"] = timer
							timer.start()

							#transmission
							self.s_id.sendto(packet_json.encode('ASCII'), (dst_ipaddr, dst_port))
							self.logger.debug("Send: %s %s to %s at attempt %d", packetType(packet["TYPE"]), packet["hash"], recipient, self.maxResend - self.waitAckPackets[packet["hash"]]["RTA"] + 1)		
			self.waitAckLock.release()
			self.waitMsgLock.release()

	'''Broadcast messge to all known active node in the network'''
	def broadcast(self, message):
		if self.hub == self.hostname:
			for peer in self.peers:
				self.sendTo(packetType.DATA, message, peer)


	'''socket setup returns the socket handler'''		
	def socketSetup(self):
		self.s_id = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		if (self.s_id.bind((self.hostname, self.port)) == -1):
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
		logging.basicConfig(format='%(asctime)s %(levelname)-3s %(message)s', \
			datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
		self.logger = logging.getLogger(__name__)

		'''heartbeat interval'''
		self.hbInterval = 5
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
		if remainingAttempts == 0:
			return self.__exit__()

		if self.portPOC != None:
			self.logger.warning("Attempt to contact POC with %d more tries",remainingAttempts)
			self.sendTo(packetType.KNOCKKNOCK, None, self.hostPOC)
		else:
			self.logger.warning("Exiting in %d seconds if no peers emerge",
			 (self.maxResend + 2) * self.ack_TIMEOUT * remainingAttempts)

		anyActivePeer = False
		self.peersLock.acquire()
		self.peerscv.wait(timeout= (self.maxResend + 2) * self.ack_TIMEOUT)
		for key in self.peers:
			if key != self.hostname and self.peers[key]["RTT"] != sys.maxsize:
				anyActivePeer = True
				break
		self.peersLock.release()

		if anyActivePeer:
			self.isCountingDown = False
			threading.Thread(target=self.nextHeartbeat).start()
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


	'''Heartbeat periodically to log current network status'''
	def heartbeat(self):
		if not self.isCountingDown:

			#periodic handshake with peers
			for peer in self.peers:
				if peer != self.hostname:
					self.sendTo(packetType.RTTSUM, self.peers[self.hostname]["RTTSUM"], peer)

			#timer will create a new thread to call heartbeat function for a given time interval
			self.updateRTTtimer = threading.Timer(self.hbInterval-1, self.updateRTT)
			self.updateRTTtimer.start()
			self.heartbeatTimer = threading.Timer(self.hbInterval, self.heartbeat)
			self.heartbeatTimer.start()

	'''updateRTT of this node, reselect hub'''
	def updateRTT(self):

		if not self.isCountingDown:
			#recalculate RTT
			self.activeCount = 0
			self.activepeers = []
			self.peersLock.acquire()
			self.peers[self.hostname]["RTTSUM"] = 0
			for key in self.peers:
				if key != self.hostname and self.peers[key]["RTT"] != sys.maxsize:
					self.activeCount = self.activeCount + 1
					self.activepeers.append(key)
					self.peers[self.hostname]["RTTSUM"] += self.peers[key]["RTT"]
			# if no active peer, revert self.hostname's RTTSUM to infinity
			self.peers[self.hostname]["RTTSUM"] = sys.maxsize if self.activeCount == 0 else self.peers[self.hostname]["RTTSUM"]
			
			self.peerscv.notify()
			self.peersLock.release()
			
			## Reselect the hub of the network
			for key in self.peers:
				if self.peers[key]["RTTSUM"] < self.peers[self.hub]["RTTSUM"]:
					self.hub = key

			self.statusChecker()

			if self.activeCount == 0:
				self.countingDown(self.probingMaxAttempts)

	'''Print network Status'''
	def statusChecker(self):

		self.logger.info("Heartbeat from %s with RTTSUM: %f\
			\n				# of active peer(s) in the network: %d \
			\n				peers: %s \
			\n 				Hub: {%s} with RTTSUM: %f ", \
			self.hostname, self.peers[self.hostname]["RTTSUM"], \
			 self.activeCount, self.activepeers, \
			  self.hub, self.peers[self.hub]["RTTSUM"])



	def __exit__(self):
		self.sendTo(packetType.TERMINATE, None, self.hostname)
		self.listenerThread.join()
		self.senderThread.join()
		#print(threading.enumerate())
		#print(self.waitAckPackets)
		try:
			self.heartbeatTimer.cancel()
			self.updateRTTtimer.cancel()
		except:
			None

		for packet in self.waitAckPackets:
			self.waitAckPackets[packet]["timer"].cancel()

		self.logger.critical("Could not established connection with other nodes. Exiting...")
