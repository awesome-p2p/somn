#!/usr/bin/env python3.3
import threading
import socket
import queue
import time
import somnPkt

globalSocketRunning = None
globalSocketSubscribers = []
UDPAlive = True
networkAlive = True

def globalSocketHandler():
    global globalSocketRunning
    print("Starting global socket handler")
    globalSocketRunning = True
  
    udpSkt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    udpSkt.bind(('', 45000))
    #TODO networkAlive and UDPAlive need to be threading events that we can kill to bring the UDP thread down...
    while networkAlive and UDPAlive:
      try:
        data, addr = udpSkt.recvfrom(24)  
      except socket.timeout:
        #print("udp looping")
        pass
      #packet = somnPkt.SomnPacket()
      #packet.Decode(data)
      else:
        for subscriber in globalSocketSubscribers:
          subscriber.udpSocketCallback(data)
        #self.RxQ.put(data)
    udpSkt.close()


class somnUDPThread(threading.Thread):
  def __init__(self, enrollPkt, RxQ, networkAlive, UDPAlive):
    threading.Thread.__init__(self)
    self.enrollPkt = enrollPkt
    self.RxQ = RxQ
    self.networkAlive = networkAlive
    self.UDPAlive = UDPAlive
  def run(self):
    global globalSocketRunning
    udpSkt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
    udpSkt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    udpSkt.sendto(self.enrollPkt.ToBytes(), ('<broadcast>', 45000))
    udpSkt.close()

    if globalSocketRunning != True:
      globalSocketThread = threading.Thread(target = globalSocketHandler)
      globalSocketThread.start()
      globalSocketSubscribers.append(self)
      
  def udpSocketCallback(self, data):
    self.RxQ.put(data)


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
