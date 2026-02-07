import random
import pygame
from typing import Dict, Tuple

from . import config as cfg

def init_stars(seed: int, map_w: int, map_h: int):
    rng = random.Random(seed)
    out = []
    for _ in range(cfg.STAR_COUNT):
        x = rng.randrange(0, map_w)
        y = rng.randrange(0, map_h)
        r = rng.choice([1, 1, 1, 2])
        out.append((x, y, r))
    return out

asteroid_tex_cache: Dict[Tuple[int, int, int], pygame.Surface] = {}  # (seed, asteroid_id, radius)->surf

def make_asteroid_texture(map_seed: int, asteroid_id: int, radius: int) -> pygame.Surface:
    rng = random.Random(map_seed * 1000003 + asteroid_id * 9176 + radius * 31)

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

def get_asteroid_tex(map_seed: int, aid: int, r: int) -> pygame.Surface:
    key = (map_seed, aid, r)
    tex = asteroid_tex_cache.get(key)
    if tex is None:
        tex = make_asteroid_texture(map_seed, aid, r)
        asteroid_tex_cache[key] = tex
    return tex
