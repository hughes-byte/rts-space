import socket
import threading
from common import recv_msg, send_msg

HOST = "127.0.0.1"   # change to server LAN IP when testing across machines
PORT = 5001

def recv_loop(sock: socket.socket):
    try:
        while True:
            msg = recv_msg(sock)
            print("\n<<", msg)
            print(">> ", end="", flush=True)
    except Exception as e:
        print("\n[disconnected]", e)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    print(f"Connected to {HOST}:{PORT}")

    t = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t.start()

    try:
        while True:
            text = input(">> ")
            send_msg(sock, {"text": text})
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
