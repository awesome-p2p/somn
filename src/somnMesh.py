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
    # Do a bunch of stuff
    networkAlive.clear()
    Rx.join()
    Tx.join()

if __name__ == "__main__":
  rxdq = queue.Queue()
  txdq = queue.Queue()
  mesh = somnMesh(txdq, rxdq)
  mesh.start()

