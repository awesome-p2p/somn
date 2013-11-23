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
  availRouteCount = 5
  

  def __init__(self, TxDataQ, RxDataQ):
    threading.Thread.__init__(self)
    self.CommTxQ = TxDataQ
    self.CommRxQ = RxDataQ
    self.nodeID = 1
     
  def enroll(self):
    print("enrolling")
    tcpRespTimeout = False
    ACK = 56
    enrollPkt = somnPkt.SomnPacket()
    enrollPkt.InitEmpty("NodeEnrollment")
    enrollPkt.PacketFields['ReqNodeID'] = self.nodeID
    enrollPkt.PacketFields['ReqNodeIP'] = IP2Int(self.nodeIP)
    enrollPkt.PacketFields['ReqNodePort'] = self.nodePort
    enrollPkt.PacketFields['ACKSeq'] = ACK

    udp = somnUDP.somnUDPThread(enrollPkt, self.UDPRxQ, self.networkAlive, self.UDPAlive)
    udp.start()
    while self.routeTable.getNodeCount() < 3 or not tcpRespTimeout:
      print("Enroll Attempt Loop")
      try:
        enrollResponse = self.TCPRxQ.get(timeout = 5)
      except queue.Empty:
        tcpRespTimeout = True
        print("Enroll failed")
        break 
      else:
        #enrollResponse = somnPkt.SomnPacket(enrollPkt)
        if enrollResponse.PacketType == somnPkt.SomnPacketType.NodeEnrollment and enrollResponse.PacketFields['ACKSeq'] == ACK:
          routeTable.addNode(enrollResponse.PacketFields['RespNodeID'], enrollResponse.PacketFields['RespNodeIP'], enrollResponse.PacketFields['RespNodePort'])
          packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollResponse, enrollResponse.PacketFields['RespNodeIP'], enrollResponse.Packetfields['RespNodePort']) 
          self.TCPTxQ.put(packedEnrollResponse)
          enrolled = True
          print("Enrolled complete")
    return udp  
  
    
  def run(self):
    socket.setdefaulttimeout(5)
    self.networkAlive.set()
    Rx = somnTCP.startSomnRx(self.nodeIP, self.nodePort, self.networkAlive, self.TCPRxQ)
    Tx = somnTCP.startSomnTx(self.networkAlive, self.TCPTxQ)
    _spinlock = 1
    while _spinlock:
      if Rx.bound and Tx.bound: _spinlock = 0
    if self.nodePort == 0:
      self.nodePort = Rx.port
      print(self.nodePort)
    enrollAttempts = 0
    while not self.enrolled and enrollAttempts < 3:
      self.UDPAlive.set()
      UDP = self.enroll()
      if not self.enrolled and enrollAttempts < 2:
        self.UDPAlive.clear()
        UDP.join()
        enrollAttempts = enrollAttempts + 1
      elif not self.enrolled:
        self.enrolled = True
        print("Setting up single node network")
      else:
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
      TxPkt = self.TxQ.get(False)
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
      pass
    
  def _handleUdpRx(self):
    #print("handleUDP")
    try:
      enrollPkt = self.UDPRxQ.get(False)
    except:
      return
    enrollRequest = somnPkt.SomnPacket(enrollPkt)
    if self.routeTable.AvailRouteCount() > 1 or (self.lastEnrollRequest == enrollRequest.PacketFields['ReqNodeID'] and self.availRouteCount > 0):
      print(enrollRequest.PacketFields)
      enrollRequest.PacketFields['RespNodeID'] = self.nodeID
      enrollRequest.PacketFields['RespNodeIP'] = IP2Int(self.nodeIP)
      enrollRequest.PacketFields['RespNodePort'] = self.nodePort
      packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollRequest, Int2IP(enrollRequest.PacketFields['ReqNodeIP']), enrollRequest.PacketFields['ReqNodePort']) 
      self.lastEnrollRequest = enrollRequest.PacketFields['ReqNodeID']
      self.TCPTxQ.put(packedEnrollResponse)
      print("Enrolled a new Node")
    else:
      self.lastEnrollRequest = enrollRequest.PacketFields['ReqNodeID']


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

  

if __name__ == "__main__":
  rxdq = queue.Queue()
  txdq = queue.Queue()
  mesh = somnMesh(txdq, rxdq)
  mesh.start()

