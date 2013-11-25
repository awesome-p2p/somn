#!/usr/bin/python

class somnRoutingTableEntry:
  nodeID = 0
  nodeAddress = ""
  nodePort = 0

  def __init__(self, nodeid, addr, port):
    nodeID = nodeid
    nodeAddress = addr
    nodePort = port

class somnRoutingTable:
  
  _nodeCount = 0
  _nodeTable = [None, None, None, None, None]

  def addNode(self, nodeid, addr, port):
    if(self._nodeCount >= 5):
      return -1

    entry = somnRoutingTableEntry(nodeid, addr, port)

    for i in range(0,5):
      if self._nodeTable[i] == None:
        self._nodeTable[i] = entry
        self._nodeCount += 1
        #route table is 1-indexed
        return i + 1
  
  #note that the route table is 1-indexed since 0 has a
  # special meaning in a route string
  def getNodeInfoByIndex(self, index):
    return self._nodeTable[index - 1]

  def getNodeIndexFromId(self, nodeId):
    for i in range(0,5):
      if self._nodeTable[i] != None:
        if self._nodeTable[i].nodeID == nodeId:
          return i + 1
    #if id not found, return -1
    return -1

  def getNodeCount(self):
    return self._nodeCount

  def getAvailRouteCount(self):
    return 5 - self._nodeCount

  def clearTable(self):
    self._nodeCount = 0
    self._nodeTable = [None, None, None, None, None]
