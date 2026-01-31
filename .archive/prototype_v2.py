# v2. Added health, health bars, enemy, attack, minimap.

import math
import random
import pygame

pygame.init()

# ============================================================
# Screen + Fullscreen (toggle this if you want windowed)
# ============================================================
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
W, H = screen.get_size()
clock = pygame.time.Clock()

# ============================================================
# Map / Camera
# ============================================================
MAP_W, MAP_H = 15000, 10000
camera = pygame.Vector2(0, 0)

EDGE_MARGIN = 20
CAMERA_SPEED = 900  # world px/sec

def clamp_camera():
    camera.x = max(0, min(MAP_W - W, camera.x))
    camera.y = max(0, min(MAP_H - H, camera.y))

def screen_to_world(p):
    return pygame.Vector2(p) + camera

def world_to_screen(p):
    return pygame.Vector2(p) - camera


# ============================================================
# Minimap
# ============================================================
MINIMAP_W, MINIMAP_H = 260, 180
MINIMAP_MARGIN = 12
minimap_rect = pygame.Rect(W - MINIMAP_W - MINIMAP_MARGIN, MINIMAP_MARGIN, MINIMAP_W, MINIMAP_H)

def world_to_minimap(p_world: pygame.Vector2) -> pygame.Vector2:
    sx = minimap_rect.x + (p_world.x / MAP_W) * minimap_rect.w
    sy = minimap_rect.y + (p_world.y / MAP_H) * minimap_rect.h
    return pygame.Vector2(sx, sy)

