import socket
from typing import List

from rts.net.transport import send_msg
from .state import ServerState

def safe_send(conn: socket.socket, msg: dict) -> bool:
    try:
        send_msg(conn, msg)
        return True
    except Exception:
        return False

def broadcast(state: ServerState, msg: dict):
    dead: List[socket.socket] = []
    with state.clients_lock:
        for conn in list(state.clients.keys()):
            if not safe_send(conn, msg):
                dead.append(conn)
        for conn in dead:
            try:
                pid = state.clients.pop(conn, None)
                conn.close()
                print(f"[-] dropped dead client pid={pid}")
            except Exception:
                pass
