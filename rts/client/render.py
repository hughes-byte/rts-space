import math
import pygame
from typing import Dict, List, Optional, Tuple

from .assets import get_asteroid_tex

def rotate_point(px, py, angle):
    ca, sa = math.cos(angle), math.sin(angle)
    return (px * ca - py * sa, px * sa + py * ca)

def transform_points(points, pos, angle, scale):
    x, y = pos
    out = []
    for px, py in points:
        rx, ry = rotate_point(px * scale, py * scale, angle)
        out.append((x + rx, y + ry))
    return out

def draw_ship(surface, screen_pos, angle, scale=0.45, tint=(220, 220, 220)):
    hull = [(0, -20), (-14, 16), (-6, 10), (0, 16), (6, 10), (14, 16)]
    cockpit = [(0, -10), (-4, 2), (4, 2)]
    hull_w = transform_points(hull, screen_pos, angle, scale)
    cockpit_w = transform_points(cockpit, screen_pos, angle, scale)
    pygame.draw.polygon(surface, tint, hull_w)
    pygame.draw.polygon(surface, (40, 40, 40), hull_w, 2)
    pygame.draw.polygon(surface, (80, 180, 255), cockpit_w)
    pygame.draw.polygon(surface, (20, 20, 20), cockpit_w, 1)

def draw_station(surface, sp):
    x, y = int(sp.x), int(sp.y)
    pygame.draw.circle(surface, (180, 180, 190), (x, y), 70, 8)
    pygame.draw.circle(surface, (70, 70, 80), (x, y), 70, 2)
    pygame.draw.circle(surface, (140, 140, 150), (x, y), 22)
    pygame.draw.circle(surface, (40, 40, 50), (x, y), 22, 2)

def draw_health_bar(surface, screen_pos, w, hp, hp_max):
    pct = 0 if hp_max <= 0 else max(0.0, min(1.0, hp / hp_max))
    x = int(screen_pos.x - w // 2)
    y = int(screen_pos.y)
    back = pygame.Rect(x, y, w, 8)
    fill = pygame.Rect(x, y, int(w * pct), 8)
    pygame.draw.rect(surface, (20, 20, 25), back)
    pygame.draw.rect(surface, (0, 220, 120), fill)
    pygame.draw.rect(surface, (90, 90, 110), back, 1)

def draw_stars(screen: pygame.Surface, stars: List[Tuple[int,int,int]], camera_pos: pygame.Vector2, W: int, H: int):
    cx, cy = camera_pos.x, camera_pos.y
    for x, y, r in stars:
        sx = x - cx
        sy = y - cy
        if -2 <= sx <= W + 2 and -2 <= sy <= H + 2:
            pygame.draw.circle(screen, (220, 220, 220), (int(sx), int(sy)), r)

def draw_asteroids(screen: pygame.Surface, ast_list: List[dict], camera, W: int, H: int, map_seed: int):
    for a in ast_list:
        ax, ay, ar = float(a["x"]), float(a["y"]), int(a["r"])
        sc = camera.world_to_screen(pygame.Vector2(ax, ay))
        if -ar <= sc.x <= W + ar and -ar <= sc.y <= H + ar:
            tex = get_asteroid_tex(map_seed, int(a["id"]), ar)
            rect = tex.get_rect(center=(int(sc.x), int(sc.y)))
            screen.blit(tex, rect)

def draw_entities(screen: pygame.Surface, ents_list: List[dict], camera, W: int, H: int,
                  player_id: Optional[int], selected_ids: set[int], small_font: pygame.font.Font):
    for ent in ents_list:
        sp = camera.world_to_screen(pygame.Vector2(ent["x"], ent["y"]))
        if not (-200 <= sp.x <= W + 200 and -200 <= sp.y <= H + 200):
            continue

        owner = int(ent["owner"])
        is_me = (player_id is not None and owner == player_id)

        if ent["type"] == "station":
            draw_station(screen, sp)
            if int(ent["id"]) in selected_ids:
                draw_health_bar(screen, sp + pygame.Vector2(0, -110), 120, ent["hp"], ent["hp_max"])

        elif ent["type"] == "fighter":
            tint = (220, 220, 220) if is_me else (255, 90, 90)
            draw_ship(screen, (sp.x, sp.y), float(ent["angle"]), scale=0.45, tint=tint)
            if int(ent["id"]) in selected_ids:
                draw_health_bar(screen, sp + pygame.Vector2(0, -30), 54, ent["hp"], ent["hp_max"])

        elif ent["type"] == "miner":
            tint = (160, 220, 255) if is_me else (255, 120, 120)
            draw_ship(screen, (sp.x, sp.y), float(ent["angle"]), scale=0.45, tint=tint)
            if int(ent["id"]) in selected_ids:
                draw_health_bar(screen, sp + pygame.Vector2(0, -30), 54, ent["hp"], ent["hp_max"])
                st = ent.get("miner_state") or "idle"
                lab = small_font.render(str(st), True, (160, 220, 255))
                screen.blit(lab, (int(sp.x - 32), int(sp.y + 16)))

def draw_minimap(surface: pygame.Surface, minimap_rect: pygame.Rect,
                 map_w: int, map_h: int, camera_pos: pygame.Vector2, W: int, H: int,
                 asts: List[dict], ents: List[dict], player_id: Optional[int]):
    pygame.draw.rect(surface, (10, 12, 18), minimap_rect)
    pygame.draw.rect(surface, (70, 70, 90), minimap_rect, 2)

    vw = (W / map_w) * minimap_rect.w
    vh = (H / map_h) * minimap_rect.h
    vx = minimap_rect.x + (camera_pos.x / map_w) * minimap_rect.w
    vy = minimap_rect.y + (camera_pos.y / map_h) * minimap_rect.h
    pygame.draw.rect(surface, (130, 130, 170), pygame.Rect(vx, vy, vw, vh), 1)

    def world_to_minimap(p_world: pygame.Vector2) -> pygame.Vector2:
        sx = minimap_rect.x + (p_world.x / map_w) * minimap_rect.w
        sy = minimap_rect.y + (p_world.y / map_h) * minimap_rect.h
        return pygame.Vector2(sx, sy)

    for a in asts:
        mp = world_to_minimap(pygame.Vector2(a["x"], a["y"]))
        r = max(1, min(3, int(a["r"]) // 60))
        pygame.draw.circle(surface, (120, 120, 130), (int(mp.x), int(mp.y)), r)

    for e in ents:
        mp = world_to_minimap(pygame.Vector2(e["x"], e["y"]))
        if player_id is not None and int(e["owner"]) == player_id:
            color = (0, 255, 120) if e["type"] != "miner" else (120, 220, 255)
            pygame.draw.circle(surface, color, (int(mp.x), int(mp.y)), 2)
        else:
            pygame.draw.circle(surface, (255, 90, 90), (int(mp.x), int(mp.y)), 2)
