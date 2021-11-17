import json
import logging
import operator
import os
import sys
import threading
from collections import defaultdict
from datetime import date
from pathlib import Path
from queue import Queue

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from PySide6.QtCore import QObject, QPoint, QRect, QSize, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QFontMetrics, QPainter, QPainterPath, QPen, \
    QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication,
    QComboBox, QErrorMessage, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow,
    QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from qt_material import apply_stylesheet

import asset_utils
import graphs
import log_parser
import stats
import update_check

matplotlib.use('Qt5Agg')
if not stats.sbbtracker_folder.exists():
    stats.sbbtracker_folder.mkdir()
logging.basicConfig(filename=stats.sbbtracker_folder.joinpath("sbbtracker.log"), filemode="w", format='%(name)s - %(levelname)s - %(message)s')

art_dim = (161, 204)
att_loc = (26, 181)
health_loc = (137, 181)

default_bg_color = "#31363b"
sns.set_style("darkgrid", {"axes.facecolor": default_bg_color})

plt.rcParams.update({'text.color': "white",
                     'xtick.color': 'white',
                     'ytick.color': 'white',
                     'figure.facecolor': default_bg_color,
                     'axes.labelcolor': "white"})

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


def update_table(table: QTableWidget, data: list[list]):
    for row in range(len(data)):
        for column in range(len(data[0])):
            table.setItem(row, column, QTableWidgetItem(str((data[row][column]))))


settings_file = stats.sbbtracker_folder.joinpath("settings.json")


def load_settings():
    if settings_file.exists():
        with open(settings_file, "r") as json_file:
            return json.load(json_file)
    else:
        return {}


settings = load_settings()


def save_settings():
    with open(settings_file, "w") as json_file:
        json.dump(settings, json_file)


default_dates = {
    "All": ("1970-01-01", date.today().strftime("%Y-%m-%d")),
    "Patch 64.2": ("2021-11-08", date.today().strftime("%Y-%m-%d")),
    "Patch 63.4": ("2021-10-18", "2021-11-08")
}

custom_dates = settings["custom_dates"] if "custom_dates" in settings else {}


class LogSignals(QObject):
    round_update = Signal(int)
    player_update = Signal(object, int)
    comp_update = Signal(str, object, int)
    stats_update = Signal(str, object)
    health_update = Signal(dict, dict)
    new_game = Signal()


