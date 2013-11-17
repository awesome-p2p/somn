#!/usr/bin/env python

import socket
import threading
from somnConst import *
import queue
import sys
import struct
import time
import somnPkt

class RxThread(threading.Thread):
  def __init__(self, ip, port, RxQ, RxAlive):
    threading.Thread.__init__(self)
    self.ip = ip
    self.port = port
    self.RxQ = RxQ
    self.RxAlive = RxAlive
  def run(self):
    try:  # create a socket
      skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
      print("Rx Thread Failed")
      skt = None
      self.RxAlive.clear()
      exit()

    try:  # bind to localhost ip/port
      skt.bind((self.ip, self.port))
    except socket.error as msg:
      print("Rx bind failed")
      print(msg)
      self.RxAlive.clear()
 
    print("Rx Thread Bound")
    while (self.RxAlive.is_set() and  (skt != None)):      
      try:  # listen for incoming packets
        skt.listen(1)
      except socket.error as msg:
        skt.close()
        skt = None
        self.RxAlive.clear()
        print("Rx Listen failed") 
        break 
      print("Rx Thread listening")
      try:  # accept connections
        con, sourceNodeIp = skt.accept()
      except socket.timeout:
        con.close()
        pass
      else: # read all data from socket, push onto the queue
        pktRx = b''
        if LOOPBACK_MODE:
          MSGLEN = 4# size of test message "Hello Somn"
        else:
          MSGLEN = 4
          while len(pktRx) < MSGLEN:
            chunk = con.rev(MSGLEN - len(pktRx))
            if chunk == b'': break
            pktRx = pktRx + chunk
          pktFlag = (struct.unpack('!I',pktRx)[0] & (3 << 30)) >> 30
          # Determine incoming packet lengt from packet type flag
          if pktFlag == 0:
            MSGLEN = (SOMN_MSG_PKT_SIZE - WORD_SIZE)
          elif pktFlag == 1:
            MSGLEN = (SOMN_MESH_PKT_SIZE - WORD_SIZE)
          elif pktFlag == 2:
            MSGLEN = (SOMN_ROUTE_PKT_SIZE - WORD_SIZE)
          elif pktFlag == 3:
            MSGLEN = 0	# No packets use this flag currently
        while len(pktRx) < MSGLEN:
          chunk = con.recv(MSGLEN - len(pktRx))
          if chunk == b'': break
          pktRx = pktRx + chunk
          packet = somnPacket()
          packet.decode(pktRx)
          self.RxQ.put(packet)
        con.close()

    if skt is not None:  
      try:
        skt.shutdown(0)
      except socket.error:
        pass
      skt.close()	  
    print("Rx thread shutting down")


class TxThread(threading.Thread):
  def __init__(self, TxQ, TxAlive):
    threading.Thread.__init__(self)
    self.TxQ = TxQ
    self.TxAlive = TxAlive
  def run(self):
    while self.TxAlive.is_set():  
      try:  # check for available outgoing packets
        packet = self.TxQ.get(False)
      except queue.Empty:
        pass
      else: # send packet to desired peer
        pktTx = packet.packet.toBytes()
        if LOOPBACK_MODE:
          IP = SOMN_LOOPBACK_IP
          PORT = SOMN_LOOPBACK_PORT
        else:
          IP = packet.ip
          PORT = packet.port
        try:  # attempt to create a socket, break on failure
          skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
          self.TxAlive.clear()
          break
        try:  # attempt to connect to desired node, if fails, generate a bad route event
          skt.connect((IP, PORT))
        except socket.error:
          # this should generate a bad route event
          break
        # hack for socket test
        totalsent = 0
        if LOOPBACK_MODE:
          MSGLEN = len(pkt)
          TxData = pkt
        else:
          MSGLEN = pkt.len
          TxData = pkt.datagram
        while  totalsent < MSGLEN:
          sent = skt.send(TxData)
          if sent == 0:
            raise RuntimeError("Python 3 sockets are dumb")
          totalsent = totalsent + sent
        self.TxQ.task_done()
        skt.shutdown(1)
        skt.close()
    
    print("Tx Thread shutting down")


# Rx thread helper start function     
def startSomnRx(RxAlive, RxQ):
  if LOOPBACK_MODE:
    localhostIp = SOMN_LOOPBACK_IP
    localhostPort = SOMN_LOOPBACK_PORT
  else:
    localhostIp = getLocalHostIp() #netifaces.ifaddresses('eth0')[netifaces.AF_INET[0]['addr']]
    localhostPort = somnConst.DEFAULT_PORT
  somnRx = RxThread(localhostIp, localhostPort, RxQ, RxAlive)
  somnRx.start()
  return somnRx
     

# Tx thread helper start function
def startSomnTx(TxAlive, TxQ):
  somnTx = TxThread(TxQ, TxAlive)
  somnTx.start()
  return somnTx

# simple loopback test function that delivers a hello somn message over the loopback address
def lbTest():
  socket.setdefaulttimeout(5)
  TxQ = queue.Queue()
  RxQ = queue.Queue()
  networkAlive = threading.Event()
  networkAlive.set()
  Rx = startSomnRx(networkAlive, RxQ)
  time.sleep(2)
  Tx = startSomnTx(networkAlive, TxQ) 
  testPkt = struct.pack('!I', 3229877312)
  TxQ.put(testPkt)
  echoPkt = RxQ.get(timeout = 10)    
  RxQ.task_done() 
  networkAlive.clear()
  Tx.join()
  Rx.join()
  pkt = struct.unpack('!I', echoPkt)
  print((pkt[0] & (3 << 30)) >> 30)
