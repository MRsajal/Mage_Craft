import pygame


def draw_back_button(surface, rect, font):
    hovered = rect.collidepoint(pygame.mouse.get_pos())
    bg = (90, 90, 110) if hovered else (70, 70, 80)
    pygame.draw.rect(surface, bg, rect, border_radius=6)
    pygame.draw.rect(surface, (180, 180, 200), rect, 2, border_radius=6)
    label = font.render("Back", True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=rect.center))
