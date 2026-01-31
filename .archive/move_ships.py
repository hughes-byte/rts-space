import math
import pygame

pygame.init()
W, H = 1400, 880
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()

# ---------- drawing helpers ----------
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

def draw_ship(surface, pos, angle, thrust=False, scale=0.6, selected=False):
    hull = [(0, -20), (-14, 16), (-6, 10), (0, 16), (6, 10), (14, 16)]
    cockpit = [(0, -10), (-4, 2), (4, 2)]
    flame = [(0, 24), (-5, 14), (0, 16), (5, 14)]

    hull_w = transform_points(hull, pos, angle, scale)
    cockpit_w = transform_points(cockpit, pos, angle, scale)

    pygame.draw.polygon(surface, (220, 220, 220), hull_w)
    pygame.draw.polygon(surface, (40, 40, 40), hull_w, 2)
    pygame.draw.polygon(surface, (80, 180, 255), cockpit_w)
    pygame.draw.polygon(surface, (20, 20, 20), cockpit_w, 1)

    if thrust:
        flame_w = transform_points(flame, pos, angle, scale)
        pygame.draw.polygon(surface, (255, 160, 40), flame_w)
        pygame.draw.polygon(surface, (255, 240, 120), flame_w, 1)

    if selected:
        pygame.draw.circle(surface, (0, 255, 120), (int(pos[0]), int(pos[1])), int(26 * scale), 2)

# ---------- game objects ----------
class Ship:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(0, 0)
        self.angle = 0.0
        self.scale = 0.45
        self.selected = False
        self.target = None  # pygame.Vector2 or None

        # movement tuning (more RTS-like than "space drift")
        self.max_speed = 5.0
        self.accel = 0.35
        self.drag = 0.90
        self.arrive_dist = 8.0
        self.turn_rate = 0.10

        # click detection
        self.pick_radius = 18 * self.scale

    def contains_point(self, p):
        return self.pos.distance_to(p) <= self.pick_radius

    def update(self):
        thrusting = False

        if self.target is not None:
            to_target = self.target - self.pos
            dist = to_target.length()

            if dist <= self.arrive_dist:
                self.target = None
                self.vel.update(0, 0)  # stop dead (RTS feel)
            else:
                desired = to_target.normalize()

                # rotate smoothly toward desired direction
                desired_angle = math.atan2(desired.x, -desired.y)
                da = (desired_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
                self.angle += max(-self.turn_rate, min(self.turn_rate, da))

                # accelerate forward along current facing
                forward = pygame.Vector2(math.sin(self.angle), -math.cos(self.angle))
                self.vel += forward * self.accel
                thrusting = True

        # cap speed + drag
        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)
        self.vel *= self.drag

        self.pos += self.vel

        # stay on screen (no wrap; RTS feel)
        self.pos.x = max(0, min(W, self.pos.x))
        self.pos.y = max(0, min(H, self.pos.y))

        return thrusting

    def draw(self, surface, thrusting=False):
        draw_ship(surface, (self.pos.x, self.pos.y), self.angle,
                  thrust=thrusting, scale=self.scale, selected=self.selected)

# ---------- spawn a bunch ----------
ships = []
cols, rows = 6, 3
start_x, start_y = 300, 250
spacing = 60
for r in range(rows):
    for c in range(cols):
        ships.append(Ship(start_x + c * spacing, start_y + r * spacing))

# ---------- selection / input state ----------
selecting = False
sel_start = pygame.Vector2(0, 0)
sel_end = pygame.Vector2(0, 0)

def rect_from_points(a, b):
    x1, y1 = min(a.x, b.x), min(a.y, b.y)
    x2, y2 = max(a.x, b.x), max(a.y, b.y)
    return pygame.Rect(x1, y1, x2 - x1, y2 - y1)

running = True
while running:
    clock.tick(60)
    mouse = pygame.Vector2(pygame.mouse.get_pos())
    mods = pygame.key.get_mods()

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        # --- Left mouse: select / box select ---
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            clicked = None
            for s in reversed(ships):
                if s.contains_point(mouse):
                    clicked = s
                    break

            if clicked is not None:
                # single click select (shift = additive)
                if not (mods & pygame.KMOD_SHIFT):
                    for s in ships:
                        s.selected = False
                clicked.selected = True
                selecting = False
            else:
                # start box selection
                selecting = True
                sel_start = mouse
                sel_end = mouse
                if not (mods & pygame.KMOD_SHIFT):
                    for s in ships:
                        s.selected = False

        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if selecting:
                selecting = False
                box = rect_from_points(sel_start, sel_end)
                for s in ships:
                    if box.collidepoint(s.pos.x, s.pos.y):
                        s.selected = True

        if e.type == pygame.MOUSEMOTION:
            if selecting:
                sel_end = mouse

        # --- Right mouse: move command (RA2 style) ---
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            selected = [s for s in ships if s.selected]
            if selected:
                # simple formation so they don't stack
                n = len(selected)
                side = math.ceil(math.sqrt(n))
                gap = 34

                origin = pygame.Vector2(
                    mouse.x - (side - 1) * gap / 2,
                    mouse.y - (side - 1) * gap / 2
                )

                for i, s in enumerate(selected):
                    ox = (i % side) * gap
                    oy = (i // side) * gap
                    s.target = origin + pygame.Vector2(ox, oy)

    # update + draw
    screen.fill((8, 10, 18))
    for s in ships:
        thrusting = s.update()
        s.draw(screen, thrusting=thrusting)

    if selecting:
        box = rect_from_points(sel_start, sel_end)
        pygame.draw.rect(screen, (0, 200, 255), box, 2)

    pygame.display.flip()

pygame.quit()
