#!/bin/python


import struct

class SomnPacketType():
    Unknown = "Unknown"
    Message = "Message"
    RouteRequest = "RouteRequest"
    BadRoute = "BadRoute"
    AddConnection = "AddConnection" 
    DropConnection = "DropConnection"
    NodeEnrollment = "NodeEnrollment"


class SomnPacket:
    PacketType = SomnPacketType.Unknown
    PacketFields = {}

    _rawData = ""
    _initialized = False



    def InitEmpty(self, packetType):
        #Check if packet has already been initialized
        if self._initialized == True:
            print("Attempting to re-initialize packet!")
            return

        self._initialized = True

        #create packet fields and initialize 
        self.PacketType = packetType
        if packetType == SomnPacketType.Message:
            self.PacketFields['Route'] = 0
            self.PacketFields['Flags'] = 0x0
            self.PacketFields['SourceID'] = 0
            self.PacketFields['DestID'] = 0
            self.PacketFields['Message'] = []
        elif packetType == SomnPacketType.RouteRequest:
            self.PacketFields['Route'] = 0
            self.PacketFields['Flags'] = 0x2
            self.PacketFields['SourceID'] = 0
            self.PacketFields['DestID'] = 0
            self.PacketFields['LastNodeID'] = 0
            self.PacketFields['RouteRequestCode'] = 0
            self.PacketFields['HTL'] = 0
            self.PacketFields['ReturnRoute'] = 0
        else:
            print("Not a message")


    def ToBytes(self):
        if self.PacketType == SomnPacketType.Message:
            word1 = ((self.PacketFields['Flags'] << 30) & 0xC0000000) | self.PacketFields['Route']
            word2 = (self.PacketFields['DestID'] << 16) | self.PacketFields['SourceID']
            message = bytes(4*16)
            return struct.pack('!IIxxxx64s', word1, word2,message)


    def Decode(self, rawData):
        #message packet is 76 bytes long
        if len(rawData) == 76:
            self.PacketType = SomnPacketType.Message

            decoded = struct.unpack('!IIxxxx64s', rawData)
            self.PacketFields['Route'] = decoded[0] & 0x3FFFFFFF
            self.PacketFields['Flags'] = decoded[0] >> 30 
            self.PacketFields['DestID'] = decoded[1] >> 16
            self.PacketFields['SourceID'] = decoded[1] & 0xFFFF 
        #length 16 is mesh routing packet
        elif len(rawData == 16):
            decoded = struct.unpack('!IIII', rawData)

            self.PacketFields['Route'] = decoded[0] & 0x3FFFFFFF
            self.PacketFields['Flags'] = decoded[0] >> 30 
            self.PacketFields['DestID'] = decoded[1] >> 16
            self.PacketFields['SourceID'] = decoded[1] & 0xFFFF 

            #distinguish between route request and bad route
            code = (decoded[2] >> 16) & 0x0FFF
            #if code = 1, route request
            if code == 1:
                self.PacketType = SomnPacketType.RouteRequest
                self.PacketFields['LastNodeID'] = decoded[2] & 0xFFFF
                self.PacketFields['ReturnRoute'] = decoded[3] & 0x3FFFFFFF

            #if code = 2, bad route
            elif code == 2:
                self.PacketType = SomnPacketType.BadRoute

        #length 24 is mesh network packet
        elif len(rawData == 24):
            decoded = struct.unpack('!IIIIII', rawData)

            #note that enrollment packet field names req = enrolling
            self.PacketFields['Route'] = decoded[0] & 0x3FFFFFFF
            self.PacketFields['Flags'] = decoded[0] >> 30 
            self.PacketFields['ReqNodeID'] = decoded[1] & 0xFFFF
            self.PacketFields['RespNodeID'] = decoded[1] >> 16
            self.PacketFields['ReqNodePort'] = decoded[2] & 0xFFFF
            self.PacketFields['RespNodePort'] = decoded[2] >> 16
            self.PacketFields['ReqNodeIP'] = decoded[3]
            self.PacketFields['RespNodeIP'] = decoded[4]
            self.PacketFields['AckSeq'] = decoded[5] & 0xFFFF

            #distinguish between types of network packets
            code = (decoded[5] >> 16)
            #code = 1, add connection packet
            if code == 1:
                self.PacketType = SomnPacketType.AddConnection

            #code = 2, drop connection packet
            elif code == 2:
                self.PacketType = SomnPacketType.DropConnection

            #code = 3, node enrollment packet
            elif code == 3:
                self.PacketType = SomnPacketType.NodeEnrollment


    
if __name__ == "__main__":
    p1 = SomnPacket()
    p1.InitEmpty(SomnPacketType.Message)

    p1.PacketFields['Route'] = 0xF0
    p1.PacketFields['Flags'] = 0x1
    p1.PacketFields['DestID'] = 0xFFFF
    p1.PacketFields['SourceID'] = 0xAAAA



    print(p1.PacketFields)
    raw = p1.ToBytes()

    print(len(raw))
    print(raw)
    p1.Decode(raw)
    print(p1.PacketFields)


