import operator

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from sbbtracker import paths, settings
from sbbtracker.languages import tr
from sbbtracker.utils import asset_utils

art_dim = (161, 204)
att_loc = (26, 181)
health_loc = (137, 181)
# 287 x 384
xp_loc = (220, 10)
hero_health_loc = (210, 280)
hero_quest_loc = (230, 134)
display_font_family = "Impact" if paths.os_name == "Windows" else "Ubuntu Bold"


def draw_text(painter, location, text, font):
    path = QPainterPath()
    path.addText(QPoint(*location), font, text)
    painter.setPen(QPen(QColor("black"), 2))
    painter.setBrush(QBrush("white"))
    painter.drawPath(path)


class BoardComp(QWidget):
    def __init__(self, parent, scale=1):
        super().__init__(parent)
        self.composition = None

        self.golden_overlay = QPixmap(asset_utils.get_asset("golden_overlay.png"))
        self.neutral_border = QPixmap(asset_utils.get_asset("neutral_border.png"))
        self.good_border = QPixmap(asset_utils.get_asset("good_border.png"))
        self.evil_border = QPixmap(asset_utils.get_asset("evil_border.png"))
        self.heart_pixmap = QPixmap(asset_utils.get_asset("hero_health.png"))
        self.xp_orb_pixmap = QPixmap(asset_utils.get_asset("xp_orb.png"))
        self.quest_pixmap = QPixmap(asset_utils.get_asset("quest_scroll.png"))
        self.attack_orb_pixmap = QPixmap(asset_utils.get_asset("attack_orb.png"))
        self.health_orb_pixmap = QPixmap(asset_utils.get_asset("health_orb.png"))

        self.last_seen = None
        self.current_round = 0
        self.player = None
        self.scale = scale
        self.custom_message = None

        self.number_display_font = QFont(display_font_family, 30, weight=QFont.Black)

    def get_image_location(self, position: int):
        if position < 4:  # slots 1 - 4
            x = (161 * position) + 300 + (position * 20)
            y = 0
        elif 4 <= position < 7:  # slots 5 - 7
            x = (161 * (position - 4)) + 300 + (161 / 2) + ((position - 4) * 20)
            y = 210
        elif 7 <= position < 9:  # treasures 1 + 2
            x = (161 * (position - 7)) + 20
            y = 440 - 175
        elif position == 9:  # treasure 3
            x = (161 / 2) + 20
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
        return x, y + 20

    def update_card_stats(self, painter: QPainter, slot: int, health: str, attack: str):
        card_location = self.get_image_location(slot)
        att_center = tuple(map(operator.add, att_loc, card_location))
        health_center = tuple(map(operator.add, health_loc, card_location))
        att_circle_center = tuple(map(operator.sub, att_center, (30, 40)))
        health_circle_center = tuple(map(operator.sub, health_center, (30, 40)))

        metrics = QFontMetrics(self.number_display_font)
        att_text_center = tuple(map(operator.sub, att_center, (metrics.horizontalAdvance(attack) / 2 - 2, -7)))
        health_text_center = tuple(map(operator.sub, health_center, (metrics.horizontalAdvance(health) / 2 - 2, -7)))
        if attack:
            if slot < 7:
                painter.drawPixmap(QPoint(*att_circle_center), self.attack_orb_pixmap)
                draw_text(painter, att_text_center, attack, self.number_display_font)
        if health:
            if slot < 7 or slot == 11:
                painter.drawPixmap(QPoint(*health_circle_center), self.health_orb_pixmap)
                draw_text(painter, health_text_center, health, self.number_display_font)

    def update_card(self, painter: QPainter, slot, content_id: str, health: str,
                    attack: str, is_golden, tribes, counter):
        card_loc = self.get_image_location(int(slot))
        actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
        path = asset_utils.get_card_path(content_id, actually_is_golden)
        pixmap = QPixmap(path)
        painter.setPen(QPen(QColor("white"), 1))
        painter.drawText(card_loc[0] + 75, card_loc[1] + 100, str(content_id))
        if not settings.get(settings.show_ids):
            painter.drawPixmap(card_loc[0], card_loc[1], pixmap)
        if "Good" in tribes:
            border = self.good_border
        elif "Evil" in tribes:
            border = self.evil_border
        else:
            border = self.neutral_border
        if actually_is_golden:
            painter.drawPixmap(card_loc[0], card_loc[1], self.golden_overlay)
        if 7 > int(slot) or int(slot) > 9:
            painter.drawPixmap(card_loc[0], card_loc[1], border)
        self.update_card_stats(painter, int(slot), str(health), str(attack))
        if int(counter) > 0:
            quest_loc = tuple(map(operator.add, card_loc, (120, -10)))
            self.draw_quest(painter, counter, quest_loc, .20)

    def draw_xp(self, painter: QPainter, location=None, xp=None):
        if xp is None:
            xp = f"{self.player.level}.{self.player.experience}"
        card_loc = self.get_image_location(11)
        xp_center = location if location is not None else tuple(map(operator.add, xp_loc, card_loc))
        xp_font = QFont(display_font_family, 35, weight=QFont.ExtraBold)
        metrics = QFontMetrics(xp_font)
        xp_text_center = tuple(map(operator.sub, xp_center,
                                   (metrics.horizontalAdvance(xp) / 2 - self.xp_orb_pixmap.width() / 2,
                                    -metrics.boundingRect(xp).height() / 3 - self.xp_orb_pixmap.height() / 2)))
        painter.drawPixmap(QPoint(*xp_center), self.xp_orb_pixmap)
        draw_text(painter, xp_text_center, str(xp), xp_font)

    def draw_health(self, painter: QPainter, location=None, health=None):
        if health is None:
            health = self.player.health
        card_loc = self.get_image_location(11)
        health_center = location if location is not None else tuple(map(operator.add, hero_health_loc, card_loc))
        health_font = QFont(display_font_family, 40, weight=QFont.ExtraBold)
        metrics = QFontMetrics(health_font)
        health_text_center = tuple(map(operator.sub, health_center, (metrics.horizontalAdvance(str(health)) / 2 -
                                       self.heart_pixmap.width() / 2,
                                       -metrics.boundingRect(str(health)).height() / 3 - self.heart_pixmap.height() / 2 + 3)))
        painter.drawPixmap(QPoint(*health_center), self.heart_pixmap)
        draw_text(painter, health_text_center, str(health), health_font)

    def draw_quest(self, painter: QPainter, counter, location, scale):
        card_loc = self.get_image_location(11)
        quest_center = location if location is not None else tuple(map(operator.add, xp_loc, card_loc))
        quest_font = QFont(display_font_family, int(170 * scale), weight=QFont.ExtraBold)
        metrics = QFontMetrics(quest_font)
        pixmap = self.quest_pixmap.scaled(self.quest_pixmap.size() * scale)
        quest_text_center = tuple(map(operator.sub, quest_center,
                                   (metrics.horizontalAdvance(counter) / 2 - pixmap.width() * 1 / 2,
                                    -metrics.boundingRect(counter).height() / 3 - pixmap.height() / 2)))
        painter.drawPixmap(QPoint(*quest_center), pixmap)
        draw_text(painter, quest_text_center, str(counter), quest_font)

    def draw_hero(self, painter: QPainter):
        if self.player:
            card_loc = self.get_image_location(11)
            path = asset_utils.get_card_path(self.player.heroid, False)
            pixmap = QPixmap(path)
            painter.setPen(QPen(QColor("white"), 1))
            painter.drawText(card_loc[0] + 75, card_loc[1] + 100, str(self.player.heroid))
            if not settings.get(settings.show_ids):
                painter.drawPixmap(card_loc[0], card_loc[1], pixmap)
            self.draw_xp(painter)
            self.draw_health(painter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        painter.scale(self.scale, self.scale)
        painter.eraseRect(QRect(0, 0, 1350, 820))
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
                                     action.cardattack, action.is_golden, action.subtypes, action.counter)
                elif action.zone == "Hero" and int(action.counter) > 0:
                    hero_loc = self.get_image_location(11)
                    quest_loc = tuple(map(operator.add, hero_loc, hero_quest_loc))
                    self.draw_quest(painter, action.counter, quest_loc, .30)
        if self.custom_message:
            last_seen_text = self.custom_message
        else:
            last_seen_text = ""
            if self.last_seen is not None:
                if self.last_seen == 0:
                    last_seen_text = tr("Last seen just now")
                elif self.last_seen > 0:
                    if self.current_round - self.last_seen == 1:
                        last_seen_text += tr("Last seen 1 turn ago")
                    else:
                        last_seen_text += tr("Last seen {0} turns ago").format(self.current_round - self.last_seen)
            else:
                last_seen_text = tr("Not yet seen")
        painter.setPen(QPen(QColor("white"), 1))
        seen_font = QFont("Roboto")
        seen_font.setPixelSize(20)
        painter.setFont(seen_font)
        painter.drawText(10, 25, last_seen_text)

