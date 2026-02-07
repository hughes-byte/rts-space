import math
import pygame
from typing import Dict, List, Optional

def rect_from_points(a: pygame.Vector2, b: pygame.Vector2) -> pygame.Rect:
    x1, y1 = min(a.x, b.x), min(a.y, b.y)
    x2, y2 = max(a.x, b.x), max(a.y, b.y)
    return pygame.Rect(x1, y1, x2 - x1, y2 - y1)

def pick_entity_at(world_pos: pygame.Vector2, ents: List[dict], player_id: Optional[int]) -> Optional[int]:
    best = None
    best_d2 = 1e18
    for e in ents:
        if player_id is None or int(e["owner"]) != player_id:
            continue
        ex, ey = float(e["x"]), float(e["y"])
        dx = world_pos.x - ex
        dy = world_pos.y - ey
        d2 = dx*dx + dy*dy
        r = 18 if e["type"] != "station" else 95
        if d2 <= r*r and d2 < best_d2:
            best = int(e["id"])
            best_d2 = d2
    return best

def pick_asteroid_at(world_pos: pygame.Vector2, asts: List[dict]) -> Optional[int]:
    for a in asts:
        dx = world_pos.x - a["x"]
        dy = world_pos.y - a["y"]
        if dx*dx + dy*dy <= a["r"] * a["r"]:
            return int(a["id"])
    return None

def get_my_station_id(ents: List[dict], player_id: Optional[int]) -> Optional[int]:
    if player_id is None:
        return None
    for e in ents:
        if e["type"] == "station" and int(e["owner"]) == player_id:
            return int(e["id"])
    return None

def selected_miners(selected_ids: set[int], ents_by_id: Dict[int, dict]) -> List[int]:
    out = []
    for uid in selected_ids:
        e = ents_by_id.get(uid)
        if e and e["type"] == "miner":
            out.append(uid)
    return out
