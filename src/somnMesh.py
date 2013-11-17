#!/usr/bin/env python3.3

import somnTCP
import somnPkt
import somnConst
import struct
import queue
import threading
import socket

class somnMesh(threading.Thread):
  TxQ = queue.Queue()
  RxQ = queue.Queue()
  routeTable = [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]
  cacheId = [0,0]
  cacheRoute = [0,0,0,0]

  _mainLoopRunning = 0
  
  def __init__(self, TxDataQ, RxDataQ):
    threading.Thread.__init__(self)
    self.TxDataQ = TxDataQ
    self.RxDataQ = RxDataQ
     
  def enroll(self):
    print("enrolling")
    udpTx = socket.socket(

  def run(self):
    socket.setdefaulttimeout(5)
    networkAlive = threading.Event()
    networkAlive.set()
    Rx = somnTCP.startSomnRx(networkAlive, self.RxQ)
    Tx = somnTCP.startSomnTx(networkAlive, self.TxQ)
    self.enroll()
    
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

