import math
import random
import queue
from typing import List, Optional

from .state import ServerState, Entity, alloc_entity_id
from . import config as cfg

def spawn_station_and_fighters(state: ServerState, player_id: int):
    if player_id == 1:
        bx, by = cfg.MAP_W * 0.30, cfg.MAP_H * 0.40
    else:
        bx, by = cfg.MAP_W * 0.70, cfg.MAP_H * 0.60

    station_id = alloc_entity_id(state)
    station = Entity(
        id=station_id, type="station", owner=player_id,
        x=float(bx), y=float(by),
        hp_max=800, hp=800
    )

    with state.world_lock:
        state.entities[station_id] = station

    ring_r = 240.0
    count = 14
    for i in range(count):
        ang = (i / count) * 2 * math.pi
        sx = bx + math.cos(ang) * ring_r
        sy = by + math.sin(ang) * ring_r

        eid = alloc_entity_id(state)
        fighter = Entity(
            id=eid, type="fighter", owner=player_id,
            x=float(sx), y=float(sy),
            hp_max=80, hp=80
        )
        with state.world_lock:
            state.entities[eid] = fighter

def spawn_miner(state: ServerState, player_id: int, station_id: int) -> Optional[int]:
    with state.world_lock:
        if station_id not in state.entities:
            return None
        st = state.entities[station_id]
        if st.owner != player_id or st.type != "station":
            return None

        rng = random.Random(cfg.MAP_SEED + player_id * 9999 + state.next_entity_id)
        ang = rng.random() * 2 * math.pi
        rr = rng.randrange(130, 190)
        sx = st.x + math.cos(ang) * rr
        sy = st.y + math.sin(ang) * rr

    eid = alloc_entity_id(state)
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

def handle_cmd_move(state: ServerState, player_id: int, cmd: dict):
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

            if e.type == "miner":
                e.miner_state = "idle"
                e.mine_asteroid_id = None
                e.mine_timer = 0.0
                e.cargo = 0

def handle_cmd_buy_miner(state: ServerState, player_id: int, cmd: dict):
    station_id = int(cmd.get("station_id", -1))
    with state.world_lock:
        credits = state.credits.get(player_id, 0)
        if credits < cfg.MINER_COST:
            return
        st = state.entities.get(station_id)
        if not st or st.type != "station" or st.owner != player_id:
            return
        state.credits[player_id] = credits - cfg.MINER_COST

    spawn_miner(state, player_id, station_id)

def handle_cmd_mine(state: ServerState, player_id: int, cmd: dict):
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

            e.mine_asteroid_id = asteroid_id
            e.miner_state = "to_asteroid"
            e.mine_timer = 0.0
            e.cargo = 0

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

def apply_commands(state: ServerState):
    while True:
        try:
            player_id, cmd = state.command_q.get_nowait()
        except queue.Empty:
            break

        t = cmd.get("type")
        if t == "cmd_move":
            handle_cmd_move(state, player_id, cmd)
        elif t == "cmd_buy_miner":
            handle_cmd_buy_miner(state, player_id, cmd)
        elif t == "cmd_mine":
            handle_cmd_mine(state, player_id, cmd)
