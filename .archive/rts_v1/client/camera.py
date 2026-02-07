import pygame
from . import config as cfg

class Camera:
    def __init__(self):
        self.pos = pygame.Vector2(0, 0)

    def clamp(self, map_w: int, map_h: int, screen_w: int, screen_h: int):
        self.pos.x = max(0, min(map_w - screen_w, self.pos.x))
        self.pos.y = max(0, min(map_h - screen_h, self.pos.y))

    def screen_to_world(self, p):
        return pygame.Vector2(p) + self.pos

    def world_to_screen(self, p):
        return pygame.Vector2(p) - self.pos

    def update_from_mouse_edge(self, dt: float, screen_w: int, screen_h: int, map_w: int, map_h: int):
        mx, my = pygame.mouse.get_pos()
        move = pygame.Vector2(0, 0)

        if mx < cfg.EDGE_MARGIN: move.x -= 1
        elif mx > screen_w - cfg.EDGE_MARGIN: move.x += 1
        if my < cfg.EDGE_MARGIN: move.y -= 1
        elif my > screen_h - cfg.EDGE_MARGIN: move.y += 1

        if move.length_squared() > 0:
            move = move.normalize() * (cfg.CAMERA_SPEED * dt)
            self.pos += move
            self.clamp(map_w, map_h, screen_w, screen_h)
