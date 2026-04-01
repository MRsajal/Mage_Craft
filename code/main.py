import pygame
import sys
import os
try:
    from .data import COLLISION as collision, EVENTS as events
    from .fire_world import load_fire_map, is_walkable, spawn_emberstones, find_spawn_tile, FIRE_TILE_SIZE, FIRE_MAP_COLS, FIRE_MAP_ROWS
except ImportError:
    from data import COLLISION as collision, EVENTS as events
    from fire_world import load_fire_map, is_walkable, spawn_emberstones, find_spawn_tile, FIRE_TILE_SIZE, FIRE_MAP_COLS, FIRE_MAP_ROWS

pygame.init()
ZOOM = 1.5
TILE_SIZE = int(16 * ZOOM)
MAP_COLS = 30
MAP_ROWS = 15

# --- UI PANEL ---
# Remove extra UI panel width and keep window size equal to the map
PANEL_WIDTH = 0
SCREEN_WIDTH = MAP_COLS * TILE_SIZE
SCREEN_HEIGHT = MAP_ROWS * TILE_SIZE
WINDOW_WIDTH = SCREEN_WIDTH
WINDOW_HEIGHT = SCREEN_HEIGHT

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Mage Game")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# Load and scale maps
map_img_src = pygame.image.load(os.path.join("images", "Mage.png")).convert()
map_img = pygame.transform.scale(map_img_src, (SCREEN_WIDTH, SCREEN_HEIGHT))

fire_map_img = load_fire_map(SCREEN_WIDTH, SCREEN_HEIGHT)

current_world = "main"  # "main" | "fire"

# --- world travel popup ---
travel_overlay_open = False
travel_go_rect = pygame.Rect(0, 0, 220, 44)
travel_back_rect = pygame.Rect(0, 0, 220, 44)

# Sleep (day) overlay state
sleep_overlay_open = False
sleep_go_rect = pygame.Rect(0, 0, 220, 44)
sleep_back_rect = pygame.Rect(0, 0, 220, 44)

# Track days spent (increment when player sleeps)
days_spent = 1

def player_event_tile(player_rect):
    """Return the event value under the player's feet (center-bottom)."""
    px = player_rect.centerx
    py = player_rect.bottom - 1
    tx = int(px // TILE_SIZE)
    ty = int(py // TILE_SIZE)
    if 0 <= tx < MAP_COLS and 0 <= ty < MAP_ROWS:
        return events[ty][tx]
    return -1


def draw_travel_popup(surface):
    """Draw the travel popup modal."""
    global travel_go_rect, travel_back_rect

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 180))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(80, 70, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 140)
    pygame.draw.rect(surface, (25, 25, 35), panel, border_radius=10)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2, border_radius=10)

    title = "TRAVEL"
    surface.blit(font.render(title, True, (255, 255, 255)), (panel.x + 20, panel.y + 20))

    msg = "Go to Fire World?" if current_world == "main" else "Return to Main World?"
    surface.blit(font.render(msg, True, (220, 220, 230)), (panel.x + 20, panel.y + 60))

    # buttons
    mouse_pos = pygame.mouse.get_pos()
    travel_go_rect = pygame.Rect(panel.x + 20, panel.y + 110, 260, 44)
    travel_back_rect = pygame.Rect(panel.x + 20, panel.y + 170, 260, 44)

    def draw_btn(r, text):
        hovered = r.collidepoint(mouse_pos)
        bg = (90, 90, 110) if hovered else (70, 70, 80)
        pygame.draw.rect(surface, bg, r, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), r, 2, border_radius=8)
        surface.blit(font.render(text, True, (255, 255, 255)), (r.x + 14, r.y + 12))

    draw_btn(travel_go_rect, "Go" if current_world == "main" else "Return")
    draw_btn(travel_back_rect, "Cancel")


