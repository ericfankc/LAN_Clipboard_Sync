# Local Network Clipboard & File Sync

**NetClip** is a lightweight, cross-platform P2P tool designed for seamless clipboard synchronization and secure file transfer over a Local Area Network (LAN). Built with Python, it operates completely offline, requiring neither an internet connection nor cloud servers.


## Key Features

* **Real-time Clipboard Sync**: Automatically synchronizes text copied to the clipboard across all connected devices in the LAN.
* **Secure File Transfer**: Implements a handshake mechanism (Request/Accept/Reject). The receiver must explicitly approve a file transfer before it begins.
* **Zero-Configuration**: Uses UDP Broadcast for automatic peer discovery. No IP configuration needed—just run and connect.
* **GUI with Progress Tracking**: Features a user-friendly Tkinter interface with real-time progress bars for file transfers.
* **Smart Auto-Open**: Automatically opens received files using the system's default application upon completion.
* **Robust Networking**: Handles TCP stickiness/fragmentation and includes a peer cleanup mechanism for offline devices.

## Requirements

* Python 3.6+
* `pyperclip` (for clipboard access)
* `tkinter`

## Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/yourusername/NetClip.git](https://github.com/yourusername/NetClip.git)
    cd NetClip
    ```

2.  **Install dependencies**
    ```bash
    pip install pyperclip
    ```

## Usage

1.  **Start the application**
    Run the GUI application on at least two computers connected to the same Wi-Fi network or local area network (LAN).
    ```bash
    python gui.py
    ```

2.  **Discovery**
    The app will automatically scan for other peers. Once discovered, they will appear in the "Online Peers" list on the left.

3.  **Clipboard Sync**
    Just copy any text (Ctrl+C) on one computer, and it will be immediately available on the clipboard of other connected peers.

4.  **File Transfer**
    * Select a peer from the list.
    * Click **"Select File & Send"**.
    * The receiver will get a prompt: *"User at [IP] wants to send [File]. Accept?"*
    * If accepted, the transfer begins with a progress bar.

## Project Structure

* **`gui.py`**: The main entry point. Handles the Tkinter GUI, clipboard monitoring thread, and bridges user actions with the network layer.
* **`network.py`**: The core networking module. Manages UDP discovery (broadcasting/listening) and TCP connections (server/client).
* **`protocol.py`**: Defines the custom application-layer protocol, including message types (`MSG_TEXT`, `MSG_FILE_REQUEST`, etc.) and packet packing/unpacking logic.

## Technical Details

* **Service Discovery**: Uses UDP broadcasting on Port `9999` to announce presence and discover peers. Implements a heartbeat mechanism to remove offline peers.
* **Data Transport**: Uses TCP on Port `10000` for reliable data transmission.
* **Protocol Design**: Custom binary protocol with a 5-byte header (`Type` + `Length`) to handle TCP stream data correctly.
* **Flow Control**: Large files are transferred in 64KB chunks to prevent memory overflow and update the UI progress bar smoothly.
