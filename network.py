import socket
import threading
import time
import os
import json
import sys
from protocol import *

BROADCAST_PORT = 9999
TCP_PORT = 10000

class NetworkManager:
    def __init__(self, on_message_received, on_file_request_callback=None):
        self.peers = {}
        self.my_ip = self.get_local_ip()
        self.on_message_received = on_message_received
        self.on_file_request_callback = on_file_request_callback
        self.running = True

    @staticmethod
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'

    def _draw_progress_bar(self, current, total, length=30):
        if total == 0:
            return
        percent = 100 * (current / total)
        filled = int(length * current // total)
        bar = '█' * filled + '-' * (length - filled)
        sys.stdout.write(f'\rSending: |{bar}| {percent:.1f}%')
        sys.stdout.flush()

    def start_discovery_server(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.bind(('', BROADCAST_PORT))
        
        def listen():
            while self.running:
                try:
                    data, addr = udp.recvfrom(1024)
                    if data.decode() == "WHO_IS_THERE" and addr[0] != self.my_ip:
                        udp.sendto(f"IAM_HERE:{self.my_ip}".encode(), addr)
                except:
                    pass
        
        threading.Thread(target=listen, daemon=True).start()

    def scan_network(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.settimeout(2)
        
        try:
            while self.running:
                udp.sendto(b"WHO_IS_THERE", ('<broadcast>', BROADCAST_PORT))
                
                start_time = time.time()
                while time.time() - start_time < 2:
                    try:
                        data, addr = udp.recvfrom(1024)
                        if data.startswith(b"IAM_HERE"):
                            peer_ip = data.decode().split(":")[1]
                            self.peers[peer_ip] = time.time()
                    except socket.timeout:
                        break
                    except:
                        pass
                
                # Remove offline peers (no response for 10 seconds)
                current_time = time.time()
                offline = [ip for ip, last_seen in self.peers.items() 
                          if current_time - last_seen > 10]
                
                for ip in offline:
                    del self.peers[ip]
                    print(f"[System] Peer offline: {ip}")
                    
        except Exception as e:
            print(f"Scanner Error: {e}")
        finally:
            udp.close()

    def start_tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('', TCP_PORT))
        server.listen(5)
        
        def accept_clients():
            while self.running:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_client, 
                               args=(conn, addr[0]), daemon=True).start()
        
        threading.Thread(target=accept_clients, daemon=True).start()

    def handle_client(self, conn, sender_ip):
        try:
            while True:
                msg_type, length = Protocol.unpack_header(conn)
                if msg_type is None:
                    break

                data = Protocol.recv_all(conn, length)
                if not data:
                    break
                
                if msg_type == MSG_FILE_REQUEST:
                    meta = json.loads(data.decode('utf-8'))
                    is_allowed = (self.on_file_request_callback(meta, sender_ip) 
                                if self.on_file_request_callback else False)
                    
                    if is_allowed:
                        conn.sendall(Protocol.pack_message(MSG_FILE_ACCEPT, "OK"))
                    else:
                        conn.sendall(Protocol.pack_message(MSG_FILE_REJECT, "NO"))
                        break
                else:
                    self.on_message_received(msg_type, data, sender_ip)

        except Exception as e:
            print(f"Handle Error: {e}")
        finally:
            conn.close()

    def send_data(self, target_ip, msg_type, data):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.connect((target_ip, TCP_PORT))
                client.sendall(Protocol.pack_message(msg_type, data))
        except Exception as e:
            print(f"[Send failed] {target_ip}: {e}")

    def send_file(self, target_ip, filepath):
        if not os.path.exists(filepath):
            return False

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        meta = {"filename": filename, "size": filesize}

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((target_ip, TCP_PORT))

            # Send request
            print(f"Requesting to send {filename}...")
            client.sendall(Protocol.pack_message(MSG_FILE_REQUEST, meta))
            
            # Wait for response
            resp_type, _ = Protocol.unpack_header(client)
            
            if resp_type == MSG_FILE_REJECT:
                print(f"Peer rejected {filename}")
                client.close()
                return False

            if resp_type == MSG_FILE_ACCEPT:
                # Read response body
                Protocol.recv_all(client, 2)  # "OK"
                
                # Send metadata (for compatibility)
                client.sendall(Protocol.pack_message(MSG_FILE_META, meta))
                
                # Send file content
                header = struct.pack('>BI', MSG_FILE_DATA, filesize)
                client.sendall(header)

                with open(filepath, 'rb') as f:
                    sent_bytes = 0
                    while chunk := f.read(65536):
                        client.sendall(chunk)
                        sent_bytes += len(chunk)
                        self._draw_progress_bar(sent_bytes, filesize)
                
                print(f"\n[Success] File sent")
                client.close()
                return True

        except Exception as e:
            print(f"\n[File send failed] {e}")
            return False