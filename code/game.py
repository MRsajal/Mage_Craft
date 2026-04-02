import pygame
import sys
import os
import random
from collections import Counter
try:
    from .data import COLLISION as collision, EVENTS as events
    from .slime_world import load_slime_map, is_slime_blocked
    from .slime_world_collision import slime_world_collision
    from .fire_world import (
        load_fire_map,
        is_walkable,
        spawn_emberstones,
        find_spawn_tile,
        FIRE_TILE_SIZE,
        FIRE_MAP_COLS,
        FIRE_MAP_ROWS,
    )
    from .player import Player
except ImportError:
    # Allow running this file directly (python code/game.py)
    from data import COLLISION as collision, EVENTS as events
    from slime_world import load_slime_map, is_slime_blocked
    from slime_world_collision import slime_world_collision
    from fire_world import (
        load_fire_map,
        is_walkable,
        spawn_emberstones,
        find_spawn_tile,
        FIRE_TILE_SIZE,
        FIRE_MAP_COLS,
        FIRE_MAP_ROWS,
    )
    from player import Player

pygame.init()
ZOOM = 1.5
TILE_SIZE = int(16 * ZOOM)
MAP_COLS = 30
MAP_ROWS = 15

SCREEN_WIDTH = MAP_COLS * TILE_SIZE
SCREEN_HEIGHT = MAP_ROWS * TILE_SIZE

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Mage Game")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

# Load and scale maps
map_img_src = pygame.image.load(os.path.join("images", "Mage.png")).convert()
map_img = pygame.transform.scale(map_img_src, (SCREEN_WIDTH, SCREEN_HEIGHT))
slime_map_img = load_slime_map(SCREEN_WIDTH, SCREEN_HEIGHT)
fire_map_img = load_fire_map(SCREEN_WIDTH, SCREEN_HEIGHT)


def load_scaled_frames(folder, frame_count, size):
    frames = []
    for index in range(frame_count):
        path = os.path.join(folder, f"{index}.png")
        if not os.path.exists(path):
            break
        image = pygame.image.load(path).convert_alpha()
        frames.append(pygame.transform.smoothscale(image, size))
    return frames


fire_spell_frames = load_scaled_frames(os.path.join("images", "fire"), 4, (28, 28))
slime_right_frames = load_scaled_frames(os.path.join("Slime", "walk", "right"), 6, (30, 30))
slime_left_frames = load_scaled_frames(os.path.join("Slime", "walk", "left"), 6, (30, 30))

# --- UI panel / state defaults ---
PANEL_WIDTH = 0
current_world = "main"  # "main" | "fire" | "slime"
slime_world_unlocked = False

# overlay / popup flags
travel_overlay_open = False
sleep_overlay_open = False
travel_cancel_rect = pygame.Rect(0, 0, 220, 44)

# Track days spent (increment when player sleeps)
days_spent = 1

SPELL_DURATION_MS = 60_000
FIRE_PROJECTILE_DURATION_MS = 850
FIRE_PROJECTILE_SPEED = 7
FIRE_PROJECTILE_SIZE = 28
SLIME_COUNT = 5
SLIME_SPEED = 1
SLIME_MAX_HP = 3
WINDCRYSTAL_DROP_SIZE = 18
PLAYER_MAX_HP = 10
PLAYER_HIT_COOLDOWN_MS = 800

# Simple UI / economy
inventory = {"mat_emberstone": 2, "mat_windcrystal": 0}
spells = ["fire_mage"]
coins = 0
xp = 0
level = 1
emberstone_items = []
windcrystal_items = []
slime_mobs = []
fire_projectiles = []
selected_spell_name = None
selected_spell_expires_at = 0
player_hp = PLAYER_MAX_HP
last_player_hit_at = 0
game_over_until_ms = 0
XP_PER_LEVEL = 5
level_xp = [10, 25, 50, 100, 150, 250, 500, 750, 9999]

# Spell progression/order system
MAGIC_SPELLS = ["Flying", "Water", "Invisibility", "Lightning Bolt", "Laser Beam"]
next_spell_unlock_index = 0
last_rewarded_level = 1
current_daily_order = None
order_completed_today = False
COIN_PER_SALE = 12
XP_PER_SALE = 6

# Spell selling UI state (track how many of each spell player wants to sell)
spell_sell_amounts = {}  # {spell_name: amount}
spell_sell_rects = {}    # {spell_name: (sell_button_rect, -_button_rect, +_button_rect)}
spell_select_rects = {}

# Random daily spell offer
random_offer_spell = None
random_offer_amount = 0
random_offer_xp = 0
random_offer_coin = 0
random_offer_btn_rect = None
daily_order_btn_rect = None

# overlays
active_overlay = None  # None | "status" | "magic" | "orders" | "spells"

# logs
log = ["> Welcome, Mage. Your sanctum awaits."]

