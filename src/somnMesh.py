#!/usr/bin/env python3.3

import somnTCP
import somnUDP
import somnPkt
import somnConst
import struct
import queue
import threading
import socket

class somnMesh(threading.Thread):
  TCPTxQ = queue.Queue()
  TCPRxQ = queue.Queue()
  UDPRxQ = queue.Queue()
  routeTable = [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]
  cacheId = [0,0]
  cacheRoute = [0,0,0,0]
  _mainLoopRunning = 0
  enrolled = False
  
  def __init__(self, TxDataQ, RxDataQ):
    threading.Thread.__init__(self)
    self.CommTxQ = TxDataQ
    self.CommRxQ = RxDataQ
     
  def enroll(self):
    print("enrolling")
    tcpRespTimeout = False
    routeIndex = 0
    ACK = self.nodeID ^ self.nodeIP
    enrollPkt = somnPkt.SomnPacket()
    enrollPkt.InitEmpty("NodeEnrollment")
    enrollPkt.PacketFields['ReqNodeID'] = self.nodeID
    enrollPkt.PacketFields['ReqNodeIP'] = self.nodeIP
    enrollPkt.PacketFields['ReqNodePort'] = self.nodePort
    enrollPkt.PacketFields['ACKSeq'] = ACK

    udp = somnUDP.somnUDPThread(enrollPkt, self.UDPRxQ, self.networkAlive)
    udp.start()
    while routeIndex < 3 or not tcpRespTimeout:
      try:
        enrollResponse = self.TCPRxQ.get(timeout = 30)
      except:
        tcpRespTimeout = True
        break
      if enrollResponse.PacketType == "EnrollResponse" and enrollResponse.PacketFields['ACKSeq'] == ACK:
        routeTable[routeIndex] = (enrollResponse.PacketFields['RespNodeID'], enrollResponse.PacketFields['RespNodeIP'], enrollResponse.PacketFields['RespNodePort'])
        routeIndex = routeIndex + 1
        # encapsulate enrollResponse 
        self.TCPTxQ.put(packedEnrollResponse)
        enrolled = True
    return udp  
    
  def run(self):
    socket.setdefaulttimeout(5)
    networkAlive = threading.Event()
    networkAlive.set()
    Rx = somnTCP.startSomnRx(networkAlive, self.TCPRxQ)
    Tx = somnTCP.startSomnTx(networkAlive, self.TCPTxQ)
    while not enrolled:
      self.enroll()
      if not enrolled:
        # then we are on our own network
        # somehow....god I am tired.
    #start main loop to handle incoming queueus
    self._mainLoopRunning = 1
    while self._mainLoopRunning:
      self._handleTcpRx()
      self._handleUdpRx()
      self._handleTx()

    # Do a bunch of stuff
    networkAlive.clear()
    Rx.join()
    Tx.join()

  def _handleTx():
    pass
 
  def _handleTcpRx():
    pass

  def _handleUdpRx():
    pass



if __name__ == "__main__":
  rxdq = queue.Queue()
  txdq = queue.Queue()
  mesh = somnMesh(txdq, rxdq)
  mesh.start()

