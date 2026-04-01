import pygame
import os
import random

# import the tile data for the fire world
try:
    from code.fire_world_walk import fire_world_walk
except Exception:
    # fallback: empty map
    fire_world_walk = [[-1]]

WALK_VALUES = {154}

# Fire world scale and tile/grid dimensions
FIRE_ZOOM = 2.0
FIRE_TILE_SIZE = int(16 * FIRE_ZOOM)
FIRE_MAP_ROWS = len(fire_world_walk)
FIRE_MAP_COLS = len(fire_world_walk[0]) if FIRE_MAP_ROWS > 0 else 0


def load_fire_map(width, height):
    """Load and return the scaled fire world surface.

    Looks for a file named `fire_world.png` in the same folder as this module.
    If the file is missing or fails to load, returns a placeholder surface.
    """
    path = os.path.join(os.path.dirname(__file__), "fire_world.png")
    try:
        img = pygame.image.load(path).convert()
    except Exception:
        # fallback placeholder
        img = pygame.Surface((width, height))
        img.fill((120, 30, 20))
    return pygame.transform.scale(img, (width, height))


def is_walkable(tx, ty):
    """Return True if the tile at (tx,ty) is walkable in the fire world.

    Expects tx,ty as tile coordinates (not pixels)."""
    if ty < 0 or ty >= len(fire_world_walk):
        return False
    row = fire_world_walk[ty]
    if tx < 0 or tx >= len(row):
        return False
    return row[tx] in WALK_VALUES


def spawn_emberstones(map_cols, map_rows, tile_size, count=6):
    """Randomly place up to `count` emberstone items on walkable tiles.

    Returns a list of pygame.Rect objects (pixel coordinates) centered on tiles.
    """
    candidates = []
    for ty in range(map_rows):
        for tx in range(map_cols):
            if is_walkable(tx, ty):
                # center position on tile
                x = tx * tile_size
                y = ty * tile_size
                candidates.append((tx, ty, x, y))

    items = []
    if not candidates:
        return items

    sample_count = min(count, len(candidates))
    chosen = random.sample(candidates, sample_count)
    # item size (pixels) - small icon
    item_w = max(8, tile_size // 2)
    item_h = item_w
    for tx, ty, x, y in chosen:
        rect = pygame.Rect(x + (tile_size - item_w) // 2, y + (tile_size - item_h) // 2, item_w, item_h)
        items.append(rect)
    return items


def find_spawn_tile(map_cols, map_rows):
    """Find a tile coordinate (tx,ty) that is walkable (value 154).

    Returns (tx, ty) or None if not found.
    """
    for ty in range(min(map_rows, len(fire_world_walk))):
        row = fire_world_walk[ty]
        for tx in range(min(map_cols, len(row))):
            if row[tx] in WALK_VALUES:
                return tx, ty
    return None