def push_log(line):
    log.insert(0, f"> {line}")
    if len(log) > 12:
        log.pop()


def count_spell(spell_name):
    return Counter(spells).get(spell_name, 0)


def spawn_slime_mobs(count=SLIME_COUNT):
    mobs = []
    candidates = []
    for ty in range(MAP_ROWS):
        for tx in range(MAP_COLS):
            if not is_slime_blocked(tx, ty):
                candidates.append((tx, ty))

    if not candidates:
        return mobs

    sample_count = min(count, len(candidates))
    for tx, ty in random.sample(candidates, sample_count):
        slime_rect = pygame.Rect(
            tx * TILE_SIZE + random.randint(2, 8),
            ty * TILE_SIZE + random.randint(2, 8),
            24,
            18,
        )
        mobs.append({"rect": slime_rect, "flash": 0, "direction": "right", "frame_index": 0.0, "hp": SLIME_MAX_HP})
    return mobs


def enter_slime_world(player):
    global current_world, slime_mobs, emberstone_items, fire_projectiles, windcrystal_items
    current_world = "slime"
    emberstone_items = []
    fire_projectiles = []
    windcrystal_items = []
    slime_mobs = spawn_slime_mobs()
    player.rect.x = 150
    player.rect.y = 150
    player.x, player.y = player.rect.topleft


def enter_fire_world(player):
    global current_world, emberstone_items, slime_mobs, fire_projectiles, windcrystal_items
    current_world = "fire"
    slime_mobs = []
    fire_projectiles = []
    windcrystal_items = []
    emberstone_items = spawn_emberstones(FIRE_MAP_COLS, FIRE_MAP_ROWS, FIRE_TILE_SIZE, count=6)
    player.rect.x = 50
    player.rect.y = 50 + 200
    player.x, player.y = player.rect.topleft


def leave_to_main_world(player):
    global current_world, slime_mobs, fire_projectiles, windcrystal_items, player_hp, last_player_hit_at
    current_world = "main"
    slime_mobs = []
    fire_projectiles = []
    windcrystal_items = []
    player_hp = PLAYER_MAX_HP
    last_player_hit_at = 0
    player.rect.x = 150
    player.rect.y = 150
    player.x, player.y = player.rect.topleft


def activate_fire_mage_spell():
    global selected_spell_name, selected_spell_expires_at
    if count_spell("fire_mage") <= 0:
        push_log("You do not own fire_mage.")
        return False
    spells.remove("fire_mage")
    selected_spell_name = "fire_mage"
    selected_spell_expires_at = pygame.time.get_ticks() + SPELL_DURATION_MS
    push_log("Activated fire_mage for 1 minute.")
    return True


def fire_spell_ready():
    return selected_spell_name == "fire_mage" and pygame.time.get_ticks() < selected_spell_expires_at


def spawn_fire_projectile(player):
    if not fire_spell_ready():
        return

    direction = 1 if player.direction == "right" else -1
    start_x = player.rect.centerx + (18 if direction > 0 else -18)
    start_y = player.rect.centery - 8
    fire_projectiles.append(
        {
            "rect": pygame.Rect(start_x, start_y, FIRE_PROJECTILE_SIZE, FIRE_PROJECTILE_SIZE),
            "vx": direction * FIRE_PROJECTILE_SPEED,
            "spawn_time": pygame.time.get_ticks(),
            "frame_index": 0,
        }
    )


def update_fire_projectiles():
    now = pygame.time.get_ticks()
    for projectile in fire_projectiles[:]:
        projectile["rect"].x += projectile["vx"]
        projectile["frame_index"] = min(len(fire_spell_frames) - 1, (now - projectile["spawn_time"]) // 120) if fire_spell_frames else 0
        if now - projectile["spawn_time"] > FIRE_PROJECTILE_DURATION_MS:
            fire_projectiles.remove(projectile)
            continue
        if projectile["rect"].right < 0 or projectile["rect"].left > SCREEN_WIDTH:
            fire_projectiles.remove(projectile)


def draw_fire_projectiles(surface):
    for projectile in fire_projectiles:
        if fire_spell_frames:
            frame = fire_spell_frames[int(projectile["frame_index"])]
            surface.blit(frame, projectile["rect"].topleft)
        else:
            pygame.draw.circle(surface, (255, 130, 50), projectile["rect"].center, projectile["rect"].width // 2)


def move_slime_axis(slime, dx, dy):
    if dx:
        slime["rect"].x += dx

    if dy:
        slime["rect"].y += dy

    slime["rect"].clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))


