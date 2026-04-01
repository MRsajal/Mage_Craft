import pygame
import sys
import os
import random
from collections import Counter
try:
    from .data import COLLISION as collision, EVENTS as events
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
fire_map_img = load_fire_map(SCREEN_WIDTH, SCREEN_HEIGHT)

# --- UI panel / state defaults ---
PANEL_WIDTH = 0
current_world = "main"  # "main" | "fire"

# overlay / popup flags
travel_overlay_open = False
sleep_overlay_open = False

# Track days spent (increment when player sleeps)
days_spent = 1

# Simple UI / economy
inventory = {"mat_emberstone": 2}
spells = ["Fireball"]
coins = 0
xp = 0
level = 1
emberstone_items = []
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

# Random daily spell offer
random_offer_spell = None
random_offer_amount = 0
random_offer_xp = 0
random_offer_coin = 0
random_offer_btn_rect = None
daily_order_btn_rect = None

# overlays
active_overlay = None  # None | "status" | "magic" | "spells"

# logs
log = ["> Welcome, Mage. Your sanctum awaits."]

def push_log(line):
    log.insert(0, f"> {line}")
    if len(log) > 12:
        log.pop()

# assets for magic screen
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

# UI rects
back_button_rect = pygame.Rect(10, 10, 90, 32)
fire_return_rect = pygame.Rect(10, 10, 110, 32)
magic_craft_rect = pygame.Rect(220, 140, 220, 52)

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
    # Daily order must be one owned spell from the player's inventory.
    if not spells:
        current_daily_order = None
        order_completed_today = False
        push_log("No daily order: you do not own any spells yet.")
        return
    current_daily_order = random.choice(list(set(spells)))
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
    panel = pygame.Rect(80, 70, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 140)
    pygame.draw.rect(surface, (25, 25, 35), panel, border_radius=10)
    pygame.draw.rect(surface, (120, 120, 140), panel, 2, border_radius=10)
    surface.blit(font.render("TRAVEL", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
    msg = "Go to Fire World?" if current_world == "main" else "Return to Main World?"
    surface.blit(font.render(msg, True, (220, 220, 230)), (panel.x + 20, panel.y + 60))
    mouse_pos = pygame.mouse.get_pos()
    global travel_go_rect, travel_back_rect
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
            f"Level: {level}",
            xp_line,
            "",
            f"Days: {days_spent}",
            f"Spells owned: {len(spells)}",

        ]
        y = panel.y + 60
        for line in lines:
            if line == "":
                y += 10
                continue
            surface.blit(font.render(line, True, (220, 220, 230)), (panel.x + 20, y))
            y += 26
        hint = "M: Craft | O: Spellbook (Accept daily order)"
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
        btn = magic_craft_rect.move(panel.x - 60, panel.y - 50)
        hovered = btn.collidepoint(mouse_pos)
        bg = (90, 90, 110) if hovered else (70, 70, 80)
        pygame.draw.rect(surface, bg, btn, border_radius=8)
        pygame.draw.rect(surface, (180, 180, 200), btn, 2, border_radius=8)
        surface.blit(font.render("Craft", True, (255, 255, 255)), (btn.x + 14, btn.y + 8))
        surface.blit(font.render("Fireball", True, (200, 200, 210)), (btn.x + 14, btn.y + 28))
        mat_have = inventory.get("mat_emberstone", 0)
        mat_need = 2
        mat_line_y = panel.y + 190
        if emberstone_img is not None:
            eimg = pygame.transform.smoothscale(emberstone_img, (24, 24))
            surface.blit(eimg, (panel.x + 20, mat_line_y))
            surface.blit(font.render(f"emberstone: {mat_have}/{mat_need}", True, (220, 220, 230)), (panel.x + 50, mat_line_y + 2))
        else:
            surface.blit(font.render(f"emberstone: {mat_have}/{mat_need}", True, (220, 220, 230)), (panel.x + 20, mat_line_y))

    elif active_overlay == "spells":
        surface.blit(font.render("SPELLBOOK - SELL SPELLS", True, (255, 255, 255)), (panel.x + 20, panel.y + 20))
        spell_counts = Counter(spells)
        y = panel.y + 60
        spell_sell_rects.clear()

        # Daily order uses single-click accept (no +/- amount controls).
        surface.blit(font.render("--- DAILY ORDER ---", True, (120, 210, 255)), (panel.x + 20, y))
        y += 30
        global daily_order_btn_rect
        daily_order_btn_rect = None

        if current_daily_order is None:
            surface.blit(font.render("No active order today.", True, (220, 220, 230)), (panel.x + 20, y))
            y += 28
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
            y += 30

            daily_order_btn_rect = pygame.Rect(panel.x + 20, y, 100, 32)
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
            surface.blit(font.render(daily_btn_text, True, (255, 255, 255)), (daily_order_btn_rect.x + 12, daily_order_btn_rect.y + 6))
            y += 44
        
        global random_offer_btn_rect
        random_offer_btn_rect = None
        surface.blit(font.render("Accept to sell instantly (one daily order per day).", True, (170, 170, 190)), (panel.x + 20, panel.bottom - 40))


def run():
    global current_world, travel_overlay_open, sleep_overlay_open, days_spent, emberstone_items, active_overlay, last_rewarded_level, coins, xp, random_offer_spell, random_offer_amount, random_offer_xp, random_offer_coin
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
                        active_overlay = "spells" if active_overlay != "spells" else None
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if active_overlay is None:
                            ev = player_event_tile(player.rect)
                            if ev == 76:
                                travel_overlay_open = True
                            elif ev == 20:
                                sleep_overlay_open = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if travel_overlay_open:
                    if travel_go_rect.collidepoint(event.pos):
                        # toggle world
                        current_world = "fire" if current_world == "main" else "main"
                        if current_world == "fire":
                            emberstone_items = spawn_emberstones(FIRE_MAP_COLS, FIRE_MAP_ROWS, FIRE_TILE_SIZE, count=6)
                            player.rect.x = 50
                            # spawn player 200px lower in the fire world
                            player.rect.y = 50 + 200
                            player.x, player.y = player.rect.topleft
                        else:
                            emberstone_items = []
                            player.rect.x = 150
                            player.rect.y = 150
                            player.x, player.y = player.rect.topleft
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
                    elif active_overlay == "spells":
                        spell_counts = Counter(spells)

                        # Accept daily order sale.
                        if daily_order_btn_rect and daily_order_btn_rect.collidepoint(pos):
                            sell_daily_order_spell()
                        
                    elif active_overlay == "magic":
                        panel = pygame.Rect(60, 50, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 100)
                        btn = magic_craft_rect.move(panel.x - 60, panel.y - 50)
                        if btn.collidepoint(pos):
                            if inventory.get("mat_emberstone", 0) >= 2:
                                inventory["mat_emberstone"] -= 2
                                spells.append("Fireball")
                                push_log("Crafted Fireball spell.")
                else:
                    if current_world == "fire" and fire_return_rect.collidepoint(event.pos):
                        current_world = "main"
                        emberstone_items = []
                        player.rect.x = 150
                        player.rect.y = 150
                        player.x, player.y = player.rect.topleft
                        push_log("Returned to Main World.")

        keys = pygame.key.get_pressed()
        # Move player only when no overlays/popup open
        if active_overlay is None and not travel_overlay_open and not sleep_overlay_open:
            player.move(keys)

        update_level_from_xp()
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

        # Apply movement with collision (main world uses COLLISION_TILE_VALUE)
        player.apply_movement(is_walkable, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world)

        # Draw
        screen.fill((0, 0, 0))
        screen.blit(fire_map_img if current_world == "fire" else map_img, (0, 0))
        player.draw(screen)

        if current_world == "fire":
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

        pygame.display.update()
        clock.tick(60)
