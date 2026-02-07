# v1
import socket
import threading
from common import recv_msg, send_msg

HOST = "0.0.0.0"
PORT = 5001

clients = []
clients_lock = threading.Lock()

def broadcast(msg: dict, exclude=None):
    dead = []
    with clients_lock:
        for c in clients:
            if exclude is not None and c is exclude:
                continue
            try:
                send_msg(c, msg)
            except Exception:
                dead.append(c)
        for c in dead:
            try:
                clients.remove(c)
                c.close()
            except Exception:
                pass

def handle_client(conn: socket.socket, addr):
    print(f"[+] client connected: {addr}")
    try:
        # announce join
        broadcast({"type": "server", "text": f"{addr} joined"}, exclude=None)

        while True:
            msg = recv_msg(conn)  # blocks
            # simple broadcast
            broadcast({"type": "chat", "from": str(addr), "data": msg}, exclude=None)

    except Exception as e:
        print(f"[-] client {addr} disconnected ({e})")
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        try:
            conn.close()
        except Exception:
            pass
        broadcast({"type": "server", "text": f"{addr} left"}, exclude=None)

def main():
    print(f"Listening on {HOST}:{PORT} ...")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()

    try:
        while True:
            conn, addr = srv.accept()
            with clients_lock:
                clients.append(conn)
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        with clients_lock:
            for c in clients:
                try:
                    c.close()
                except Exception:
                    pass
        srv.close()

if __name__ == "__main__":
    main()