class LogThread(QThread):
    def __init__(self, *args, **kwargs):
        super(LogThread, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.args = args
        self.kwargs = kwargs
        self.signals = LogSignals()

    def run(self):
        queue = Queue()
        threading.Thread(target=log_parser.run,
                         args=(
                             queue,),
                         daemon=True).start()
        round_number = 0
        current_player = None
        names_to_health = defaultdict(dict)
        ids_to_heroes = {}
        while True:
            update = queue.get()
            job = update.job
            state = update.state
            if job == log_parser.JOB_NEWGAME:
                # window[Keys.ReattachButton.value].update(visible=False)
                names_to_health.clear()
                ids_to_heroes.clear()
                current_player = None
                round_number = 0
                self.signals.new_game.emit()
                self.signals.round_update.emit(0)
            elif job == log_parser.JOB_INITCURRENTPLAYER:
                current_player = state
                self.signals.player_update.emit(state, round_number)
            elif job == log_parser.JOB_ROUNDINFO:
                round_number = state.round_num
                self.signals.round_update.emit(round_number)
            elif job == log_parser.JOB_PLAYERINFO:
                self.signals.player_update.emit(state, round_number)
                names_to_health[state.playerid][round_number] = state.health
                ids_to_heroes[state.playerid] = asset_utils.get_card_art_name(state.heroid, state.heroname)
            elif job == log_parser.JOB_BOARDINFO:
                for player_id in state:
                    self.signals.comp_update.emit(player_id, state[player_id], round_number)
            elif job == log_parser.JOB_ENDCOMBAT:
                self.signals.health_update.emit(names_to_health, ids_to_heroes)
                # pass
            elif job == log_parser.JOB_ENDGAME:
                if state:
                    self.signals.stats_update.emit(asset_utils.get_card_art_name(current_player.heroid,
                                                                                 current_player.heroname), state)


class UpdateCheckSignals(QObject):
    github_update = Signal()


class UpdateCheckThread(QThread):
    def __init__(self, *args, **kwargs):
        super(UpdateCheckThread, self).__init__()
        self.args = args
        self.kwargs = kwargs
        self.signals = UpdateCheckSignals()

    def run(self):
        update_check.run()
        # wait for an update
        self.signals.github_update.emit()


class SBBTracker(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SBBTracker")
        self.first_comp = BoardComp()
        self.ids_to_comps = {index: BoardComp() for index in range(0, 8)}
        self.round_indicator = QLabel("Waiting for match to start...")
        self.round_indicator.setFont(round_font)
        self.player_stats = stats.PlayerStats()
        self.player_ids = []

        self.comp_tabs = QTabWidget()
        for index in self.ids_to_comps:
            self.comp_tabs.addTab(self.ids_to_comps[index], f"Player{index}")

        self.reset_button = QPushButton("Reattach to Storybook Brawl")
        self.reset_button.setFixedSize(300, 25)
        self.reset_button.clicked.connect(self.reattatch_to_log)
        round_widget = QWidget()
        round_layout = QHBoxLayout(round_widget)
        round_layout.addWidget(self.round_indicator)
        round_layout.addWidget(self.reset_button)

        comps_widget = QWidget()
        layout = QVBoxLayout(comps_widget)
        layout.addWidget(round_widget)
        layout.addWidget(self.comp_tabs)

        self.match_history = MatchHistory(self.player_stats)
        self.health_graph = HealthGraph()
        self.stats_graph = StatsGraph(self.player_stats)

        main_tabs = QTabWidget()
        main_tabs.addTab(comps_widget, "Board Comps")
        main_tabs.addTab(self.health_graph, "Health Graph")
        main_tabs.addTab(self.match_history, "Match History")
        main_tabs.addTab(self.stats_graph, "Stats Graphs")

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        export_action = QAction("&Export stats", self)
        export_action.triggered.connect(self.export_csv)
        delete_action = QAction("&Delete stats", self)
        delete_action.triggered.connect(self.delete_stats)
        file_menu.addAction(export_action)
        file_menu.addAction(delete_action)
        help_menu = menu_bar.addMenu("&Help")
        bug_action = QAction("&Report a bug", self)
        bug_action.triggered.connect(self.open_issues)
        help_menu.addAction(bug_action)

        discord_action = QAction(QPixmap("../assets/icons/discord.png"), "&Discord", menu_bar)
        menu_bar.addAction(discord_action)
        discord_action.triggered.connect(self.open_discord)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(main_tabs)

        self.setCentralWidget(main_widget)

        self.setFixedSize(QSize(1350, 840))

        self.github_updates = UpdateCheckThread()
        self.github_updates.signals.github_update.connect(self.github_update_popup)

        self.log_updates = LogThread()
        self.log_updates.signals.comp_update.connect(self.update_comp)
        self.log_updates.signals.player_update.connect(self.update_player)
        self.log_updates.signals.round_update.connect(self.update_round_num)
        self.log_updates.signals.stats_update.connect(self.update_stats)
        self.log_updates.signals.health_update.connect(self.health_graph.update_graph)
        self.log_updates.signals.new_game.connect(self.new_game)

        self.log_updates.start()
        self.github_updates.start()

    def get_player_index(self, player_id: str):
        if player_id not in self.player_ids:
            self.player_ids.append(player_id)
        return self.player_ids.index(player_id)

    def new_game(self):
        self.player_ids.clear()
        for comp in self.ids_to_comps.values():
            comp.composition = None
            comp.player = None

    def get_comp(self, index: int):
        return self.ids_to_comps[index]

    def update_round_num(self, round_number):
        self.round_indicator.setText(f"Turn {round_number}")
        self.round_indicator.update()
        self.reset_button.hide()

    def update_player(self, player, round_number):
        index = self.get_player_index(player.playerid)
        real_hero_name = asset_utils.get_card_art_name(player.heroid, player.heroname)
        title = f"{real_hero_name}" if player.health > 0 else f"{real_hero_name} *DEAD*"
        self.comp_tabs.setTabText(index, title)
        comp = self.get_comp(index)
        comp.player = player
        comp.current_round = round_number
        self.update()

    def update_comp(self, player_id, player, round_number):
        index = self.get_player_index(player_id)
        comp = self.get_comp(index)
        comp.composition = player
        comp.last_seen = round_number
        self.update()

    def update_stats(self, starting_hero: str, player):
        place = player.place if int(player.health) <= 0 else "1"
        self.player_stats.update_stats(starting_hero, asset_utils.get_card_art_name(player.heroid, player.heroname),
                                       place, player.mmr)
        self.match_history.update_history_table()
        self.match_history.update_stats_table()

    def open_url(self, url_string: str):
        url = QUrl(url_string)
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, 'Open Url', 'Could not open url')

    def open_discord(self):
        self.open_url('https://discord.com/invite/2AJctfj239')

    def open_github_release(self):
        self.open_url("https://github.com/SBBTracker/SBBTracker/releases/latest")

    def open_issues(self):
        self.open_url("https://github.com/SBBTracker/SBBTracker/issues")

    def github_update_popup(self):
        reply = QMessageBox.question(self, "New update available!",
                                     "New version available!\nWould you like to go to the download page?")
        if reply == QMessageBox.Yes:
            self.open_github_release()

    def export_csv(self):
        filepath, filetype = QFileDialog.getSaveFileName(parent=None, caption='Export to .csv',
                                                         dir=str(Path(os.environ['USERPROFILE']).joinpath("Documents")),
                                                         filter="Text CSV (*.csv)")
        self.player_stats.export(Path(filepath))

    def delete_stats(self):
        reply = QMessageBox.question(self, "Delete all Stats", "Do you want to delete *ALL* saved stats?")
        if reply == QMessageBox.Yes:
            self.player_stats.delete()

    def reattatch_to_log(self):
        reply = QMessageBox.question(self, "Reattach?",
                                     """Would you like to reattach to the Storybook Brawl log?
This can fix the tracker not connecting to the game.
This will import all games played since SBB was last opened.
(you can restart the game to avoid this)""")
        if reply == QMessageBox.Yes:
            try:
                os.remove(log_parser.offsetfile)
            except Exception as e:
                logging.warning(str(e))
        self.reset_button.hide()
        self.update()

    def closeEvent(self, *args, **kwargs):
        super(QMainWindow, self).closeEvent(*args, **kwargs)
        self.github_updates.terminate()
        self.log_updates.terminate()
        self.player_stats.save()


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
                painter.drawPixmap(QPoint(*att_circle_center), QPixmap("../assets/attack_orb.png"))
                path = QPainterPath()
                path.addText(QPoint(*att_text_center), font, attack)
                painter.setPen(QPen(QColor("black"), 1))
                painter.setBrush(QBrush("white"))
                painter.drawPath(path)
        if health:
            if slot < 7 or slot == 11:
                painter.drawPixmap(QPoint(*health_circle_center), QPixmap("../assets/health_orb.png"))
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
        if self.player:
            self.update_card(painter, 11, self.player.heroname, self.player.heroid, self.player.health, "", False)


class MatchHistory(QWidget):
    def __init__(self, player_stats: stats.PlayerStats):
        super().__init__()
        self.player_stats = player_stats
        self.match_history_table = QTableWidget(stats.stats_per_page, 4)
        self.page = 1
        self.display_starting_hero = True
        self.filter = "All"
        self.match_history_table.setHorizontalHeaderLabels(["Starting Hero", "Ending Hero", "Place", "+/- MMR"])
        self.match_history_table.setColumnWidth(0, 130)
        self.match_history_table.setColumnWidth(1, 120)
        self.match_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.match_history_table.setFocusPolicy(Qt.NoFocus)
        self.match_history_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.match_history_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        paged_table = QWidget()
        paged_table.setMaximumWidth(533)
        paged_layout = QVBoxLayout(paged_table)
        paged_layout.addWidget(self.match_history_table)

        buttons_widget = QWidget()
        page_buttons = QHBoxLayout(buttons_widget)
        prev_button = QPushButton("<")
        prev_button.clicked.connect(lambda: self.page_down(prev_button))
        prev_button.setMaximumWidth(50)
        next_button = QPushButton(">")
        next_button.setMaximumWidth(50)
        next_button.clicked.connect(lambda: self.page_up(next_button))

        self.page_indicator = QLabel("1")
        self.page_indicator.setFont(QFont("Roboto", 16))

        page_buttons.addWidget(prev_button, alignment=Qt.AlignRight)
        page_buttons.addWidget(self.page_indicator, alignment=Qt.AlignCenter | Qt.AlignVCenter)
        page_buttons.addWidget(next_button, alignment=Qt.AlignLeft)
        page_buttons.setSpacing(0)

        paged_layout.addWidget(buttons_widget)
        paged_table.resize(200, paged_table.height())

        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_table = QTableWidget(len(asset_utils.hero_ids), 5)
        self.stats_table.setHorizontalHeaderLabels(stats.headings)
        self.stats_table.setColumnWidth(0, 130)
        self.stats_table.setColumnWidth(1, 130)
        self.stats_table.setColumnWidth(2, 130)

        filter_widget = QWidget()
        toggle_hero = QPushButton("Show Ending Heroes")
        toggle_hero.clicked.connect(lambda: self.toggle_heroes(toggle_hero))
        all_dates = default_dates | custom_dates
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(all_dates.keys())
        self.filter_combo.activated.connect(self.filter_stats)
        filter_label = QLabel("Filter Stats:")
        filter_label.setFont(QFont("Roboto", 16))

        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.addWidget(toggle_hero, alignment=Qt.AlignLeft)
        filter_layout.addWidget(filter_label, alignment=Qt.AlignRight)
        filter_layout.addWidget(self.filter_combo, alignment=Qt.AlignLeft)

        stats_layout.addWidget(filter_widget)
        stats_layout.addWidget(self.stats_table)

        tables_layout = QHBoxLayout(self)
        tables_layout.addWidget(paged_table)
        tables_layout.addWidget(stats_widget)

        self.update_history_table()
        self.update_stats_table()

    def page_up(self, button: QPushButton):
        if self.page < self.player_stats.get_num_pages():
            self.page += 1
        button.setDisabled(self.page == 1)
        self.update_history_table()

    def page_down(self, button: QPushButton):
        if self.page > 1:
            self.page -= 1
        button.setDisabled(self.page == self.player_stats.get_num_pages())
        self.update_history_table()

    def update_history_table(self):
        history = self.player_stats.get_page(self.page)
        update_table(self.match_history_table, history)
        start_num = (self.page - 1) * stats.stats_per_page + 1
        self.match_history_table.setVerticalHeaderLabels([str(i) for i in range(start_num,
                                                                                start_num + stats.stats_per_page + 1)])
        self.page_indicator.setText(f'Page {self.page} of {self.player_stats.get_num_pages()}')

    def update_stats_table(self):
        all_dates = default_dates | custom_dates
        hero_stats = self.player_stats.filter(*all_dates[self.filter])
        chosen_stats = hero_stats[int(not self.display_starting_hero)]
        update_table(self.stats_table, chosen_stats)

    def toggle_heroes(self, button: QPushButton):
        self.display_starting_hero = not self.display_starting_hero
        self.update_stats_table()
        text = "Show Ending Heroes" if self.display_starting_hero else "Show Starting Heroes"
        button.setText(text)

    def filter_stats(self):
        self.filter = self.filter_combo.currentText()
        self.update_stats_table()


class HealthGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.figure = None
        self.canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.ax = self.canvas.figure.subplots()
        self.layout.addWidget(self.canvas)

    def update_graph(self, names_to_health, ids_to_heroes):
        self.ax.cla()
        self.figure = graphs.make_health_graph(names_to_health, ids_to_heroes, self.ax)
        self.canvas.draw()


class StatsGraph(QWidget):
    def __init__(self, player_stats: stats.PlayerStats):
        super().__init__()
        self.player_stats = player_stats

        self.figure = None
        self.canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.ax = self.canvas.figure.subplots()

        self.graph_selection = QComboBox()
        self.graph_selection.setMaximumWidth(200)
        self.graph_selection.addItems([graphs.matches_per_hero, graphs.mmr_change])
        self.graph_selection.activated.connect(self.update_graph)
        self.selection = graphs.mmr_change

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.graph_selection)
        self.layout.addWidget(self.canvas)

        self.update_graph()

    def update_graph(self):
        self.selection = self.graph_selection.currentText()
        self.ax.cla()
        self.figure = graphs.make_stats_graph(self.player_stats.df, self.selection, self.ax)
        self.canvas.draw()


app = QApplication(sys.argv)
apply_stylesheet(app, theme='dark_teal.xml')
stylesheet = app.styleSheet()
app.setStyleSheet(stylesheet + "QTabBar{ text-transform: none; }")
window = SBBTracker()
window.show()

sys.exit(app.exec())
