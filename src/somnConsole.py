#!/usr/bin/env python3.2

import somnMesh
import curses
import multiprocessing

uiRunning = True

#IPC multiprocessing manager
ipcMgr = multiprocessing.Manager()

#Output list written to by all nodes
globalNodeOutput = ipcMgr.list()


def startupNewNode(nodeOutputList):
  node = somnMesh.CreateNode(nodePrintCallback)
  node.start()
  node.join()

def nodePrintCallback(nodeId, outputStr):
  globalNodeOutput.append("{0:04X}: {1}".format(nodeId, outputStr))
  
def menu_addnode(scr):
  outputList = globalNodeOutput
  p = multiprocessing.Process(target=startupNewNode, args=(outputList,) , daemon=True)
  p.start()

def menu_quit(scr):
  global uiRunning
  uiRunning = False

menuOptions = [
    ('A', 'Add Node', menu_addnode),
    ('K', 'Kill Nodes', None),
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
  
def uiMain(mainscr):
  while uiRunning:
    screenwidth = mainscr.getmaxyx()[1]
    screenheight = mainscr.getmaxyx()[0]


    mainscr.clear()
    mainscr.timeout(500)
    mainscr.hline(0,0,'=',screenwidth)
    mainscr.addstr(1,1, "SOMN Control Panel")
    mainscr.hline(2,0,'=',screenwidth)

    drawMenu(mainscr)
    drawNodeOutput(mainscr)

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
