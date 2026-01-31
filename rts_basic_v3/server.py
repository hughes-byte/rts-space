import socket
import threading
import queue
import time
import math
import random
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

from common import recv_msg, send_msg

HOST = "0.0.0.0"
PORT = 5001

# =========================
# Timing
# =========================
TICK_HZ = 60.0
DT = 1.0 / TICK_HZ
SNAPSHOT_HZ = 30.0
SNAP_EVERY_TICKS = max(1, int(TICK_HZ / SNAPSHOT_HZ))

# =========================
# World / Economy config
# =========================
MAP_W, MAP_H = 15000, 10000
MAP_SEED = 1337

CREDITS_START = 500
MINER_COST = 120

MINING_TIME = 4.0
MINING_REWARD = 80

# Asteroids
ASTEROID_COUNT = 60
ASTEROID_GAP = 250
AST_MIN_R = 35
AST_MAX_R = 110
AST_EDGE_PAD = 600

# =========================
# Entities
# =========================
@dataclass
class Asteroid:
    id: int
    x: float
    y: float
    r: float

@dataclass
class Entity:
    id: int
    type: str               # "station"|"fighter"|"miner"
    owner: int              # player_id
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    angle: float = 0.0
    hp: float = 100.0
    hp_max: float = 100.0

    # movement / intent
    tx: Optional[float] = None
    ty: Optional[float] = None

    # miner state
    miner_state: str = "idle"         # idle,to_asteroid,mining,returning
    mine_asteroid_id: Optional[int] = None
    mine_timer: float = 0.0
    cargo: int = 0
    home_station_id: Optional[int] = None

class ServerState:
    def __init__(self):
        self.running = True

        self.next_player_id = 1
        self.next_entity_id = 1
        self.next_asteroid_id = 1

        self.clients_lock = threading.Lock()
        self.clients: Dict[socket.socket, int] = {}  # conn -> player_id

        self.world_lock = threading.Lock()
        self.entities: Dict[int, Entity] = {}
        self.asteroids: Dict[int, Asteroid] = {}

        self.credits: Dict[int, int] = {}

        self.command_q: "queue.Queue[tuple[int, dict]]" = queue.Queue()

state = ServerState()

# =========================
# Networking helpers
# =========================
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

# =========================
# Asteroid generation (non-overlap + gap)
# =========================
def generate_asteroids(seed: int):
    rng = random.Random(seed)
    placed: List[Asteroid] = []
    tries = 0
    max_tries = 140000

    while len(placed) < ASTEROID_COUNT and tries < max_tries:
        tries += 1
        r = rng.randrange(AST_MIN_R, AST_MAX_R + 1)
        x = rng.randrange(AST_EDGE_PAD + r, MAP_W - AST_EDGE_PAD - r)
        y = rng.randrange(AST_EDGE_PAD + r, MAP_H - AST_EDGE_PAD - r)

        ok = True
        for a in placed:
            d = math.hypot(x - a.x, y - a.y)
            if d < (r + a.r + ASTEROID_GAP):
                ok = False
                break
        if ok:
            aid = state.next_asteroid_id
            state.next_asteroid_id += 1
            placed.append(Asteroid(aid, float(x), float(y), float(r)))

    if len(placed) < ASTEROID_COUNT:
        print(f"[!] Warning: placed only {len(placed)}/{ASTEROID_COUNT} asteroids")

    with state.world_lock:
        state.asteroids = {a.id: a for a in placed}

def resolve_circle_vs_asteroids(x: float, y: float, radius: float) -> Tuple[float, float, bool]:
    """
    Push the circle out of asteroids if overlapping. This is a cheap collision rule (not pathfinding).
    """
    did = False
    for a in state.asteroids.values():
        dx = x - a.x
        dy = y - a.y
        dist = math.hypot(dx, dy)
        min_dist = radius + a.r
        if dist == 0:
            x += min_dist
            did = True
        elif dist < min_dist:
            nx = dx / dist
            ny = dy / dist
            x = a.x + nx * min_dist
            y = a.y + ny * min_dist
            did = True
    return x, y, did

