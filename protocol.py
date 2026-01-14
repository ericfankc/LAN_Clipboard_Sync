import struct
import json

# Message type definitions
MSG_TEXT = 1
MSG_FILE_META = 2
MSG_FILE_DATA = 3
MSG_FILE_REQUEST = 4
MSG_FILE_ACCEPT = 5
MSG_FILE_REJECT = 6

class Protocol:
    @staticmethod
    def pack_message(msg_type, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')
        
        header = struct.pack('>BI', msg_type, len(data))
        return header + data

    @staticmethod
    def unpack_header(sock):
        header_data = Protocol.recv_all(sock, 5)
        if not header_data:
            return None, None
        return struct.unpack('>BI', header_data)

    @staticmethod
    def recv_all(sock, n):
        data = b''
        while len(data) < n:
            try:
                packet = sock.recv(min(n - len(data), 65536))
                if not packet:
                    return None
                data += packet
            except:
                return None
        return data