def draw_sleep_popup(surface):
    """Draw the sleep popup modal offering to start a new day."""
    global sleep_go_rect, sleep_back_rect

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 180))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(80, 70, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 140)
    pygame.draw.rect(surface, (20, 20, 30), panel, border_radius=10)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2, border_radius=10)

    surface.blit(font.render("REST", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
    surface.blit(font.render("Sleep and start a new day?", True, (220, 220, 230)), (panel.x + 20, panel.y + 60))

    mouse_pos = pygame.mouse.get_pos()
    sleep_go_rect = pygame.Rect(panel.x + 20, panel.y + 110, 260, 44)
    sleep_back_rect = pygame.Rect(panel.x + 20, panel.y + 170, 260, 44)

    def draw_btn(r, text):
        hovered = r.collidepoint(mouse_pos)
        bg = (90, 90, 110) if hovered else (70, 70, 80)
        pygame.draw.rect(surface, bg, r, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), r, 2, border_radius=8)
        surface.blit(font.render(text, True, (255, 255, 255)), (r.x + 14, r.y + 12))

    draw_btn(sleep_go_rect, "Sleep")
    draw_btn(sleep_back_rect, "Cancel")

# --- Simple UI state / economy ---
inventory = {"mat_emberstone": 2}
spells = {"fire_spell": 0}
coins = 0
xp = 0
level = 1
# emberstone items in the fire world (list of pygame.Rect)
emberstone_items = []
# XP_PER_LEVEL no longer used for leveling; keep for display fallback if needed
XP_PER_LEVEL = 5
level_xp = [10, 25, 50, 100, 150, 250, 500, 750, 9999]


def update_level_from_xp():
    """Update `level` from total `xp` using thresholds in level_xp.

    level 1: xp < level_xp[0]
    level 2: xp >= level_xp[0]
    level 3: xp >= level_xp[1]
    ...
    """
    global level
    lvl = 1
    for threshold in level_xp:
        if xp >= threshold:
            lvl += 1
        else:
            break
    level = lvl

# UI overlay state
active_overlay = None  # None | "status" | "magic"

# Log messages
log = [
    "> Welcome, Mage. Your sanctum awaits.",
]

# helper to push log entries
def push_log(line):
    log.insert(0, f"> {line}")
    if len(log) > 12:
        log.pop()

# Assets for magic screen
FIREBALL_IMG_PATH = "spell_fireball.png"
EMBERSTONE_IMG_PATH = "mat_emberstone.png"

try:
    fireball_img = pygame.image.load(os.path.join("images", FIREBALL_IMG_PATH)).convert_alpha()
except Exception:
    fireball_img = None

try:
    emberstone_img = pygame.image.load(os.path.join("images", EMBERSTONE_IMG_PATH)).convert_alpha()
except Exception:
    emberstone_img = None

# Back button rect used by overlays
back_button_rect = pygame.Rect(10, 10, 90, 32)

def draw_back_button(surface, mouse_pos):
    hovered = back_button_rect.collidepoint(mouse_pos)
    bg = (90, 90, 110) if hovered else (70, 70, 80)
    pygame.draw.rect(surface, bg, back_button_rect, border_radius=6)
    pygame.draw.rect(surface, (180, 180, 200), back_button_rect, 2, border_radius=6)
    label = font.render("Back", True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=back_button_rect.center))

# Fire-world return button (visible in fire world)
fire_return_rect = pygame.Rect(10, 10, 110, 32)

def draw_fire_return_button(surface):
    hovered = fire_return_rect.collidepoint(pygame.mouse.get_pos())
    bg = (120, 60, 40) if hovered else (90, 50, 30)
    pygame.draw.rect(surface, bg, fire_return_rect, border_radius=6)
    pygame.draw.rect(surface, (200, 160, 120), fire_return_rect, 2, border_radius=6)
    label = font.render("Return", True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=fire_return_rect.center))

# Magic craft button rect
magic_craft_rect = pygame.Rect(220, 140, 220, 52)

