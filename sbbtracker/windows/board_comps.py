import operator

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from sbbtracker import paths, settings
from sbbtracker.utils import asset_utils

art_dim = (161, 204)
att_loc = (26, 181)
health_loc = (137, 181)
xp_loc = (265, 60)
hero_health_loc = (220, 280)
display_font_family = "Impact" if paths.os_name == "Windows" else "Ubuntu Bold"


def get_image_location(position: int):
    if position < 4:  # slots 1 - 4
        x = (161 * position) + 300 + (position * 20)
        y = 0
    elif 4 <= position < 7:  # slots 5 - 7
        x = (161 * (position - 4)) + 300 + (161 / 2) + ((position - 4) * 20)
        y = 210
    elif 7 <= position < 9:  # treasures 1 + 2
        x = (161 * (position - 7))
        y = 440 - 175
    elif position == 9:  # treasure 3
        x = (161 / 2)
        y = 440
    elif position == 10:  # spell
        x = 850
        y = 440
    elif position == 11:  # hero
        x = 940
        y = 240
    else:
        x = 0
        y = 0
    return x, y + 5


class BoardComp(QWidget):
    def __init__(self):
        super().__init__()
        self.composition = None
        self.golden_overlay = QPixmap(asset_utils.get_asset("golden_overlay.png"))
        self.border = QPixmap(asset_utils.get_asset("neutral_border.png"))
        self.last_seen = None
        self.current_round = 0
        self.player = None
        self.scale = 1

        self.number_display_font = QFont(display_font_family, 25, weight=QFont.ExtraBold)

    def update_card_stats(self, painter: QPainter, slot: int, health: str, attack: str):
        card_location = get_image_location(slot)
        att_center = tuple(map(operator.add, att_loc, card_location))
        health_center = tuple(map(operator.add, health_loc, card_location))
        att_circle_center = tuple(map(operator.sub, att_center, (30, 40)))
        health_circle_center = tuple(map(operator.sub, health_center, (30, 40)))

        metrics = QFontMetrics(self.number_display_font)
        att_text_center = tuple(map(operator.sub, att_center, (metrics.horizontalAdvance(attack) / 2 - 2, -4)))
        health_text_center = tuple(map(operator.sub, health_center, (metrics.horizontalAdvance(health) / 2 - 2, -4)))
        if attack:
            if slot < 7:
                painter.drawPixmap(QPoint(*att_circle_center), QPixmap(asset_utils.get_asset("attack_orb.png")))
                path = QPainterPath()
                path.addText(QPoint(*att_text_center), self.number_display_font, attack)
                painter.setPen(QPen(QColor("black"), 1))
                painter.setBrush(QBrush("white"))
                painter.drawPath(path)
        if health:
            if slot < 7 or slot == 11:
                painter.drawPixmap(QPoint(*health_circle_center), QPixmap(asset_utils.get_asset("health_orb.png")))
                path = QPainterPath()
                path.addText(QPoint(*health_text_center), self.number_display_font, health)
                painter.setPen(QPen(QColor("black"), 1))
                painter.setBrush(QBrush("white"))
                painter.drawPath(path)

    def update_card(self, painter: QPainter, slot, content_id: str, health: str,
                    attack: str, is_golden):
        card_loc = get_image_location(int(slot))
        actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
        path = asset_utils.get_card_path(content_id, actually_is_golden)
        pixmap = QPixmap(path)
        painter.setPen(QPen(QColor("white"), 1))
        painter.drawText(card_loc[0] + 75, card_loc[1] + 100, str(content_id))
        if not settings.get(settings.show_ids):
            painter.drawPixmap(card_loc[0], card_loc[1], pixmap)
        painter.drawPixmap(card_loc[0], card_loc[1], self.border)
        if actually_is_golden:
            painter.drawPixmap(card_loc[0], card_loc[1], self.golden_overlay)
        self.update_card_stats(painter, int(slot), str(health), str(attack))

    def update_xp(self, painter: QPainter):
        xp = f"{self.player.level}.{self.player.experience}"
        card_loc = get_image_location(11)
        xp_center = tuple(map(operator.add, xp_loc, card_loc))
        xp_font = QFont(display_font_family, 35, weight=QFont.ExtraBold)
        metrics = QFontMetrics(xp_font)
        xp_orb_center = tuple(map(operator.sub, xp_center, (53, 65)))
        xp_text_center = tuple(map(operator.sub, xp_center, (metrics.horizontalAdvance(xp) / 2 - 2, -4)))
        painter.drawPixmap(QPoint(*xp_orb_center), QPixmap(asset_utils.get_asset("xp_orb.png")))
        path = QPainterPath()
        path.addText(QPoint(*xp_text_center), xp_font, xp)
        painter.setPen(QPen(QColor("black"), 1))
        painter.setBrush(QBrush("white"))
        painter.drawPath(path)

    def update_hero_health(self, painter: QPainter):
        card_loc = get_image_location(11)
        health_center = tuple(map(operator.add, hero_health_loc, card_loc))
        health_circle_center = tuple(map(operator.add, health_center, (-10, -10)))
        health_font = QFont(display_font_family, 35, weight=QFont.ExtraBold)
        metrics = QFontMetrics(health_font)
        health_text_center = tuple(map(operator.sub, health_circle_center, (metrics.horizontalAdvance(str(self.player.health)) / 2 - 65, -75)))
        painter.drawPixmap(QPoint(*health_circle_center), QPixmap(asset_utils.get_asset("hero_health.png")))
        path = QPainterPath()
        path.addText(QPoint(*health_text_center), health_font, str(self.player.health))
        painter.setPen(QPen(QColor("black"), 1))
        painter.setBrush(QBrush("white"))
        painter.drawPath(path)

    def draw_hero(self, painter: QPainter):
        if self.player:
            card_loc = get_image_location(11)
            path = asset_utils.get_card_path(self.player.heroid, False)
            pixmap = QPixmap(path)
            painter.setPen(QPen(QColor("white"), 1))
            painter.drawText(card_loc[0] + 75, card_loc[1] + 100, str(self.player.heroid))
            if not settings.get(settings.show_ids):
                painter.drawPixmap(card_loc[0], card_loc[1], pixmap)
            self.update_xp(painter)
            self.update_hero_health(painter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.scale(self.scale, self.scale)
        self.draw_hero(painter)
        if self.composition is not None:
            for action in self.composition:
                if action.zone != "Hero":
                    #  skip hero because we handle it elsewhere
                    #  spells broke
                    slot = action.slot
                    zone = action.zone
                    position = 10 if zone == 'Spell' else (7 + int(slot)) if zone == "Treasure" else slot
                    self.update_card(painter, position, action.content_id, action.cardhealth,
                                     action.cardattack, action.is_golden)
        else:
            painter.eraseRect(QRect(0, 0, 1350, 820))
            self.draw_hero(painter)
        last_seen_text = ""
        if self.last_seen is not None:
            if self.last_seen == 0:
                last_seen_text = "Last seen just now"
            elif self.last_seen > 0:
                last_seen_text = f"Last seen {self.current_round - self.last_seen}"
                if self.current_round - self.last_seen == 1:
                    last_seen_text += " turn ago"
                else:
                    last_seen_text += " turns ago"
        else:
            last_seen_text = "Not yet seen"
        painter.setPen(QPen(QColor("white"), 1))
        seen_font = QFont("Roboto")
        seen_font.setPixelSize(20)
        painter.setFont(seen_font)
        painter.drawText(10, 25, last_seen_text)