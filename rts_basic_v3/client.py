import socket
import threading
import math
import random
import pygame
from typing import Dict, Optional, List, Tuple

from common import send_msg, recv_msg

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5001

pygame.init()

# Fullscreen like your prototype:
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
W, H = screen.get_size()
clock = pygame.time.Clock()

font = pygame.font.SysFont("consolas", 22)
small = pygame.font.SysFont("consolas", 18)

# =========================
# Replicated state
# =========================
player_id: Optional[int] = None
MAP_W, MAP_H = 15000, 10000
MAP_SEED = 1337

camera = pygame.Vector2(0, 0)
EDGE_MARGIN = 20
CAMERA_SPEED = 900

asteroids: Dict[int, dict] = {}     # id -> {id,x,y,r}
entities: Dict[int, dict] = {}      # id -> entity dict
credits: Dict[int, int] = {}
tick = 0

state_lock = threading.Lock()

# =========================
# Helpers: coordinate transforms
# =========================
def clamp_camera():
    camera.x = max(0, min(MAP_W - W, camera.x))
    camera.y = max(0, min(MAP_H - H, camera.y))

def screen_to_world(p):
    return pygame.Vector2(p) + camera

def world_to_screen(p):
    return pygame.Vector2(p) - camera

# =========================
# Stars (client-only, deterministic)
# =========================
STAR_COUNT = 5000
stars = []
def init_stars(seed):
    rng = random.Random(seed)
    out = []
    for _ in range(STAR_COUNT):
        x = rng.randrange(0, MAP_W)
        y = rng.randrange(0, MAP_H)
        r = rng.choice([1, 1, 1, 2])
        out.append((x, y, r))
    return out

# =========================
# Asteroid textures (client-only, deterministic)
# =========================
asteroid_tex_cache: Dict[Tuple[int, int], pygame.Surface] = {}  # (asteroid_id, radius)->surf