def draw_overlay(surface):
    """Draw the active overlay (status or magic)."""
    global active_overlay

    if active_overlay is None:
        return

    # ensure level is up-to-date whenever we open overlays
    update_level_from_xp()

    mouse_pos = pygame.mouse.get_pos()

    # dim background
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 180))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(60, 50, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 100)
    pygame.draw.rect(surface, (25, 25, 35), panel, border_radius=10)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2, border_radius=10)

    draw_back_button(surface, mouse_pos)

    if active_overlay == "status":
        surface.blit(font.render("STATUS", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))

        # next level threshold for display
        next_threshold = None
        # level 1 -> use level_xp[0] as next
        idx = max(0, level - 1)
        if idx < len(level_xp):
            next_threshold = level_xp[idx]

        xp_line = f"XP: {xp}" if next_threshold is None else f"XP: {xp}/{next_threshold}"

        lines = [
            f"Coins: {coins}",
            f"Level: {level}",
            xp_line,
            "",
            f"Days: {days_spent}",
            f"Fire spells: {spells.get('fire_spell', 0)}",
        ]
        y = panel.y + 60
        for line in lines:
            if line == "":
                y += 10
                continue
            surface.blit(font.render(line, True, (220, 220, 230)), (panel.x + 20, y))
            y += 26

        hint = "Press M for Magic crafting"
        surface.blit(font.render(hint, True, (170, 170, 190)), (panel.x + 20, panel.bottom - 40))

    elif active_overlay == "magic":
        surface.blit(font.render("MAGIC", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))

        # spell icon
        icon_rect = pygame.Rect(panel.x + 20, panel.y + 70, 96, 96)
        pygame.draw.rect(surface, (45, 45, 55), icon_rect)
        pygame.draw.rect(surface, (120, 120, 140), icon_rect, 2)
        if fireball_img is not None:
            img = pygame.transform.smoothscale(fireball_img, (92, 92))
            surface.blit(img, (icon_rect.x + 2, icon_rect.y + 2))
        else:
            surface.blit(font.render("Fire", True, (255, 120, 80)), (icon_rect.x + 20, icon_rect.y + 38))

        # craft button
        btn = magic_craft_rect.move(panel.x - 60, panel.y - 50)  # because panel is inset
        hovered = btn.collidepoint(mouse_pos)
        bg = (90, 90, 110) if hovered else (70, 70, 80)
        pygame.draw.rect(surface, bg, btn, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), btn, 2, border_radius=8)
        surface.blit(font.render("Craft", True, (255, 255, 255)), (btn.x + 14, btn.y + 8))
        surface.blit(font.render("Fireball", True, (200, 200, 210)), (btn.x + 14, btn.y + 28))

        # materials display (with emberstone icon)
        mat_have = inventory.get("mat_emberstone", 0)
        mat_need = 2
        mat_line_y = panel.y + 190
        if emberstone_img is not None:
            eimg = pygame.transform.smoothscale(emberstone_img, (24, 24))
            surface.blit(eimg, (panel.x + 20, mat_line_y))
            surface.blit(
                font.render(f"emberstone: {mat_have}/{mat_need}", True, (220, 220, 230)),
                (panel.x + 50, mat_line_y + 2),
            )
        else:
            surface.blit(
                font.render(f"emberstone: {mat_have}/{mat_need}", True, (220, 220, 230)),
                (panel.x + 20, mat_line_y),
            )

# Debug: precompute rects for collision tiles (value 38)
COLLISION_TILE_VALUE = 38
collision_debug_rects = []
for ty in range(MAP_ROWS):
    for tx in range(MAP_COLS):
        if collision[ty][tx] == COLLISION_TILE_VALUE:
            collision_debug_rects.append(
                pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            )

# Quick lookup for solid tiles during collision checks
solid_tile_rects = collision_debug_rects

# Precompute fire-world ground rects using fire world tile size
fire_walk_rects = []
for ty in range(FIRE_MAP_ROWS):
    for tx in range(FIRE_MAP_COLS):
        if is_walkable(tx, ty):
            fire_walk_rects.append(pygame.Rect(tx * FIRE_TILE_SIZE, ty * FIRE_TILE_SIZE, FIRE_TILE_SIZE, FIRE_TILE_SIZE))

# -------------------
# CREATE PLAYER
# -------------------
player = None  # player object is now in code.player

