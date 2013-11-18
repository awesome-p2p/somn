#!/usr/bin/env python3.3
import threading
import socket
import queue
import time
import somnPkt

class somnUDPThread(threading.Thread):
  def __init__(self, enrollPkt, RxQ, networkAlive, UDPAlive):
    threading.Thread.__init__(self)
    self.enrollPkt = enrollPkt
    self.RxQ = RxQ
    self.networkAlive = networkAlive
    self.UDPAlive = UDPAlive
  def run(self):
    udpSkt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    udpSkt.sendto("Hello There".encode("utf-8"), ('<broadcast>', 45000))
    udpSkt.close()

    udpSkt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    udpSkt.bind(('', 45000))
    while self.networkAlive.is_set() and self.UDPAlive.is_set():
      try:
        data, addr = udpSkt.recvfrom(24)  
      except socket.timeout:
        print("udp looping")
        pass
      #packet = somnPkt.SomnPacket()
      #packet.Decode(data)
      else:
        self.RxQ.put(data)
    udpSkt.close()

if __name__=="__main__":
  socket.setdefaulttimeout(5)
  rxdq = queue.Queue()
  networkAlive = threading.Event()
  udpThread = somnUDPThread("Hello There", rxdq, networkAlive)
  networkAlive.set()
  udpThread.start()
  time.sleep(30)
  packet = rxdq.get(timeout = 15)
  print(packet)
  networkAlive.clear()
  udpThread.join()
