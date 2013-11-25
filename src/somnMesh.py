#!/usr/bin/env python3.2

import somnTCP
import somnUDP
import somnPkt
import somnRouteTable
from somnLib import *
import struct
import queue
import threading
import socket
import time
import random

class somnMesh(threading.Thread):
  TCPTxQ = queue.Queue()
  TCPRxQ = queue.Queue()
  UDPRxQ = queue.Queue()
  UDPAlive = threading.Event()
  networkAlive = threading.Event()
  routeTable = somnRouteTable.somnRoutingTable()
  cacheId = [0,0,0,0]
  cacheRoute = [0,0,0,0]
  _mainLoopRunning = 0
  enrolled = False
  nodeID = 0
  nodeIP = "127.0.0.1"
  nodePort = 0
  lastEnrollReq = 0
  connCache = [('',0),('',0),('',0)]
   

  def __init__(self, TxDataQ, RxDataQ):
    threading.Thread.__init__(self)
    self.CommTxQ = TxDataQ
    self.CommRxQ = RxDataQ
    random.seed()
    self.nodeID = random.getrandbits(16)
    self.nextConnCacheIndex = 0

  def enroll(self):
    print("enrolling")
    tcpRespTimeout = False
    ACK = random.getrandbits(16)
    enrollPkt = somnPkt.SomnPacket()
    enrollPkt.InitEmpty("NodeEnrollment")
    enrollPkt.PacketFields['ReqNodeID'] = self.nodeID
    enrollPkt.PacketFields['ReqNodeIP'] = IP2Int(self.nodeIP)
    enrollPkt.PacketFields['ReqNodePort'] = self.nodePort
    enrollPkt.PacketFields['AckSeq'] = ACK

    udp = somnUDP.somnUDPThread(enrollPkt, self.UDPRxQ, self.networkAlive, self.UDPAlive)
    udp.start()
    while not tcpRespTimeout and self.routeTable.getNodeCount() < 3: 
      try:
        enrollResponse = self.TCPRxQ.get(timeout = 1)
      except queue.Empty:
        tcpRespTimeout = True
        break 
      else:
       # print("-------- START ENROLL ----------")
       # print(enrollResponse.PacketFields)
       # print(enrollResponse.PacketType)
       # print("-------- END ENROLL ---------")
        if enrollResponse.PacketType == somnPkt.SomnPacketType.NodeEnrollment and enrollResponse.PacketFields['AckSeq'] == ACK:
          self.routeTable.addNode(enrollResponse.PacketFields['RespNodeID'], enrollResponse.PacketFields['RespNodeIP'], enrollResponse.PacketFields['RespNodePort'])
          
          packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollResponse, Int2IP(enrollResponse.PacketFields['RespNodeIP']), enrollResponse.PacketFields['RespNodePort']) 
          self.TCPTxQ.put(packedEnrollResponse)
          self.enrolled = True
          print("Enrolled to: ", enrollResponse.PacketFields['RespNodeID'])
          self.TCPRxQ.task_done()
          #break
    return udp  
  
    
  def run(self):
    socket.setdefaulttimeout(5)
    self.networkAlive.set()
    Rx = somnTCP.startSomnRx(self.nodeIP, self.nodePort, self.networkAlive, self.TCPRxQ)
    Tx = somnTCP.startSomnTx(self.networkAlive, self.TCPTxQ)
    
    while True:
      if Rx.bound and Tx.bound: break
    
    self.nodePort = Rx.port
    print(self.nodeID,self.nodePort)
   
    enrollAttempts = 0
    
    while not self.enrolled:
      self.UDPAlive.set()
      UDP = self.enroll()
      if self.enrolled: 
        break
      elif enrollAttempts < 2:
        self.UDPAlive.clear()
        UDP.join()
        enrollAttempts = enrollAttempts + 1
      else:
        self.enrolled = True
        print("Enrolled as Alhpa Node")
        break
    #start main loop to handle incoming queueus
    self._mainLoopRunning = 1
    testCount = 0
    while self._mainLoopRunning:
      self._handleTcpRx()
      self._handleUdpRx()
      self._handleTx()
      #time.sleep(5)
      #testCount = testCount + 1

    # Do a bunch of stuff
    self.networkAlive.clear()
    UDP.join()
    Rx.join()
    Tx.join()

  def _handleTx(self):
    #print("Handle TX")
    
    try:
      TxPkt = self.CommTxQ.get(False)
    except:
      return

    route = 0
    destId = TxPkt.PacketFields['DestID']
    #check cache for route to dest ID
    if destId in cacheId:
      route = cacheRoute[cacheId.index(destId)]
    else:
      route = self._getRoute(destId)
    
    #pop first step in route from route string
    newRoute = self._popRoute(route)
    nextRouteStep = newRoute[0]

    #set route string in packet
    TxPkt.PacketFields['Route'] = newRoute[1]

    #create wrapper packet to send to next step in route
    nextHopAddr = self.routeTable.getNodeInfoByIndex(nextRouteStep)
    txPktWrapper = SomnPktTxWrapper(TxPkt, nextHopAddr[1], nextHopAddr[2])

    #send packet to TX layer
    self.TCPTxQ.put(txPktWrapper)
    
 
  def _handleTcpRx(self):
    #print("Handle RX")
    try:
      RxPkt = self.TCPRxQ.get(False)
    except:
      return
    #RxPkt = somnPkt.SomnPacket(rawPkt)
    pktType = RxPkt.PacketType
    if pktType == somnPkt.SomnPacketType.NodeEnrollment:
      #print("Enrollment Packet Received")
      # There is a potential for stale enroll responses from enrollment phase, drop stale enroll responses
      if RxPkt.PacketFields['ReqNodeID'] == self.nodeID: return
      # We need to disable a timer, enroll the node, if timer has expired, do nothing
      for idx, pendingEnroll in enumerate(self.connCache):
        #print(pendingEnroll[0])
        if (RxPkt.PacketFields['ReqNodeID'], RxPkt.PacketFields['AckSeq']) == pendingEnroll[0]:
            # disable timer
            pendingEnroll[1].cancel()
            # clear connCache entry
            self.connCache[idx] = (('',0),) 
            # add node
            self.routeTable.addNode(RxPkt.PacketFields['ReqNodeID'], RxPkt.PacketFields['ReqNodeIP'], RxPkt.PacketFields['ReqNodePort'])
            print("Enrolled Node: ", RxPkt.PacketFields['ReqNodeID'])
            break

    elif pktType == somnPkt.PacketType.Message:
      print("Message Packet Received")
      # Check if we are the dest node
      if RxPkt.PacketFields['DestID'] == self.nodeID:
        print(RxPkt.PacketFields['Message'])
        # self.commRxQ.put(RxPkt) # TODO: strip headers before pushing onto queue
      # otherwise, propagate the message along the route
      elif not RxPkt.PacketFields['Route']:
        # generate bad_route event
        print("nothing to see here, move along folks")
      else:
        nextHop, RxPkt.PacketFields['Route'] = self._popRoute(RxPkt.PacketFields['Route'])
        TxPkt = somnPkt.SomnTxPacketWrapper(RxPkt, self.routeTable.getNodeInfoByIndex(nextHop)) 
        self.TCPTxQ.put(TxPkt)
    
    elif pktType == somnPkt.PacketType.RouteRequest:
      print("Route Req Packet Received")
      # if route field is -0-, then it is an in-progress route request
      # otherwise it is a returning route request
      if not RxPkt.PacketFields['Route']:
        # check if we have the destid in our routeTable
        idx = self.routeTable.getNodeIndexById(RxPkt.PacketFields['DestId'])
        if idx < 0: # Continue route request
          if RxPkt.PacketFields['HTL'] > 1:
            RxPkt.PacketFields['ReturnRoute'] = self._pushRoute(RxPkt.PacketFields['ReturnRoute'], self.routeTable.getIndexFromId(RxPkt.PacketFields['LastNodeID'])) 
            RxPkt.PacketFields['HTL'] = RxPkt.PacketFields['HTL'] - 1
            RxPkt.PacketFields['LastNodeID'] = self.nodeID
            #TODO: transmit to all nodes, except the transmitting node
            #TxPkt = somnPkt.SomnPacketTxWapper(RxPkt, 0,0)
          elif RxPkt.PacketFields['HTL'] == 1: # Last Node in query path
            RxPkt.PacketFields['HTL'] = RxPkt.PacketFields['HTL'] - 1
            TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, self.routeTable.getNodeInfoByIndex(self.routeTable.getIndexFromId(RxPkt.PacketFields['LastNodeID'])))
            self.TCPTxQ.put(TxPkt)
          else:
            TxIndex, RxPkt.PacketFields['ReturnRoute'] = self._popRoute(RxPkt.PacketFields['ReturnRoute'])
            TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, self.routeTable.getNodeInfoByIndex(TxIndex))
            self.TCPTxQ.put(TxPkt)
        else: # Dest Node is contained in route table
          RxPkt.PacketFields['HTL'] = 0
          RxPkt.PacketFields['Route'] = self._pushRoute(RxPkt.PacketFields['Route'], idx) 
          TxIndex, RxPkt.PacketFields['ReturnRoute'] = self._popRoute(RxPkt.PacketFields['ReturnRoute'])
          RxPkt.PacketFields['LastNodeID'] = self.nodeID
          TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, self.routeTable.getNodeInfoByIndex(TxIndex))
          self.TCPTxQ.put(TxPkt)
      else: # route path is non-empty
        RxPkt.PacketFields['Route'] = self._pushRoute(RxPkt.PacketFields['Route'], self.routeTable.getIndexFromNodeId(RxPkt.PacketFields['LastNodeID']))
        RxPkt.PacketFields['LastNodeID'] = self.nodeID
        TxIndex, RxPkt.PacketFields['ReturnRoute'] = self._popRoute(RxPkt.PacketFields['ReturnRoute'])
        TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, self.routeTable.getNodeInfoByIndex(TxIndex))

    elif pktType == somnPkt.PacketType.BadRoute:
      print("Bad Route Packet Received")
    
    elif pktType == somnPkt.PacketType.AddConnection:
      for pendingConn in self.connCache:
        if (RxPkt.PacketFields['RespNodeID'], RxPkt.PacketFields['AckSeq']) == pendingConn[1]: # This is response 
          # cancel timer
          pendingConn[2].cancel()
          # add node
          routeTable.addNode(RxPkt.PacketFields['RespNodeID'], RxPkt.PacketFields['RespNodeIP'], RxPkt.PacketFields['RespNodePort'])
          # send AddConnection ACK packet
          packedTxPkt = somnPkt.SomnPacketTxWrapper(somnPkt.SomnPacket(RxPkt.ToBytes()),Int2IP(RxPkt.PacketFields['RespNodeIP']), RxPkt.PacketFields['RespNodePort'])
          self.TCPTxQ.put(packedTxPkt)
          return
      # This is an incoming request 
      # generate a TCP Tx packet, start a timer, store ReqNodeID and timer object
      TxPkt = somnPkt.SomnPacket(RxPkt.ToBytes())
      TxPkt.Packetfields['RespNodeID'] = self.nodeID
      TxPkt.Packetfields['RespNodeIP'] = self.nodeIP
      TxPkt.Packetfields['RespNodePort'] = self.nodePort
      connCacheTag = (TxPkt.PacketFilds['ReqNodeID'], TxtPkt.PacketFields['AckSeq'])
      TxTimer = threading.Timer(5.0, self._connTimeout, connCacheTag)
      self.connCache[self.nextconnCacheEntry] = (connCacheTag, TxTimer)
      self.nextConnCacheEntry = self.nextConnCacheEntry + 1
      if self.nextConnCacheEntry >= len(self.connCache):
        self.nextConnCacheEntry = 0
      print("Add Conn Packet Received")
    
    elif pktType == somnPkt.PacketType.DropConnection:
      print("Drop Conn Packet Received")
    
    else: return
    
  def _handleUdpRx(self):
    #print("handleUDP")
    try:
      enrollPkt = self.UDPRxQ.get(False)
    except:
      return
    enrollRequest = somnPkt.SomnPacket(enrollPkt)
    if self.routeTable.getNodeIndexFromId(enrollRequest.PacketFields['ReqNodeID']) > 0: 
      return
    
    if self.routeTable.getAvailRouteCount() > 2 or (self.lastEnrollReq == enrollRequest.PacketFields['ReqNodeID'] and self.routeTable.getAvailRouteCount() > 0):
      enrollRequest.PacketFields['RespNodeID'] = self.nodeID
      enrollRequest.PacketFields['RespNodeIP'] = IP2Int(self.nodeIP)
      enrollRequest.PacketFields['RespNodePort'] = self.nodePort
      packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollRequest, Int2IP(enrollRequest.PacketFields['ReqNodeIP']), enrollRequest.PacketFields['ReqNodePort']) 
      connCacheTag = (enrollRequest.PacketFields['ReqNodeID'], enrollRequest.PacketFields['AckSeq'])
      TxTimer = threading.Timer(10.0, self._enrollTimeout, connCacheTag)
      self.connCache[self.nextConnCacheIndex] = (connCacheTag, TxTimer)
      self.nextConnCacheIndex = self.nextConnCacheIndex + 1
      if self.nextConnCacheIndex >= len(self.connCache): self.nextConnCacheIndex = 0
      #print("------- START UDP LISTEN -----------")
      #print(self.routeTable.getAvailRouteCount())
      #print("Responded to Enroll Request")
      #print("---------- END UDP LISTEN-----------")
      self.TCPTxQ.put(packedEnrollResponse)
      TxTimer.start()
    else:
      self.lastEnrollReq = enrollRequest.PacketFields['ReqNodeID']


  #get route from this node to dest node
  def _getRoute(self, destId):
    #first, check if the dest is a neighboring node
    routeIndex = self.routeTable.getNodeIndexFromId(destId)
    if routeIndex != -1:
      return routeIndex & 0x7

    #unknown route (discover from mesh)

    return 0
      

  def _popRoute(self, route):
    firstStep = route & 0x7
    newRoute = route >> 3
    return (firstStep, newRoute)

  def _pushRoute(self, route, nextStep):
    newRoute = (route << 3) | (nextStep & 0x7)
    return newRoute

  def _enrollTimeout(self, nodeID, ACK):
    for idx, pendingEnroll in enumerate(self.connCache):
      if (nodeID, ACK) == pendingEnroll[0]:
        self.connCache[idx] = (('',0),)
        break
    return

  def _connTimeout(self, nodeIP, nodePort):
    for idx, connAttempt in enumerate(self.connCache):
      if (nodeIP, nodePort) == connAttempt[0]:
        self.connCache[idx] = (('',0),)
        break
    return

if __name__ == "__main__":
  rxdq = queue.Queue()
  txdq = queue.Queue()
  mesh = somnMesh(txdq, rxdq)
  mesh.start()

