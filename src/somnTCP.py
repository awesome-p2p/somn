#!/usr/bin/env python

import socket
import threading
import somnConst
import queue

class RxThread(threading.Thread):
  def __init__(self, ip, port, RxQ, RxAlive):
    threading.Thread.__init__(self)
    self.ip = ip
    self.port = port
    self.rxQ = RxQ
    self.RxAlive = RxAlive
  def run(self):
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    skt.bind((self.ip, self.port))

    while threading.isSet(self.RxAlive):
      skt.listen(1)

      con, sourceNodeIp = skt.accept()

      while 1:
        pktRx = con.recv(somnConst.MAX_PACKET_SIZE)
        if not pktRx: break
        self.RxQ.put(pktRx)
      con.close()


class TxThread(threading.Thread):
  def __init__(self, TxQ, TxAlive):
    threading.Thread.__init__(self)
    self.TxQ = TxQ
    self.TxAlive = TxAlive
  def run(self):
    while threading.isSet(self.TxAlive):
      pkt = TxQ.get()
      IP = pkt.destIP
      PORT = pkt.destPort
      skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      skt.connet((IP, PORT))
      skt.send(pkt.raw())
      skt.close()

     
def startSomnRx(RxAlive, RxQ):
  #localhostIp = netifaces.ifaddresses('eth0')[netifaces.AF_INET[0]['addr']
  #localhostPort = somnConst.DEFAULT_PORT
  localhostIp = "127.0.0.1" 
  localhostPort = 56000
  somnRx = RxThread(localhostIp, localhostPort, RxQ, RxAlive))
  somnRx.start()
  return somnRx
     
  
def startSomnTx(TxAlive, TxQ):
  somnTx = TxThread(TxAlive, TxQ)
  somnTx.start()
  return somnTx

def main():
  TxQ = queue.queue
  networkAlive = threading.Event
  TxAlive.set()
  RxAlive.set()
  Rx = startSomnRx(networkAlive, RxQ)
  Tx = startSomnTx(networkAlive, TxQ) 
  TxQ.put(testPkt)
  RxQ.get(echoPkt)     
  networkAlive.clear()
  Tx.join()
  Rx.join()

if __name__ == "__main__":
  main()