# =========================
# Spawning
# =========================
def alloc_entity_id() -> int:
    eid = state.next_entity_id
    state.next_entity_id += 1
    return eid

def spawn_station_and_fighters(player_id: int):
    # put players on different sides so they don't spawn stacked
    if player_id == 1:
        bx, by = MAP_W * 0.30, MAP_H * 0.40
    else:
        bx, by = MAP_W * 0.70, MAP_H * 0.60

    station_id = alloc_entity_id()
    station = Entity(
        id=station_id, type="station", owner=player_id,
        x=float(bx), y=float(by),
        hp_max=800, hp=800
    )
    # station is slow
    station_speed = 60.0
    station.vx = 0
    station.vy = 0

    with state.world_lock:
        state.entities[station_id] = station

    # spawn fighters around station
    ring_r = 240.0
    count = 14
    for i in range(count):
        ang = (i / count) * 2 * math.pi
        sx = bx + math.cos(ang) * ring_r
        sy = by + math.sin(ang) * ring_r

        eid = alloc_entity_id()
        fighter = Entity(
            id=eid, type="fighter", owner=player_id,
            x=float(sx), y=float(sy),
            hp_max=80, hp=80
        )
        with state.world_lock:
            state.entities[eid] = fighter

def spawn_miner(player_id: int, station_id: int) -> Optional[int]:
    with state.world_lock:
        if station_id not in state.entities:
            return None
        st = state.entities[station_id]
        if st.owner != player_id or st.type != "station":
            return None

        # spawn near station
        rng = random.Random(MAP_SEED + player_id * 9999 + state.next_entity_id)
        ang = rng.random() * 2 * math.pi
        rr = rng.randrange(130, 190)
        sx = st.x + math.cos(ang) * rr
        sy = st.y + math.sin(ang) * rr

    eid = alloc_entity_id()
    miner = Entity(
        id=eid, type="miner", owner=player_id,
        x=float(sx), y=float(sy),
        hp_max=90, hp=90,
        miner_state="idle",
        mine_asteroid_id=None,
        mine_timer=0.0,
        cargo=0,
        home_station_id=station_id,
    )
    with state.world_lock:
        state.entities[eid] = miner
    return eid

