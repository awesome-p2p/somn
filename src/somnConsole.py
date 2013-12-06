#!/usr/bin/env python3.2

import somnMesh
import curses
import multiprocessing
import queue
import time

uiRunning = True

#IPC multiprocessing manager
ipcMgr = multiprocessing.Manager()

#Output list written to by all nodes
globalNodeOutput = ipcMgr.list()

#Node list
nodeList = ipcMgr.list()

#Node dictionary
nodeDict = dict()

#pop-up window
popupwin = None


def startupNewNode(txq, rxq, cmdpipe):
  nodetxq = queue.Queue()
  noderxq = queue.Queue()

  node = somnMesh.somnMesh(nodetxq, noderxq, nodePrintCallback)
  node.start()

  time.sleep(1)
  #while node._mainLoopRunning:
  while True:
    #put anything on txq on nodetxq
    try:
      nexttx = txq.get(False)
      nodetxq.put(nexttx)
    except:
      pass

    #put anything on noderxq on rxq
    try:
      nextrx = noderxq.get(False)
      rxq.put(nextrx)
    except:
      pass

    #get next command
    if cmdpipe.poll(0.5):
      nextcmd = cmdpipe.recv()

      if nextcmd == "GETID":
        cmdpipe.send(node.nodeID)
      elif nextcmd == "GETCONN":
        cmdpipe.send(node.routeTable.getConnectedNodes())




  #after node is killed, remove it from dict
  node.join()
  del nodeDict[nodeId]

def nodePrintCallback(nodeId, outputStr):
  globalNodeOutput.append("{0:04X}: {1}".format(nodeId, outputStr))
  
def menu_addnode(scr):
  outputList = globalNodeOutput

  #create queues/pipes for comm with new process
  txq = multiprocessing.Queue()
  rxq = multiprocessing.Queue()
  pipeCon1, pipeCon2 = multiprocessing.Pipe()

  p = multiprocessing.Process(target=startupNewNode, daemon=True, args=(txq, rxq, pipeCon2))

  p.start()

  #wait for node to start and get node id
  time.sleep(1)
  pipeCon1.send("GETID")
  nodeid = pipeCon1.recv()

  nodeDict[nodeid] = (txq, rxq, pipeCon1)
  print("Added node: {0}".format(nodeid))

def menu_quit(scr):
  global uiRunning
  uiRunning = False

def menu_print(scr):
  subwin = scr.derwin(10, 10, 10, 10)
  subwin.border()
  subwin.addstr(1,1,"FFF")
  subwin.refresh()
  subwin.getch()

def menu_sendmsg(scr):
  subwin = scr.derwin(5, 40, 10, 20)

  #get source node
  subwin.border()
  subwin.addstr(1, 1, "Choose Sender: ")
  subwin.refresh()
  curses.echo()
  srcnode = subwin.getstr()

  #get dest node
  subwin.erase()
  subwin.border()
  subwin.addstr(1, 1, "Choose Dest: ")
  subwin.refresh()
  curses.echo()
  destnode = subwin.getstr()

  #get message
  subwin.erase()
  subwin.border()
  subwin.addstr(1, 1, "Enter Message: ")
  subwin.refresh()
  curses.echo()
  messagecontents = str(subwin.getstr())

  srcnodeint = int(srcnode, 16)
  destnodeint = int(destnode, 16)

  if srcnodeint in nodeDict:
    nodeDict[srcnodeint][0].put(somnMesh.somnData(destnodeint, messagecontents))
  else:
    subwin.erase()
    subwin.border()
    subwin.addstr(1,1, "Invalid Source Node")
    subwin.addstr(2,1, "(Press any key)")
    subwin.getch()

  subwin.getch()

menuOptions = [
    ('A', 'Add Node', menu_addnode),
    #('K', 'Kill Nodes', None),
    ('P', 'Print Graph', menu_print),
    ('S', 'Send Message', menu_sendmsg),
    ('Q', 'Quit', menu_quit)]

def drawMenu(scr):
  x = 4
  y = 5
  scr.addstr(y, x, "MAIN MENU:")
  y += 1

  for opt in menuOptions:
    scr.addstr(y, x + 1, "{0}) {1}".format(opt[0], opt[1]))
    y += 1

def drawNodeOutput(scr):
  maxlines = 20
  x = 50
  y = 5
  scr.addstr(y, x, "NODE OUTPUT:")
  y += 1

  while globalNodeOutput is not None and len(globalNodeOutput) > maxlines:
    globalNodeOutput.pop(0)

  if globalNodeOutput is not None:
    for line in globalNodeOutput:
      scr.addstr(y, x, line)
      y += 1

def drawNodeList(scr):
  x = 30
  y = 5
  maxy = y + 20
  scr.addstr(y, x, "NODE LIST:")
  y += 1

  for nodeid in nodeDict:
    if y > maxy:
      scr.addstr(y, x, "...")
      break
    scr.addstr(y, x, "{0:04X}".format(nodeid))
    y += 1
  
def uiMain(mainscr):
  while uiRunning:
    screenwidth = mainscr.getmaxyx()[1]
    screenheight = mainscr.getmaxyx()[0]


    mainscr.timeout(500)
    mainscr.clear()
    mainscr.border()
    mainscr.addstr(1,1, "SOMN Control Panel")
    mainscr.hline(2,1,'=',screenwidth - 2)

    drawMenu(mainscr)
    drawNodeOutput(mainscr)
    drawNodeList(mainscr)

    mainscr.refresh()

    mainscr.addstr(3,1, "Active Processes: {0}".format(len(multiprocessing.active_children())))

    c = mainscr.getch()

    # c is -1 if getch times out
    if c != -1:
      for opt in menuOptions:
        if c == ord(opt[0].lower()) or c == ord(opt[0].upper()):
          if opt[2] is not None:
            opt[2](mainscr)


if __name__ == "__main__":
  curses.wrapper(uiMain)
