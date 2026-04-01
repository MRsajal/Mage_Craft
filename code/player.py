import pygame
import os


def load_images(path, count=None):
    """Load frames named 0.png..N.png from a folder."""
    if count is None:
        i = 0
        while True:
            if not os.path.exists(os.path.join(path, f"{i}.png")):
                break
            i += 1
        count = i

    images = []
    for i in range(count):
        img = pygame.image.load(f"{path}/{i}.png").convert_alpha()
        img = pygame.transform.scale(img, (68, 68))  # slightly smaller player sprite
        images.append(img)
    return images


# Frame placeholders; will be loaded in Player.__init__ after display init
right_frames = None
left_frames = None
idle_right_frames = None
idle_left_frames = None


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y

        self.speed = 2

        self.direction = "right"
        self.frame_index = 0
        self.animation_speed = 0.5

        self.state = "idle"  # "idle" or "walk"
        # load frames lazily (safe because display is initialized before Player is created)
        global right_frames, left_frames, idle_right_frames, idle_left_frames
        if right_frames is None:
            right_frames = load_images("Player/walk/right", 15)
        if left_frames is None:
            left_frames = load_images("Player/walk/left", 15)
        if idle_right_frames is None:
            idle_right_frames = load_images("Player/idle/right", 13)
        if idle_left_frames is None:
            idle_left_frames = load_images("Player/idle/left", 13)
        self.image = idle_right_frames[0]

        # Use a dedicated hitbox (smaller than the sprite)
        self.rect = pygame.Rect(self.x, self.y, 30, 42)
        self.sprite_offset = pygame.Vector2(-19, -24)  # align smaller sprite over hitbox

    def move(self, keys):
        dx = 0
        dy = 0

        if keys[pygame.K_LEFT]:
            dx = -self.speed
            self.direction = "left"

        if keys[pygame.K_RIGHT]:
            dx = self.speed
            self.direction = "right"

        if keys[pygame.K_UP]:
            dy = -self.speed

        if keys[pygame.K_DOWN]:
            dy = self.speed

        moving = (dx != 0 or dy != 0)
        self.state = "walk" if moving else "idle"

        # Move & collide per-axis (must be handled by game loop via _move_axis exposed)
        self._pending_dx = dx
        self._pending_dy = dy

    def _get_overlapping_solid_tiles(self, is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world):
        # Compute tile range overlapped by rect (fix off-by-one on right/bottom)
        left = self.rect.left // TILE_SIZE
        right = (self.rect.right - 1) // TILE_SIZE
        top = self.rect.top // TILE_SIZE
        bottom = (self.rect.bottom - 1) // TILE_SIZE

        tiles = []
        for ty in range(int(top), int(bottom) + 1):
            for tx in range(int(left), int(right) + 1):
                if 0 <= tx < MAP_COLS and 0 <= ty < MAP_ROWS:
                    if current_world == "main":
                        if collision[ty][tx] == COLLISION_TILE_VALUE:
                            tiles.append(pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE))
                    else:
                        if is_walkable_func(tx, ty):
                            tiles.append(pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        return tiles

    def _move_axis(self, dx, dy, is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world):
        if dx == 0 and dy == 0:
            return

        self.rect.x += dx
        self.rect.y += dy

        for tile in self._get_overlapping_solid_tiles(is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world):
            if self.rect.colliderect(tile):
                if dx > 0:
                    self.rect.right = tile.left
                elif dx < 0:
                    self.rect.left = tile.right
                if dy > 0:
                    self.rect.bottom = tile.top
                elif dy < 0:
                    self.rect.top = tile.bottom

        self.rect.clamp_ip(pygame.Rect(0, 0, MAP_COLS * TILE_SIZE, MAP_ROWS * TILE_SIZE))
        self.x, self.y = self.rect.topleft

    def apply_movement(self, is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world):
        dx = getattr(self, '_pending_dx', 0)
        dy = getattr(self, '_pending_dy', 0)
        # Move per-axis
        self._move_axis(dx, 0, is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world)
        self._move_axis(0, dy, is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world)

        # Animation update
        moving = (dx != 0 or dy != 0)
        if moving:
            self.frame_index += self.animation_speed
            if self.frame_index >= len(right_frames):
                self.frame_index = 0
        else:
            self.frame_index += self.animation_speed
            idle_len = max(1, len(idle_right_frames))
            if self.frame_index >= idle_len:
                self.frame_index = 0

        # Update image
        if moving:
            if self.direction == "right":
                self.image = right_frames[int(self.frame_index)]
            else:
                self.image = left_frames[int(self.frame_index)]
        else:
            if self.direction == "right":
                self.image = idle_right_frames[int(self.frame_index) % len(idle_right_frames)]
            else:
                self.image = idle_left_frames[int(self.frame_index) % len(idle_left_frames)]

    def draw(self, surface):
        surface.blit(self.image, (self.rect.x + self.sprite_offset.x, self.rect.y + self.sprite_offset.y))

    def check_collision(self, is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world):
        return any(self.rect.colliderect(t) for t in self._get_overlapping_solid_tiles(is_walkable_func, collision, TILE_SIZE, MAP_COLS, MAP_ROWS, COLLISION_TILE_VALUE, current_world))
