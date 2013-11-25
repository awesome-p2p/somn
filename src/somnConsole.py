#!/usr/bin/python

import somnMesh
import curses

uiRunning = True

globalNodeOutput = []


def nodePrintCallback(nodeId, outputStr):
  globalNodeOutput.append("{0:04X}: {1}".format(nodeId, outputStr))
  
def menu_addnode(scr):
  node = somnMesh.CreateNode(nodePrintCallback)
  node.start()

def menu_quit(scr):
  global uiRunning
  uiRunning = False

menuOptions = [
    ('A', 'Add Node', menu_addnode),
    ('K', 'Kill Nodes', None),
    ('Q', 'Quit', menu_quit)]

def drawMenu(scr):
  x = 10
  y = 5
  scr.addstr(y, x, "Main Menu")
  y += 1

  for opt in menuOptions:
    scr.addstr(y, x, "{0}) {1}".format(opt[0], opt[1]))
    y += 1

def drawNodeOutput(scr):
  maxlines = 20
  x = 40
  y = 5
  scr.addstr(y, x, "Node Output:")
  y += 1

  while len(globalNodeOutput) > maxlines:
    globalNodeOutput.pop(0)

  for line in globalNodeOutput:
    scr.addstr(y, x, line)
    y += 1
  
def uiMain(mainscr):
  while uiRunning:
    mainscr.clear()
    mainscr.timeout(500)
    mainscr.addstr(0,0, "Test!")

    drawMenu(mainscr)
    drawNodeOutput(mainscr)

    mainscr.refresh()
    mainscr.addstr(1,1, "{0}".format(len(globalNodeOutput)))

    c = mainscr.getch()

    # c is -1 if getch times out
    if c != -1:
      for opt in menuOptions:
        if c == ord(opt[0].lower()) or c == ord(opt[0].upper()):
          if opt[2] is not None:
            opt[2](mainscr)


if __name__ == "__main__":
  curses.wrapper(uiMain)
