import pygame


def draw_back_button(surface, rect, font):
    hovered = rect.collidepoint(pygame.mouse.get_pos())
    bg = (18, 24, 42, 220) if hovered else (15, 19, 36, 190)
    button = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(button, bg, button.get_rect(), border_radius=12)
    pygame.draw.rect(button, (140, 180, 255, 130 if hovered else 80), button.get_rect(), 2, border_radius=12)
    surface.blit(button, rect.topleft)
    label = font.render("Back", True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=rect.center))