def draw_minimap(surface, stars, asteroids, base, ships, enemy_structures):
    # background
    pygame.draw.rect(surface, (10, 12, 18), minimap_rect)
    pygame.draw.rect(surface, (70, 70, 90), minimap_rect, 2)

    # viewport box
    vw = (W / MAP_W) * minimap_rect.w
    vh = (H / MAP_H) * minimap_rect.h
    vx = minimap_rect.x + (camera.x / MAP_W) * minimap_rect.w
    vy = minimap_rect.y + (camera.y / MAP_H) * minimap_rect.h
    pygame.draw.rect(surface, (130, 130, 170), pygame.Rect(vx, vy, vw, vh), 1)

    # asteroids (as tiny dots)
    for center, radius, _tex in asteroids:
        mp = world_to_minimap(center)
        # dot size based on asteroid radius (clamped)
        r = max(1, min(3, radius // 60))
        pygame.draw.circle(surface, (120, 120, 130), (int(mp.x), int(mp.y)), r)

    # friendly base
    mpb = world_to_minimap(base.pos)
    pygame.draw.circle(surface, (0, 200, 120), (int(mpb.x), int(mpb.y)), 3)

    # friendly ships
    for s in ships:
        mp = world_to_minimap(s.pos)
        pygame.draw.circle(surface, (0, 255, 120), (int(mp.x), int(mp.y)), 2)

    # enemy structures
    for e in enemy_structures:
        mp = world_to_minimap(e.pos)
        pygame.draw.circle(surface, (255, 80, 80), (int(mp.x), int(mp.y)), 3)


# ============================================================
# Drawing helpers
# ============================================================
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

def draw_ship(surface, screen_pos, angle, thrust=False, scale=0.6):
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

def draw_station(surface, screen_pos):
    x, y = int(screen_pos.x), int(screen_pos.y)
    pygame.draw.circle(surface, (180, 180, 190), (x, y), 70, 8)
    pygame.draw.circle(surface, (70, 70, 80), (x, y), 70, 2)
    pygame.draw.circle(surface, (140, 140, 150), (x, y), 22)
    pygame.draw.circle(surface, (40, 40, 50), (x, y), 22, 2)

    for ang in (0, math.pi/2, math.pi, 3*math.pi/2):
        sx = x + int(math.cos(ang) * 48)
        sy = y + int(math.sin(ang) * 48)
        pygame.draw.line(surface, (140, 140, 155), (x, y), (sx, sy), 6)
        pygame.draw.line(surface, (40, 40, 50), (x, y), (sx, sy), 2)

    pygame.draw.rect(surface, (160, 160, 175), pygame.Rect(x - 12, y - 90, 24, 26), border_radius=6)
    pygame.draw.rect(surface, (60, 60, 70), pygame.Rect(x - 12, y - 90, 24, 26), 2, border_radius=6)

def draw_enemy_base(surface, screen_pos):
    x, y = int(screen_pos.x), int(screen_pos.y)
    pygame.draw.circle(surface, (200, 80, 80), (x, y), 78, 10)
    pygame.draw.circle(surface, (70, 25, 25), (x, y), 78, 2)
    pygame.draw.circle(surface, (180, 60, 60), (x, y), 26)
    pygame.draw.circle(surface, (40, 15, 15), (x, y), 26, 2)
    # little spikes
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        x1 = x + int(math.cos(a) * 60)
        y1 = y + int(math.sin(a) * 60)
        x2 = x + int(math.cos(a) * 92)
        y2 = y + int(math.sin(a) * 92)
        pygame.draw.line(surface, (170, 60, 60), (x1, y1), (x2, y2), 6)
        pygame.draw.line(surface, (40, 15, 15), (x1, y1), (x2, y2), 2)

def draw_health_bar(surface, screen_pos, w, h, hp, hp_max):
    # health bar above unit (screen space)
    x = int(screen_pos.x - w // 2)
    y = int(screen_pos.y - h)
    pct = 0 if hp_max <= 0 else max(0.0, min(1.0, hp / hp_max))

    back = pygame.Rect(x, y, w, 8)
    fill = pygame.Rect(x, y, int(w * pct), 8)

    pygame.draw.rect(surface, (20, 20, 25), back)
    pygame.draw.rect(surface, (0, 220, 120), fill)
    pygame.draw.rect(surface, (90, 90, 110), back, 1)


# ============================================================
# Procedural asteroids (non-overlap + texture)
# ============================================================
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
                       edge_pad=600, gap=250, max_tries=140000, seed=1337):
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
        print(f"Warning: only placed {len(out)}/{count} asteroids. Try bigger map or smaller gap/count.")
    return out

# stars + asteroids
rng = random.Random(1337)
STAR_COUNT = 5000
stars = [(rng.randrange(0, MAP_W), rng.randrange(0, MAP_H), rng.choice([1, 1, 1, 2])) for _ in range(STAR_COUNT)]
ASTEROID_COUNT = 60
ASTEROID_GAP = 250
asteroids = generate_asteroids(ASTEROID_COUNT, MAP_W, MAP_H, gap=ASTEROID_GAP)

def resolve_circle_vs_asteroids(pos, radius):
    did = False
    p = pygame.Vector2(pos)
    for center, r, _tex in asteroids:
        d = p - center
        dist = d.length()
        min_dist = radius + r
        if dist == 0:
            p.x += min_dist
            did = True
        elif dist < min_dist:
            p = center + (d / dist) * min_dist
            did = True
    return p, did


# ============================================================
# Combat: bullets
# ============================================================
class Bullet:
    def __init__(self, pos, vel, dmg, team):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.dmg = dmg
        self.team = team  # "player" or "enemy"
        self.life = 1.5   # seconds

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt

    def draw(self, surf):
        sp = world_to_screen(self.pos)
        pygame.draw.circle(surf, (255, 230, 120), (int(sp.x), int(sp.y)), 2)


# ============================================================
# Game objects
# ============================================================
class GameObject:
    def __init__(self, x, y, hp_max):
        self.pos = pygame.Vector2(x, y)
        self.hp_max = hp_max
        self.hp = hp_max
        self.alive = True

    def take_damage(self, amount):
        if not self.alive:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

class Ship(GameObject):
    def __init__(self, x, y):
        super().__init__(x, y, hp_max=80)
        self.vel = pygame.Vector2(0, 0)
        self.angle = 0.0
        self.scale = 0.45
        self.selected = False

        self.move_target = None   # world vec2
        self.attack_target = None # enemy object ref (or None)

        # movement
        self.max_speed = 5.0
        self.accel = 0.35
        self.drag = 0.90
        self.arrive_dist = 10.0
        self.turn_rate = 0.10
        self.pick_radius = 18 * self.scale

        # combat
        self.attack_range = 520
        self.fire_rate = 3.0   # shots/sec
        self.fire_cd = 0.0
        self.bullet_speed = 900
        self.bullet_dmg = 10

    def contains_point_world(self, p):
        return self.pos.distance_to(p) <= self.pick_radius

    def set_move(self, p):
        self.move_target = pygame.Vector2(p)
        self.attack_target = None

    def set_attack(self, enemy_obj):
        self.attack_target = enemy_obj
        self.move_target = None

    def update(self, dt, bullets, enemy_structures):
        if not self.alive:
            return False

        thrusting = False

        # validate attack target
        if self.attack_target is not None and (not self.attack_target.alive):
            self.attack_target = None

        # decide what to do
        target_pos = None
        do_attack = False

        if self.attack_target is not None:
            target_pos = self.attack_target.pos
            do_attack = True
        elif self.move_target is not None:
            target_pos = self.move_target
        else:
            target_pos = None

        # movement toward target_pos (if any)
        if target_pos is not None:
            to_t = target_pos - self.pos
            dist = to_t.length()

            # for attack: stop within range
            stop_dist = self.arrive_dist
            if do_attack:
                stop_dist = min(self.attack_range * 0.85, self.attack_range - 40)

            if dist <= stop_dist:
                if not do_attack:
                    self.move_target = None
                    self.vel.update(0, 0)
            else:
                desired = to_t.normalize()
                desired_angle = math.atan2(desired.x, -desired.y)
                da = (desired_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
                self.angle += max(-self.turn_rate, min(self.turn_rate, da))

                forward = pygame.Vector2(math.sin(self.angle), -math.cos(self.angle))
                self.vel += forward * self.accel
                thrusting = True

        # fire if attacking and in range
        if self.fire_cd > 0:
            self.fire_cd -= dt

        if do_attack and self.attack_target is not None and self.attack_target.alive:
            dist = self.pos.distance_to(self.attack_target.pos)
            if dist <= self.attack_range and self.fire_cd <= 0:
                dirv = (self.attack_target.pos - self.pos)
                if dirv.length() > 0:
                    dirv = dirv.normalize()
                else:
                    dirv = pygame.Vector2(1, 0)

                # spawn bullet from ship "nose"
                muzzle = self.pos + dirv * 18
                vel = dirv * self.bullet_speed
                bullets.append(Bullet(muzzle, vel, self.bullet_dmg, team="player"))
                self.fire_cd = 1.0 / self.fire_rate

        # physics
        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)
        self.vel *= self.drag
        new_pos = self.pos + self.vel

        # bounds + asteroid collision
        new_pos.x = max(0, min(MAP_W, new_pos.x))
        new_pos.y = max(0, min(MAP_H, new_pos.y))
        ship_radius = 18 * self.scale
        new_pos, hit = resolve_circle_vs_asteroids(new_pos, ship_radius)
        if hit:
            self.vel.update(0, 0)

        self.pos = new_pos
        return thrusting

    def draw(self, surf, thrusting=False):
        sp = world_to_screen(self.pos)
        draw_ship(surf, (sp.x, sp.y), self.angle, thrust=thrusting, scale=self.scale)

        # health bar only when selected (per your request)
        if self.selected:
            draw_health_bar(surf, sp + pygame.Vector2(0, -20), 54, 0, self.hp, self.hp_max)


class Station(GameObject):
    def __init__(self, x, y):
        super().__init__(x, y, hp_max=800)
        self.vel = pygame.Vector2(0, 0)
        self.selected = False
        self.target = None

        self.max_speed = 1.2
        self.accel = 0.08
        self.drag = 0.92
        self.arrive_dist = 12.0
        self.pick_radius = 95

    def contains_point_world(self, p):
        return self.pos.distance_to(p) <= self.pick_radius

    def set_move(self, p):
        self.target = pygame.Vector2(p)

    def update(self, dt):
        if not self.alive:
            return False

        moving = False
        if self.target is not None:
            to_t = self.target - self.pos
            dist = to_t.length()
            if dist <= self.arrive_dist:
                self.target = None
                self.vel.update(0, 0)
            else:
                self.vel += to_t.normalize() * self.accel
                moving = True

        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)
        self.vel *= self.drag

        new_pos = self.pos + self.vel
        new_pos.x = max(0, min(MAP_W, new_pos.x))
        new_pos.y = max(0, min(MAP_H, new_pos.y))

        new_pos, hit = resolve_circle_vs_asteroids(new_pos, 95)
        if hit:
            self.vel.update(0, 0)

        self.pos = new_pos
        return moving

    def draw(self, surf):
        sp = world_to_screen(self.pos)
        draw_station(surf, sp)
        if self.selected:
            draw_health_bar(surf, sp + pygame.Vector2(0, -95), 120, 0, self.hp, self.hp_max)


class EnemyBase(GameObject):
    def __init__(self, x, y):
        super().__init__(x, y, hp_max=900)
        self.pick_radius = 100

    def contains_point_world(self, p):
        return self.pos.distance_to(p) <= self.pick_radius

    def draw(self, surf):
        sp = world_to_screen(self.pos)
        draw_enemy_base(surf, sp)
        # (enemy health not shown unless you want it)

# ============================================================
# Spawn player base centered on screen at start
# ============================================================
base = Station(MAP_W * 0.30, MAP_H * 0.40)  # tweak spawn spot
camera.x = base.pos.x - W / 2
camera.y = base.pos.y - H / 2
clamp_camera()

# spawn ships around base
ships = []
ring_r = 240
ship_count = 18
for i in range(ship_count):
    ang = (i / ship_count) * 2 * math.pi
    sx = base.pos.x + math.cos(ang) * ring_r
    sy = base.pos.y + math.sin(ang) * ring_r
    ships.append(Ship(sx, sy))

# ============================================================
# Spawn enemy base (static)
# ============================================================
enemy_base = EnemyBase(MAP_W * 0.78, MAP_H * 0.70)
enemy_structures = [enemy_base]

# ============================================================
# Selection / Commands
# ============================================================
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
    return [s for s in ships if s.selected and s.alive]

def issue_move_command(world_mouse):
    # base move (slow) if selected
    if base.selected and base.alive:
        base.set_move(world_mouse)

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
        s.set_move(origin + pygame.Vector2(ox, oy))

def issue_attack_command(enemy_obj):
    sel = selected_ships()
    for s in sel:
        s.set_attack(enemy_obj)

def enemy_at_world_point(p_world):
    # pick closest enemy structure under cursor
    for e in enemy_structures:
        if e.alive and e.contains_point_world(p_world):
            return e
    return None


# ============================================================
# Camera edge scroll
# ============================================================
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
        clamp_camera()


# ============================================================
# Bullets + hit detection
# ============================================================
bullets = []

def update_bullets(dt):
    global bullets
    new_bullets = []
    for b in bullets:
        b.update(dt)
        if b.life <= 0:
            continue

        # collision: player bullets hit enemy structures
        if b.team == "player":
            hit = False
            for e in enemy_structures:
                if e.alive and b.pos.distance_to(e.pos) <= e.pick_radius:
                    e.take_damage(b.dmg)
                    hit = True
                    break
            if hit:
                continue

        new_bullets.append(b)

    bullets = new_bullets


# ============================================================
# Main loop
# ============================================================
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

        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False

        # Right click: deselect
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            selecting = False
            clear_selection()

        # Left down: select unit OR start box select
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            clicked_unit = False

            # select base first
            if base.alive and base.contains_point_world(mouse_world):
                if not (mods & pygame.KMOD_SHIFT):
                    clear_selection()
                base.selected = True
                selecting = False
                clicked_unit = True
            else:
                # select ships
                clicked_ship = None
                for s in reversed(ships):
                    if s.alive and s.contains_point_world(mouse_world):
                        clicked_ship = s
                        break

                if clicked_ship is not None:
                    if not (mods & pygame.KMOD_SHIFT):
                        clear_selection()
                    clicked_ship.selected = True
                    selecting = False
                    clicked_unit = True

            if not clicked_unit:
                selecting = True
                sel_start_screen = mouse_screen
                sel_end_screen = mouse_screen

        if e.type == pygame.MOUSEMOTION and selecting:
            sel_end_screen = mouse_screen

        # Left up: click -> attack if enemy under cursor, else move. Drag -> box select.
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if selecting:
                box = rect_from_points(sel_start_screen, sel_end_screen)
                selecting = False

                if box.width < 6 and box.height < 6:
                    # click command:
                    enemy = enemy_at_world_point(mouse_world)
                    if enemy is not None:
                        issue_attack_command(enemy)
                    else:
                        issue_move_command(mouse_world)
                else:
                    # box selection replaces selection unless shift held
                    if not (mods & pygame.KMOD_SHIFT):
                        clear_selection()

                    # base in box?
                    bp = world_to_screen(base.pos)
                    if base.alive and box.collidepoint(bp.x, bp.y):
                        base.selected = True

                    for s in ships:
                        if not s.alive:
                            continue
                        sp = world_to_screen(s.pos)
                        if box.collidepoint(sp.x, sp.y):
                            s.selected = True

    # ------------------------------------------------------------
    # Update
    # ------------------------------------------------------------
    base.update(dt)

    thrusting_states = []
    for s in ships:
        thrusting_states.append(s.update(dt, bullets, enemy_structures))

    update_bullets(dt)

    # remove dead ships if you want (optional). I keep them but skip draw/select.

    # ------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------
    screen.fill((8, 10, 18))

    # stars (culled)
    cx, cy = camera.x, camera.y
    for x, y, r in stars:
        sx = x - cx
        sy = y - cy
        if -2 <= sx <= W + 2 and -2 <= sy <= H + 2:
            pygame.draw.circle(screen, (220, 220, 220), (int(sx), int(sy)), r)

    # asteroids (textured, culled)
    for center, radius, tex in asteroids:
        sc = world_to_screen(center)
        if -radius <= sc.x <= W + radius and -radius <= sc.y <= H + radius:
            rect = tex.get_rect(center=(int(sc.x), int(sc.y)))
            screen.blit(tex, rect)

    # enemy structures
    for eobj in enemy_structures:
        if eobj.alive:
            eobj.draw(screen)

    # player base + ships
    if base.alive:
        base.draw(screen)

    for s, thr in zip(ships, thrusting_states):
        if s.alive:
            s.draw(screen, thrusting=thr)

    # bullets
    for b in bullets:
        b.draw(screen)

    # selection rectangle
    if selecting:
        box = rect_from_points(sel_start_screen, sel_end_screen)
        pygame.draw.rect(screen, (0, 200, 255), box, 2)

    # minimap (top-right)
    draw_minimap(screen, stars, asteroids, base, [s for s in ships if s.alive], [e for e in enemy_structures if e.alive])

    pygame.display.flip()

pygame.quit()
