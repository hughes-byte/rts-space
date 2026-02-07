import pygame

from rts.net import protocol as P
from . import config as cfg
from .model import ClientModel
from .camera import Camera
from .assets import init_stars
from .netclient import NetClient
from .render import draw_stars, draw_asteroids, draw_entities, draw_minimap
from .input import rect_from_points, pick_entity_at, pick_asteroid_at, get_my_station_id, selected_miners

def main():
    pygame.init()

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    W, H = screen.get_size()
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 22)
    small = pygame.font.SysFont("consolas", 18)

    model = ClientModel()
    cam = Camera()
    net = NetClient()
    net.connect(cfg.SERVER_HOST, cfg.SERVER_PORT)

    stars = []
    selected_ids: set[int] = set()
    selecting = False
    sel_start = pygame.Vector2(0, 0)
    sel_end = pygame.Vector2(0, 0)

    centered_once = False
    running = True

    minimap_rect = pygame.Rect(W - cfg.MINIMAP_W - cfg.MINIMAP_MARGIN, cfg.MINIMAP_MARGIN, cfg.MINIMAP_W, cfg.MINIMAP_H)

    while running:
        RENDER_HZ = 120
        dt = clock.tick(RENDER_HZ) / 1000.0

        # Drain network inbox on main thread
        while True:
            try:
                msg = net.inbox.get_nowait()
            except Exception:
                break

            t = msg.get("type")
            if t == P.MAP_INIT:
                model.apply_map_init(msg)
                with model.lock:
                    stars = init_stars(model.MAP_SEED, model.MAP_W, model.MAP_H)
                print(f"[client] map_init player_id={model.player_id} asteroids={len(model.asteroids)}")

            elif t == P.SNAPSHOT:
                model.apply_snapshot(msg)

            elif t == "_disconnect":
                print("[client] disconnected:", msg.get("error"))
                running = False

        with model.lock:
            pid = model.player_id
            map_w, map_h, map_seed = model.MAP_W, model.MAP_H, model.MAP_SEED
            ast_list = list(model.asteroids.values())
            ents_list = list(model.entities.values())
            ents_by_id = dict(model.entities)
            credits = dict(model.credits)
            tick = model.tick

        cam.update_from_mouse_edge(dt, W, H, map_w, map_h)

        mouse_screen = pygame.Vector2(pygame.mouse.get_pos())
        mouse_world = cam.screen_to_world(mouse_screen)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False

            # Buy miner
            if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                sid = get_my_station_id(ents_list, pid)
                if sid is not None:
                    net.send({"type": P.CMD_BUY_MINER, "station_id": sid})

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

                if is_click:
                    picked = pick_entity_at(mouse_world, ents_list, pid)
                    if picked is not None:
                        selected_ids = {picked}
                    else:
                        aid = pick_asteroid_at(mouse_world, ast_list)
                        if aid is not None:
                            miners = selected_miners(selected_ids, ents_by_id)
                            if miners:
                                net.send({"type": P.CMD_MINE, "unit_ids": miners, "asteroid_id": aid})
                            else:
                                if selected_ids:
                                    net.send({"type": P.CMD_MOVE, "unit_ids": list(selected_ids),
                                              "x": float(mouse_world.x), "y": float(mouse_world.y)})
                        else:
                            if selected_ids:
                                net.send({"type": P.CMD_MOVE, "unit_ids": list(selected_ids),
                                          "x": float(mouse_world.x), "y": float(mouse_world.y)})
                else:
                    selected_ids.clear()
                    if pid is not None:
                        for ent in ents_list:
                            if int(ent["owner"]) != pid:
                                continue
                            sp = cam.world_to_screen(pygame.Vector2(ent["x"], ent["y"]))
                            if box.collidepoint(sp.x, sp.y):
                                selected_ids.add(int(ent["id"]))

        # Center camera once
        if (not centered_once) and pid is not None and ents_list:
            for ent in ents_list:
                if ent["type"] == "station" and int(ent["owner"]) == pid:
                    cam.pos.x = float(ent["x"]) - W / 2
                    cam.pos.y = float(ent["y"]) - H / 2
                    cam.clamp(map_w, map_h, W, H)
                    centered_once = True
                    break

        # Draw
        screen.fill((8, 10, 18))
        draw_stars(screen, stars, cam.pos, W, H)
        draw_asteroids(screen, ast_list, cam, W, H, map_seed)
        draw_entities(screen, ents_list, cam, W, H, pid, selected_ids, small)

        if selecting:
            box = rect_from_points(sel_start, sel_end)
            pygame.draw.rect(screen, (0, 200, 255), box, 2)

        draw_minimap(screen, minimap_rect, map_w, map_h, cam.pos, W, H, ast_list, ents_list, pid)

        my_credits = credits.get(pid or -1, 0)
        hud = font.render(f"Credits: {my_credits}    (M) Buy Miner", True, (220, 220, 230))
        screen.blit(hud, (14, 14))
        hud2 = small.render(f"tick={tick}  selected={len(selected_ids)}  (RMB deselect)", True, (160, 160, 175))
        screen.blit(hud2, (14, 42))

        pygame.display.flip()

    net.close()
    pygame.quit()
