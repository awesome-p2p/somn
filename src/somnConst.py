LOOPBACK_MODE = 0
SOMN_LOOPBACK_IP = "127.0.0.1"
SOMN_LOOPBACK_PORT = 45000
LOOPBACK_MSG_SIZE = 4
WORD_SIZE = 4

SOMN_MSG_PKT_SIZE = 19 * WORD_SIZE
SOMN_MESH_PKT_SIZE = 6 * WORD_SIZE
SOMN_ROUTE_PKT_SIZE = 4 * WORD_SIZE

def IP2Int(IP):
    o = list(map(int, IP.split('.')))
    res = (16777216 * o[0]) + (65536 * o[1]) + (256 * o[2]) + o[3]
    return res

def Int2IP(Int):
    o1 = int(Int / 16777216) % 256
    o2 = int(Int / 65536) % 256
    o3 = int(Int / 256) % 256
    o4 = int(Int) % 256
    return '%(o1)s.%(o2)s.%(o3)s.%(o4)s' % locals()
