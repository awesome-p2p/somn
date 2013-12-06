#!/usr/bin/env python3.2

import somnMesh
import curses
import multiprocessing

uiRunning = True

#IPC multiprocessing manager
ipcMgr = multiprocessing.Manager()

#Output list written to by all nodes
globalNodeOutput = ipcMgr.list()

#Node list
nodeList = ipcMgr.list()


def startupNewNode():
  node = somnMesh.CreateNode(nodePrintCallback)
  node.start()
  nodeList.append(node.nodeID)
  node.join()
  nodeList.remove(node.nodeID)

def nodePrintCallback(nodeId, outputStr):
  globalNodeOutput.append("{0:04X}: {1}".format(nodeId, outputStr))
  
def menu_addnode(scr):
  outputList = globalNodeOutput
  p = multiprocessing.Process(target=startupNewNode, daemon=True)
  p.start()

def menu_quit(scr):
  global uiRunning
  uiRunning = False

def menu_print(scr):
  
  pass

def menu_sendmsg(scr):
  pass

menuOptions = [
    ('A', 'Add Node', menu_addnode),
    ('K', 'Kill Nodes', None),
    ('Q', 'Quit', menu_quit),
    ('P', 'Print Graph', menu_print)
    ('S', 'Send Message', menu_sendmsg)]

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
  x = 30
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
  x = 80
  y = 5
  scr.addstr(y, x, "NODE LIST:")
  y += 1

  for line in nodeList:
    scr.addstr(y, x, "{0:04X}".format(line))
    y += 1
  
def uiMain(mainscr):
  mainscr.timeout(500)
  while uiRunning:
    screenwidth = mainscr.getmaxyx()[1]
    screenheight = mainscr.getmaxyx()[0]


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
