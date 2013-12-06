#!/usr/bin/python3.3

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

PING_TIMEOUT = 5

class somnData():
  def __init__(self, ID, data):
    self.nodeID = ID
    self.data = data

class somnMesh(threading.Thread):
  TCPTxQ = queue.Queue()
  TCPRxQ = queue.Queue()
  UDPRxQ = queue.Queue()
  UDPAlive = threading.Event()
  networkAlive = threading.Event()
  routeTable = somnRouteTable.somnRoutingTable()
  cacheId = [0,0,0,0]
  cacheRoute = [0,0,0,0]
  cacheNextIndex = 0
  _mainLoopRunning = 0
  enrolled = False
  nodeID = 0
  nodeIP = "127.0.0.1"
  nodePort = 0
  lastEnrollReq = 0
  connCache = [('',0),('',0),('',0)]
  _printCallbackFunction = None
   

  def __init__(self, TxDataQ, RxDataQ, printCallback = None):
    threading.Thread.__init__(self)
    self.CommTxQ = TxDataQ
    self.CommRxQ = RxDataQ
    random.seed()
    self.nodeID = random.getrandbits(16)
    self.nextConnCacheIndex = 0
    self._printCallbackFunction = printCallback

    TCPTxQ = queue.Queue()
    TCPRxQ = queue.Queue()
    UDPRxQ = queue.Queue()
    
    self.pendingRouteID = 0
    self.pendingRoute = 0
    self.pendingRouteHTL = 1
    self.routeLock = threading.Lock()
    self.routeBlock = threading.Event()

    self.pingTimer = threading.Timer(random.randrange(45,90), self._pingRouteTable)
    self.pingCache = [0,0,0,0,0]
    self.pingLock = threading.Lock()

  def printinfo(self, outputStr):
      if self._printCallbackFunction == None:
          print("{0:04X}: {1}".format(self.nodeID, outputStr))
      else:
        self._printCallbackFunction(self.nodeID, outputStr)

  def enroll(self):
    #self.printinfo("enrolling")
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
      respNodeID = enrollResponse.PacketFields['RespNodeID']
      respNodeIP = enrollResponse.PacketFields['RespNodeIP']
      respNodePort = enrollResponse.PacketFields['RespNodePort']
      #self.printinfo("Got enrollment response from {0:04X}".format(respNodeID))
      self.routeTable.getNodeIndexFromId(respNodeID)
      if  self.routeTable.getNodeIndexFromId(respNodeID) > 0:
        self.TCPRxQ.task_done()
        continue
      elif enrollResponse.PacketType == somnPkt.SomnPacketType.NodeEnrollment and enrollResponse.PacketFields['AckSeq'] == ACK:
        if self.routeTable.addNode(respNodeID, Int2IP(respNodeIP), respNodePort) < 0:
          self.printinfo("Something went wrong in adding the node")
          #TODO: Can we make this an exception?
        packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollResponse, Int2IP(respNodeIP),respNodePort) 
        self.TCPTxQ.put(packedEnrollResponse)
        self.enrolled = True
        self.printinfo("Enrolled to: {0:04X}".format(respNodeID))
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
    #self.printinfo("Port: {0}".format(self.nodePort))
   
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
        self.printinfo("Enrolled as Alpha Node")
        break
    #start main loop to handle incoming queueus
    self._mainLoopRunning = 1
    rxThread = threading.Thread(target = self._handleTcpRx)
    rxThread.start()
    self.pingTimer.start()
    while self._mainLoopRunning:
      self._handleUdpRx()
      self._handleTx()

    # Do a bunch of stuff
    try:
      self.pingTimer.cancel()
    except:
      pass
    self.networkAlive.clear()
    UDP.networkAlive = False
    UDP.join()
    Rx.join()
    Tx.join()
    self.TCPRxQ.join()
    self.TCPTxQ.join()
    self.CommTxQ.join()
    self.CommRxQ.join()

  def _pingRouteTable(self):
    # check if previous route requests were returned
    self.pingLock.acquire()
    for idx, node in enumerate(self.pingCache):
      if node != 0:
        # remove nodes where no response was returned
        self.printinfo("Dropping Node: {0:04X}".format(node))
        self.routeTable.removeNodeByIndex(self.routeTable.getNodeIndexFromId(node))
      # unset returned route cache
      self.pingCache[idx] = 0
    self.pingLock.release()
    
    # send a RouteReqeust for node 0xFFFF to each entry in the routing table
    for node in self.routeTable.getConnectedNodes():
      nodeIndex = self.routeTable.getNodeIndexFromId(node)
      self.pingLock.acquire()
      self.pingCache[nodeIndex - 1] = node
      self.pingLock.release()
      pingPkt = somnPkt.SomnPacket()
      pingPkt.InitEmpty(somnPkt.SomnPacketType.RouteRequest)
      pingPkt.PacketFields['SourceID'] = self.nodeID
      pingPkt.PacketFields['LastNodeID'] = self.nodeID
      pingPkt.PacketFields['DestID'] = 0xFFFF
      pingPkt.PacketFields['HTL'] = 1
      TxInfo = self.routeTable.getNodeInfoByIndex(nodeIndex)
      TxPkt = somnPkt.SomnPacketTxWrapper(pingPkt, TxInfo.nodeAddress, TxInfo.nodePort)
      self.TCPTxQ.put(TxPkt)
    self.pingTimer = threading.Timer(random.randrange(45,90), self._pingRouteTable)
    self.pingTimer.start()

  def _handleTx(self):
    #print("Handle TX")
    
    try:
      TxData = self.CommTxQ.get(False)
    except:
      return

    #TODO: Tx Data coming from the Comm Layer needs to packetized
    route = 0
    #check cache for route to dest ID
    if TxData.nodeID in self.cacheId:
      route = self.cacheRoute[self.cacheId.index(TxData.nodeID)]
    else:
      route = self._getRoute(TxData.nodeID)
      #TODO Lock around this 
      self.pendingRouteID = 0 
      self.pendingRouteHTL = 1
    if route == 0: # no valid rout found
      self.printinfo(" *** NO ROUTE FOUND *** ")
      return

    # inset path into cache, for now this is a FIFO eviction policy, should upgrade to an LFU policy
    self.cacheId[self.cacheNextIndex] = TxData.nodeID
    self.cacheRoute[self.cacheNextIndex] = route
    self.cacheNextIndex = self.cacheNextIndex + 1
    if self.cacheNextIndex > 3:
      self.cacheNextIndex = 0
    #pop first step in route from route string
    nextRoute, newRoute = self._popRoute(route)
    #nextRouteStep = newRoute[0]

    #set route string in packet
    TxPkt = somnPkt.SomnPacket()
    TxPkt.InitEmpty(somnPkt.SomnPacketType.Message)
    TxPkt.PacketFields['SourceID'] = self.nodeID
    TxPkt.PacketFields['DestID'] = TxData.nodeID
    TxPkt.PacketFields['Message'] = TxData.data
    TxPkt.PacketFields['Route'] = newRoute
    #create wrapper packet to send to next step in route
    TxNodeInfo = self.routeTable.getNodeInfoByIndex(nextRoute)
    if TxNodeInfo is None:
      self.cacheRoute[self.cacheId.index(TxData.nodeID)] = 0
      self.CommTxQ.task_done()
      self.CommTxQ.put(TxData)
      return
    txPktWrapper = somnPkt.SomnPacketTxWrapper(TxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)

    #send packet to TX layer
    self.TCPTxQ.put(txPktWrapper)
    self.CommTxQ.task_done()
 
  def _handleTcpRx(self):
    while self._mainLoopRunning:
      try:
        RxPkt = self.TCPRxQ.get(False)
      except:
        continue
      pktType = RxPkt.PacketType
      #self.printinfo("Rx'd TCP packet of type: {0}".format(pktType))
      if pktType == somnPkt.SomnPacketType.NodeEnrollment:
        #print("Enrollment Packet Received")
        self.pingTimer.cancel()
        # There is a potential for stale enroll responses from enrollment phase, drop stale enroll responses
        if RxPkt.PacketFields['ReqNodeID'] == self.nodeID: continue 
        # We need to disable a timer, enroll the node, if timer has expired, do nothing
        for idx, pendingEnroll in enumerate(self.connCache):
          if (RxPkt.PacketFields['ReqNodeID'], RxPkt.PacketFields['AckSeq']) == pendingEnroll[0]:
              # disable timer
              pendingEnroll[1].cancel()
              # clear connCache entry
              self.connCache[idx] = (('',0),) 
              # add node
              self.routeTable.addNode(RxPkt.PacketFields['ReqNodeID'], Int2IP(RxPkt.PacketFields['ReqNodeIP']), RxPkt.PacketFields['ReqNodePort'])
              #self.printinfo("Enrolled Node:{0:04X} ".format(RxPkt.PacketFields['ReqNodeID']))
              break
        self.pingTimer = threading.Timer(random.randrange(45,90), self._pingRouteTable)
        self.pingTimer.start()
      elif pktType == somnPkt.SomnPacketType.Message:
        #print("({0:X}) Message Packet Received".format(self.nodeID))
        # Check if we are the dest node
        if RxPkt.PacketFields['DestID'] == self.nodeID:
          self.printinfo("{0:04X} -> {1:04X}: {2}".format(RxPkt.PacketFields['SourceID'], self.nodeID, RxPkt.PacketFields['Message']))
          # strip headers before pushing onto queue
          commData = somnData(RxPkt.PacketFields['SourceID'], RxPkt.PacketFields['Message'])
          self.CommRxQ.put(commData)
        # otherwise, propagate the message along the route
        elif not RxPkt.PacketFields['Route']:
          # generate bad_route event
          print("nothing to see here, move along folks")
        else:
          nextHop, RxPkt.PacketFields['Route'] = self._popRoute(RxPkt.PacketFields['Route'])
          TxNodeInfo = self.routeTable.getNodeInfoByIndex(nextHop) 
          if TxNodeInfo is None:
            # this should generate a bad route pacekt
            self.printinfo("Invalid Route Event")
            self.TCPRxQ.task_done()
            continue
          TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort) 
          self.TCPTxQ.put(TxPkt)
      
      elif pktType == somnPkt.SomnPacketType.RouteRequest:
        #print("Route Req Packet Received")
        if RxPkt.PacketFields['SourceID'] == self.nodeID:
          # this our route request, deal with it.
          if self.pendingRouteID == RxPkt.PacketFields['DestID']:
            self.routeLock.acquire()
            #self.printinfo("Servicing Returned Route for {0:04X}".format(self.pendingRouteID))
            if RxPkt.PacketFields['Route'] != 0:
              self.pendingRoute = self._pushRoute(RxPkt.PacketFields['Route'], self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['LastNodeID']))
              self.routeBlock.set()
              self.routeLock.release()
              self.TCPRxQ.task_done()
              continue
            elif RxPkt.PacketFields['HTL'] < 10:
              self.routeLock.release()
              self.pendingRouteHTL = self.pendingRouteHTL + 1
              RxPkt.PacketFields['HTL'] = self.pendingRouteHTL
              RxPkt.PacketFields['ReturnRoute'] = 0
              TxNodeInfo = self.routeTable.getNodeInfoByIndex(self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['LastNodeID']))
              RxPkt.PacketFields['LastNodeID'] = self.nodeID
              TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
              self.TCPTxQ.put(TxPkt)
              self.TCPRxQ.task_done()
              continue
          
          elif RxPkt.PacketFields['DestID'] == 0xFFFF:
            self.pingLock.acquire()
            for idx, node in enumerate(self.pingCache):
              if node == RxPkt.PacketFields['LastNodeID']:
                self.pingCache[idx] = 0
            self.pingLock.release()
            self.TCPRxQ.task_done()
            continue

          else: # this route has been served
            #self.routeLock.release()
            #RxPkt.Reset()
            self.TCPRxQ.task_done()
            continue 
        # if route field is -0-, then it is an in-progress route request
        # otherwise it is a returning route request
        elif not RxPkt.PacketFields['Route']:
          # check if we have the destid in our routeTable
          idx = self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['DestID'])
          if idx < 0: # Continue route request
            if RxPkt.PacketFields['HTL'] > 1:
              #print("got multi Hop route request")
              RxPkt.PacketFields['ReturnRoute'] = self._pushRoute(RxPkt.PacketFields['ReturnRoute'], self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['LastNodeID'])) 
              RxPkt.PacketFields['HTL'] = RxPkt.PacketFields['HTL'] - 1
              lastID = RxPkt.PacketFields['LastNodeID'] 
              RxPkt.PacketFields['LastNodeID'] = self.nodeID
              #transmit to all nodes, except the transmitting node
              i = 1
              while i <= self.routeTable.getNodeCount():
                TxNodeInfo = self.routeTable.getNodeInfoByIndex(i)
                i = i + 1
                if not TxNodeInfo.nodeID == lastID:
                  #continue
                  TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
                  self.TCPTxQ.put(TxPkt)
              self.TCPRxQ.task_done()
              continue
            elif RxPkt.PacketFields['HTL'] == 1: # Last Node in query path
              RxPkt.PacketFields['HTL'] = RxPkt.PacketFields['HTL'] - 1
              TxNodeInfo = self.routeTable.getNodeInfoByIndex(self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['LastNodeID']))
              RxPkt.PacketFields['LastNodeID'] = self.nodeID
              TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
              self.TCPTxQ.put(TxPkt)
              self.TCPRxQ.task_done()
              continue
            else:
              #if RxPkt.PacketFields['ReturnRoute'] == 0:
              #  TxIndex = self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['SourceID'])
              #else: 
              TxIndex, RxPkt.PacketFields['ReturnRoute'] = self._popRoute(RxPkt.PacketFields['ReturnRoute'])
              RxPkt.PacketFields['LastNodeID'] = self.nodeID
              TxNodeInfo = self.routeTable.getNodeInfoByIndex(TxIndex)
              TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
              self.TCPTxQ.put(TxPkt)
              self.TCPRxQ.task_done()
              continue
          else: # Dest Node is contained in route table
            RxPkt.PacketFields['HTL'] = 0
            RxPkt.PacketFields['Route'] = self._pushRoute(RxPkt.PacketFields['Route'], self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['DestID'])) 
            #if RxPkt.PacketFields['ReturnRoute'] == 0: # Route did not go past HTL = 1
            #  TxIndex = self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['SourceID'])
            #else:
            #  TxIndex, RxPkt.PacketFields['ReturnRoute'] = self._popRoute(RxPkt.PacketFields['ReturnRoute'])
            TxIndex = self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['LastNodeID'])
            RxPkt.PacketFields['LastNodeID'] = self.nodeID
            TxNodeInfo = self.routeTable.getNodeInfoByIndex(TxIndex)
            #print("Dest Node Found: ",RxPkt.PacketFields)
            TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
            self.TCPTxQ.put(TxPkt)
            self.TCPRxQ.task_done()
            continue
        else: # route path is non-empty
          RxPkt.PacketFields['Route'] = self._pushRoute(RxPkt.PacketFields['Route'], self.routeTable.getNodeIndexFromId(RxPkt.PacketFields['LastNodeID']))
          RxPkt.PacketFields['LastNodeID'] = self.nodeID
          #print("Route Non Empty: ",RxPkt.PacketFields)
          TxIndex, RxPkt.PacketFields['ReturnRoute'] = self._popRoute(RxPkt.PacketFields['ReturnRoute'])
          TxNodeInfo = self.routeTable.getNodeInfoByIndex(TxIndex)
          TxPkt = somnPkt.SomnPacketTxWrapper(RxPkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
          self.TCPTxQ.put(TxPkt)
          self.TCPRxQ.task_done()
          continue
      
      elif pktType == somnPkt.SomnPacketType.BadRoute:
        print("Bad Route Packet Received")
        self.TCPRxQ.task_done()
        continue
      
      elif pktType == somnPkt.SomnPacketType.AddConnection:
        for pendingConn in self.connCache:
          if (RxPkt.PacketFields['RespNodeID'], RxPkt.PacketFields['AckSeq']) == pendingConn[1]: # This is response 
            # cancel timer
            pendingConn[2].cancel()
            # add node
            routeTable.addNode(RxPkt.PacketFields['RespNodeID'], Int2IP(RxPkt.PacketFields['RespNodeIP']), RxPkt.PacketFields['RespNodePort'])
            # send AddConnection ACK packet
            packedTxPkt = somnPkt.SomnPacketTxWrapper(somnPkt.SomnPacket(RxPkt.ToBytes()),Int2IP(RxPkt.PacketFields['RespNodeIP']), RxPkt.PacketFields['RespNodePort'])
            self.TCPTxQ.put(packedTxPkt)
            continue 
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
      
      elif pktType == somnPkt.SomnPacketType.DropConnection:
        print("Drop Conn Packet Received")
      
      else: 
        #RxPkt.Reset()
        self.TCPRxQ.task_done()
        continue
      #RxPkt.Reset()
      self.TCPRxQ.task_done()
      continue

  def _handleUdpRx(self):
    #print("handleUDP")
    try:
      enrollPkt = self.UDPRxQ.get(False)
    except:
      return
    enrollRequest = somnPkt.SomnPacket(enrollPkt)
    self.UDPRxQ.task_done()
    #ignore incoming enrollment requests from self
    if enrollRequest.PacketFields['ReqNodeID'] == self.nodeID:
      return

    #self.printinfo("Got enrollment request from {0:04X}".format(enrollRequest.PacketFields['ReqNodeID']))

    if self.routeTable.getNodeIndexFromId(enrollRequest.PacketFields['ReqNodeID']) > 0: 
      #self.printinfo("Node already connected, ignoring")
      #self.UDPRxQ.task_done()
      return

    
    if self.routeTable.getAvailRouteCount() > 4 or (self.lastEnrollReq == enrollRequest.PacketFields['ReqNodeID'] and self.routeTable.getAvailRouteCount() > 0):
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
    #self.UDPRxQ.task_done()
    return
   
  #get route from this node to dest node
  def _getRoute(self, destId):
    #first, check if the dest is a neighboring node
    routeIndex = self.routeTable.getNodeIndexFromId(destId)
    if routeIndex != -1:
      return routeIndex & 0x7

    #unknown route (discover from mesh)
    routePkt = somnPkt.SomnPacket()
    routePkt.InitEmpty(somnPkt.SomnPacketType.RouteRequest)
    routePkt.PacketFields['SourceID'] = self.nodeID
    routePkt.PacketFields['LastNodeID'] = self.nodeID
    routePkt.PacketFields['RouteRequestCode'] = 1 #random.getrandbits(16)
    routePkt.PacketFields['DestID'] = destId
    routePkt.PacketFields['HTL'] = 1
    self.pendingRouteID = destId
    self.pendingRoute = 0
    t = threading.Timer(10, self._routeTimeout)
    idx = 1
    while idx <= self.routeTable.getNodeCount():
      TxNodeInfo = self.routeTable.getNodeInfoByIndex(idx)
      #print("getRoute Packet Type: ", routePkt.PacketFields)
      TxPkt = somnPkt.SomnPacketTxWrapper(routePkt, TxNodeInfo.nodeAddress, TxNodeInfo.nodePort)
      self.TCPTxQ.put(TxPkt)
      idx = idx + 1
    t.start()  
    #self.printinfo("Waiting for route")
    self.routeBlock.wait()
    self.routeBlock.clear()
    #self.printinfo("Waiting Done") 
    try:
      t.cancel()
    except:
      pass
    return self.pendingRoute
  
  def _routeTimeout(self):
    self.routeLock.acquire()
    if not self.routeBlock.isSet():
      #self.printinfo("routeTimer Activate")
      self.pendingRoute = 0
      self.pendingRouteID = 0
      self.routeBlock.set()
    self.routeLock.release()
    #self.printinfo("routeTimer exit")


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

  def addConnection(self, DestNodeID):
    addConnPkt = somnPkt.SomnPkt()
    addConnPkt.InitEmpty(somnPkt.SomnPacketType.AddConnection)
    addConnPkt.PacketFields['ReqNodeID'] = self.nodeID
    addConnPkt.PacketFields['ReqNodeIP'] = self.nodeIP
    addConnPkt.PacketFields['ReqNodePort'] = self.nodePort
    addConnPkt.PacketFields['AckSeq'] = random.randbits(16)
    route = self._getRoute(DestNodeID)
    if route > 0: 
      addConnPkt.PacketFields['Route'] = route
    else:
      self.printinfo("AddConnection Failed to get route")
    

def CreateNode(printCallback = None):
  mesh = somnMesh(queue.Queue(), queue.Queue(), printCallback)
  return mesh

if __name__ == "__main__":
  mesh = CreateNode()
  mesh.start()

