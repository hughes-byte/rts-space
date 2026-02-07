import math
import pygame

pygame.init()
W, H = 1400, 880
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()

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

def draw_ship(surface, pos, angle, thrust=False, scale=0.6):
    # Ship in local coordinates (pointing "up" = negative y)
    hull = [
        (0, -20),   # nose
        (-14, 16),  # left wing
        (-6, 10),   # left inner
        (0, 16),    # tail center
        (6, 10),    # right inner
        (14, 16),   # right wing
    ]

    cockpit = [
        (0, -10),
        (-4, 2),
        (4, 2),
    ]

    # Flame (only if thrusting)
    flame = [
        (0, 24),
        (-5, 14),
        (0, 16),
        (5, 14),
    ]

    hull_w = transform_points(hull, pos, angle, scale)
    cockpit_w = transform_points(cockpit, pos, angle, scale)

    pygame.draw.polygon(surface, (220, 220, 220), hull_w)      # body
    pygame.draw.polygon(surface, (40, 40, 40), hull_w, 2)      # outline
    pygame.draw.polygon(surface, (80, 180, 255), cockpit_w)    # cockpit
    pygame.draw.polygon(surface, (20, 20, 20), cockpit_w, 1)

    if thrust:
        flame_w = transform_points(flame, pos, angle)
        pygame.draw.polygon(surface, (255, 160, 40), flame_w)
        pygame.draw.polygon(surface, (255, 240, 120), flame_w, 1)

# --- Demo loop ---
pos = [W / 2, H / 2]
vel = [0.0, 0.0]
angle = 0.0
turn_speed = 0.06
accel = 0.18
drag = 0.99

running = True
while running:
    dt = clock.tick(60) / 1000.0

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        angle -= turn_speed
    if keys[pygame.K_RIGHT]:
        angle += turn_speed

    thrusting = keys[pygame.K_UP]
    if thrusting:
        # forward direction (ship points up in local coords)
        vel[0] += math.sin(angle) * accel
        vel[1] += -math.cos(angle) * accel

    # apply drag and move
    vel[0] *= drag
    vel[1] *= drag
    pos[0] = (pos[0] + vel[0]) % W
    pos[1] = (pos[1] + vel[1]) % H

    screen.fill((8, 10, 18))
    draw_ship(screen, pos, angle, thrust=thrusting)

    pygame.display.flip()

pygame.quit()
