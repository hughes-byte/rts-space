import socket
import threading
import pygame
import math
from typing import Dict, List, Optional, Tuple

from common import send_msg, recv_msg

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5001

WIN_W, WIN_H = 1100, 750

# Client-side “replicated” state
class ReplicatedWorld:
    def __init__(self):
        self.lock = threading.Lock()
        self.tick = 0
        self.units: Dict[int, dict] = {}  # id -> {id, owner, x, y}

world = ReplicatedWorld()

player_id: Optional[int] = None
map_w = 2000
map_h = 1500

def recv_thread(sock: socket.socket):
    global player_id, map_w, map_h
    try:
        while True:
            msg = recv_msg(sock)
            mtype = msg.get("type")

            if mtype == "welcome":
                player_id = int(msg["player_id"])
                map_w = int(msg.get("map_w", map_w))
                map_h = int(msg.get("map_h", map_h))
                print(f"[client] welcome player_id={player_id} map=({map_w}x{map_h})")

            elif mtype == "snapshot":
                with world.lock:
                    world.tick = int(msg.get("tick", world.tick))
                    units = msg.get("units", [])
                    world.units = {int(u["id"]): u for u in units}

            else:
                # server events etc.
                pass

    except Exception as e:
        print("[client] disconnected:", e)

def rect_from_points(a: pygame.Vector2, b: pygame.Vector2) -> pygame.Rect:
    x1, y1 = min(a.x, b.x), min(a.y, b.y)
    x2, y2 = max(a.x, b.x), max(a.y, b.y)
    return pygame.Rect(x1, y1, x2 - x1, y2 - y1)

def main():
    global player_id

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    # HELLO handshake
    send_msg(sock, {"type": "hello", "name": "player"})
    t = threading.Thread(target=recv_thread, args=(sock,), daemon=True)
    t.start()

    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("RTS Basic Client")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)

    selecting = False
    sel_start = pygame.Vector2(0, 0)
    sel_end = pygame.Vector2(0, 0)
    selected_ids: set[int] = set()

    def owned_unit_ids_snapshot(units: Dict[int, dict]) -> List[int]:
        if player_id is None:
            return []
        return [uid for uid, u in units.items() if int(u["owner"]) == player_id]

    def pick_unit_at(pos: pygame.Vector2, units: Dict[int, dict]) -> Optional[int]:
        # pick nearest unit within radius
        best = None
        best_d2 = 1e9
        for uid, u in units.items():
            x, y = float(u["x"]), float(u["y"])
            dx = pos.x - x
            dy = pos.y - y
            d2 = dx*dx + dy*dy
            if d2 <= 14*14 and d2 < best_d2:
                best = uid
                best_d2 = d2
        return best

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                selecting = True
                sel_start = pygame.Vector2(pygame.mouse.get_pos())
                sel_end = sel_start

            if e.type == pygame.MOUSEMOTION and selecting:
                sel_end = pygame.Vector2(pygame.mouse.get_pos())

            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                if not selecting:
                    continue
                selecting = False

                start = sel_start
                end = sel_end
                box = rect_from_points(start, end)

                # Treat tiny drag as click
                is_click = box.width < 6 and box.height < 6

                with world.lock:
                    units = dict(world.units)

                if is_click:
                    click_pos = pygame.Vector2(pygame.mouse.get_pos())
                    uid = pick_unit_at(click_pos, units)
                    if uid is not None and player_id is not None and int(units[uid]["owner"]) == player_id:
                        # single select
                        selected_ids = {uid}
                    else:
                        # click ground => issue move for selected units
                        if selected_ids:
                            send_msg(sock, {
                                "type": "cmd_move",
                                "unit_ids": list(selected_ids),
                                "x": float(click_pos.x),
                                "y": float(click_pos.y),
                            })
                else:
                    # box select: select owned units whose positions are in box
                    selected_ids.clear()
                    if player_id is not None:
                        for uid, u in units.items():
                            if int(u["owner"]) != player_id:
                                continue
                            x, y = float(u["x"]), float(u["y"])
                            if box.collidepoint(x, y):
                                selected_ids.add(uid)

        # draw
        screen.fill((10, 12, 18))

        with world.lock:
            units = dict(world.units)
            tick = world.tick

        # draw units
        for uid, u in units.items():
            x, y = float(u["x"]), float(u["y"])
            owner = int(u["owner"])
            is_me = (player_id is not None and owner == player_id)

            color = (0, 220, 120) if is_me else (255, 90, 90)
            pygame.draw.circle(screen, color, (int(x), int(y)), 8)

            # outline
            pygame.draw.circle(screen, (25, 25, 30), (int(x), int(y)), 8, 2)

            # selection ring
            if uid in selected_ids:
                pygame.draw.circle(screen, (220, 220, 120), (int(x), int(y)), 14, 2)

        # selection box
        if selecting:
            box = rect_from_points(sel_start, sel_end)
            pygame.draw.rect(screen, (0, 200, 255), box, 2)

        # HUD
        pid_txt = "?" if player_id is None else str(player_id)
        hud = font.render(f"player_id={pid_txt}  tick={tick}  selected={len(selected_ids)}", True, (220, 220, 230))
        screen.blit(hud, (12, 10))
        hint = font.render("Drag box to select. Click unit to select. Click ground to move. ESC quits.", True, (160, 160, 175))
        screen.blit(hint, (12, 34))

        pygame.display.flip()

    try:
        sock.close()
    except Exception:
        pass
    pygame.quit()

if __name__ == "__main__":
    main()
