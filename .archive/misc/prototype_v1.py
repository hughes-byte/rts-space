# v1.

import math
import random
import pygame

pygame.init()

# -------------------- Screen + Map --------------------
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
W, H = screen.get_size()
clock = pygame.time.Clock()

# Bigger map (tweak these)
MAP_W, MAP_H = 15000, 10000

# Camera = top-left world coordinate currently shown
camera = pygame.Vector2(0, 0)

# Edge-scroll settings
EDGE_MARGIN = 20
CAMERA_SPEED = 900  # world px/sec


# -------------------- Coordinate transforms --------------------
def screen_to_world(screen_xy):
    return pygame.Vector2(screen_xy) + camera

def world_to_screen(world_xy):
    return pygame.Vector2(world_xy) - camera


# -------------------- Drawing helpers --------------------
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

def draw_ship(surface, screen_pos, angle, thrust=False, scale=0.6, selected=False):
    hull = [(0, -20), (-14, 16), (-6, 10), (0, 16), (6, 10), (14, 16)]
    cockpit = [(0, -10), (-4, 2), (4, 2)]
    flame = [(0, 24), (-5, 14), (0, 16), (5, 14)]

    hull_w = transform_points(hull, screen_pos, angle, scale)
    cockpit_w = transform_points(cockpit, screen_pos, angle, scale)

    pygame.draw.polygon(surface, (220, 220, 220), hull_w)
    pygame.draw.polygon(surface, (40, 40, 40), hull_w, 2)
    pygame.draw.polygon(surface, (80, 180, 255), cockpit_w)
    pygame.draw.polygon(surface, (20, 20, 20), cockpit_w, 1)

    if thrust:
        flame_w = transform_points(flame, screen_pos, angle, scale)
        pygame.draw.polygon(surface, (255, 160, 40), flame_w)
        pygame.draw.polygon(surface, (255, 240, 120), flame_w, 1)

    if selected:
        pygame.draw.circle(
            surface, (0, 255, 120),
            (int(screen_pos[0]), int(screen_pos[1])),
            int(26 * scale), 2
        )

def draw_station(surface, screen_pos, selected=False):
    """
    Simple procedural station: ring + hub + spokes.
    screen_pos is screen coords.
    """
    x, y = int(screen_pos.x), int(screen_pos.y)

    # main ring
    pygame.draw.circle(surface, (180, 180, 190), (x, y), 70, 8)
    pygame.draw.circle(surface, (70, 70, 80), (x, y), 70, 2)

    # hub
    pygame.draw.circle(surface, (140, 140, 150), (x, y), 22)
    pygame.draw.circle(surface, (40, 40, 50), (x, y), 22, 2)

    # spokes
    for ang in (0, math.pi/2, math.pi, 3*math.pi/2):
        sx = x + int(math.cos(ang) * 48)
        sy = y + int(math.sin(ang) * 48)
        pygame.draw.line(surface, (140, 140, 155), (x, y), (sx, sy), 6)
        pygame.draw.line(surface, (40, 40, 50), (x, y), (sx, sy), 2)

    # docks
    pygame.draw.rect(surface, (160, 160, 175), pygame.Rect(x - 12, y - 90, 24, 26), border_radius=6)
    pygame.draw.rect(surface, (60, 60, 70), pygame.Rect(x - 12, y - 90, 24, 26), 2, border_radius=6)

    if selected:
        pygame.draw.circle(surface, (0, 255, 120), (x, y), 95, 2)


# -------------------- Procedural asteroid textures --------------------
def make_asteroid_texture(radius, rng):
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

    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    return surf


def generate_asteroids(count, map_w, map_h, *, min_radius=35, max_radius=110,
                       edge_pad=600, gap=250, max_tries=120000, seed=1337):
    rng = random.Random(seed)
    out = []
    tries = 0

    while len(out) < count and tries < max_tries:
        tries += 1

        r = rng.randrange(min_radius, max_radius + 1)
        x = rng.randrange(edge_pad + r, map_w - edge_pad - r)
        y = rng.randrange(edge_pad + r, map_h - edge_pad - r)
        c = pygame.Vector2(x, y)

        ok = True
        for (c2, r2, _tex) in out:
            if c.distance_to(c2) < (r + r2 + gap):
                ok = False
                break

        if ok:
            tex = make_asteroid_texture(r, rng)
            out.append((c, r, tex))

    if len(out) < count:
        print(f"Warning: only placed {len(out)}/{count} asteroids. Increase map size or reduce gap/count.")
    return out


# -------------------- World generation --------------------
rng = random.Random(1337)

STAR_COUNT = 4500
stars = []
for _ in range(STAR_COUNT):
    x = rng.randrange(0, MAP_W)
    y = rng.randrange(0, MAP_H)
    r = rng.choice([1, 1, 1, 2])
    stars.append((x, y, r))