def update_slime_mobs(player, now_ms, current_hp, last_hit_at):
    for slime in slime_mobs:
        if slime["flash"] > 0:
            slime["flash"] -= 1

        dx_to_player = player.rect.centerx - slime["rect"].centerx
        dy_to_player = player.rect.centery - slime["rect"].centery

        step_x = 0
        step_y = 0
        if abs(dx_to_player) > 2:
            step_x = SLIME_SPEED if dx_to_player > 0 else -SLIME_SPEED
        if abs(dy_to_player) > 2:
            step_y = SLIME_SPEED if dy_to_player > 0 else -SLIME_SPEED

        move_slime_axis(slime, step_x, 0)
        move_slime_axis(slime, 0, step_y)

        moving = step_x != 0 or step_y != 0
        if step_x > 0:
            slime["direction"] = "right"
        elif step_x < 0:
            slime["direction"] = "left"

        if moving:
            frames = slime_right_frames if slime["direction"] == "right" else slime_left_frames
            if frames:
                slime["frame_index"] = (slime["frame_index"] + 0.2) % len(frames)
        else:
            slime["frame_index"] = 0.0

    for projectile in fire_projectiles[:]:
        for slime in slime_mobs[:]:
            if projectile["rect"].colliderect(slime["rect"]):
                slime["hp"] -= 1
                slime["flash"] = 8
                if projectile in fire_projectiles:
                    fire_projectiles.remove(projectile)
                if slime["hp"] <= 0:
                    slime_mobs.remove(slime)
                    drop_rect = pygame.Rect(
                        slime["rect"].centerx - (WINDCRYSTAL_DROP_SIZE // 2),
                        slime["rect"].centery - (WINDCRYSTAL_DROP_SIZE // 2),
                        WINDCRYSTAL_DROP_SIZE,
                        WINDCRYSTAL_DROP_SIZE,
                    )
                    windcrystal_items.append(drop_rect)
                    push_log("A slime dropped windcrystal.")
                break

    if now_ms - last_hit_at >= PLAYER_HIT_COOLDOWN_MS:
        for slime in slime_mobs:
            if slime["rect"].colliderect(player.rect):
                current_hp = max(0, current_hp - 1)
                last_hit_at = now_ms
                push_log(f"Slime hit you: HP {current_hp}/{PLAYER_MAX_HP}")
                break

    return current_hp, last_hit_at


def draw_slime_mobs(surface):
    for slime in slime_mobs:
        frames = slime_right_frames if slime.get("direction") == "right" else slime_left_frames
        if frames:
            frame = frames[int(slime.get("frame_index", 0)) % len(frames)]
            sprite_rect = frame.get_rect(center=slime["rect"].center)
            surface.blit(frame, sprite_rect.topleft)
            if slime["flash"] > 0:
                flash = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
                flash.fill((255, 180, 80, 120))
                surface.blit(flash, sprite_rect.topleft)
        else:
            color = (80, 200, 110) if slime["flash"] == 0 else (255, 180, 80)
            pygame.draw.ellipse(surface, color, slime["rect"])
            eye_w = 3
            eye_h = 4
            pygame.draw.rect(surface, (20, 30, 20), pygame.Rect(slime["rect"].x + 6, slime["rect"].y + 5, eye_w, eye_h))
            pygame.draw.rect(surface, (20, 30, 20), pygame.Rect(slime["rect"].right - 9, slime["rect"].y + 5, eye_w, eye_h))

# assets for magic screen
FIREBALL_IMG_PATH = "spell_fireball.png"
EMBERSTONE_IMG_PATH = "mat_emberstone.png"
WINDCRYSTAL_IMG_PATH = "mat_windcrystal.png"
try:
    fireball_img = pygame.image.load(os.path.join("images", FIREBALL_IMG_PATH)).convert_alpha()
except Exception:
    fireball_img = None
try:
    emberstone_img = pygame.image.load(os.path.join("images", EMBERSTONE_IMG_PATH)).convert_alpha()
except Exception:
    emberstone_img = None
try:
    windcrystal_img = pygame.image.load(os.path.join("images", WINDCRYSTAL_IMG_PATH)).convert_alpha()
except Exception:
    windcrystal_img = None

# UI rects
back_button_rect = pygame.Rect(10, 10, 90, 32)
fire_return_rect = pygame.Rect(10, 10, 110, 32)
magic_fire_craft_rect = pygame.Rect(220, 140, 220, 52)
magic_flying_craft_rect = pygame.Rect(220, 210, 220, 52)

# collision helpers (debug rects)
COLLISION_TILE_VALUE = 38
collision_debug_rects = []
for ty in range(MAP_ROWS):
    for tx in range(MAP_COLS):
        if collision[ty][tx] == COLLISION_TILE_VALUE:
            collision_debug_rects.append(pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE))

# precompute fire-world walk rects (not required but kept)
fire_walk_rects = []
for ty in range(FIRE_MAP_ROWS):
    for tx in range(FIRE_MAP_COLS):
        if is_walkable(tx, ty):
            fire_walk_rects.append(pygame.Rect(tx * FIRE_TILE_SIZE, ty * FIRE_TILE_SIZE, FIRE_TILE_SIZE, FIRE_TILE_SIZE))


def update_level_from_xp():
    global level
    lvl = 1
    for threshold in level_xp:
        if xp >= threshold:
            lvl += 1
        else:
            break
    level = lvl


def grant_next_spell(reason):
    global next_spell_unlock_index
    if next_spell_unlock_index >= len(MAGIC_SPELLS):
        push_log("All magic spells unlocked.")
        return False
    spell_name = MAGIC_SPELLS[next_spell_unlock_index]
    spells.append(spell_name)
    next_spell_unlock_index += 1
    push_log(f"Learned {spell_name} ({reason}).")
    return True


def issue_daily_order():
    global current_daily_order, order_completed_today
    # Always issue exactly one order per day.
    previous_order = current_daily_order
    order_pool = list(set(spells))
    if not order_pool:
        order_pool = ["Fireball"]

    if len(order_pool) > 1 and previous_order in order_pool:
        order_pool.remove(previous_order)

    current_daily_order = random.choice(order_pool)
    order_completed_today = False
    push_log(f"Daily order: Sell 1x {current_daily_order}.")


def generate_random_spell_offer():
    """Generate a random daily spell offer with random amount, xp, and coin.
    Only offers spells that player owns in spells array."""
    global random_offer_spell, random_offer_amount, random_offer_xp, random_offer_coin
    
    # Only pick from spells the player actually owns
    if not spells:
        random_offer_spell = None
        random_offer_amount = 0
        random_offer_xp = 0
        random_offer_coin = 0
        push_log("No spells to offer today.")
        return
    
    # Get unique spells from owned array
    unique_owned_spells = list(set(spells))
    random_offer_spell = random.choice(unique_owned_spells)
    # Only one spell can be requested in the daily offer.
    random_offer_amount = 1
    random_offer_xp = random.randint(5, 20)
    random_offer_coin = random.randint(10, 25)
    push_log(f"Random offer: {random_offer_amount}x {random_offer_spell} = +{random_offer_coin} coins, +{random_offer_xp} XP.")


def sell_daily_order_spell():
    global coins, xp, order_completed_today, current_daily_order
    if current_daily_order is None:
        push_log("No active order today.")
        return
    if order_completed_today:
        push_log("Daily order already completed.")
        return
    if current_daily_order in spells:
        spells.remove(current_daily_order)
        coins += COIN_PER_SALE
        xp += XP_PER_SALE
        order_completed_today = True
        push_log(f"Sold {current_daily_order}: +{COIN_PER_SALE} coins, +{XP_PER_SALE} XP.")
    else:
        push_log(f"You do not own {current_daily_order}.")


def player_event_tile(player_rect, tile_size=TILE_SIZE, map_cols=MAP_COLS, map_rows=MAP_ROWS):
    px = player_rect.centerx
    py = player_rect.bottom - 1
    tx = int(px // tile_size)
    ty = int(py // tile_size)
    if 0 <= tx < map_cols and 0 <= ty < map_rows:
        return events[ty][tx]
    return -1


def draw_back_button(surface, mouse_pos):
    hovered = back_button_rect.collidepoint(mouse_pos)
    bg = (90, 90, 110) if hovered else (70, 70, 80)
    pygame.draw.rect(surface, bg, back_button_rect, border_radius=6)
    pygame.draw.rect(surface, (180, 180, 200), back_button_rect, 2, border_radius=6)
    label = font.render("Back", True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=back_button_rect.center))


def draw_fire_return_button(surface):
    hovered = fire_return_rect.collidepoint(pygame.mouse.get_pos())
    bg = (120, 60, 40) if hovered else (90, 50, 30)
    pygame.draw.rect(surface, bg, fire_return_rect, border_radius=6)
    pygame.draw.rect(surface, (200, 160, 120), fire_return_rect, 2, border_radius=6)
    label = font.render("Return", True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=fire_return_rect.center))


def draw_travel_popup(surface):
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 180))
    surface.blit(shade, (0, 0))
    panel = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    pygame.draw.rect(surface, (25, 25, 35), panel)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2)
    surface.blit(font.render("TRAVEL", True, (255, 255, 255)), (panel.x + 30, panel.y + 24))
    if current_world == "main":
        msg = "Choose destination"
    else:
        msg = "Return to Main World?"
    surface.blit(font.render(msg, True, (220, 220, 230)), (panel.x + 30, panel.y + 64))
    mouse_pos = pygame.mouse.get_pos()
    global travel_go_rect, travel_back_rect, travel_cancel_rect
    btn_w = min(460, SCREEN_WIDTH - 60)
    btn_x = (SCREEN_WIDTH - btn_w) // 2
    first_y = 130
    gap = 68
    travel_go_rect = pygame.Rect(btn_x, first_y, btn_w, 52)
    travel_back_rect = pygame.Rect(btn_x, first_y + gap, btn_w, 52)
    travel_cancel_rect = pygame.Rect(btn_x, first_y + (gap * 2), btn_w, 52)

    def draw_btn(r, text):
        hovered = r.collidepoint(mouse_pos)
        bg = (90, 90, 110) if hovered else (70, 70, 80)
        pygame.draw.rect(surface, bg, r, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), r, 2, border_radius=8)
        surface.blit(font.render(text, True, (255, 255, 255)), (r.x + 14, r.y + 12))

    if current_world == "main":
        draw_btn(travel_go_rect, "Fire World")
        if slime_world_unlocked:
            draw_btn(travel_back_rect, "World Of Slime")
            draw_btn(travel_cancel_rect, "Cancel")
        else:
            draw_btn(travel_back_rect, "Cancel")
    else:
        draw_btn(travel_go_rect, "Return")
        draw_btn(travel_back_rect, "Cancel")


