import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import pyperclip
import platform
import subprocess
import json
import time
from network import NetworkManager, MSG_TEXT, MSG_FILE_META, MSG_FILE_DATA

class GuiNetworkManager(NetworkManager):
    def __init__(self, on_message, on_file_request, progress_callback):
        super().__init__(on_message, on_file_request)
        self.progress_callback = progress_callback

    def _draw_progress_bar(self, current, total, length=30):
        if total > 0:
            self.progress_callback(current, total)

class ClipboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cross-Network Synchronizer (Bidirectional + Consent)")
        self.root.geometry("600x550")
        
        self.last_clipboard = ""
        self.is_remote_update = False
        self.incoming_file_meta = None
        self.selected_peer_ip = None

        self.net = GuiNetworkManager(
            self.on_data_received,
            self.ask_file_permission,
            self.update_progress
        )
        
        self.setup_ui()
        self.net.start_discovery_server()
        self.net.start_tcp_server()
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()
        self.refresh_peer_list()
        self.scan_peers()

    def ask_file_permission(self, meta, sender_ip):
        """Ask user whether to accept incoming file"""
        filename = meta['filename']
        filesize_mb = meta['size'] / (1024 * 1024)
        
        result = messagebox.askyesno(
            "Receive File Request",
            f"User from {sender_ip} wants to send a file:\n\n"
            f"Filename: {filename}\n"
            f"Size: {filesize_mb:.2f} MB\n\n"
            f"Accept this file?"
        )
        
        if result:
            self.root.after(0, lambda: self.file_label.config(
                text=f"Receiving {filename}...", fg="orange"))
            self.selected_peer_ip = sender_ip
            self.root.after(0, lambda: self.send_btn.config(
                state=tk.NORMAL, 
                text=f"Send back to {sender_ip}", 
                bg="#FF9800"))
        
        return result

    def setup_ui(self):
        # Top frame
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X, padx=10)
        tk.Label(top_frame, text=f"Local IP: {self.net.my_ip}", 
                font=("Arial", 12, "bold"), fg="#333").pack(side=tk.LEFT)
        tk.Button(top_frame, text="Rescan", 
                 command=self.scan_peers).pack(side=tk.RIGHT)

        # Middle frame
        mid_frame = tk.Frame(self.root)
        mid_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # Peer list panel
        left_panel = tk.LabelFrame(mid_frame, text="Online Peers")
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        self.peer_listbox = tk.Listbox(left_panel, width=25, height=15)
        self.peer_listbox.pack(expand=True, fill=tk.Y, padx=5, pady=5)
        self.peer_listbox.bind('<<ListboxSelect>>', self.on_peer_select)

        # Clipboard panel
        right_panel = tk.LabelFrame(mid_frame, text="Clipboard Sync")
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        self.text_area = tk.Text(right_panel, height=10, width=40, state=tk.DISABLED)
        self.text_area.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # File transfer panel
        bottom_frame = tk.LabelFrame(self.root, text="File Transfer")
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        self.file_label = tk.Label(bottom_frame, text="Ready", fg="gray")
        self.file_label.pack(side=tk.LEFT, padx=5)
        self.send_btn = tk.Button(bottom_frame, text="Select File & Send",
                                  command=self.send_file_action, state=tk.DISABLED,
                                  bg="#4CAF50", fg="white")
        self.send_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        self.progress = ttk.Progressbar(bottom_frame, orient=tk.HORIZONTAL,
                                       length=100, mode='determinate')
        self.progress.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

    def scan_peers(self):
        threading.Thread(target=self.net.scan_network, daemon=True).start()

    def refresh_peer_list(self):
        current_selection = self.peer_listbox.curselection()
        selected_ip = self.peer_listbox.get(current_selection) if current_selection else None
        
        self.peer_listbox.delete(0, tk.END)
        for ip in self.net.peers:
            self.peer_listbox.insert(tk.END, ip)
            if ip == selected_ip:
                self.peer_listbox.select_set(tk.END)
        
        self.root.after(3000, self.refresh_peer_list)

    def on_peer_select(self, event):
        selection = self.peer_listbox.curselection()
        if selection:
            ip = self.peer_listbox.get(selection[0])
            self.selected_peer_ip = ip
            self.send_btn.config(state=tk.NORMAL, 
                               text=f"Send to {ip}", 
                               bg="#2196F3")

    def update_clipboard_ui(self, text):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, text)
        self.text_area.config(state=tk.DISABLED)

    def update_progress(self, current, total):
        self.root.after(0, lambda: self._update_ui_safe(current, total))

    def _update_ui_safe(self, current, total):
        percentage = (current / total) * 100
        self.progress['value'] = percentage
        mb_current = current / 1048576
        mb_total = total / 1048576
        self.file_label.config(
            text=f"Transferring: {percentage:.1f}% ({mb_current:.1f}MB / {mb_total:.1f}MB)",
            fg="blue")

    def send_file_action(self):
        if not self.selected_peer_ip:
            messagebox.showwarning("Warning", "Please select a recipient first!")
            return
        
        filepath = filedialog.askopenfilename()
        if not filepath:
            return
        
        filename = os.path.basename(filepath)
        self.file_label.config(text=f"Waiting for peer to accept {filename}...", fg="blue")
        self.progress['value'] = 0
        
        def run_send():
            success = self.net.send_file(self.selected_peer_ip, filepath)
            if not success:
                self.root.after(0, lambda: self.file_label.config(
                    text=f"Peer rejected {filename}", fg="red"))
                self.root.after(0, lambda: messagebox.showwarning(
                    "Send Failed", "Peer rejected your file transfer request."))
        
        threading.Thread(target=run_send, daemon=True).start()

    def on_data_received(self, msg_type, data, sender_ip):
        if msg_type == MSG_TEXT:
            text = data.decode('utf-8')
            if text != self.last_clipboard:
                self.is_remote_update = True
                pyperclip.copy(text)
                self.is_remote_update = False
                self.root.after(0, self.update_clipboard_ui, text)
                self.selected_peer_ip = sender_ip
                self.root.after(0, lambda: self.send_btn.config(
                    state=tk.NORMAL, 
                    text=f"Send back to {sender_ip}", 
                    bg="#FF9800"))

        elif msg_type == MSG_FILE_META:
            try:
                self.incoming_file_meta = json.loads(data.decode('utf-8'))
            except:
                pass

        elif msg_type == MSG_FILE_DATA:
            if self.incoming_file_meta:
                filename = "recv_" + self.incoming_file_meta['filename']
                try:
                    with open(filename, 'wb') as f:
                        f.write(data)
                    full_path = os.path.abspath(filename)
                    self.incoming_file_meta = None
                    
                    self.root.after(0, lambda: self.file_label.config(
                        text=f"Received: {filename}", fg="green"))
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Receive Success", f"File saved to:\n{full_path}"))
                    self.root.after(0, lambda: self.open_file(full_path))
                    
                    self.selected_peer_ip = sender_ip
                    self.root.after(0, lambda: self.send_btn.config(
                        state=tk.NORMAL, 
                        text=f"Send back to {sender_ip}", 
                        bg="#FF9800"))
                except Exception as e:
                    print(f"File write error: {e}")

    @staticmethod
    def open_file(filepath):
        try:
            system = platform.system()
            if system == 'Windows':
                os.startfile(filepath)
            elif system == 'Darwin':
                subprocess.call(('open', filepath))
            else:
                subprocess.call(('xdg-open', filepath))
        except:
            pass

    def monitor_clipboard(self):
        try:
            self.last_clipboard = pyperclip.paste()
            self.root.after(0, self.update_clipboard_ui, self.last_clipboard)
        except:
            pass
        
        while True:
            try:
                current = pyperclip.paste()
                if current != self.last_clipboard and not self.is_remote_update:
                    self.last_clipboard = current
                    self.root.after(0, self.update_clipboard_ui, current)
                    
                    for ip in list(self.net.peers.keys()):
                        self.net.send_data(ip, MSG_TEXT, current)
                
                time.sleep(1)
            except:
                time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = ClipboardApp(root)
    root.mainloop()