import random
import pygame


def spawn_slime_mobs(count, map_rows, map_cols, tile_size, is_blocked, max_hp):
    mobs = []
    candidates = []
    for ty in range(map_rows):
        for tx in range(map_cols):
            if not is_blocked(tx, ty):
                candidates.append((tx, ty))

    if not candidates:
        return mobs

    sample_count = min(count, len(candidates))
    for tx, ty in random.sample(candidates, sample_count):
        slime_rect = pygame.Rect(
            tx * tile_size + random.randint(2, 8),
            ty * tile_size + random.randint(2, 8),
            24,
            18,
        )
        mobs.append({"rect": slime_rect, "flash": 0, "direction": "right", "frame_index": 0.0, "hp": max_hp})
    return mobs


def spawn_fire_projectile(player, fire_projectiles, projectile_size, projectile_speed, now_ms):
    direction = 1 if player.direction == "right" else -1
    start_x = player.rect.centerx + (18 if direction > 0 else -18)
    start_y = player.rect.centery - 8
    fire_projectiles.append(
        {
            "rect": pygame.Rect(start_x, start_y, projectile_size, projectile_size),
            "vx": direction * projectile_speed,
            "spawn_time": now_ms,
            "frame_index": 0,
        }
    )


def update_fire_projectiles(fire_projectiles, now_ms, duration_ms, frame_count, screen_width):
    for projectile in fire_projectiles[:]:
        projectile["rect"].x += projectile["vx"]
        projectile["frame_index"] = min(frame_count - 1, (now_ms - projectile["spawn_time"]) // 120) if frame_count > 0 else 0
        if now_ms - projectile["spawn_time"] > duration_ms:
            fire_projectiles.remove(projectile)
            continue
        if projectile["rect"].right < 0 or projectile["rect"].left > screen_width:
            fire_projectiles.remove(projectile)


def draw_fire_projectiles(surface, fire_projectiles, fire_spell_frames):
    for projectile in fire_projectiles:
        if fire_spell_frames:
            frame = fire_spell_frames[int(projectile["frame_index"])]
            surface.blit(frame, projectile["rect"].topleft)
        else:
            pygame.draw.circle(surface, (255, 130, 50), projectile["rect"].center, projectile["rect"].width // 2)


def move_slime_axis(slime, dx, dy, screen_width, screen_height):
    if dx:
        slime["rect"].x += dx

    if dy:
        slime["rect"].y += dy

    slime["rect"].clamp_ip(pygame.Rect(0, 0, screen_width, screen_height))


def update_slime_mobs(
    player,
    slime_mobs,
    fire_projectiles,
    windcrystal_items,
    now_ms,
    current_hp,
    last_hit_at,
    *,
    screen_width,
    screen_height,
    slime_speed,
    player_hit_cooldown_ms,
    player_max_hp,
    windcrystal_drop_size,
    slime_right_frames,
    slime_left_frames,
    push_log,
):
    for slime in slime_mobs:
        if slime["flash"] > 0:
            slime["flash"] -= 1

        dx_to_player = player.rect.centerx - slime["rect"].centerx
        dy_to_player = player.rect.centery - slime["rect"].centery

        step_x = 0
        step_y = 0
        if abs(dx_to_player) > 2:
            step_x = slime_speed if dx_to_player > 0 else -slime_speed
        if abs(dy_to_player) > 2:
            step_y = slime_speed if dy_to_player > 0 else -slime_speed

        move_slime_axis(slime, step_x, 0, screen_width, screen_height)
        move_slime_axis(slime, 0, step_y, screen_width, screen_height)

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
                        slime["rect"].centerx - (windcrystal_drop_size // 2),
                        slime["rect"].centery - (windcrystal_drop_size // 2),
                        windcrystal_drop_size,
                        windcrystal_drop_size,
                    )
                    windcrystal_items.append(drop_rect)
                    push_log("A slime dropped windcrystal.")
                break

    if now_ms - last_hit_at >= player_hit_cooldown_ms:
        for slime in slime_mobs:
            if slime["rect"].colliderect(player.rect):
                current_hp = max(0, current_hp - 1)
                last_hit_at = now_ms
                push_log(f"Slime hit you: HP {current_hp}/{player_max_hp}")
                break

    return current_hp, last_hit_at


def draw_slime_mobs(surface, slime_mobs, slime_right_frames, slime_left_frames):
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
