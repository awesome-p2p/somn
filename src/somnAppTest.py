#!/usr/bin/python3.2

import cmd
import queue
import time
from somnMesh import *

TxQ = queue.Queue()
RxQ = queue.Queue()

class somnIf(cmd.Cmd):
  def do_send(self, s):
    line = s.split()
    if len(line) != 2:
      print("*** invalid number of arguments ***")
      return
    packet = somnData(int(line[0], 16),line[1])  
    TxQ.put(packet)

  def do_read(self, s):
    try:
      packet = RxQ.get(False)
    except:
      return
    print(packet)

  def do_exit(self, s):
    return True

if __name__ =="__main__":
  somnNode = somnMesh(TxQ, RxQ)
  somnNode.start()
  time.sleep(5)
  somnIf().cmdloop()
  somnNode._mainLoopRunning = 0
  somnNode.join() 
  exit() 
