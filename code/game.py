import pygame
import sys
import os
from collections import Counter
try:
    from .data import COLLISION as collision, EVENTS as events
    from .slime_world import load_slime_map, is_slime_blocked
    from .slime_world_collision import slime_world_collision
    from .game_combat import (
        spawn_slime_mobs as _spawn_slime_mobs,
        spawn_fire_projectile as _spawn_fire_projectile,
        update_fire_projectiles as _update_fire_projectiles,
        draw_fire_projectiles as _draw_fire_projectiles,
        update_slime_mobs as _update_slime_mobs,
        draw_slime_mobs as _draw_slime_mobs,
    )
    from .game_progression import (
        count_spell as _count_spell,
        update_level_from_xp as _update_level_from_xp,
        grant_next_spell as _grant_next_spell,
        issue_daily_order as _issue_daily_order,
        generate_random_spell_offer as _generate_random_spell_offer,
        sell_daily_order_spell as _sell_daily_order_spell,
    )
    from .fire_world import (
        load_fire_map,
        is_walkable,
        spawn_emberstones,
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
    from game_combat import (
        spawn_slime_mobs as _spawn_slime_mobs,
        spawn_fire_projectile as _spawn_fire_projectile,
        update_fire_projectiles as _update_fire_projectiles,
        draw_fire_projectiles as _draw_fire_projectiles,
        update_slime_mobs as _update_slime_mobs,
        draw_slime_mobs as _draw_slime_mobs,
    )
    from game_progression import (
        count_spell as _count_spell,
        update_level_from_xp as _update_level_from_xp,
        grant_next_spell as _grant_next_spell,
        issue_daily_order as _issue_daily_order,
        generate_random_spell_offer as _generate_random_spell_offer,
        sell_daily_order_spell as _sell_daily_order_spell,
    )
    from fire_world import (
        load_fire_map,
        is_walkable,
        spawn_emberstones,
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
font = pygame.font.SysFont("georgia", 22)
title_font = pygame.font.SysFont("georgia", 32, bold=True)
body_font = pygame.font.SysFont("georgia", 20)
small_font = pygame.font.SysFont("georgia", 16)

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
control_overlay_open = False
control_close_rect = pygame.Rect(0, 0, 220, 44)

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
control_btn_rect = None

# overlays
active_overlay = None  # None | "status" | "magic" | "orders" | "spells"
overlay_scroll_y = 0

# logs
log = ["> Welcome, Mage. Your sanctum awaits."]

def push_log(line):
    log.insert(0, f"> {line}")
    if len(log) > 12:
        log.pop()


def count_spell(spell_name):
    return _count_spell(spells, spell_name)


def spawn_slime_mobs(count=SLIME_COUNT):
    return _spawn_slime_mobs(count, MAP_ROWS, MAP_COLS, TILE_SIZE, is_slime_blocked, SLIME_MAX_HP)


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

    _spawn_fire_projectile(
        player,
        fire_projectiles,
        FIRE_PROJECTILE_SIZE,
        FIRE_PROJECTILE_SPEED,
        pygame.time.get_ticks(),
    )


def update_fire_projectiles():
    _update_fire_projectiles(
        fire_projectiles,
        pygame.time.get_ticks(),
        FIRE_PROJECTILE_DURATION_MS,
        len(fire_spell_frames),
        SCREEN_WIDTH,
    )


def draw_fire_projectiles(surface):
    _draw_fire_projectiles(surface, fire_projectiles, fire_spell_frames)


def update_slime_mobs(player, now_ms, current_hp, last_hit_at):
    return _update_slime_mobs(
        player,
        slime_mobs,
        fire_projectiles,
        windcrystal_items,
        now_ms,
        current_hp,
        last_hit_at,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        slime_speed=SLIME_SPEED,
        player_hit_cooldown_ms=PLAYER_HIT_COOLDOWN_MS,
        player_max_hp=PLAYER_MAX_HP,
        windcrystal_drop_size=WINDCRYSTAL_DROP_SIZE,
        slime_right_frames=slime_right_frames,
        slime_left_frames=slime_left_frames,
        push_log=push_log,
    )


def draw_slime_mobs(surface):
    _draw_slime_mobs(surface, slime_mobs, slime_right_frames, slime_left_frames)


def draw_soft_glow(surface, center, color, radius, alpha=90):
    glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    glow_center = (radius * 2, radius * 2)
    pygame.draw.circle(glow, (*color, alpha // 4), glow_center, radius * 2)
    pygame.draw.circle(glow, (*color, alpha // 2), glow_center, int(radius * 1.35))
    pygame.draw.circle(glow, (*color, alpha), glow_center, int(radius * 0.8))
    surface.blit(glow, glow.get_rect(center=center))


def draw_mystic_panel(surface, rect, title, subtitle=None):
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(overlay, (12, 16, 30, 218), overlay.get_rect(), border_radius=18)
    pygame.draw.rect(overlay, (38, 48, 78, 145), overlay.get_rect().inflate(-6, -6), border_radius=14)
    pygame.draw.rect(overlay, (140, 180, 255, 90), overlay.get_rect(), 2, border_radius=18)
    pygame.draw.line(overlay, (125, 210, 255, 110), (24, 48), (rect.width - 24, 48), 1)
    overlay.blit(title_font.render(title, True, (245, 247, 255)), (24, 14))
    if subtitle:
        overlay.blit(small_font.render(subtitle, True, (170, 186, 220)), (24, 52))
    surface.blit(overlay, rect.topleft)
    draw_soft_glow(surface, rect.topleft, (130, 170, 255), 42, 90)
    draw_soft_glow(surface, rect.topright, (170, 130, 255), 42, 90)
    draw_soft_glow(surface, (rect.centerx, rect.top + 10), (110, 220, 255), 56, 100)


def draw_mystic_button(surface, rect, text, mouse_pos, accent=(120, 180, 255), secondary=None):
    hovered = rect.collidepoint(mouse_pos)
    button = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(button, (15, 19, 36, 205 if hovered else 170), button.get_rect(), border_radius=12)
    pygame.draw.rect(button, (*accent, 130 if hovered else 80), button.get_rect(), 2, border_radius=12)
    pygame.draw.rect(button, (255, 255, 255, 25), button.get_rect().inflate(-8, -8), 1, border_radius=10)
    surface.blit(button, rect.topleft)
    label = body_font.render(text, True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=rect.center))
    if secondary:
        sublabel = small_font.render(secondary, True, (188, 202, 228))
        surface.blit(sublabel, sublabel.get_rect(center=(rect.centerx, rect.centery + 12)))


def draw_stat_card(surface, rect, label, value, accent, detail=None, progress=None):
    card = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(card, (15, 19, 36, 190), card.get_rect(), border_radius=14)
    pygame.draw.rect(card, (*accent, 85), card.get_rect(), 1, border_radius=14)
    label_surface = small_font.render(label, True, (172, 186, 220))
    value_surface = body_font.render(value, True, (248, 249, 255))
    label_y = 12
    value_y = 10
    card.blit(label_surface, (14, label_y))
    value_x = rect.width - value_surface.get_width() - 14
    card.blit(value_surface, (value_x, value_y))
    if detail:
        card.blit(small_font.render(detail, True, (188, 204, 232)), (14, rect.height - 21))
    if progress is not None:
        bar_rect = pygame.Rect(14, rect.height - 18, rect.width - 28, 6)
        pygame.draw.rect(card, (32, 40, 65, 220), bar_rect, border_radius=4)
        fill_rect = bar_rect.copy()
        fill_rect.width = max(0, min(bar_rect.width, int(bar_rect.width * progress)))
        pygame.draw.rect(card, (*accent, 220), fill_rect, border_radius=4)
    surface.blit(card, rect.topleft)


def get_overlay_scroll_max():
    viewport_height = 134
    if active_overlay == "status":
        content_height = 260
    elif active_overlay == "magic":
        content_height = 280
    elif active_overlay == "orders":
        content_height = 210
    elif active_overlay == "spells":
        content_height = max(210, 112 + (52 * len(Counter(spells))))
    else:
        content_height = viewport_height
    return max(0, content_height - viewport_height)


def clamp_overlay_scroll():
    global overlay_scroll_y
    overlay_scroll_y = max(0, min(overlay_scroll_y, get_overlay_scroll_max()))


def draw_control_popup(surface):
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((4, 6, 14, 186))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    draw_mystic_panel(surface, panel, "CONTROL", "How the menu buttons and keys work")

    lines = [
        "J: Open Status",
        "M: Open Forge",
        "O: Open Orders",
        "C: Open Spellbook",
        "Enter: Use event tiles for Travel or Rest",
        "Space: Cast fire_mage when active",
        "Mouse wheel / PageUp / PageDown: Scroll menu panels",
    ]

    y = panel.y + 92
    for line in lines:
        surface.blit(body_font.render(line, True, (228, 234, 245)), (panel.x + 28, y))
        y += 30

    global control_close_rect
    control_close_rect = pygame.Rect(10, 10, 90, 32)
    draw_mystic_button(surface, control_close_rect, "Cancel", pygame.mouse.get_pos(), accent=(180, 140, 255))

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
    level = _update_level_from_xp(xp, level_xp)


def grant_next_spell(reason):
    global next_spell_unlock_index
    next_spell_unlock_index, granted = _grant_next_spell(
        spells,
        next_spell_unlock_index,
        MAGIC_SPELLS,
        reason,
        push_log,
    )
    return granted


def issue_daily_order():
    global current_daily_order, order_completed_today
    current_daily_order, order_completed_today = _issue_daily_order(spells, current_daily_order, push_log)


def generate_random_spell_offer():
    global random_offer_spell, random_offer_amount, random_offer_xp, random_offer_coin

    (
        random_offer_spell,
        random_offer_amount,
        random_offer_xp,
        random_offer_coin,
    ) = _generate_random_spell_offer(spells, push_log)


def sell_daily_order_spell():
    global coins, xp, order_completed_today
    coins, xp, order_completed_today = _sell_daily_order_spell(
        spells,
        current_daily_order,
        order_completed_today,
        coins,
        xp,
        COIN_PER_SALE,
        XP_PER_SALE,
        push_log,
    )


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
    accent = (140, 180, 255) if hovered else (180, 140, 255)
    draw_mystic_button(surface, back_button_rect, "Back", mouse_pos, accent=accent)


def draw_fire_return_button(surface):
    draw_mystic_button(surface, fire_return_rect, "Return", pygame.mouse.get_pos(), accent=(255, 160, 110))


def draw_travel_popup(surface):
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((4, 6, 14, 186))
    surface.blit(shade, (0, 0))
    panel = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    draw_mystic_panel(surface, panel, "TRAVEL", "Choose the destination for this night")
    if current_world == "main":
        msg = "Choose destination"
    else:
        msg = "Return to Main World?"
    surface.blit(body_font.render(msg, True, (228, 234, 245)), (panel.x + 28, panel.y + 84))
    mouse_pos = pygame.mouse.get_pos()
    global travel_go_rect, travel_back_rect, travel_cancel_rect
    btn_w = min(460, SCREEN_WIDTH - 120)
    btn_x = (SCREEN_WIDTH - btn_w) // 2
    first_y = panel.y + 130
    gap = 64
    travel_go_rect = pygame.Rect(btn_x, first_y, btn_w, 52)
    travel_back_rect = pygame.Rect(btn_x, first_y + gap, btn_w, 52)
    travel_cancel_rect = pygame.Rect(btn_x, first_y + (gap * 2), btn_w, 52)

    if current_world == "main":
        draw_mystic_button(surface, travel_go_rect, "Fire World", mouse_pos, accent=(255, 160, 110), secondary="Open the ember gate")
        if slime_world_unlocked:
            draw_mystic_button(surface, travel_back_rect, "World Of Slime", mouse_pos, accent=(120, 220, 255), secondary="Unlocks at level 2")
            draw_mystic_button(surface, travel_cancel_rect, "Cancel", mouse_pos, accent=(180, 140, 255))
        else:
            draw_mystic_button(surface, travel_back_rect, "Cancel", mouse_pos, accent=(180, 140, 255))
    else:
        draw_mystic_button(surface, travel_go_rect, "Return", mouse_pos, accent=(120, 220, 255), secondary="Go back to the main world")
        draw_mystic_button(surface, travel_back_rect, "Cancel", mouse_pos, accent=(180, 140, 255))


def draw_sleep_popup(surface):
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((4, 6, 14, 186))
    surface.blit(shade, (0, 0))
    panel = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    draw_mystic_panel(surface, panel, "REST", "A quiet day closes and a new one begins")
    surface.blit(body_font.render("Sleep and start a new day?", True, (228, 234, 245)), (panel.x + 28, panel.y + 84))
    mouse_pos = pygame.mouse.get_pos()
    global sleep_go_rect, sleep_back_rect
    sleep_go_rect = pygame.Rect(panel.x + 28, panel.y + 128, 280, 52)
    sleep_back_rect = pygame.Rect(panel.x + 28, panel.y + 192, 280, 52)

    draw_mystic_button(surface, sleep_go_rect, "Sleep", mouse_pos, accent=(120, 220, 255), secondary="Advance the day")
    draw_mystic_button(surface, sleep_back_rect, "Cancel", mouse_pos, accent=(180, 140, 255))


def draw_overlay(surface):
    global active_overlay
    if active_overlay is None:
        return
    clamp_overlay_scroll()
    update_level_from_xp()
    mouse_pos = pygame.mouse.get_pos()
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((4, 6, 14, 186))
    surface.blit(shade, (0, 0))
    panel = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    overlay_title = {
        "status": "SANCTUM STATUS",
        "magic": "ARCANE FORGE",
        "orders": "ORDERS",
        "spells": "SPELLBOOK",
    }.get(active_overlay, "MENU")
    overlay_subtitle = {
        "status": "Coins, vitality, growth, and daily progress",
        "magic": None,
        "orders": "Daily contracts and spell sales",
        "spells": "Select your active magic",
    }.get(active_overlay)
    panel_title = "" if active_overlay == "magic" else overlay_title
    draw_mystic_panel(surface, panel, panel_title, overlay_subtitle)
    if active_overlay == "magic":
        title_surface = title_font.render(overlay_title, True, (245, 247, 255))
        surface.blit(title_surface, title_surface.get_rect(midtop=(panel.centerx, 14)))
    draw_back_button(surface, mouse_pos)

    content_view = pygame.Rect(panel.x + 18, panel.y + 80, panel.width - 36, panel.height - 126)
    previous_clip = surface.get_clip()
    surface.set_clip(content_view)
    content_scroll_y = overlay_scroll_y

    if active_overlay == "status":
        next_threshold = None
        idx = max(0, level - 1)
        if idx < len(level_xp):
            next_threshold = level_xp[idx]
        xp_line = f"XP: {xp}" if next_threshold is None else f"XP: {xp}/{next_threshold}"
        card_w = (panel.width - 80) // 2
        card_h = 62
        left_x = panel.x + 24
        right_x = left_x + card_w + 16
        top_y = panel.y + 92 - content_scroll_y
        stats = [
            ((left_x, top_y), "Coins", str(coins), (120, 220, 255), None, None),
            ((right_x, top_y), "HP", f"{player_hp}/{PLAYER_MAX_HP}", (255, 140, 160), None, player_hp / PLAYER_MAX_HP),
            ((left_x, top_y + 78), "Level", str(level), (175, 145, 255), None, None),
            ((right_x, top_y + 78), "XP", xp_line, (110, 220, 255), None, (xp / next_threshold) if next_threshold else None),
            ((left_x, top_y + 156), "Days", str(days_spent), (150, 235, 185), None, None),
            ((right_x, top_y + 156), "Spells", str(len(spells)), (245, 190, 120), f"Owned: {len(Counter(spells))}", None),
        ]
        for rect_pos, label, value, accent, detail, progress in stats:
            draw_stat_card(surface, pygame.Rect(rect_pos[0], rect_pos[1], card_w, card_h), label, value, accent, detail=detail, progress=progress)

        global control_btn_rect
        control_btn_rect = pygame.Rect(back_button_rect.right + 10, back_button_rect.y, 110, back_button_rect.height)
        draw_mystic_button(surface, control_btn_rect, "Control", mouse_pos, accent=(170, 140, 255))

    elif active_overlay == "magic":
        surface.blit(body_font.render("Crafting focus", True, (180, 202, 230)), (panel.x + 24, panel.y + 88 - content_scroll_y))

        fire_btn = magic_fire_craft_rect.move(panel.x - 60, panel.y - 32 - content_scroll_y)
        draw_mystic_button(surface, fire_btn, "Craft fire_mage", mouse_pos, accent=(255, 160, 110), secondary="Costs 2 emberstone")

        flying_btn = magic_flying_craft_rect.move(panel.x - 60, panel.y - 32 - content_scroll_y)
        draw_mystic_button(surface, flying_btn, "Craft Flying", mouse_pos, accent=(120, 220, 255), secondary="Costs 2 windcrystal")

        mat_have = inventory.get("mat_emberstone", 0)
        mat_need = 2
        mat_line_y = panel.y + 276
        surface.blit(body_font.render(f"emberstone: {mat_have}/{mat_need}", True, (228, 234, 245)), (panel.x + 24, mat_line_y))

        wind_have = inventory.get("mat_windcrystal", 0)
        wind_need = 2
        wind_line_y = mat_line_y + 34
        surface.blit(body_font.render(f"windcrystal: {wind_have}/{wind_need}", True, (228, 234, 245)), (panel.x + 24, wind_line_y))

    elif active_overlay == "orders":
        spell_counts = Counter(spells)
        global daily_order_btn_rect
        daily_order_btn_rect = None

        order_card = pygame.Rect(panel.x + 24, panel.y + 92 - content_scroll_y, panel.width - 48, 220)
        pygame.draw.rect(surface, (18, 24, 42), order_card, border_radius=16)
        pygame.draw.rect(surface, (120, 210, 255), order_card, 1, border_radius=16)
        surface.blit(body_font.render("Daily order", True, (180, 202, 230)), (order_card.x + 16, order_card.y + 14))

        if current_daily_order is None:
            surface.blit(body_font.render("No active order today.", True, (228, 234, 245)), (order_card.x + 16, order_card.y + 54))
        else:
            have_daily = spell_counts.get(current_daily_order, 0)
            can_sell_daily = (not order_completed_today) and have_daily >= 1
            surface.blit(body_font.render(f"Sell 1x {current_daily_order}", True, (228, 234, 245)), (order_card.x + 16, order_card.y + 50))
            surface.blit(body_font.render(f"Reward: +{COIN_PER_SALE} coins, +{XP_PER_SALE} XP", True, (155, 220, 170)), (order_card.x + 16, order_card.y + 84))
            if order_completed_today:
                daily_status = "Completed today"
            elif have_daily > 0:
                daily_status = f"have: {have_daily}"
            else:
                daily_status = "don't have required spell"
            surface.blit(small_font.render(daily_status, True, (180, 194, 218)), (order_card.x + 16, order_card.y + 116))
            daily_order_btn_rect = pygame.Rect(order_card.x + 16, order_card.bottom - 52, 180, 36)
            if can_sell_daily:
                daily_btn_text = "ACCEPT"
                daily_btn_accent = (110, 220, 180)
            elif order_completed_today:
                daily_btn_text = "Sold"
                daily_btn_accent = (150, 160, 180)
            else:
                daily_btn_text = "Can't sell"
                daily_btn_accent = (150, 160, 180)
            draw_mystic_button(surface, daily_order_btn_rect, daily_btn_text, mouse_pos, accent=daily_btn_accent)

    elif active_overlay == "spells":
        spell_counts = Counter(spells)
        global spell_select_rects
        spell_select_rects.clear()

        surface.blit(body_font.render("Owned magic", True, (180, 202, 230)), (panel.x + 24, panel.y + 68 - content_scroll_y))
        y = panel.y + 94 - content_scroll_y
        unique_spells = list(spell_counts.keys())
        if not unique_spells:
            surface.blit(body_font.render("No spells owned.", True, (228, 234, 245)), (panel.x + 24, y))
            y += 28
        else:
            for spell_name in unique_spells:
                row_rect = pygame.Rect(panel.x + 24, y, panel.width - 48, 42)
                selected = spell_name == selected_spell_name
                accent = (120, 220, 255) if selected else ((170, 140, 255) if row_rect.collidepoint(mouse_pos) else (110, 130, 170))
                draw_mystic_button(surface, row_rect, f"{spell_name} x{spell_counts[spell_name]}", mouse_pos, accent=accent)
                spell_select_rects[spell_name] = row_rect
                y += 52

        if selected_spell_name is not None:
            if selected_spell_name == "fire_mage" and pygame.time.get_ticks() < selected_spell_expires_at:
                remaining = max(0, (selected_spell_expires_at - pygame.time.get_ticks()) // 1000)
                status_line = f"Active: {selected_spell_name} ({remaining}s left)"
            else:
                status_line = f"Selected: {selected_spell_name}"
            surface.blit(small_font.render(status_line, True, (170, 220, 180)), (panel.x + 24, panel.bottom - 82 - content_scroll_y))

        surface.blit(small_font.render("Click a spell to select it. Fire mage can be used with SPACE for 1 minute.", True, (180, 194, 218)), (panel.x + 24, panel.bottom - 50 - content_scroll_y))

    surface.set_clip(previous_clip)

    scroll_max = get_overlay_scroll_max()
    if scroll_max > 0:
        track_rect = pygame.Rect(content_view.right - 10, content_view.y + 4, 4, content_view.height - 8)
        pygame.draw.rect(surface, (38, 48, 78, 170), track_rect, border_radius=3)
        thumb_height = max(24, int(track_rect.height * (content_view.height / (content_view.height + scroll_max))))
        thumb_range = track_rect.height - thumb_height
        thumb_y = track_rect.y if scroll_max == 0 else track_rect.y + int(thumb_range * (overlay_scroll_y / scroll_max))
        thumb_rect = pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_height)
        pygame.draw.rect(surface, (140, 180, 255, 210), thumb_rect, border_radius=3)


def run():
    global current_world, travel_overlay_open, sleep_overlay_open, control_overlay_open, days_spent, emberstone_items, active_overlay, overlay_scroll_y, last_rewarded_level, coins, xp, random_offer_spell, random_offer_amount, random_offer_xp, random_offer_coin, slime_world_unlocked
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
                if control_overlay_open:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        control_overlay_open = False
                elif travel_overlay_open:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        travel_overlay_open = False
                else:
                    if event.key == pygame.K_j:
                        update_level_from_xp()
                        active_overlay = "status" if active_overlay != "status" else None
                        overlay_scroll_y = 0
                    elif event.key == pygame.K_m:
                        update_level_from_xp()
                        active_overlay = "magic" if active_overlay != "magic" else None
                        overlay_scroll_y = 0
                    elif event.key == pygame.K_o:
                        update_level_from_xp()
                        active_overlay = "orders" if active_overlay != "orders" else None
                        overlay_scroll_y = 0
                    elif event.key == pygame.K_c:
                        update_level_from_xp()
                        active_overlay = "spells" if active_overlay != "spells" else None
                        overlay_scroll_y = 0
                    elif event.key == pygame.K_PAGEUP:
                        overlay_scroll_y = max(0, overlay_scroll_y - 48)
                    elif event.key == pygame.K_PAGEDOWN:
                        overlay_scroll_y = min(get_overlay_scroll_max(), overlay_scroll_y + 48)
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

            if event.type == pygame.MOUSEWHEEL:
                if active_overlay is not None and not travel_overlay_open and not sleep_overlay_open and not control_overlay_open:
                    overlay_scroll_y = max(0, min(get_overlay_scroll_max(), overlay_scroll_y - (event.y * 36)))

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if control_overlay_open:
                    if control_close_rect.collidepoint(event.pos) or back_button_rect.collidepoint(event.pos):
                        control_overlay_open = False
                elif travel_overlay_open:
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
                elif control_overlay_open:
                    if control_close_rect.collidepoint(event.pos) or back_button_rect.collidepoint(event.pos):
                        control_overlay_open = False
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
                        overlay_scroll_y = 0
                    elif active_overlay == "status" and 'control_btn_rect' in globals() and control_btn_rect.collidepoint(pos):
                        control_overlay_open = True
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
                        fire_btn = magic_fire_craft_rect.move(panel.x - 60, panel.y - 50 - overlay_scroll_y)
                        flying_btn = magic_flying_craft_rect.move(panel.x - 60, panel.y - 50 - overlay_scroll_y)
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
        if control_overlay_open:
            draw_control_popup(screen)
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
