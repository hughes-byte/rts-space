import math
import random
from typing import List, Tuple

from .state import ServerState, Asteroid
from . import config as cfg

def generate_asteroids(state: ServerState, seed: int):
    rng = random.Random(seed)
    placed: List[Asteroid] = []
    tries = 0
    max_tries = 140000

    while len(placed) < cfg.ASTEROID_COUNT and tries < max_tries:
        tries += 1
        r = rng.randrange(cfg.AST_MIN_R, cfg.AST_MAX_R + 1)
        x = rng.randrange(cfg.AST_EDGE_PAD + r, cfg.MAP_W - cfg.AST_EDGE_PAD - r)
        y = rng.randrange(cfg.AST_EDGE_PAD + r, cfg.MAP_H - cfg.AST_EDGE_PAD - r)

        ok = True
        for a in placed:
            d = math.hypot(x - a.x, y - a.y)
            if d < (r + a.r + cfg.ASTEROID_GAP):
                ok = False
                break
        if ok:
            aid = state.next_asteroid_id
            state.next_asteroid_id += 1
            placed.append(Asteroid(aid, float(x), float(y), float(r)))

    if len(placed) < cfg.ASTEROID_COUNT:
        print(f"[!] Warning: placed only {len(placed)}/{cfg.ASTEROID_COUNT} asteroids")

    with state.world_lock:
        state.asteroids = {a.id: a for a in placed}

def resolve_circle_vs_asteroids(state: ServerState, x: float, y: float, radius: float) -> Tuple[float, float, bool]:
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
