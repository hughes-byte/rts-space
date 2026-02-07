import socket
import threading
import queue

from rts.net.transport import recv_msg, send_msg
from rts.net import protocol as P

class NetClient:
    def __init__(self):
        self.sock: socket.socket | None = None
        self.inbox: "queue.Queue[dict]" = queue.Queue()

    def connect(self, host: str, port: int):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = sock

        send_msg(sock, {"type": P.HELLO, "name": "player"})
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _recv_loop(self):
        assert self.sock is not None
        try:
            while True:
                msg = recv_msg(self.sock)
                self.inbox.put(msg)
        except Exception as e:
            self.inbox.put({"type": "_disconnect", "error": str(e)})

    def send(self, msg: dict):
        if self.sock is None:
            return
        send_msg(self.sock, msg)

    def close(self):
        if self.sock is None:
            return
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = None