# -------------------
# GAME LOOP
# -------------------
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if travel_overlay_open:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    travel_overlay_open = False
            else:
                if event.key == pygame.K_j:
                    update_level_from_xp()
                    active_overlay = "status" if active_overlay != "status" else None
                elif event.key == pygame.K_m:
                    update_level_from_xp()
                    active_overlay = "magic" if active_overlay != "magic" else None
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # Open travel popup only if standing on event tile 76
                    if active_overlay is None:
                        ev = player_event_tile(player.rect)
                        if ev == 76:
                            travel_overlay_open = True
                        elif ev == 20:
                            # offer sleep option
                            sleep_overlay_open = True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if travel_overlay_open:
                if travel_go_rect.collidepoint(event.pos):
                    # toggle world
                    current_world = "fire" if current_world == "main" else "main"
                    # spawn emberstones when entering the fire world; clear when leaving
                    if current_world == "fire":
                        # treat fire world as a separate grid: spawn emberstones using fire grid
                        emberstone_items = spawn_emberstones(FIRE_MAP_COLS, FIRE_MAP_ROWS, FIRE_TILE_SIZE, count=6)
                        # spawn player at fixed location (50,50) in pixels within fire world
                        player.rect.x = 50
                        player.rect.y = 50
                        player.x, player.y = player.rect.topleft
                    else:
                        emberstone_items = []
                        # when returning to main world, reset player to the main-world start location
                        player.rect.x = 150
                        player.rect.y = 150
                        player.x, player.y = player.rect.topleft
                    travel_overlay_open = False
                elif travel_back_rect.collidepoint(event.pos):
                    travel_overlay_open = False
            elif sleep_overlay_open:
                if sleep_go_rect.collidepoint(event.pos):
                    # perform sleep: increment days and close overlay
                    days_spent += 1
                    push_log(f"You slept. Day {days_spent} begins.")
                    sleep_overlay_open = False
                elif sleep_back_rect.collidepoint(event.pos):
                    sleep_overlay_open = False
            elif active_overlay is not None:
                pos = event.pos
                # back
                if back_button_rect.collidepoint(pos):
                    active_overlay = None
                elif active_overlay == "magic":
                    panel = pygame.Rect(60, 50, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 100)
                    btn = magic_craft_rect.move(panel.x - 60, panel.y - 50)
                    if btn.collidepoint(pos):
                        # craft requires 2 emberstone
                        if inventory.get("mat_emberstone", 0) >= 2:
                            inventory["mat_emberstone"] -= 2
                            spells["fire_spell"] = spells.get("fire_spell", 0) + 1
                            push_log("Crafted Fireball spell.")
            else:
                # general clicks when no overlay is open
                if current_world == "fire" and fire_return_rect.collidepoint(event.pos):
                    current_world = "main"
                    emberstone_items = []
                    # reset player to main-world location on return
                    player.rect.x = 150
                    player.rect.y = 150
                    player.x, player.y = player.rect.topleft
                    push_log("Returned to Main World.")

    keys = pygame.key.get_pressed()

    # Move player (disable movement when overlay is open)
    if active_overlay is None and not travel_overlay_open:
        player.move(keys)

    # Keep level synced even if xp changes later
    update_level_from_xp()

    # If in fire world, check for emberstone collection
    if current_world == "fire":
        for it in emberstone_items[:]:
            if player.rect.colliderect(it):
                emberstone_items.remove(it)
                inventory["mat_emberstone"] = inventory.get("mat_emberstone", 0) + 1
                push_log("Picked up emberstone.")

        # gravity/fall in fire world uses FIRE_TILE_SIZE grid. check tile under player's feet in fire grid
        below_px = player.rect.centerx
        below_py = player.rect.bottom - 1
        below_tx = int(below_px // FIRE_TILE_SIZE)
        below_ty = int(below_py // FIRE_TILE_SIZE)
        if 0 <= below_tx < FIRE_MAP_COLS and 0 <= below_ty < FIRE_MAP_ROWS:
            if not is_walkable(below_tx, below_ty):
                player.rect.y += 1
                player.x, player.y = player.rect.topleft
                # prevent falling past scaled map bottom
                if player.rect.bottom > fire_map_img.get_height():
                    player.rect.bottom = fire_map_img.get_height()
                    player.x, player.y = player.rect.topleft
        else:
            if player.rect.bottom < fire_map_img.get_height():
                player.rect.y += 1
                player.x, player.y = player.rect.topleft

    # Draw
    screen.fill((0, 0, 0))
    # draw current world map
    screen.blit(fire_map_img if current_world == "fire" else map_img, (0, 0))
    player.draw(screen)

    # draw fire-world return button
    if current_world == "fire":
        draw_fire_return_button(screen)

    # Overlays
    draw_overlay(screen)
    if travel_overlay_open:
        draw_travel_popup(screen)
    if sleep_overlay_open:
        draw_sleep_popup(screen)

    # draw emberstone items in fire world
    if current_world == "fire":
        for it in emberstone_items:
            if emberstone_img is not None:
                # scale emberstone image larger for visibility
                img = pygame.transform.smoothscale(emberstone_img, (it.width, it.height))
                screen.blit(img, it.topleft)
            else:
                pygame.draw.ellipse(screen, (255, 180, 60), it)

    pygame.display.update()
    clock.tick(60)