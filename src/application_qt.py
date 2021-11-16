import operator
import sys
import threading
from queue import Queue

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout, QLabel,
    QMainWindow,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)
from qt_material import apply_stylesheet

import application_constants
import asset_utils
import log_parser
from stats import PlayerStats

art_dim = (161, 204)
att_loc = (26, 181)
health_loc = (137, 181)
player_ids = []

round_font = QFont("Roboto", 18)


def get_image_location(position: int):
    if position < 4:
        x = (161 * position) + 300 + (position * 20)
        y = 0
    elif 4 <= position < 7:
        x = (161 * (position - 4)) + 300 + (161 / 2) + ((position - 4) * 20)
        y = 210
    elif 7 <= position < 9:
        x = (161 * (position - 7))
        y = 440 - 175
    elif position == 9:
        x = (161 / 2)
        y = 440
    elif position == 10:
        x = 900
        y = 440
    elif position == 11:
        x = 1090
        y = 440
    else:
        x = 0
        y = 0
    return x, y + 5


def get_player_index(player_id: str):
    if player_id not in player_ids:
        player_ids.append(player_id)
    return player_ids.index(player_id)


class SBBTracker(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SBBTracker")
        self.first_comp = BoardComp()
        self.ids_to_comps = {index: BoardComp() for index in range(0, 8)}
        self.round_indicator = QLabel("Waiting for match to start...")
        self.round_indicator.setFont(round_font)

        self.comp_tabs = QTabWidget()
        self.comp_tabs.setStyleSheet("QTabBar{ text-transform: none; }")
        for index in self.ids_to_comps:
            self.comp_tabs.addTab(self.ids_to_comps[index], f"Player{index}")

        comps_widget = QWidget()
        layout = QVBoxLayout(comps_widget)
        layout.addWidget(self.round_indicator)
        layout.addWidget(self.comp_tabs)

        main_tabs = QTabWidget()
        main_tabs.setStyleSheet("QTabBar{ text-transform: none; }")
        main_tabs.addTab(comps_widget, "Board Comps")
        main_tabs.addTab(QWidget(), "Health Graph")
        main_tabs.addTab(MatchHistory(), "Match History")
        main_tabs.addTab(QWidget(), "Stats Graphs")

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(QAction("&Export stats", self))
        file_menu.addAction(QAction("&Delete stats", self))
        menu_bar.addMenu("&Help")
        menu_bar.addMenu("&About")

        menu_bar.setCornerWidget(QPushButton(QPixmap("../assets/icons/discord.png"), "Discord"))

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        # main_layout.addWidget(menu_bar)
        main_layout.addWidget(main_tabs)

        self.setCentralWidget(main_widget)

        self.setFixedSize(QSize(1350, 820))

    def get_comp(self, index: int):
        return self.ids_to_comps[index]

    def update_round_num(self, round_number):
        self.round_indicator.setText(f"Turn {round_number}")
        self.round_indicator.update()

    def update_player(self, player, round_number):
        index = get_player_index(player.playerid)
        self.comp_tabs.setTabText(index, player.heroname)
        comp = self.get_comp(index)
        comp.player = player
        comp.current_round = round_number
        comp.update()

    def update_comp(self, player_id, player, round_number):
        index = get_player_index(player_id)
        comp = self.get_comp(index)
        comp.composition = player
        comp.last_seen = round_number
        comp.update()


class BoardComp(QWidget):
    def __init__(self):
        super().__init__()
        self.composition = None
        self.golden_overlay = QPixmap("../assets/golden_overlay.png")
        self.border = QPixmap("../assets/neutral_border.png")
        self.last_seen = None
        self.current_round = 0
        self.player = None

    def update_card_stats(self, painter: QPainter, slot: int, health: str, attack: str):
        card_location = get_image_location(slot)
        att_center = tuple(map(operator.add, att_loc, card_location))
        health_center = tuple(map(operator.add, health_loc, card_location))
        att_circle_center = tuple(map(operator.sub, att_center, (30, 40)))
        health_circle_center = tuple(map(operator.sub, health_center, (30, 40)))
        font = QFont("Impact", 25, QFont.ExtraBold)
        metrics = QFontMetrics(font)
        att_text_center = tuple(map(operator.sub, att_center, (metrics.horizontalAdvance(attack) / 2, -4)))
        health_text_center = tuple(map(operator.sub, health_center, (metrics.horizontalAdvance(health) / 2, -4)))
        if attack:
            if slot < 7:
                painter.drawPixmap(QPoint(*att_circle_center), QPixmap("../assets/attack_orb.png"))  # '#856515'))
                # graph.draw_image("../assets/attack_orb.png", location=att_circle_center)
                path = QPainterPath()
                path.addText(QPoint(*att_text_center), font, attack)
                painter.setPen(QPen(QColor("black"), 1))
                painter.setBrush(QBrush("white"))
                painter.drawPath(path)
        if health:
            if slot < 7 or slot == 11:
                painter.drawPixmap(QPoint(*health_circle_center), QPixmap("../assets/health_orb.png"))  # '#851717'))
                # graph.draw_image("../assets/health_orb.png", location=health_circle_center)
                path = QPainterPath()
                path.addText(QPoint(*health_text_center), font, health)
                painter.setPen(QPen(QColor("black"), 1))
                painter.setBrush(QBrush("white"))
                painter.drawPath(path)

    def update_card(self, painter: QPainter, slot, cardname: str, content_id: str, health: str,
                    attack: str, is_golden):
        card_loc = get_image_location(int(slot))
        actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
        path = asset_utils.get_card_path(cardname, content_id, actually_is_golden)
        pixmap = QPixmap(path)
        painter.drawPixmap(card_loc[0], card_loc[1], pixmap)
        painter.drawPixmap(card_loc[0], card_loc[1], self.border)
        if actually_is_golden:
            painter.drawPixmap(card_loc[0], card_loc[1], self.golden_overlay)
        # painter.drawPixmap(card_loc[0], card_loc[1], self.border)
        self.update_card_stats(painter, int(slot), str(health), str(attack))

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.composition is not None:
            used_slots = []
            for action in self.composition:
                slot = action.slot
                zone = action.zone
                position = 10 if zone == 'Spell' else (7 + int(slot)) if zone == "Treasure" else slot
                self.update_card(painter, position, action.cardname, action.content_id, action.cardhealth,
                                 action.cardattack, action.is_golden)
                used_slots.append(str(position))
            if self.player:
                self.update_card(painter, 11, self.player.heroname, self.player.heroid, self.player.health, "", False)
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
            painter.setFont(QFont("Roboto", 12))
            painter.drawText(5, 20, last_seen_text)
        else:
            painter.eraseRect(QRect(0, 0, 1350, 820))


class MatchHistory(QWidget):
    def __init__(self):
        super().__init__()
        self.match_history_table = QTableWidget(application_constants.stats_per_page, 4)
        self.stats = PlayerStats()

        self.match_history_table.setHorizontalHeaderLabels(["Starting Hero", "Ending Hero", "Place", "+/-MMR"])
        self.match_history_table.setColumnWidth(0, 130)
        self.match_history_table.setColumnWidth(1, 120)
        history = self.stats.get_page(1)
        for row in range(len(history)):
            for column in range(len(history[0])):
                self.match_history_table.setItem(row, column, QTableWidgetItem(str((history[row][column]))))
        paged_table = QWidget()
        paged_table.setMaximumWidth(533)
        paged_layout = QVBoxLayout(paged_table)
        paged_layout.addWidget(self.match_history_table)

        buttons_widget = QWidget()
        page_buttons = QHBoxLayout(buttons_widget)
        page_buttons.addWidget(QPushButton("Prev"))
        page_buttons.addWidget(QLabel("Page: 1"), alignment=Qt.AlignCenter | Qt.AlignVCenter)
        page_buttons.addWidget(QPushButton("Next"))
        paged_layout.addWidget(buttons_widget)
        paged_table.resize(200, paged_table.height())
        tab_layout = QHBoxLayout(self)
        tab_layout.addWidget(paged_table)
        tab_layout.addWidget(QTableWidget(40, 5))


def log_queue(app: SBBTracker):
    queue = Queue()
    threading.Thread(target=log_parser.run,
                     args=(
                         queue,
                         "../data/source/storybookbrawl.com/storybookbrawl/version/2021-11-14/source/Player.log"),
                     daemon=True).start()
    round_number = 0
    while True:
        update = queue.get()
        job = update.job
        state = update.state
        if job == log_parser.JOB_NEWGAME:
            # window[Keys.ReattachButton.value].update(visible=False)
            for player_id in player_ids:
                index = get_player_index(player_id)
                board_comp = app.get_comp(index)
                board_comp.composition = None
                board_comp.update()

            player_ids.clear()
            # names_to_health.clear()
            # ids_to_heroes.clear()
            current_player = None
            round_number = 0
            app.update_round_num(0)
        elif job == log_parser.JOB_INITCURRENTPLAYER:
            # current_player = values[event]
            pass
        elif job == log_parser.JOB_ROUNDINFO:
            round_number = state.round_num
            app.update_round_num(round_number)
        elif job == log_parser.JOB_PLAYERINFO:
            app.update_player(state, round_number)
        elif job == log_parser.JOB_BOARDINFO:
            for player_id in state:
                # index = get_player_index(player_id)
                app.update_comp(player_id, state[player_id], round_number)
                # window[app.get_player_round_key(index)].update(f"Last seen round: {round_number}")
        elif job == log_parser.JOB_ENDCOMBAT:
            # if health_fig_agg is not None:
            #     graphs.delete_fig_agg(health_fig_agg)
            # health_fig_agg = graphs.draw_matplotlib_figure(window[Keys.HealthGraph.value].TKCanvas,
            #                                                graphs.make_health_graph(names_to_health, ids_to_heroes))
            # window.refresh()
            pass
        elif job == log_parser.JOB_ENDGAME:
            pass
            # player = values[event]
            # if player:
            #     place = player.place if int(player.health) <= 0 else "1"
            #   player_stats.update_stats(asset_utils.get_card_art_name(current_player.heroid, current_player.heroname),
            #                               asset_utils.get_card_art_name(player.heroid, player.heroname), place,
            #                               player.mmr)


app = QApplication(sys.argv)
apply_stylesheet(app, theme='dark_teal.xml')
window = SBBTracker()
window.show()

# os.remove(log_parser.offsetfile)
threading.Thread(target=log_queue, args=(window,), daemon=True).start()

app.exec()
