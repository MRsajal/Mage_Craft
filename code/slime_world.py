import os
import pygame

try:
    from .slime_world_collision import slime_world_collision
except Exception:
    try:
        from slime_world_collision import slime_world_collision
    except Exception:
        slime_world_collision = [[-1]]

SLIME_BLOCK_TILE = 102
SLIME_MAP_ROWS = len(slime_world_collision)
SLIME_MAP_COLS = len(slime_world_collision[0]) if SLIME_MAP_ROWS > 0 else 0


def load_slime_map(width, height):
    """Load and scale the world_of_slime map image."""
    candidates = []
    project_image = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "images", "world_of_slime.png"))
    candidates.append(project_image)
    alt_project_image = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "images", "slime_world.png"))
    candidates.append(alt_project_image)
    module_image = os.path.join(os.path.dirname(__file__), "world_of_slime.png")
    candidates.append(module_image)

    for path in candidates:
        try:
            if os.path.exists(path):
                img = pygame.image.load(path).convert()
                return pygame.transform.scale(img, (width, height))
        except Exception:
            continue

    fallback = pygame.Surface((width, height))
    fallback.fill((40, 120, 80))
    return fallback


def is_slime_blocked(tx, ty):
    """Return True if this slime-world tile is a collision tile."""
    if ty < 0 or ty >= len(slime_world_collision):
        return True
    row = slime_world_collision[ty]
    if tx < 0 or tx >= len(row):
        return True
    return row[tx] == SLIME_BLOCK_TILE