# =========================
# Command handling
# =========================
def handle_cmd_move(player_id: int, cmd: dict):
    unit_ids = cmd.get("unit_ids", [])
    tx = float(cmd.get("x", 0.0))
    ty = float(cmd.get("y", 0.0))

    n = len(unit_ids)
    if n <= 0:
        return

    side = int(math.ceil(math.sqrt(n)))
    gap = 42.0
    origin_x = tx - (side - 1) * gap / 2.0
    origin_y = ty - (side - 1) * gap / 2.0

    with state.world_lock:
        owned: List[Entity] = []
        for uid in unit_ids:
            e = state.entities.get(int(uid))
            if e and e.owner == player_id:
                owned.append(e)

        for i, e in enumerate(owned):
            ox = (i % side) * gap
            oy = (i // side) * gap
            e.tx = origin_x + ox
            e.ty = origin_y + oy

            # moving cancels mining for miners
            if e.type == "miner":
                e.miner_state = "idle"
                e.mine_asteroid_id = None
                e.mine_timer = 0.0
                e.cargo = 0

def handle_cmd_buy_miner(player_id: int, cmd: dict):
    station_id = int(cmd.get("station_id", -1))
    with state.world_lock:
        credits = state.credits.get(player_id, 0)
        if credits < MINER_COST:
            return
        # validate station ownership
        st = state.entities.get(station_id)
        if not st or st.type != "station" or st.owner != player_id:
            return
        state.credits[player_id] = credits - MINER_COST

    spawn_miner(player_id, station_id)

def handle_cmd_mine(player_id: int, cmd: dict):
    unit_ids = cmd.get("unit_ids", [])
    asteroid_id = int(cmd.get("asteroid_id", -1))

    with state.world_lock:
        if asteroid_id not in state.asteroids:
            return

        a = state.asteroids[asteroid_id]

        for uid in unit_ids:
            e = state.entities.get(int(uid))
            if not e:
                continue
            if e.owner != player_id:
                continue
            if e.type != "miner":
                continue

            # assign mining target and kick FSM
            e.mine_asteroid_id = asteroid_id
            e.miner_state = "to_asteroid"
            e.mine_timer = 0.0
            e.cargo = 0

            # land point just outside asteroid surface (toward miner position)
            dx = e.x - a.x
            dy = e.y - a.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                nx, ny = dx / dist, dy / dist
            else:
                nx, ny = 1.0, 0.0
            land_x = a.x + nx * (a.r + 10.0)
            land_y = a.y + ny * (a.r + 10.0)
            e.tx = land_x
            e.ty = land_y

def apply_commands():
    while True:
        try:
            player_id, cmd = state.command_q.get_nowait()
        except queue.Empty:
            break

        t = cmd.get("type")
        if t == "cmd_move":
            handle_cmd_move(player_id, cmd)
        elif t == "cmd_buy_miner":
            handle_cmd_buy_miner(player_id, cmd)
        elif t == "cmd_mine":
            handle_cmd_mine(player_id, cmd)

# =========================
# Simulation
# =========================
def move_toward(e: Entity, speed: float):
    if e.tx is None or e.ty is None:
        return

    dx = e.tx - e.x
    dy = e.ty - e.y
    dist = math.hypot(dx, dy)

    if dist < 6.0:
        e.x = e.tx
        e.y = e.ty
        e.tx = None
        e.ty = None
        e.vx = 0.0
        e.vy = 0.0
        return

    nx = dx / dist
    ny = dy / dist

    e.vx = nx * speed
    e.vy = ny * speed
    e.x += e.vx * DT
    e.y += e.vy * DT

    # face direction (ship nose "up": forward = (sin, -cos) — we store angle to match client draw)
    e.angle = math.atan2(nx, -ny)

def tick_entities():
    with state.world_lock:
        # update each entity
        for e in state.entities.values():
            if e.hp <= 0:
                continue

            if e.type == "fighter":
                # simple movement (no pathfinding)
                move_toward(e, speed=260.0)
                e.x, e.y, hit = resolve_circle_vs_asteroids(e.x, e.y, radius=10.0)
                if hit:
                    e.tx = None
                    e.ty = None

            elif e.type == "station":
                # slow movement
                move_toward(e, speed=60.0)
                e.x, e.y, hit = resolve_circle_vs_asteroids(e.x, e.y, radius=95.0)
                if hit:
                    e.tx = None
                    e.ty = None

            elif e.type == "miner":
                # miner FSM
                if e.miner_state == "to_asteroid":
                    move_toward(e, speed=180.0)
                    e.x, e.y, hit = resolve_circle_vs_asteroids(e.x, e.y, radius=10.0)
                    if hit:
                        e.tx = None
                        e.ty = None
                    # arrived?
                    if e.tx is None and e.ty is None:
                        e.miner_state = "mining"
                        e.mine_timer = MINING_TIME

                elif e.miner_state == "mining":
                    e.mine_timer -= DT
                    e.angle += 0.6 * DT
                    if e.mine_timer <= 0:
                        e.cargo = MINING_REWARD
                        e.miner_state = "returning"

                        # go dock near station
                        st = state.entities.get(e.home_station_id or -1)
                        if st and st.type == "station":
                            e.tx = st.x
                            e.ty = st.y - 110.0
                        else:
                            # no home => idle
                            e.miner_state = "idle"
                            e.mine_asteroid_id = None
                            e.cargo = 0
                            e.tx = None
                            e.ty = None

                elif e.miner_state == "returning":
                    move_toward(e, speed=180.0)
                    e.x, e.y, hit = resolve_circle_vs_asteroids(e.x, e.y, radius=10.0)
                    if hit:
                        e.tx = None
                        e.ty = None

                    if e.tx is None and e.ty is None:
                        # deposit
                        if e.cargo > 0:
                            state.credits[e.owner] = state.credits.get(e.owner, 0) + e.cargo
                        e.cargo = 0

                        # AUTO-LOOP BACK to asteroid if still assigned
                        if e.mine_asteroid_id is not None and e.mine_asteroid_id in state.asteroids:
                            a = state.asteroids[e.mine_asteroid_id]
                            dx = e.x - a.x
                            dy = e.y - a.y
                            dist = math.hypot(dx, dy)
                            if dist > 0:
                                nx, ny = dx / dist, dy / dist
                            else:
                                nx, ny = 1.0, 0.0
                            land_x = a.x + nx * (a.r + 10.0)
                            land_y = a.y + ny * (a.r + 10.0)
                            e.tx = land_x
                            e.ty = land_y
                            e.miner_state = "to_asteroid"
                            e.mine_timer = 0.0
                        else:
                            e.miner_state = "idle"

                else:
                    # idle miners still can be moved by cmd_move
                    move_toward(e, speed=180.0)
                    e.x, e.y, hit = resolve_circle_vs_asteroids(e.x, e.y, radius=10.0)
                    if hit:
                        e.tx = None
                        e.ty = None

            # clamp
            e.x = max(0, min(MAP_W, e.x))
            e.y = max(0, min(MAP_H, e.y))

def build_map_init(player_id: int) -> dict:
    with state.world_lock:
        ast_list = [{"id": a.id, "x": a.x, "y": a.y, "r": a.r} for a in state.asteroids.values()]
    return {
        "type": "map_init",
        "player_id": player_id,
        "map_w": MAP_W,
        "map_h": MAP_H,
        "map_seed": MAP_SEED,
        "asteroids": ast_list,
    }

def build_snapshot(tick: int) -> dict:
    with state.world_lock:
        ents = []
        for e in state.entities.values():
            if e.hp <= 0:
                continue
            ents.append({
                "id": e.id,
                "type": e.type,
                "owner": e.owner,
                "x": e.x,
                "y": e.y,
                "angle": e.angle,
                "hp": e.hp,
                "hp_max": e.hp_max,
                # miner extras
                "miner_state": e.miner_state if e.type == "miner" else None,
                "mine_asteroid_id": e.mine_asteroid_id if e.type == "miner" else None,
            })
        credits = dict(state.credits)
    return {"type": "snapshot", "tick": tick, "entities": ents, "credits": credits}

def sim_loop():
    tick = 0
    next_time = time.perf_counter()

    while state.running:
        now = time.perf_counter()
        if now < next_time:
            time.sleep(max(0.0, next_time - now))
            continue

        apply_commands()
        tick_entities()
        tick += 1

        if tick % SNAP_EVERY_TICKS == 0:
            broadcast(build_snapshot(tick))

        next_time += DT

# =========================
# Client thread
# =========================
def handle_client(conn: socket.socket, addr):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    player_id = None
    try:
        hello = recv_msg(conn)
        if hello.get("type") != "hello":
            raise ValueError("expected hello")

        with state.world_lock:
            player_id = state.next_player_id
            state.next_player_id += 1
            state.credits[player_id] = CREDITS_START

        with state.clients_lock:
            state.clients[conn] = player_id

        print(f"[+] {addr} => player_id={player_id}")

        # spawn this player's starting stuff
        spawn_station_and_fighters(player_id)

        # send map init once
        safe_send(conn, build_map_init(player_id))

        # then read commands forever
        while state.running:
            msg = recv_msg(conn)
            t = msg.get("type")
            if t in ("cmd_move", "cmd_buy_miner", "cmd_mine"):
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
    generate_asteroids(MAP_SEED)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    print(f"Server listening on {HOST}:{PORT} (tick={TICK_HZ}Hz, snap={SNAPSHOT_HZ}Hz)")

    threading.Thread(target=sim_loop, daemon=True).start()

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

if __name__ == "__main__":
    main()