def make_asteroid_texture(asteroid_id: int, radius: int, seed: int) -> pygame.Surface:
    # deterministic RNG per asteroid
    rng = random.Random(seed * 1000003 + asteroid_id * 9176 + radius * 31)

    size = radius * 2 + 6
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2

    base = rng.randrange(95, 140)
    highlight = min(255, base + rng.randrange(30, 60))
    shadow = max(0, base - rng.randrange(40, 70))

    pygame.draw.circle(surf, (base, base, base, 255), (cx, cy), radius)

    sx = cx - int(radius * 0.18)
    sy = cy - int(radius * 0.18)
    for i in range(radius, 0, -3):
        t = i / radius
        col = int(shadow * (1 - t) + highlight * t)
        alpha = int(10 + 35 * (1 - t))
        pygame.draw.circle(surf, (col, col, col, alpha), (sx, sy), i)

    speck_count = int(radius * radius * 0.08)
    for _ in range(speck_count):
        x = rng.randrange(cx - radius, cx + radius)
        y = rng.randrange(cy - radius, cy + radius)
        if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
            v = base + rng.randrange(-35, 35)
            v = max(0, min(255, v))
            a = rng.randrange(40, 120)
            surf.set_at((x, y), (v, v, v, a))

    crater_count = rng.randrange(4, 10)
    for _ in range(crater_count):
        cr = rng.randrange(max(6, radius // 8), max(10, radius // 3))
        x = y = 0
        for _try in range(30):
            x = rng.randrange(cx - radius + cr, cx + radius - cr)
            y = rng.randrange(cy - radius + cr, cy + radius - cr)
            if (x - cx) ** 2 + (y - cy) ** 2 <= (radius - cr) ** 2:
                break

        rim = (min(255, base + 35),) * 3 + (110,)
        pit = (max(0, base - 55),) * 3 + (140,)
        pygame.draw.circle(surf, pit, (x + 2, y + 2), cr)
        pygame.draw.circle(surf, rim, (x - 1, y - 1), cr, 2)
        pygame.draw.circle(surf, (0, 0, 0, 40), (x, y), cr, 1)

    pygame.draw.circle(surf, (60, 60, 70, 255), (cx, cy), radius, 3)
    return surf

def get_asteroid_tex(aid: int, r: int) -> pygame.Surface:
    key = (aid, r)
    tex = asteroid_tex_cache.get(key)
    if tex is None:
        tex = make_asteroid_texture(aid, r, MAP_SEED)
        asteroid_tex_cache[key] = tex
    return tex

# =========================
# Drawing (ships/stations simplified)
# =========================
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

# =========================
# Minimap
# =========================
MINIMAP_W, MINIMAP_H = 260, 180
MINIMAP_MARGIN = 12
minimap_rect = pygame.Rect(W - MINIMAP_W - MINIMAP_MARGIN, MINIMAP_MARGIN, MINIMAP_W, MINIMAP_H)

def world_to_minimap(p_world: pygame.Vector2) -> pygame.Vector2:
    sx = minimap_rect.x + (p_world.x / MAP_W) * minimap_rect.w
    sy = minimap_rect.y + (p_world.y / MAP_H) * minimap_rect.h
    return pygame.Vector2(sx, sy)

def draw_minimap(surface):
    pygame.draw.rect(surface, (10, 12, 18), minimap_rect)
    pygame.draw.rect(surface, (70, 70, 90), minimap_rect, 2)

    vw = (W / MAP_W) * minimap_rect.w
    vh = (H / MAP_H) * minimap_rect.h
    vx = minimap_rect.x + (camera.x / MAP_W) * minimap_rect.w
    vy = minimap_rect.y + (camera.y / MAP_H) * minimap_rect.h
    pygame.draw.rect(surface, (130, 130, 170), pygame.Rect(vx, vy, vw, vh), 1)

    with state_lock:
        asts = list(asteroids.values())
        ents = list(entities.values())

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

# =========================
# Input + selection
# =========================
selected_ids: set[int] = set()
selecting = False
sel_start = pygame.Vector2(0, 0)
sel_end = pygame.Vector2(0, 0)

def rect_from_points(a, b):
    x1, y1 = min(a.x, b.x), min(a.y, b.y)
    x2, y2 = max(a.x, b.x), max(a.y, b.y)
    return pygame.Rect(x1, y1, x2 - x1, y2 - y1)

def update_camera(dt):
    mx, my = pygame.mouse.get_pos()
    move = pygame.Vector2(0, 0)

    if mx < EDGE_MARGIN: move.x -= 1
    elif mx > W - EDGE_MARGIN: move.x += 1
    if my < EDGE_MARGIN: move.y -= 1
    elif my > H - EDGE_MARGIN: move.y += 1

    if move.length_squared() > 0:
        move = move.normalize() * (CAMERA_SPEED * dt)
        camera.x += move.x
        camera.y += move.y
        clamp_camera()

def pick_entity_at(world_pos: pygame.Vector2, ents: List[dict]) -> Optional[int]:
    # pick nearest owned unit within radius
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

def get_my_station_id(ents: List[dict]) -> Optional[int]:
    if player_id is None:
        return None
    for e in ents:
        if e["type"] == "station" and int(e["owner"]) == player_id:
            return int(e["id"])
    return None

def selected_miners(ents_by_id: Dict[int, dict]) -> List[int]:
    out = []
    for uid in selected_ids:
        e = ents_by_id.get(uid)
        if e and e["type"] == "miner":
            out.append(uid)
    return out

# =========================
# Network receive
# =========================
def recv_loop(sock: socket.socket):
    global player_id, MAP_W, MAP_H, MAP_SEED, stars, tick
    try:
        while True:
            msg = recv_msg(sock)
            t = msg.get("type")
            if t == "map_init":
                with state_lock:
                    player_id = int(msg["player_id"])
                    MAP_W = int(msg["map_w"])
                    MAP_H = int(msg["map_h"])
                    MAP_SEED = int(msg["map_seed"])
                    ast_list = msg["asteroids"]
                    asteroids.clear()
                    for a in ast_list:
                        asteroids[int(a["id"])] = a
                # init stars after map info
                stars[:] = init_stars(MAP_SEED)
                # center camera on your station once snapshots start
                print(f"[client] map_init player_id={player_id} asteroids={len(asteroids)}")

            elif t == "snapshot":
                with state_lock:
                    tick = int(msg["tick"])
                    credits.clear()
                    for k, v in msg.get("credits", {}).items():
                        credits[int(k)] = int(v)
                    entities.clear()
                    for e in msg.get("entities", []):
                        entities[int(e["id"])] = e
            else:
                pass
    except Exception as e:
        print("[client] disconnected:", e)

# =========================
# Main
# =========================
def main():
    global selecting, sel_start, sel_end, selected_ids

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    send_msg(sock, {"type": "hello", "name": "player"})
    threading.Thread(target=recv_loop, args=(sock,), daemon=True).start()

    # wait a moment for init
    # (don’t block hard; game will just show blank until init comes in)

    running = True
    centered_once = False

    while running:
        dt = clock.tick(60) / 1000.0
        update_camera(dt)

        mouse_screen = pygame.Vector2(pygame.mouse.get_pos())
        mouse_world = screen_to_world(mouse_screen)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

            # Buy miner
            if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                with state_lock:
                    ents_list = list(entities.values())
                sid = get_my_station_id(ents_list)
                if sid is not None:
                    send_msg(sock, {"type": "cmd_buy_miner", "station_id": sid})

            # Right click deselect
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                selecting = False
                selected_ids.clear()

            # Left down -> start select
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                selecting = True
                sel_start = pygame.Vector2(pygame.mouse.get_pos())
                sel_end = sel_start

            if e.type == pygame.MOUSEMOTION and selecting:
                sel_end = pygame.Vector2(pygame.mouse.get_pos())

            # Left up -> click or box
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and selecting:
                selecting = False
                box = rect_from_points(sel_start, sel_end)
                is_click = box.width < 6 and box.height < 6

                with state_lock:
                    ents_list = list(entities.values())
                    ents_by_id = dict(entities)
                    ast_list = list(asteroids.values())

                if is_click:
                    # click on own unit selects it
                    picked = pick_entity_at(mouse_world, ents_list)
                    if picked is not None:
                        selected_ids = {picked}
                    else:
                        # click asteroid => miners mine
                        aid = pick_asteroid_at(mouse_world, ast_list)
                        if aid is not None:
                            miners = selected_miners(ents_by_id)
                            if miners:
                                send_msg(sock, {"type": "cmd_mine", "unit_ids": miners, "asteroid_id": aid})
                            else:
                                # no miners selected => treat as move
                                if selected_ids:
                                    send_msg(sock, {"type": "cmd_move", "unit_ids": list(selected_ids),
                                                    "x": float(mouse_world.x), "y": float(mouse_world.y)})
                        else:
                            # empty => move selected
                            if selected_ids:
                                send_msg(sock, {"type": "cmd_move", "unit_ids": list(selected_ids),
                                                "x": float(mouse_world.x), "y": float(mouse_world.y)})
                else:
                    # box select owned units
                    selected_ids.clear()
                    if player_id is not None:
                        # box is in screen-space; check entities projected to screen
                        for ent in ents_list:
                            if int(ent["owner"]) != player_id:
                                continue
                            sp = world_to_screen(pygame.Vector2(ent["x"], ent["y"]))
                            if box.collidepoint(sp.x, sp.y):
                                selected_ids.add(int(ent["id"]))

        # Draw
        screen.fill((8, 10, 18))

        with state_lock:
            ast_list = list(asteroids.values())
            ents_list = list(entities.values())
            my_credits = credits.get(player_id or -1, 0)
            t = tick

        # Center camera on station once after we have entities
        if (not centered_once) and player_id is not None and ents_list:
            for ent in ents_list:
                if ent["type"] == "station" and int(ent["owner"]) == player_id:
                    camera.x = float(ent["x"]) - W / 2
                    camera.y = float(ent["y"]) - H / 2
                    clamp_camera()
                    centered_once = True
                    break

        # stars (culled)
        cx, cy = camera.x, camera.y
        for x, y, r in stars:
            sx = x - cx
            sy = y - cy
            if -2 <= sx <= W + 2 and -2 <= sy <= H + 2:
                pygame.draw.circle(screen, (220, 220, 220), (int(sx), int(sy)), r)

        # asteroids (textured)
        for a in ast_list:
            ax, ay, ar = float(a["x"]), float(a["y"]), int(a["r"])
            sc = world_to_screen(pygame.Vector2(ax, ay))
            if -ar <= sc.x <= W + ar and -ar <= sc.y <= H + ar:
                tex = get_asteroid_tex(int(a["id"]), ar)
                rect = tex.get_rect(center=(int(sc.x), int(sc.y)))
                screen.blit(tex, rect)

        # entities
        for ent in ents_list:
            sp = world_to_screen(pygame.Vector2(ent["x"], ent["y"]))
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
                    lab = small.render(str(st), True, (160, 220, 255))
                    screen.blit(lab, (int(sp.x - 32), int(sp.y + 16)))

        # selection box
        if selecting:
            box = rect_from_points(sel_start, sel_end)
            pygame.draw.rect(screen, (0, 200, 255), box, 2)

        # minimap
        draw_minimap(screen)

        # HUD
        hud = font.render(f"Credits: {my_credits}    (M) Buy Miner", True, (220, 220, 230))
        screen.blit(hud, (14, 14))
        hud2 = small.render(f"tick={t}  selected={len(selected_ids)}  (RMB deselect)", True, (160, 160, 175))
        screen.blit(hud2, (14, 42))

        pygame.display.flip()

    try:
        sock.close()
    except Exception:
        pass
    pygame.quit()

if __name__ == "__main__":
    main()