ASTEROID_COUNT = 60
asteroids = generate_asteroids(ASTEROID_COUNT, MAP_W, MAP_H)


# -------------------- Collision --------------------
def resolve_circle_vs_asteroids(pos, radius):
    did = False
    p = pygame.Vector2(pos)

    for center, r, _tex in asteroids:
        delta = p - center
        dist = delta.length()
        min_dist = radius + r

        if dist == 0:
            p.x += min_dist
            did = True
            continue

        if dist < min_dist:
            n = delta / dist
            p = center + n * min_dist
            did = True

    return p, did


# -------------------- Units --------------------
class Ship:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)  # WORLD
        self.vel = pygame.Vector2(0, 0)
        self.angle = 0.0
        self.scale = 0.45
        self.selected = False
        self.target = None  # WORLD target

        self.max_speed = 5.0
        self.accel = 0.35
        self.drag = 0.90
        self.arrive_dist = 10.0
        self.turn_rate = 0.10

        self.pick_radius = 18 * self.scale

    def contains_point_world(self, world_p):
        return self.pos.distance_to(world_p) <= self.pick_radius

    def update(self):
        thrusting = False

        if self.target is not None:
            to_target = self.target - self.pos
            dist = to_target.length()

            if dist <= self.arrive_dist:
                self.target = None
                self.vel.update(0, 0)
            else:
                desired = to_target.normalize()
                desired_angle = math.atan2(desired.x, -desired.y)
                da = (desired_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
                self.angle += max(-self.turn_rate, min(self.turn_rate, da))

                forward = pygame.Vector2(math.sin(self.angle), -math.cos(self.angle))
                self.vel += forward * self.accel
                thrusting = True

        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)
        self.vel *= self.drag

        new_pos = self.pos + self.vel
        new_pos.x = max(0, min(MAP_W, new_pos.x))
        new_pos.y = max(0, min(MAP_H, new_pos.y))

        ship_radius = 18 * self.scale
        new_pos, hit = resolve_circle_vs_asteroids(new_pos, ship_radius)
        if hit:
            self.vel.update(0, 0)

        self.pos = new_pos
        return thrusting

    def draw(self, surface, thrusting=False):
        sp = world_to_screen(self.pos)
        draw_ship(surface, (sp.x, sp.y), self.angle, thrust=thrusting,
                  scale=self.scale, selected=self.selected)


class Station:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)   # WORLD
        self.vel = pygame.Vector2(0, 0)
        self.selected = False
        self.target = None               # WORLD target

        # Very slow movement
        self.max_speed = 1.2
        self.accel = 0.08
        self.drag = 0.92
        self.arrive_dist = 10.0

        self.pick_radius = 95  # click radius in world units

    def contains_point_world(self, world_p):
        return self.pos.distance_to(world_p) <= self.pick_radius

    def update(self):
        moving = False

        if self.target is not None:
            to_target = self.target - self.pos
            dist = to_target.length()

            if dist <= self.arrive_dist:
                self.target = None
                self.vel.update(0, 0)
            else:
                desired = to_target.normalize()
                self.vel += desired * self.accel
                moving = True

        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)
        self.vel *= self.drag

        new_pos = self.pos + self.vel
        new_pos.x = max(0, min(MAP_W, new_pos.x))
        new_pos.y = max(0, min(MAP_H, new_pos.y))

        # station collision with asteroids (bigger radius)
        station_radius = 95
        new_pos, hit = resolve_circle_vs_asteroids(new_pos, station_radius)
        if hit:
            self.vel.update(0, 0)

        self.pos = new_pos
        return moving

    def draw(self, surface):
        sp = world_to_screen(self.pos)
        draw_station(surface, sp, selected=self.selected)


# -------------------- Spawn base in center of map and center camera on it --------------------
base = Station((MAP_W / 2) - 600, MAP_H / 2)

# Put camera so base starts centered on screen
camera.x = base.pos.x - W / 2
camera.y = base.pos.y - H / 2
camera.x = max(0, min(MAP_W - W, camera.x))
camera.y = max(0, min(MAP_H - H, camera.y))

# Spawn ships around the base in a ring
ships = []
ring_r = 220
ship_count = 18
for i in range(ship_count):
    ang = (i / ship_count) * 2 * math.pi
    sx = base.pos.x + math.cos(ang) * ring_r
    sy = base.pos.y + math.sin(ang) * ring_r
    ships.append(Ship(sx, sy))


# -------------------- Selection + Commands --------------------
selecting = False
sel_start_screen = pygame.Vector2(0, 0)
sel_end_screen = pygame.Vector2(0, 0)

