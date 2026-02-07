import math
import time

from .state import ServerState, Entity
from . import config as cfg
from .commands import apply_commands
from .worldgen import resolve_circle_vs_asteroids
from .snapshots import build_snapshot
from .netserver import broadcast

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
    e.x += e.vx * cfg.DT
    e.y += e.vy * cfg.DT

    e.angle = math.atan2(nx, -ny)

def tick_entities(state: ServerState):
    with state.world_lock:
        for e in state.entities.values():
            if e.hp <= 0:
                continue

            if e.type == "fighter":
                move_toward(e, speed=260.0)
                e.x, e.y, hit = resolve_circle_vs_asteroids(state, e.x, e.y, radius=10.0)
                if hit:
                    e.tx = None
                    e.ty = None

            elif e.type == "station":
                move_toward(e, speed=60.0)
                e.x, e.y, hit = resolve_circle_vs_asteroids(state, e.x, e.y, radius=95.0)
                if hit:
                    e.tx = None
                    e.ty = None

            elif e.type == "miner":
                if e.miner_state == "to_asteroid":
                    move_toward(e, speed=180.0)
                    e.x, e.y, hit = resolve_circle_vs_asteroids(state, e.x, e.y, radius=10.0)
                    if hit:
                        e.tx = None
                        e.ty = None
                    if e.tx is None and e.ty is None:
                        e.miner_state = "mining"
                        e.mine_timer = cfg.MINING_TIME

                elif e.miner_state == "mining":
                    e.mine_timer -= cfg.DT
                    e.angle += 0.6 * cfg.DT
                    if e.mine_timer <= 0:
                        e.cargo = cfg.MINING_REWARD
                        e.miner_state = "returning"

                        st = state.entities.get(e.home_station_id or -1)
                        if st and st.type == "station":
                            e.tx = st.x
                            e.ty = st.y - 110.0
                        else:
                            e.miner_state = "idle"
                            e.mine_asteroid_id = None
                            e.cargo = 0
                            e.tx = None
                            e.ty = None

                elif e.miner_state == "returning":
                    move_toward(e, speed=180.0)
                    e.x, e.y, hit = resolve_circle_vs_asteroids(state, e.x, e.y, radius=10.0)
                    if hit:
                        e.tx = None
                        e.ty = None

                    if e.tx is None and e.ty is None:
                        if e.cargo > 0:
                            state.credits[e.owner] = state.credits.get(e.owner, 0) + e.cargo
                        e.cargo = 0

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
                    move_toward(e, speed=180.0)
                    e.x, e.y, hit = resolve_circle_vs_asteroids(state, e.x, e.y, radius=10.0)
                    if hit:
                        e.tx = None
                        e.ty = None

            e.x = max(0, min(cfg.MAP_W, e.x))
            e.y = max(0, min(cfg.MAP_H, e.y))

def sim_loop(state: ServerState):
    tick = 0
    next_time = time.perf_counter()

    while state.running:
        now = time.perf_counter()
        if now < next_time:
            time.sleep(max(0.0, next_time - now))
            continue

        apply_commands(state)
        tick_entities(state)
        tick += 1

        if tick % cfg.SNAP_EVERY_TICKS == 0:
            broadcast(state, build_snapshot(state, tick))

        next_time += cfg.DT