def draw_sleep_popup(surface):
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 180))
    surface.blit(shade, (0, 0))
    panel = pygame.Rect(80, 70, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 140)
    pygame.draw.rect(surface, (20, 20, 30), panel, border_radius=10)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2, border_radius=10)
    surface.blit(font.render("REST", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
    surface.blit(font.render("Sleep and start a new day?", True, (220, 220, 230)), (panel.x + 20, panel.y + 60))
    mouse_pos = pygame.mouse.get_pos()
    global sleep_go_rect, sleep_back_rect
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


def draw_overlay(surface):
    global active_overlay
    if active_overlay is None:
        return
    update_level_from_xp()
    mouse_pos = pygame.mouse.get_pos()
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 180))
    surface.blit(shade, (0, 0))
    panel = pygame.Rect(60, 50, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 100)
    pygame.draw.rect(surface, (25, 25, 35), panel, border_radius=10)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2, border_radius=10)
    draw_back_button(surface, mouse_pos)

    if active_overlay == "status":
        surface.blit(font.render("STATUS", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
        next_threshold = None
        idx = max(0, level - 1)
        if idx < len(level_xp):
            next_threshold = level_xp[idx]
        xp_line = f"XP: {xp}" if next_threshold is None else f"XP: {xp}/{next_threshold}"
        lines = [
            f"Coins: {coins}",
            f"HP: {player_hp}/{PLAYER_MAX_HP}",
            f"Level: {level}",
            xp_line,
            "",
            f"Days: {days_spent}",
            f"Spells owned: {len(spells)}",
            f"Windcrystal: {inventory.get('mat_windcrystal', 0)}",

        ]
        y = panel.y + 60
        for line in lines:
            if line == "":
                y += 10
                continue
            surface.blit(font.render(line, True, (220, 220, 230)), (panel.x + 20, y))
            y += 26
        hint = "M: Craft | O: Orders | C: Spells"
        surface.blit(font.render(hint, True, (170, 170, 190)), (panel.x + 20, panel.bottom - 40))

    elif active_overlay == "magic":
        surface.blit(font.render("MAGIC", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
        icon_rect = pygame.Rect(panel.x + 20, panel.y + 70, 96, 96)
        pygame.draw.rect(surface, (45, 45, 55), icon_rect)
        pygame.draw.rect(surface, (120, 120, 140), icon_rect, 2)
        if fireball_img is not None:
            img = pygame.transform.smoothscale(fireball_img, (92, 92))
            surface.blit(img, (icon_rect.x + 2, icon_rect.y + 2))
        else:
            surface.blit(font.render("Fire", True, (255, 120, 80)), (icon_rect.x + 20, icon_rect.y + 38))
        fire_btn = magic_fire_craft_rect.move(panel.x - 60, panel.y - 50)
        hovered_fire = fire_btn.collidepoint(mouse_pos)
        bg_fire = (90, 90, 110) if hovered_fire else (70, 70, 80)
        pygame.draw.rect(surface, bg_fire, fire_btn, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), fire_btn, 2, border_radius=8)
        surface.blit(font.render("Craft", True, (255, 255, 255)), (fire_btn.x + 14, fire_btn.y + 8))
        surface.blit(font.render("fire_mage", True, (200, 200, 210)), (fire_btn.x + 14, fire_btn.y + 28))

        flying_btn = magic_flying_craft_rect.move(panel.x - 60, panel.y - 50)
        hovered_flying = flying_btn.collidepoint(mouse_pos)
        bg_flying = (90, 90, 110) if hovered_flying else (70, 70, 80)
        pygame.draw.rect(surface, bg_flying, flying_btn, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), flying_btn, 2, border_radius=8)
        surface.blit(font.render("Craft", True, (255, 255, 255)), (flying_btn.x + 14, flying_btn.y + 8))
        surface.blit(font.render("Flying", True, (200, 200, 210)), (flying_btn.x + 14, flying_btn.y + 28))
        mat_have = inventory.get("mat_emberstone", 0)
        mat_need = 2
        mat_line_y = panel.y + 190
        if emberstone_img is not None:
            eimg = pygame.transform.smoothscale(emberstone_img, (24, 24))
            surface.blit(eimg, (panel.x + 20, mat_line_y))
            surface.blit(font.render(f"emberstone: {mat_have}/{mat_need}", True, (220, 220, 230)), (panel.x + 50, mat_line_y + 2))
        else:
            surface.blit(font.render(f"emberstone: {mat_have}/{mat_need}", True, (220, 220, 230)), (panel.x + 20, mat_line_y))

        wind_have = inventory.get("mat_windcrystal", 0)
        wind_need = 2
        wind_line_y = mat_line_y + 34
        if windcrystal_img is not None:
            wimg = pygame.transform.smoothscale(windcrystal_img, (24, 24))
            surface.blit(wimg, (panel.x + 20, wind_line_y))
            surface.blit(font.render(f"windcrystal: {wind_have}/{wind_need}", True, (220, 220, 230)), (panel.x + 50, wind_line_y + 2))
        else:
            surface.blit(font.render(f"windcrystal: {wind_have}/{wind_need}", True, (220, 220, 230)), (panel.x + 20, wind_line_y))

    elif active_overlay == "orders":
        surface.blit(font.render("ORDERS", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
        spell_counts = Counter(spells)
        global daily_order_btn_rect
        daily_order_btn_rect = None

        y = panel.y + 70
        surface.blit(font.render("--- DAILY ORDER ---", True, (120, 210, 255)), (panel.x + 20, y))
        y += 34

        if current_daily_order is None:
            surface.blit(font.render("No active order today.", True, (220, 220, 230)), (panel.x + 20, y))
        else:
            have_daily = spell_counts.get(current_daily_order, 0)
            can_sell_daily = (not order_completed_today) and have_daily >= 1
            surface.blit(font.render(f"Sell 1x {current_daily_order}", True, (220, 220, 230)), (panel.x + 20, y))
            y += 26
            surface.blit(font.render(f"Reward: +{COIN_PER_SALE}C +{XP_PER_SALE}XP", True, (150, 200, 150)), (panel.x + 20, y))
            y += 26
            if order_completed_today:
                daily_status = "Completed today"
            elif have_daily > 0:
                daily_status = f"have: {have_daily}"
            else:
                daily_status = "don't have required spell"
            surface.blit(font.render(daily_status, True, (180, 180, 200)), (panel.x + 20, y))
            y += 34
            daily_order_btn_rect = pygame.Rect(panel.x + 20, y, 140, 34)
            if can_sell_daily:
                daily_btn_color = (80, 120, 100)
                daily_btn_text = "ACCEPT"
            elif order_completed_today:
                daily_btn_color = (60, 60, 70)
                daily_btn_text = "Sold"
            else:
                daily_btn_color = (60, 60, 70)
                daily_btn_text = "Can't sell"
            pygame.draw.rect(surface, daily_btn_color, daily_order_btn_rect, border_radius=6)
            surface.blit(font.render(daily_btn_text, True, (255, 255, 255)), (daily_order_btn_rect.x + 12, daily_order_btn_rect.y + 7))

        surface.blit(font.render("Press C to open spells.", True, (170, 170, 190)), (panel.x + 20, panel.bottom - 40))

    elif active_overlay == "spells":
        surface.blit(font.render("SPELLBOOK", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
        spell_counts = Counter(spells)
        global spell_select_rects
        spell_select_rects.clear()

        surface.blit(font.render("Owned magic", True, (120, 210, 255)), (panel.x + 20, panel.y + 56))
        y = panel.y + 88
        unique_spells = list(spell_counts.keys())
        if not unique_spells:
            surface.blit(font.render("No spells owned.", True, (220, 220, 230)), (panel.x + 20, y))
            y += 28
        else:
            for spell_name in unique_spells:
                row_rect = pygame.Rect(panel.x + 20, y, panel.width - 40, 40)
                hovered = row_rect.collidepoint(mouse_pos)
                selected = spell_name == selected_spell_name
                bg = (85, 105, 120) if selected else ((75, 75, 90) if hovered else (60, 60, 70))
                pygame.draw.rect(surface, bg, row_rect, border_radius=8)
                pygame.draw.rect(surface, (180, 180, 200), row_rect, 1, border_radius=8)
                surface.blit(font.render(f"{spell_name} x{spell_counts[spell_name]}", True, (255, 255, 255)), (row_rect.x + 12, row_rect.y + 11))
                spell_select_rects[spell_name] = row_rect
                y += 48

        if selected_spell_name is not None:
            if selected_spell_name == "fire_mage" and pygame.time.get_ticks() < selected_spell_expires_at:
                remaining = max(0, (selected_spell_expires_at - pygame.time.get_ticks()) // 1000)
                status_line = f"Active: {selected_spell_name} ({remaining}s left)"
            else:
                status_line = f"Selected: {selected_spell_name}"
            surface.blit(font.render(status_line, True, (170, 220, 180)), (panel.x + 20, panel.bottom - 70))

        surface.blit(font.render("Click a spell to select it. Fire mage can be used with SPACE for 1 minute.", True, (170, 170, 190)), (panel.x + 20, panel.bottom - 40))


def run():
    global current_world, travel_overlay_open, sleep_overlay_open, days_spent, emberstone_items, active_overlay, last_rewarded_level, coins, xp, random_offer_spell, random_offer_amount, random_offer_xp, random_offer_coin, slime_world_unlocked
    global selected_spell_name, selected_spell_expires_at, fire_projectiles, slime_mobs, player_hp, last_player_hit_at, game_over_until_ms
    # instantiate player after display initialized (safe for image loads)
    player = Player(150, 150)
    issue_daily_order()
    generate_random_spell_offer()

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
                    elif event.key == pygame.K_o:
                        update_level_from_xp()
                        active_overlay = "orders" if active_overlay != "orders" else None
                    elif event.key == pygame.K_c:
                        update_level_from_xp()
                        active_overlay = "spells" if active_overlay != "spells" else None
                    elif event.key == pygame.K_SPACE:
                        if fire_spell_ready():
                            spawn_fire_projectile(player)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if active_overlay is None:
                            if current_world == "main":
                                ev = player_event_tile(player.rect)
                                if ev == 76:
                                    travel_overlay_open = True
                                elif ev == 20:
                                    sleep_overlay_open = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if travel_overlay_open:
                    if current_world == "main":
                        if travel_go_rect.collidepoint(event.pos):
                            enter_fire_world(player)
                            travel_overlay_open = False
                        elif travel_back_rect.collidepoint(event.pos):
                            if slime_world_unlocked:
                                enter_slime_world(player)
                            travel_overlay_open = False
                        elif slime_world_unlocked and travel_cancel_rect.collidepoint(event.pos):
                            travel_overlay_open = False
                    else:
                        if travel_go_rect.collidepoint(event.pos):
                            leave_to_main_world(player)
                            travel_overlay_open = False
                        elif travel_back_rect.collidepoint(event.pos):
                            travel_overlay_open = False
                elif sleep_overlay_open:
                    if sleep_go_rect.collidepoint(event.pos):
                        days_spent += 1
                        issue_daily_order()
                        generate_random_spell_offer()
                        push_log(f"You slept. Day {days_spent} begins.")
                        sleep_overlay_open = False
                    elif sleep_back_rect.collidepoint(event.pos):
                        sleep_overlay_open = False
                elif active_overlay is not None:
                    pos = event.pos
                    if back_button_rect.collidepoint(pos):
                        active_overlay = None
                    elif active_overlay == "orders":
                        if daily_order_btn_rect and daily_order_btn_rect.collidepoint(pos):
                            sell_daily_order_spell()

                    elif active_overlay == "spells":
                        for spell_name, rect in spell_select_rects.items():
                            if rect.collidepoint(pos):
                                if spell_name == "fire_mage":
                                    activate_fire_mage_spell()
                                else:
                                    global selected_spell_name, selected_spell_expires_at
                                    selected_spell_name = spell_name
                                    selected_spell_expires_at = 0
                                    push_log(f"Selected {spell_name}.")
                                break

                    elif active_overlay == "magic":
                        panel = pygame.Rect(60, 50, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 100)
                        fire_btn = magic_fire_craft_rect.move(panel.x - 60, panel.y - 50)
                        flying_btn = magic_flying_craft_rect.move(panel.x - 60, panel.y - 50)
                        if fire_btn.collidepoint(pos):
                            if inventory.get("mat_emberstone", 0) >= 2:
                                inventory["mat_emberstone"] -= 2
                                spells.append("fire_mage")
                                push_log("Crafted fire_mage spell.")
                            else:
                                push_log("Need 2 emberstone.")
                        elif flying_btn.collidepoint(pos):
                            if inventory.get("mat_windcrystal", 0) >= 2:
                                inventory["mat_windcrystal"] -= 2
                                spells.append("Flying")
                                push_log("Crafted Flying magic.")
                            else:
                                push_log("Need 2 windcrystal.")
                else:
                    if current_world in ("fire", "slime") and fire_return_rect.collidepoint(event.pos):
                        leave_to_main_world(player)
                        push_log("Returned to Main World.")

        keys = pygame.key.get_pressed()
        # Move player only when no overlays/popup open
        if active_overlay is None and not travel_overlay_open and not sleep_overlay_open and pygame.time.get_ticks() >= game_over_until_ms:
            player.move(keys)

        update_level_from_xp()
        if (not slime_world_unlocked) and level >= 2:
            slime_world_unlocked = True
            push_log("World Of Slime unlocked.")

        if selected_spell_name == "fire_mage" and pygame.time.get_ticks() >= selected_spell_expires_at:
            selected_spell_name = None
            selected_spell_expires_at = 0
            push_log("fire_mage expired.")

        while level > last_rewarded_level:
            granted = grant_next_spell(f"level {last_rewarded_level + 1}")
            last_rewarded_level += 1
            if not granted:
                break

        # emberstone pickup in fire world
        if current_world == "fire":
            for it in emberstone_items[:]:
                if player.rect.colliderect(it):
                    emberstone_items.remove(it)
                    inventory["mat_emberstone"] = inventory.get("mat_emberstone", 0) + 1
                    push_log("Picked up emberstone.")

            # gravity
            below_px = player.rect.centerx
            below_py = player.rect.bottom - 1
            below_tx = int(below_px // FIRE_TILE_SIZE)
            below_ty = int(below_py // FIRE_TILE_SIZE)
            if 0 <= below_tx < FIRE_MAP_COLS and 0 <= below_ty < FIRE_MAP_ROWS:
                if not is_walkable(below_tx, below_ty):
                    player.rect.y += 1
                    player.x, player.y = player.rect.topleft
                    if player.rect.bottom > fire_map_img.get_height():
                        player.rect.bottom = fire_map_img.get_height()
                        player.x, player.y = player.rect.topleft
            else:
                if player.rect.bottom < fire_map_img.get_height():
                    player.rect.y += 1
                    player.x, player.y = player.rect.topleft

        update_fire_projectiles()

        if current_world == "slime":
            for it in windcrystal_items[:]:
                if player.rect.colliderect(it):
                    windcrystal_items.remove(it)
                    inventory["mat_windcrystal"] = inventory.get("mat_windcrystal", 0) + 1
                    push_log("Picked up windcrystal.")

            now_ms = pygame.time.get_ticks()
            player_hp, last_player_hit_at = update_slime_mobs(player, now_ms, player_hp, last_player_hit_at)
            if player_hp <= 0:
                game_over_until_ms = now_ms + 1200
                push_log("GAME OVER - You were defeated.")
                leave_to_main_world(player)
                push_log("Auto-teleported home. HP restored.")

        def world_solid_tile(tx, ty):
            if current_world == "slime":
                return is_slime_blocked(tx, ty)
            if current_world == "fire":
                return is_walkable(tx, ty)
            return False

        # Apply movement with collision (main world uses COLLISION_TILE_VALUE)
        active_collision = slime_world_collision if current_world == "slime" else collision
        active_collision_value = 102 if current_world == "slime" else COLLISION_TILE_VALUE
        player.apply_movement(world_solid_tile, active_collision, TILE_SIZE, MAP_COLS, MAP_ROWS, active_collision_value, current_world)

        # Draw
        screen.fill((0, 0, 0))
        if current_world == "slime":
            screen.blit(slime_map_img, (0, 0))
        elif current_world == "fire":
            screen.blit(fire_map_img, (0, 0))
        else:
            screen.blit(map_img, (0, 0))

        if current_world == "slime":
            draw_slime_mobs(screen)

        if current_world == "slime":
            for it in windcrystal_items:
                if windcrystal_img is not None:
                    img = pygame.transform.smoothscale(windcrystal_img, (it.width, it.height))
                    screen.blit(img, it.topleft)
                else:
                    pygame.draw.ellipse(screen, (120, 220, 255), it)

        player.draw(screen, sprite_scale=0.8 if current_world == "slime" else 1.0)

        draw_fire_projectiles(screen)

        if current_world in ("fire", "slime"):
            draw_fire_return_button(screen)

        draw_overlay(screen)
        if travel_overlay_open:
            draw_travel_popup(screen)
        if sleep_overlay_open:
            draw_sleep_popup(screen)

        # draw emberstones
        if current_world == "fire":
            for it in emberstone_items:
                if emberstone_img is not None:
                    img = pygame.transform.smoothscale(emberstone_img, (it.width, it.height))
                    screen.blit(img, it.topleft)
                else:
                    pygame.draw.ellipse(screen, (255, 180, 60), it)

        if current_world == "slime":
            for slime in slime_mobs:
                if slime["flash"] > 0:
                    pygame.draw.ellipse(screen, (255, 180, 80), slime["rect"])

        hp_label = font.render(f"HP: {player_hp}/{PLAYER_MAX_HP}", True, (255, 220, 220))
        screen.blit(hp_label, (10, SCREEN_HEIGHT - 28))

        if pygame.time.get_ticks() < game_over_until_ms:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            screen.blit(overlay, (0, 0))
            title = font.render("GAME OVER", True, (255, 120, 120))
            subtitle = font.render("Auto-teleporting home...", True, (240, 240, 240))
            screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 12)))
            screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 18)))

        pygame.display.update()
        clock.tick(60)
