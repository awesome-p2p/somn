#!/usr/bin/env python3.3

import somnTCP
import somnUDP
import somnPkt
import somnConst
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
  routeTable = [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]
  cacheId = [0,0]
  cacheRoute = [0,0,0,0]
  _mainLoopRunning = 0
  enrolled = False
  nodeID = 0
  nodeIP = "0.0.0.0"
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
    routeIndex = 0
    ACK = 56
    enrollPkt = somnPkt.SomnPacket()
    enrollPkt.InitEmpty("NodeEnrollment")
    enrollPkt.PacketFields['ReqNodeID'] = self.nodeID
    enrollPkt.PacketFields['ReqNodeIP'] = self.nodeIP
    enrollPkt.PacketFields['ReqNodePort'] = self.nodePort
    enrollPkt.PacketFields['ACKSeq'] = ACK

    udp = somnUDP.somnUDPThread(enrollPkt, self.UDPRxQ, self.networkAlive, self.UDPAlive)
    udp.start()
    while routeIndex < 3 or not tcpRespTimeout:
      print("Enroll Attempt Loop")
      try:
        enrollPkt = self.TCPRxQ.get(timeout = 5)
      except queue.Empty:
        tcpRespTimeout = True
        print("Enroll failed")
        break 
      else:
        enrollResponse = somnPkt.SomnPacket()
        enrollResponse.Decode(enrollPkt)
        if enrollResponse.PacketType == somnPkt.SomnPacketType.NodeEnrollment and enrollResponse.PacketFields['ACKSeq'] == ACK:
          routeTable[routeIndex] = (enrollResponse.PacketFields['RespNodeID'], enrollResponse.PacketFields['RespNodeIP'], enrollResponse.PacketFields['RespNodePort'])
          routeIndex = routeIndex + 1
          packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollResponse, enrollResponse.PacketFields['RespNodeIP'], enrollResponse.Packetfields['RespNodePort']) 
          self.TCPTxQ.put(packedEnrollResponse)
          enrolled = True
          availRouteCount = availRouteCount - 1
          print("Enrolled complete")
    return udp  
  
    
  def run(self):
    socket.setdefaulttimeout(5)
    self.networkAlive.set()
    Rx = somnTCP.startSomnRx(self.networkAlive, self.TCPRxQ)
    Tx = somnTCP.startSomnTx(self.networkAlive, self.TCPTxQ)
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
    print("Handle TX")
    pass
 
  def _handleTcpRx(self):
    print("Handle RX")
    try:
      RxPkt = self.TCPRxQ.get(False)
    except:
      pass
    
  def _handleUdpRx(self):
    print("handleUDP")
    try:
      enrollRequest = self.UDPRxQ.get(False)
    except:
      return
    
    if self.availRouteCount > 1 or (self.lastEnrollRequest == enrollRequest.PacketFields['ReqNodeID'] and self.availRouteCount > 0):
      print(enrollRequest)
      enrollRequest.PacketFields['RespNodeID'] = self.nodeID
      enrollRequest.PacketFields['RespNodeIP'] = self.nodeIP
      enrollRequest.PacketFields['RespNodePort'] = self.nodePort
      packedEnrollResponse = somnPkt.SomnPacketTxWrapper(enrollRequest, enrollResponse.PacketFields['ReqNodeIP'], enrollResponse.Packetfields['ReqNodePort']) 
      self.lastEnrollRequest = enrollRequest.PacketFields['ReqNodeID']
      self.TCPTxQ.put(packedEnrollResponse) 
    else:
      self.lastEnrollRequest = enrollRequest.PacketFields['ReqNodeID']

if __name__ == "__main__":
  rxdq = queue.Queue()
  txdq = queue.Queue()
  mesh = somnMesh(txdq, rxdq)
  mesh.start()

