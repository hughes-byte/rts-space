import socket
import threading

from rts.net.transport import recv_msg, send_msg
from rts.net import protocol as P
from .state import ServerState
from . import config as cfg
from .worldgen import generate_asteroids
from .commands import spawn_station_and_fighters
from .snapshots import build_map_init
from .simulation import sim_loop

state = ServerState()

def handle_client(conn: socket.socket, addr):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    player_id = None
    try:
        hello = recv_msg(conn)
        if hello.get("type") != P.HELLO:
            raise ValueError("expected hello")

        with state.world_lock:
            player_id = state.next_player_id
            state.next_player_id += 1
            state.credits[player_id] = cfg.CREDITS_START

        with state.clients_lock:
            state.clients[conn] = player_id

        print(f"[+] {addr} => player_id={player_id}")

        spawn_station_and_fighters(state, player_id)

        send_msg(conn, build_map_init(state, player_id))

        while state.running:
            msg = recv_msg(conn)
            t = msg.get("type")
            if t in P.SERVER_CMDS:
                state.command_q.put((player_id, msg))

    except Exception as e:
        print(f"[-] client {addr} disconnected: {e}")
    finally:
        with state.clients_lock:
            if conn in state.clients:
                pid = state.clients.pop(conn, None)
                print(f"[-] removed client pid={pid}")
        try:
            conn.close()
        except Exception:
            pass

def main():
    generate_asteroids(state, cfg.MAP_SEED)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((cfg.HOST, cfg.PORT))
    srv.listen()
    print(f"Server listening on {cfg.HOST}:{cfg.PORT} (tick={cfg.TICK_HZ}Hz, snap={cfg.SNAPSHOT_HZ}Hz)")

    threading.Thread(target=sim_loop, args=(state,), daemon=True).start()

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        state.running = False
        try:
            srv.close()
        except Exception:
            pass

        with state.clients_lock:
            for c in list(state.clients.keys()):
                try:
                    c.close()
                except Exception:
                    pass
            state.clients.clear()