def rect_from_points(a, b):
    x1, y1 = min(a.x, b.x), min(a.y, b.y)
    x2, y2 = max(a.x, b.x), max(a.y, b.y)
    return pygame.Rect(x1, y1, x2 - x1, y2 - y1)

def clear_selection():
    base.selected = False
    for s in ships:
        s.selected = False

def selected_ships():
    return [s for s in ships if s.selected]

def issue_move_command(world_mouse):
    # If base selected, it moves slowly
    if base.selected:
        base.target = pygame.Vector2(world_mouse)

    sel = selected_ships()
    if not sel:
        return

    n = len(sel)
    side = math.ceil(math.sqrt(n))
    gap = 42
    origin = pygame.Vector2(
        world_mouse.x - (side - 1) * gap / 2,
        world_mouse.y - (side - 1) * gap / 2
    )

    for i, s in enumerate(sel):
        ox = (i % side) * gap
        oy = (i // side) * gap
        s.target = origin + pygame.Vector2(ox, oy)


# -------------------- Camera edge scroll --------------------
def update_camera(dt):
    mx, my = pygame.mouse.get_pos()
    move = pygame.Vector2(0, 0)

    if mx < EDGE_MARGIN:
        move.x -= 1
    elif mx > W - EDGE_MARGIN:
        move.x += 1

    if my < EDGE_MARGIN:
        move.y -= 1
    elif my > H - EDGE_MARGIN:
        move.y += 1

    if move.length_squared() > 0:
        move = move.normalize() * (CAMERA_SPEED * dt)
        camera.x += move.x
        camera.y += move.y

    camera.x = max(0, min(MAP_W - W, camera.x))
    camera.y = max(0, min(MAP_H - H, camera.y))


# -------------------- Main loop --------------------
running = True
while running:
    dt = clock.tick(60) / 1000.0
    update_camera(dt)

    mouse_screen = pygame.Vector2(pygame.mouse.get_pos())
    mouse_world = screen_to_world(mouse_screen)
    mods = pygame.key.get_mods()

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        # Right click: deselect everything
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            selecting = False
            clear_selection()

        # Left down: select base/ship OR start box select
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            clicked_unit = False

            # Base click takes priority
            if base.contains_point_world(mouse_world):
                if not (mods & pygame.KMOD_SHIFT):
                    clear_selection()
                base.selected = True
                selecting = False
                clicked_unit = True
            else:
                # check ships
                clicked = None
                for s in reversed(ships):
                    if s.contains_point_world(mouse_world):
                        clicked = s
                        break

                if clicked is not None:
                    if not (mods & pygame.KMOD_SHIFT):
                        clear_selection()
                    clicked.selected = True
                    selecting = False
                    clicked_unit = True

            if not clicked_unit:
                selecting = True
                sel_start_screen = mouse_screen
                sel_end_screen = mouse_screen

        if e.type == pygame.MOUSEMOTION and selecting:
            sel_end_screen = mouse_screen

        # Left up: tiny drag => move, else box select
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if selecting:
                box = rect_from_points(sel_start_screen, sel_end_screen)
                selecting = False

                if box.width < 6 and box.height < 6:
                    issue_move_command(mouse_world)
                else:
                    if not (mods & pygame.KMOD_SHIFT):
                        clear_selection()

                    # select base if its screen position inside box
                    bp = world_to_screen(base.pos)
                    if box.collidepoint(bp.x, bp.y):
                        base.selected = True

                    for s in ships:
                        sp = world_to_screen(s.pos)
                        if box.collidepoint(sp.x, sp.y):
                            s.selected = True

    # -------------------- Update --------------------
    base.update()
    thrusting_states = []
    for s in ships:
        thrusting_states.append(s.update())

    # -------------------- Draw --------------------
    screen.fill((8, 10, 18))

    # Stars (culled)
    cx, cy = camera.x, camera.y
    for x, y, r in stars:
        sx = x - cx
        sy = y - cy
        if -2 <= sx <= W + 2 and -2 <= sy <= H + 2:
            pygame.draw.circle(screen, (220, 220, 220), (int(sx), int(sy)), r)

    # Asteroids (textured, culled)
    for center, radius, tex in asteroids:
        sc = world_to_screen(center)
        if -radius <= sc.x <= W + radius and -radius <= sc.y <= H + radius:
            rect = tex.get_rect(center=(int(sc.x), int(sc.y)))
            screen.blit(tex, rect)

    # Station then ships
    base.draw(screen)
    for s, thr in zip(ships, thrusting_states):
        s.draw(screen, thrusting=thr)

    # Selection box (screen-space)
    if selecting:
        box = rect_from_points(sel_start_screen, sel_end_screen)
        pygame.draw.rect(screen, (0, 200, 255), box, 2)

    pygame.display.flip()

pygame.quit()
