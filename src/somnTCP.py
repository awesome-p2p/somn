#!/usr/bin/env python

import socket
import threading
#import somnConst
import Queue
import sys

class RxThread(threading.Thread):
  def __init__(self, ip, port, RxQ, RxAlive):
    threading.Thread.__init__(self)
    self.ip = ip
    self.port = port
    self.RxQ = RxQ
    self.RxAlive = RxAlive
  def run(self):
    try:
      skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error as msg:
      print "Rx Thread Failed"
      skt = None
      sys.exit(1)
    
    try:
      skt.bind((self.ip, self.port))
    except socket.error as msg:
      print "Rx bind failed"

    while (self.RxAlive.is_set() and  (skt != None)):      
      try:
        skt.listen(1)
      except socket.error as msg:
        skt.close()
        skt = None
        self.RxAlive.clear()
        print "Rx Listen failed" 
        break 

      try:
        con, sourceNodeIp = skt.accept()
      except socket.timeout:
        pass
      else:
        while 1:
          pktRx = con.recv(1024)#somnConst.MAX_PACKET_SIZE)
          if not pktRx: break
          self.RxQ.put(pktRx)
        con.close()

    if skt is not None:  skt.close()  
    print "Rx thread shutting down"


class TxThread(threading.Thread):
  def __init__(self, TxQ, TxAlive):
    threading.Thread.__init__(self)
    self.TxQ = TxQ
    self.TxAlive = TxAlive
  def run(self):
    while self.TxAlive.is_set():
      try:
        pkt = self.TxQ.get(False)
        self.TxQ.task_done()
      except Queue.Empty:
        pass
      else:
        #IP = pkt.destIP
        #PORT = pkt.destPort
        IP = "127.0.0.1"
        PORT = 45000
        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        skt.connect((IP, PORT))
        skt.send(pkt)
        skt.close()
    
    print "Tx Thread shutting down"

     
def startSomnRx(RxAlive, RxQ):
  #localhostIp = netifaces.ifaddresses('eth0')[netifaces.AF_INET[0]['addr']
  #localhostPort = somnConst.DEFAULT_PORT
  localhostIp = "127.0.0.1" 
  localhostPort = 45000
  somnRx = RxThread(localhostIp, localhostPort, RxQ, RxAlive)
  somnRx.start()
  return somnRx
     
  
def startSomnTx(TxAlive, TxQ):
  somnTx = TxThread(TxQ, TxAlive)
  somnTx.start()
  return somnTx

def lbTest():
  socket.setdefaulttimeout(15)
  TxQ = Queue.Queue()
  RxQ = Queue.Queue()
  networkAlive = threading.Event()
  networkAlive.set()
  Rx = startSomnRx(networkAlive, RxQ)
  Tx = startSomnTx(networkAlive, TxQ) 
  testPkt = "Hello SOMN"
  TxQ.put(testPkt)
  echoPkt = RxQ.get()    
  print echoPkt
  RxQ.task_done() 
  networkAlive.clear()
  Tx.join()
  Rx.join()
