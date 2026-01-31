import json
import socket
import struct

MAX_MSG_BYTES = 2_000_000  # sanity cap

def send_msg(sock: socket.socket, obj: dict) -> None:
    payload = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    header = struct.pack("!I", len(payload))
    sock.sendall(header + payload)

def recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data

def recv_msg(sock: socket.socket) -> dict:
    header = recv_exact(sock, 4)
    (length,) = struct.unpack("!I", header)
    if length < 0 or length > MAX_MSG_BYTES:
        raise ValueError(f"bad message length: {length}")
    payload = recv_exact(sock, length)
    return json.loads(payload.decode("utf-8"))
