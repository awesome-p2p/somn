#!/usr/bin/env python

from struct import *

class somnBasePkt():
  init
  getSrcId
  getDestId

class somnMsgPkt(somnBasePkt):
  getData
  packData
  
class somnBaseRoutePkt(somnBasePkt):
  popRoute
  pushRoute
  getRouteFLags

class somnRtRequestPkt(somnBaseRoutePkt):
  

   

class somnCntPkt

