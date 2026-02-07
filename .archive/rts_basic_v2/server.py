# v2
import socket
import threading
import queue
import time
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

from common import recv_msg, send_msg

HOST = "0.0.0.0"
PORT = 5001

# --- simulation rates ---
TICK_HZ = 30.0
DT = 1.0 / TICK_HZ
SNAPSHOT_HZ = 20.0
SNAP_EVERY_TICKS = max(1, int(TICK_HZ / SNAPSHOT_HZ))

# --- world size (just for reference; clients can ignore) ---
MAP_W, MAP_H = 2000, 1500

@dataclass
class Unit:
    id: int
    owner: int
    x: float
    y: float
    tx: Optional[float] = None
    ty: Optional[float] = None
    speed: float = 220.0  # units per second

class ServerState:
    def __init__(self):
        self.next_player_id = 1
        self.next_unit_id = 1

        self.clients_lock = threading.Lock()
        self.clients: Dict[socket.socket, int] = {}  # conn -> player_id

        self.world_lock = threading.Lock()
        self.units: Dict[int, Unit] = {}            # unit_id -> Unit

        self.command_q: "queue.Queue[tuple[int, dict]]" = queue.Queue()

        self.running = True

    def alloc_player_id(self) -> int:
        pid = self.next_player_id
        self.next_player_id += 1
        return pid

    def alloc_unit_id(self) -> int:
        uid = self.next_unit_id
        self.next_unit_id += 1
        return uid

state = ServerState()

def safe_send(conn: socket.socket, msg: dict) -> bool:
    try:
        send_msg(conn, msg)
        return True
    except Exception:
        return False

def broadcast(msg: dict):
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

def spawn_units_for_player(player_id: int):
    # spawn 6 units per player in different regions
    with state.world_lock:
        base_x = 300 if player_id == 1 else 1700
        base_y = 400 if player_id == 1 else 1100
        for i in range(6):
            uid = state.alloc_unit_id()
            u = Unit(
                id=uid,
                owner=player_id,
                x=base_x + (i % 3) * 45,
                y=base_y + (i // 3) * 45
            )
            state.units[uid] = u

def handle_client(conn: socket.socket, addr):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    player_id = None
    try:
        # Expect HELLO first
        hello = recv_msg(conn)
        if hello.get("type") != "hello":
            raise ValueError("expected hello")

        player_id = state.alloc_player_id()
        with state.clients_lock:
            state.clients[conn] = player_id

        # Send welcome
        safe_send(conn, {"type": "welcome", "player_id": player_id, "map_w": MAP_W, "map_h": MAP_H})
        print(f"[+] {addr} => player_id={player_id}")

        # Create some units for this player
        spawn_units_for_player(player_id)

        # Notify others (optional)
        broadcast({"type": "server_event", "event": "player_joined", "player_id": player_id})

        # Read loop: push commands into command queue
        while state.running:
            msg = recv_msg(conn)
            mtype = msg.get("type")

            if mtype == "cmd_move":
                # enqueue command for sim thread to validate/apply
                state.command_q.put((player_id, msg))
            elif mtype == "ping":
                safe_send(conn, {"type": "pong", "t": msg.get("t")})
            else:
                # ignore unknown messages for now
                pass

    except Exception as e:
        print(f"[-] client {addr} disconnected: {e}")
    finally:
        # Remove client
        with state.clients_lock:
            if conn in state.clients:
                pid = state.clients.pop(conn, None)
                print(f"[-] removed client pid={pid}")
        try:
            conn.close()
        except Exception:
            pass
        if player_id is not None:
            broadcast({"type": "server_event", "event": "player_left", "player_id": player_id})

def apply_move_command(player_id: int, cmd: dict):
    # cmd: {"type":"cmd_move","unit_ids":[...],"x":..,"y":..}
    unit_ids = cmd.get("unit_ids", [])
    tx = float(cmd.get("x", 0.0))
    ty = float(cmd.get("y", 0.0))

    # Formation: small grid offsets so they don't stack
    n = len(unit_ids)
    if n == 0:
        return

    side = int(math.ceil(math.sqrt(n)))
    gap = 28.0
    origin_x = tx - (side - 1) * gap / 2.0
    origin_y = ty - (side - 1) * gap / 2.0

    with state.world_lock:
        # validate ownership
        owned: List[Unit] = []
        for uid in unit_ids:
            u = state.units.get(int(uid))
            if u and u.owner == player_id:
                owned.append(u)

        for i, u in enumerate(owned):
            ox = (i % side) * gap
            oy = (i // side) * gap
            u.tx = origin_x + ox
            u.ty = origin_y + oy

def sim_tick():
    # Apply queued commands
    while True:
        try:
            player_id, cmd = state.command_q.get_nowait()
        except queue.Empty:
            break
        if cmd.get("type") == "cmd_move":
            apply_move_command(player_id, cmd)

    # Update units toward targets
    with state.world_lock:
        for u in state.units.values():
            if u.tx is None or u.ty is None:
                continue

            dx = u.tx - u.x
            dy = u.ty - u.y
            dist = math.hypot(dx, dy)

            if dist < 3.0:
                u.x, u.y = u.tx, u.ty
                u.tx, u.ty = None, None
                continue

            vx = (dx / dist) * u.speed
            vy = (dy / dist) * u.speed
            u.x += vx * DT
            u.y += vy * DT

            # clamp inside map
            u.x = max(0, min(MAP_W, u.x))
            u.y = max(0, min(MAP_H, u.y))

def build_snapshot(tick: int) -> dict:
    with state.world_lock:
        units_payload = [
            {"id": u.id, "owner": u.owner, "x": u.x, "y": u.y}
            for u in state.units.values()
        ]
    return {"type": "snapshot", "tick": tick, "units": units_payload}

def sim_loop():
    tick = 0
    next_time = time.perf_counter()
    while state.running:
        now = time.perf_counter()
        if now < next_time:
            time.sleep(max(0.0, next_time - now))
            continue

        # run one sim tick
        sim_tick()
        tick += 1

        # broadcast snapshot occasionally
        if tick % SNAP_EVERY_TICKS == 0:
            snap = build_snapshot(tick)
            broadcast(snap)

        next_time += DT

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    print(f"Server listening on {HOST}:{PORT} (tick={TICK_HZ}Hz, snapshot={SNAPSHOT_HZ}Hz)")

    sim_thread = threading.Thread(target=sim_loop, daemon=True)
    sim_thread.start()

    try:
        while True:
            conn, addr = srv.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
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

if __name__ == "__main__":
    main()
