import calendar
import datetime
import json
import logging
import operator
import os
import platform
import shutil
import sys
import threading
from collections import defaultdict
from datetime import date
from pathlib import Path
from queue import Queue
from tempfile import NamedTemporaryFile

import matplotlib

# matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from PySide6 import QtGui
from PySide6.QtCore import QObject, QPoint, QRect, QSettings, QSize, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QCursor, QDesktopServices, QFont, QFontMetrics, QGuiApplication, \
    QIcon, \
    QIntValidator, \
    QPainter, QPainterPath, \
    QPen, \
    QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication,
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QErrorMessage, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit, QMainWindow,
    QMenuBar, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSlider, QSpinBox, QStyle, QTabWidget, QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from qt_material import apply_stylesheet

import asset_utils
import graphs
import log_parser
import stats
import updater
import version

if not stats.sbbtracker_folder.exists():
    stats.sbbtracker_folder.mkdir()
logging.basicConfig(filename=stats.sbbtracker_folder.joinpath("sbbtracker.log"), filemode="w",
                    format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

art_dim = (161, 204)
att_loc = (26, 181)
health_loc = (137, 181)
xp_loc = (137, 40)

default_bg_color = "#31363b"
default_bg_color_rgb = "49, 54, 59"
sns.set_style("darkgrid", {"axes.facecolor": default_bg_color})

plt.rcParams.update({'text.color': "white",
                     'xtick.color': 'white',
                     'ytick.color': 'white',
                     'figure.facecolor': default_bg_color,
                     'axes.labelcolor': "white"})

round_font = QFont("Roboto", 18)
display_font_family = "Impact" if log_parser.os_name == "Windows" else "Ubuntu Bold"


class Settings:
    boardcomp_transparency = "boardcomp-transparency"
    save_stats = "save-stats"
    monitor = "monitor"
    filter_ = "filter"
    enable_overlay = "enable-overlay"
    live_palette = "live-palette"
    matchmaking_only = "matchmaking-only"


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
        x = 850
        y = 440
    elif position == 11:
        x = 1040
        y = 440
    else:
        x = 0
        y = 0
    return x, y + 5


def round_to_xp(round_number: int):
    lvl = min(6, (round_number - 1) // 3 + 2)
    xp = (round_number - 1) % 3 if lvl != 6 else 0
    return "0.0" if round_number == 0 else f"{lvl}.{xp}"


def update_table(table: QTableWidget, data: list[list]):
    for row in range(len(data)):
        for column in range(len(data[0])):
            datum = (data[row][column])
            table.setItem(row, column, QTableWidgetItem(str(datum)))


settings_file = stats.sbbtracker_folder.joinpath("settings.json")


def load_settings():
    if settings_file.exists():
        try:
            with open(settings_file, "r") as json_file:
                return json.load(json_file)
        except Exception as e:
            logging.error("Couldn't load settings file!")
            logging.error(str(e))
    return {}


settings = load_settings()


def save_settings():
    with NamedTemporaryFile(delete=False, mode='w', newline='') as temp_file:
        json.dump(settings, temp_file)
        temp_name = temp_file.name
    try:
        with open(temp_name) as file:
            json.load(file)
        shutil.move(temp_name, settings_file)
    except:
        logging.error("Couldn't save settings correctly")


today = date.today()
_, days_this_month = calendar.monthrange(today.year, today.month)
first_day_this_month = today.replace(day=1)
last_day_this_month = today.replace(day=days_this_month)
last_day_prev_month = first_day_this_month - datetime.timedelta(days=1)
first_day_prev_month = last_day_prev_month.replace(day=1)

default_dates = {
    "All Matches": ("1970-01-01", today.isoformat()),
    "Latest Patch (64.2)": ("2021-11-08", today.isoformat()),
    "Previous Patch (63.4)": ("2021-10-18", "2021-11-08"),
    "Today": (today.isoformat(), today.isoformat()),
    "Last 7 days": ((today - datetime.timedelta(days=7)).isoformat(), today.isoformat()),
    "Last 30 days": ((today - datetime.timedelta(days=30)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
    "This month": (first_day_this_month.isoformat(), last_day_this_month.isoformat()),
    "Last month": (first_day_prev_month.isoformat(), last_day_prev_month.isoformat()),
}


class LogThread(QThread):
    round_update = Signal(int)
    player_update = Signal(object, int)
    comp_update = Signal(str, object, int)
    stats_update = Signal(str, object)
    player_info_update = Signal(graphs.LivePlayerStates)
    health_update = Signal(object)
    new_game = Signal(bool)

    def __init__(self, *args, **kwargs):
        super(LogThread, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.args = args
        self.kwargs = kwargs

    def run(self):
        queue = Queue()
        threading.Thread(target=log_parser.run,
                         args=(
                             queue,),
                         daemon=True).start()
        round_number = 0
        current_player = None
        states = graphs.LivePlayerStates()
        matchmaking = False
        while True:
            update = queue.get()
            job = update.job
            state = update.state
            if job == log_parser.JOB_MATCHMAKING:
                matchmaking = True
            elif job == log_parser.JOB_NEWGAME:
                states.clear()
                current_player = None
                round_number = 0
                self.new_game.emit(matchmaking)
                self.round_update.emit(0)
                matchmaking = False
            elif job == log_parser.JOB_INITCURRENTPLAYER:
                current_player = state
                self.player_update.emit(state, round_number)
            elif job == log_parser.JOB_ROUNDINFO:
                round_number = state.round_num
                self.round_update.emit(round_number)
            elif job == log_parser.JOB_PLAYERINFO:
                self.player_update.emit(state, round_number)
                xp = f"{state.level}.{state.experience}"
                states.update_player(state.playerid, round_number, state.health, xp,
                                     asset_utils.get_card_art_name(state.heroid, state.heroname))
            elif job == log_parser.JOB_BOARDINFO:
                for player_id in state:
                    self.comp_update.emit(player_id, state[player_id], round_number)
            elif job == log_parser.JOB_ENDCOMBAT:
                self.player_info_update.emit(states)
            elif job == log_parser.JOB_ENDGAME:
                if state and current_player:
                    self.stats_update.emit(asset_utils.get_card_art_name(current_player.heroid,
                                                                                 current_player.heroname), state)
            elif job == log_parser.JOB_HEALTHUPDATE:
                self.health_update.emit(state)


class SettingsWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.hide()
        self.main_window = main_window
        main_widget = QFrame()
        main_layout = QVBoxLayout(main_widget)
        general_settings = QWidget()
        overlay_settings = QWidget()
        about_tab = QWidget()
        settings_tabs = QTabWidget()
        settings_tabs.addTab(general_settings, "General")
        settings_tabs.addTab(overlay_settings, "Overlay")
        settings_tabs.addTab(about_tab, "About")

        self.setWindowIcon(QIcon(asset_utils.get_asset("icon.png")))
        self.setWindowTitle("Settings")

        about_layout = QVBoxLayout(about_tab)
        about_layout.addWidget(QLabel(f"SBBTracker v{version.__version__}"))
        about_layout.addStretch()

        general_layout = QFormLayout(general_settings)

        export_button = QPushButton("Export Stats")
        export_button.clicked.connect(main_window.export_csv)
        delete_button = QPushButton("Delete Stats")
        delete_button.clicked.connect(lambda: main_window.delete_stats(self))

        save_stats_checkbox = QCheckBox()
        save_stats_checkbox.setChecked(settings.setdefault(Settings.save_stats, True))
        save_stats_checkbox.stateChanged.connect(self.toggle_saving)

        self.graph_color_chooser = QComboBox()
        palettes = list(graphs.color_palettes.keys())
        self.graph_color_chooser.addItems(palettes)
        self.graph_color_chooser.setCurrentIndex(palettes.index(settings.get(Settings.live_palette, "vibrant")))
        self.graph_color_chooser.currentTextChanged.connect(main_window.live_graphs.set_color_palette)

        matchmaking_only_checkbox = QCheckBox()
        matchmaking_only_checkbox.setChecked(settings.setdefault(Settings.matchmaking_only, False))
        matchmaking_only_checkbox.setEnabled(save_stats_checkbox.checkState())
        matchmaking_only_checkbox.stateChanged.connect(self.toggle_matchmaking)

        save_stats_checkbox.stateChanged.connect(lambda state: matchmaking_only_checkbox.setEnabled(bool(state)))

        general_layout.addWidget(export_button)
        general_layout.addWidget(delete_button)
        general_layout.addRow("Save match results", save_stats_checkbox)
        general_layout.addRow("Ignore practice and group lobbies", matchmaking_only_checkbox)
        general_layout.addRow("Graph color palette", self.graph_color_chooser)

        overlay_layout = QFormLayout(overlay_settings)
        enable_overlay_checkbox = QCheckBox()
        enable_overlay_checkbox.setChecked(settings.setdefault(Settings.enable_overlay, False))
        enable_overlay_checkbox.stateChanged.connect(main_window.toggle_overlay)


        choose_monitor = QComboBox()
        monitors = QGuiApplication.screens()
        choose_monitor.addItems([f"Monitor {i + 1}" for i in range(0, len(monitors))])
        choose_monitor.setCurrentIndex(settings.setdefault(Settings.monitor, 1))
        choose_monitor.currentIndexChanged.connect(self.main_window.overlay.select_monitor)

        slider_editor = QHBoxLayout()
        self.transparency_slider = QSlider(Qt.Horizontal)
        self.transparency_editor = QLineEdit()
        saved_scaling = settings.setdefault(Settings.boardcomp_transparency, 0)
        self.transparency_slider.setValue(saved_scaling)
        self.transparency_slider.setMaximum(100)
        self.transparency_slider.setMinimum(0)
        self.transparency_slider.valueChanged.connect(lambda val: self.transparency_editor.setText(str(val)))
        self.transparency_editor.setValidator(QIntValidator(0, 200))
        self.transparency_editor.setText(str(saved_scaling))
        self.transparency_editor.textEdited.connect(
            lambda text: self.transparency_slider.setValue(int(text)) if text != '' else None)
        slider_editor.addWidget(self.transparency_slider)
        slider_editor.addWidget(self.transparency_editor)

        overlay_layout.addRow("Enable overlay", enable_overlay_checkbox)
        overlay_layout.addRow("Choose overlay monitor", choose_monitor)
        overlay_layout.addRow("Adjust overlay transparency", slider_editor)

        save_close_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        close_button = QPushButton("Cancel")
        close_button.clicked.connect(self.hide)
        save_close_layout.addStretch()
        save_close_layout.addWidget(self.save_button)
        save_close_layout.addWidget(close_button)

        main_layout.addWidget(settings_tabs)
        main_layout.addLayout(save_close_layout)

        self.setCentralWidget(main_widget)
        self.setFixedSize(600, 600)

    def toggle_matchmaking(self, state):
        self.main_window.ignore_nonmatchmaking = bool(state)

    def toggle_saving(self, state):
        self.main_window.save_stats = bool(state)

    def save(self):
        settings[Settings.save_stats] = self.main_window.save_stats
        settings[Settings.live_palette] = self.graph_color_chooser.currentText()
        settings[Settings.matchmaking_only] = self.main_window.ignore_nonmatchmaking
        if self.transparency_editor.text():
            settings[Settings.boardcomp_transparency] = int(self.transparency_editor.text())

        save_settings()
        self.hide()
        self.main_window.overlay.update_monitor()
        self.main_window.overlay.set_transparency()
        self.main_window.show_overlay()


class SBBTracker(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SBBTracker")
        self.comps = [BoardComp() for _ in range(0, 8)]
        self.round_indicator = QLabel("Waiting for match to start...")
        self.round_indicator.setFont(round_font)
        self.player_stats = stats.PlayerStats()
        self.player_ids = []
        self.save_stats = settings.get(Settings.save_stats, True)

        self.overlay = OverlayWindow(self)
        settings.setdefault(Settings.enable_overlay, False)
        self.show_overlay()
        self.in_matchmaking = False
        self.ignore_nonmatchmaking = False

        self.comp_tabs = QTabWidget()
        for index in range(len(self.comps)):
            self.comp_tabs.addTab(self.comps[index], f"Player{index}")

        self.reset_button = QPushButton("Reattach to Storybook Brawl")
        self.reset_button.setMaximumWidth(self.reset_button.fontMetrics().boundingRect("Reattach to Storybook Brawl")
                                          .width() * 2)
        self.reset_button.clicked.connect(self.reattatch_to_log)
        round_widget = QWidget()
        round_layout = QHBoxLayout(round_widget)
        round_layout.addWidget(self.round_indicator)
        round_layout.addWidget(self.reset_button)

        comps_widget = QWidget()
        layout = QVBoxLayout(comps_widget)
        layout.addWidget(round_widget)
        layout.addWidget(self.comp_tabs)

        self.match_history = MatchHistory(self, self.player_stats)
        self.live_graphs = LiveGraphs()
        self.stats_graph = StatsGraph(self.player_stats)

        main_tabs = QTabWidget()
        main_tabs.addTab(comps_widget, "Board Comps")
        main_tabs.addTab(self.live_graphs, "Live Graphs")
        main_tabs.addTab(self.match_history, "Match History")
        main_tabs.addTab(self.stats_graph, "Stats Graphs")

        # toolbar = self.titleBar
        toolbar = QToolBar(self)
        toolbar.setMinimumHeight(40)
        toolbar.setStyleSheet("QToolBar {border-bottom: none; border-top: none;}")
        discord_action = QAction(QPixmap(asset_utils.get_asset("icons/discord.png")), "&Join our Discord", self)
        # toolbar.insertAction(toolbar.minimize, discord_action)
        toolbar.addAction(discord_action)
        discord_action.triggered.connect(self.open_discord)

        bug_action = QAction(QPixmap(asset_utils.get_asset("icons/bug_report.png")), "&Report a bug", self)
        toolbar.insertAction(discord_action, bug_action)
        bug_action.triggered.connect(self.open_issues)

        self.settings_window = SettingsWindow(self)
        settings_action = QAction(QPixmap(asset_utils.get_asset("icons/settings.png")), "&Settings", self)
        toolbar.insertAction(bug_action, settings_action)
        settings_action.triggered.connect(self.settings_window.show)

        main_tabs.setCornerWidget(toolbar)

        self.setWindowIcon(QIcon(asset_utils.get_asset("icon.png")))

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_tabs)

        self.setCentralWidget(main_widget)
        self.setMinimumSize(QSize(1200, 800))
        self.setBaseSize(QSize(1400, 900))
        self.github_updates = updater.UpdateCheckThread()
        self.github_updates.github_update.connect(self.github_update_popup)

        self.log_updates = LogThread()
        self.log_updates.comp_update.connect(self.update_comp)
        self.log_updates.player_update.connect(self.update_player)
        self.log_updates.round_update.connect(self.update_round_num)
        self.log_updates.stats_update.connect(self.update_stats)
        self.log_updates.player_info_update.connect(self.live_graphs.update_graph)
        self.log_updates.player_info_update.connect(self.overlay.update_placements)
        self.log_updates.new_game.connect(self.new_game)
        self.log_updates.health_update.connect(self.update_health)

        self.resize(1300, 800)

        self.log_updates.start()
        self.github_updates.start()

    def get_player_index(self, player_id: str):
        if player_id not in self.player_ids:
            self.player_ids.append(player_id)
        return self.player_ids.index(player_id)

    def new_game(self, matchmaking):
        self.player_ids.clear()
        self.overlay.enable_hovers()
        self.in_matchmaking = matchmaking
        for index in range(0, 8):
            self.comp_tabs.tabBar().setTabTextColor(index, "white")
            comp = self.comps[index]
            comp.composition = None
            comp.player = None
            comp.current_round = 0
            comp.last_seen = None

            overlay_comp = self.overlay.comps[index]
            overlay_comp.composition = None
            overlay_comp.player = None
            overlay_comp.current_round = 0
            overlay_comp.last_seen = None

    def get_comp(self, index: int):
        return self.comps[index]

    def update_round_num(self, round_number):
        self.round_indicator.setText(f"Turn {round_number} ({round_to_xp(round_number)})")
        self.round_indicator.update()

    def update_player(self, player, round_number):
        index = self.get_player_index(player.playerid)
        real_hero_name = asset_utils.get_card_art_name(player.heroid, player.heroname)
        title = f"{real_hero_name}"
        if player.health <= 0:
            self.comp_tabs.tabBar().setTabTextColor(index, "red")
            title += " *DEAD*"
        self.comp_tabs.tabBar().setTabText(index, title)
        comp = self.get_comp(index)
        comp.player = player
        comp.current_round = round_number
        self.overlay.comps[index].current_round = round_number
        self.overlay.new_places[int(player.place) - 1] = index

        self.update()

    def update_comp(self, player_id, player, round_number):
        index = self.get_player_index(player_id)
        comp = self.get_comp(index)
        comp.composition = player
        comp.last_seen = round_number

        self.overlay.update_comp(index, player, round_number)
        self.update()

    def update_stats(self, starting_hero: str, player):
        if self.save_stats and (not self.ignore_nonmatchmaking or self.in_matchmaking):
            place = player.place if int(player.health) <= 0 else "1"
            self.player_stats.update_stats(starting_hero, asset_utils.get_card_art_name(player.heroid, player.heroname),
                                           place, player.mmr)
            self.match_history.update_history_table()
            self.match_history.update_stats_table()
        self.overlay.disable_hovers()

    def update_health(self, player):
        index = self.get_player_index(player.playerid)
        new_place = int(player.place)
        places = self.overlay.places
        places.remove(index)
        places.insert(new_place - 1, index)

    def toggle_overlay(self):
        settings[Settings.enable_overlay] = not settings[Settings.enable_overlay]

    def show_overlay(self):
        if settings[Settings.enable_overlay]:
            self.overlay.show()
        else:
            self.overlay.hide()

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

    def github_update_popup(self, update_notes: str):
        update_msg = "Would you like to automatically download and install?" if log_parser.os_name == "Windows" else "Would you like to go to the download page?"
        reply = QMessageBox.question(self, "New update available!",
                                     f"""New version available!
 
 Changes:
 
 {update_notes}
 
 {update_msg}""")
        if reply == QMessageBox.Yes:
            if log_parser.os_name == "Windows":
                self.install_update()
            else:
                self.open_github_release()

    def install_update(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Updater")
        dialog_layout = QVBoxLayout(dialog)
        self.download_progress = QProgressBar(dialog)
        dialog_layout.addWidget(QLabel("Downloading update..."))
        dialog_layout.addWidget(self.download_progress)
        dialog.show()
        dialog.update()
        logging.info("Starting download...")
        updater.self_update(self.handle_progress)
        self.close()
        sys.exit(0)

    def handle_progress(self, blocknum, blocksize, totalsize):

        read_data = blocknum * blocksize
        if totalsize > 0:
            download_percentage = read_data * 100 / totalsize
            logging.info(f"Download at: {download_percentage}%")

            self.download_progress.setValue(download_percentage)

            QApplication.processEvents()

    def export_csv(self):
        filepath, filetype = QFileDialog.getSaveFileName(parent=None, caption='Export to .csv',
                                                         dir=str(Path(os.environ['USERPROFILE']).joinpath("Documents")),
                                                         filter="Text CSV (*.csv)")
        self.player_stats.export(Path(filepath))

    def delete_stats(self, window):
        reply = QMessageBox.question(window, "Delete all Stats", "Do you want to delete *ALL* saved stats?")
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
        self.update()

    def closeEvent(self, *args, **kwargs):
        super(QMainWindow, self).closeEvent(*args, **kwargs)
        self.github_updates.terminate()
        self.log_updates.terminate()
        self.player_stats.save()
        self.overlay.close()
        save_settings()


class BoardComp(QWidget):
    def __init__(self):
        super().__init__()
        self.composition = None
        self.golden_overlay = QPixmap(asset_utils.get_asset("golden_overlay.png"))
        self.border = QPixmap(asset_utils.get_asset("neutral_border.png"))
        self.last_seen = None
        self.current_round = 0
        self.player = None

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
        self.update_card_stats(painter, int(slot), str(health), str(attack))

    def update_xp(self, painter: QPainter, xp: str):
        card_loc = get_image_location(11)
        xp_center = tuple(map(operator.add, xp_loc, card_loc))
        metrics = QFontMetrics(self.number_display_font)
        xp_orb_center = tuple(map(operator.sub, xp_center, (30, 40)))
        xp_text_center = tuple(map(operator.sub, xp_center, (metrics.horizontalAdvance(xp) / 2 - 2, -4)))
        painter.drawPixmap(QPoint(*xp_orb_center), QPixmap(asset_utils.get_asset("xp_orb.png")))
        path = QPainterPath()
        path.addText(QPoint(*xp_text_center), self.number_display_font, xp)
        painter.setPen(QPen(QColor("black"), 1))
        painter.setBrush(QBrush("white"))
        painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.composition is not None:
            used_slots = []
            for action in self.composition:
                if int(action.level) != 1:
                    #  skip level 1 characters because we can't normally get them
                    slot = action.slot
                    zone = action.zone
                    position = 10 if zone == 'Spell' else (7 + int(slot)) if zone == "Treasure" else slot
                    self.update_card(painter, position, action.cardname, action.content_id, action.cardhealth,
                                     action.cardattack, action.is_golden)
                    used_slots.append(str(position))
        else:
            painter.eraseRect(QRect(0, 0, 1350, 820))
        if self.player:
            self.update_card(painter, 11, self.player.heroname, self.player.heroid, self.player.health, "", False)
            self.update_xp(painter, f"{self.player.level}.{self.player.experience}")
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


class MatchHistory(QWidget):
    def __init__(self, parent, player_stats: stats.PlayerStats):
        super().__init__()
        self.parent = parent
        self.player_stats = player_stats
        self.match_history_table = QTableWidget(stats.stats_per_page, 4)
        self.page = 1
        self.display_starting_hero = 0
        self.filter_ = settings.setdefault(Settings.filter_, "All Matches")
        self.match_history_table.setHorizontalHeaderLabels(["Starting Hero", "Ending Hero", "Place", "+/- MMR"])
        self.match_history_table.setColumnWidth(0, 140)
        self.match_history_table.setColumnWidth(1, 140)
        self.match_history_table.setColumnWidth(2, 80)
        self.match_history_table.setColumnWidth(3, 85)
        self.match_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.match_history_table.setFocusPolicy(Qt.NoFocus)
        self.match_history_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.match_history_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.match_history_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        paged_table = QWidget()
        paged_table.setMaximumWidth(533)
        paged_layout = QVBoxLayout(paged_table)

        buttons_widget = QWidget()
        page_buttons = QHBoxLayout(buttons_widget)
        self.prev_button = QPushButton("<")
        self.prev_button.clicked.connect(self.page_down)
        self.prev_button.setMaximumWidth(50)
        self.next_button = QPushButton(">")
        self.next_button.setMaximumWidth(50)
        self.next_button.clicked.connect(self.page_up)

        self.page_indicator = QLabel("1")
        self.page_indicator.setFont(QFont("Roboto", 16))

        page_buttons.addWidget(self.prev_button, alignment=Qt.AlignRight)
        page_buttons.addWidget(self.page_indicator, alignment=Qt.AlignCenter | Qt.AlignVCenter)
        page_buttons.addWidget(self.next_button, alignment=Qt.AlignLeft)
        page_buttons.setSpacing(0)

        paged_layout.addWidget(self.match_history_table)
        paged_layout.addWidget(buttons_widget)
        paged_table.resize(200, paged_table.height())

        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_table = QTableWidget(len(asset_utils.hero_ids) + 1, 6)
        self.stats_table.setHorizontalHeaderLabels(stats.headings)
        self.stats_table.setColumnWidth(0, 130)
        self.stats_table.setColumnWidth(1, 115)
        self.stats_table.setColumnWidth(2, 115)
        self.stats_table.setColumnWidth(3, 90)
        self.stats_table.setColumnWidth(4, 90)
        self.stats_table.setColumnWidth(5, 110)
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stats_table.setFocusPolicy(Qt.NoFocus)
        self.stats_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stats_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stats_table.setStyleSheet("""
QTabBar::tab:left,
QTabBar::tab:right{
  padding: 1px 0;
  width: 30px;
}""")
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.stats_table.horizontalHeader().sectionClicked.connect(self.sort_stats)

        filter_widget = QWidget()
        self.toggle_hero = QComboBox()
        hero_types = ["Starting Heroes", "Ending Heroes"]
        self.toggle_hero.activated.connect(self.toggle_heroes)
        self.toggle_hero.addItems(hero_types)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(default_dates.keys())
        index = self.filter_combo.findText(self.filter_)
        if index != -1:  # -1 for not found
            self.filter_combo.setCurrentIndex(index)
        self.filter_combo.activated.connect(self.filter_stats)
        self.sort_col = 0
        self.sort_asc = False

        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.addWidget(self.toggle_hero)
        filter_layout.addWidget(self.filter_combo)

        stats_layout.addWidget(filter_widget)
        stats_layout.addWidget(self.stats_table)

        tables_layout = QHBoxLayout(self)
        tables_layout.addWidget(paged_table)
        tables_layout.addWidget(stats_widget)

        table_font = QFont("Roboto")
        table_font.setPixelSize(14)

        # self.match_history_table.setFont(table_font)
        # self.stats_table.setFont(table_font)

        self.update_history_table()
        self.update_stats_table()

    def page_up(self):
        if self.page < self.player_stats.get_num_pages():
            self.page += 1
        self.update_history_table()

    def page_down(self):
        if self.page > 1:
            self.page -= 1
        self.update_history_table()

    def update_history_table(self):
        history = self.player_stats.get_page(self.page)
        update_table(self.match_history_table, history)
        start_num = (self.page - 1) * stats.stats_per_page + 1
        self.match_history_table.setVerticalHeaderLabels([str(i) for i in range(start_num,
                                                                                start_num + stats.stats_per_page + 1)])
        self.page_indicator.setText(f'Page {self.page} of {max(1, self.player_stats.get_num_pages())}')

    def update_stats_table(self):
        start, end = default_dates[self.filter_]
        hero_stats = self.player_stats.filter(start, end, self.sort_col, self.sort_asc)
        chosen_stats = hero_stats[self.display_starting_hero]
        update_table(self.stats_table, chosen_stats)

    def toggle_heroes(self, index: int):
        self.display_starting_hero = index
        self.update_stats_table()

    def filter_stats(self):
        self.filter_ = self.filter_combo.currentText()
        settings[Settings.filter_] = self.filter_
        self.update_stats_table()

    def sort_stats(self, index: int):
        # ▼ ▲
        self.sort_asc = (self.sort_col == index) and (not self.sort_asc)
        self.sort_col = index
        headings = stats.headings.copy()
        headings[index] = headings[index] + ("▼" if self.sort_asc else "▲")
        self.stats_table.setHorizontalHeaderLabels(headings)
        self.update_stats_table()


class LiveGraphs(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.user_palette = settings.setdefault(Settings.live_palette, "paired")
        self.states = None

        self.health_canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.xp_canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.health_ax = self.health_canvas.figure.subplots()
        self.xp_ax = self.xp_canvas.figure.subplots()

        graphs_tabs = QTabWidget(self)
        graphs_tabs.addTab(self.health_canvas, "Health Graph")
        graphs_tabs.addTab(self.xp_canvas, "XP Graph")
        self.layout.addWidget(graphs_tabs)

    def set_color_palette(self, palette):
        self.user_palette = palette
        self.update_graph()

    def update_graph(self, states: graphs.LivePlayerStates = None):
        if states:
            self.states = states

        if self.states:
            self.xp_ax.cla()
            graphs.xp_graph(self.states, self.xp_ax, self.user_palette)
            self.xp_canvas.draw()

            self.health_ax.cla()
            graphs.live_health_graph(self.states, self.health_ax, self.user_palette)
            self.health_canvas.draw()


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
        self.figure = graphs.stats_graph(self.player_stats.df, self.selection, self.ax)
        self.canvas.draw()


def resoultion_offset(resolution: (int, int)):
    if resolution == (1920, 1080):
        return 0
    if resolution == (2560, 1440):
        return 43
    if resolution == (3840, 2160):
        return 63
    else:
        return 0


hover_size = (84, 68)
p1_loc = (38, 247)
hover_distance = 15
base_size = (1920, 1080)


class OverlayWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)

        self.main_window = main_window
        self.monitor = None
        self.scale_factor = (1, 1)
        self.dpi_scale = 1
        self.select_monitor(settings.get("monitor", 0))
        self.hover_regions = [HoverRegion(self, *map(operator.mul, hover_size, self.scale_factor)) for _ in range(0, 8)]
        self.update_monitor()

        self.show_hide = True

        self.comps = [BoardComp() for _ in range(0, 8)]
        self.comp_widgets = [QFrame(self) for _ in range(0, 8)]
        self.places = list(range(0, 8))
        self.new_places = list(range(0, 8))
        for index in range(len(self.comps)):
            comp = self.comps[index]
            widget = self.comp_widgets[index]

            comp.setParent(widget)
            widget.setVisible(False)
            widget.setMinimumSize(1100, 650)
            comp.setMinimumSize(1100, 650)
            widget.move(round(self.size().width() / 2 - 100), 0)
        self.set_transparency()

        self.show_button = QPushButton("Show Tracker", self)
        self.show_button.clicked.connect(self.show_hide_main_window)
        self.show_button.move(40, 40)
        self.show_button.resize(self.show_button.sizeHint().width(), self.show_button.sizeHint().height())

        self.disable_hovers()

    def show_hide_main_window(self):
        if self.show_hide:
            self.main_window.setWindowState(Qt.WindowState.WindowActive)
            self.show_button.setText("Hide Tracker")
        else:
            self.main_window.showMinimized()
            self.show_button.setText("Show Tracker")
        self.show_hide = not self.show_hide

    def disable_hovers(self):
        for hover in self.hover_regions:
            hover.setVisible(False)

    def enable_hovers(self):
        for hover in self.hover_regions:
            hover.setVisible(True)

    def show_comp(self, index):
        widget = self.comp_widgets[self.places[index]]
        widget.setVisible(True)

    def hide_comp(self, index):
        widget = self.comp_widgets[self.places[index]]
        widget.setVisible(False)

    def update_comp(self, index, player, round_number):
        comp = self.comps[index]
        comp.composition = player
        comp.last_seen = round_number
        self.update()

    def update_placements(self):
        self.places = self.new_places.copy()
        self.new_places = list(range(0, 8))
        for widget in self.comp_widgets:
            #  fixes bug where hovering over the hero at the end of combat gets the overlay stuck
            widget.setVisible(False)

    def select_monitor(self, index):
        screens = QGuiApplication.screens()
        # if the number of monitors is reduced, just pick the first monitor by default
        adjusted_index = index if index < len(screens) else 0
        self.monitor = QGuiApplication.screens()[adjusted_index]
        settings[Settings.monitor] = adjusted_index

    def update_monitor(self):
        self.dpi_scale = (self.monitor.logicalDotsPerInch() / 96)
        self.real_size = tuple(map(operator.mul, (self.dpi_scale, self.dpi_scale), self.monitor.size().toTuple()))
        self.setMinimumSize(*self.real_size)
        self.setGeometry(self.monitor.geometry())
        self.scale_factor = tuple(map(operator.truediv, self.monitor.size().toTuple(), base_size))
        self.update_hovers()

    def update_hovers(self):
        size = self.monitor.size()

        true_scale = (self.scale_factor[0] * self.dpi_scale, self.scale_factor[1] * self.dpi_scale,)

        for i in range(len(self.hover_regions)):
            hover = self.hover_regions[i]
            loc = (p1_loc[0] * true_scale[0], (p1_loc[1] * true_scale[1]) +
                   (hover_distance * (true_scale[1]) * i) +
                   (hover_size[1] * true_scale[1] * i) +
                   resoultion_offset(tuple(size * self.monitor.devicePixelRatio() for size in self.real_size)))
            hover.move(*loc)
            new_size = tuple(map(operator.mul, hover_size, true_scale))
            hover.resize(*new_size)
            hover.background.setMinimumSize(*new_size)
            hover.enter_hover.connect(lambda y=i: self.show_comp(y))
            hover.leave_hover.connect(lambda y=i: self.hide_comp(y))
        self.update()

    def set_transparency(self):
        alpha = (100 - settings.get(Settings.boardcomp_transparency, 0)) / 100
        style = f"background-color: rgba({default_bg_color_rgb}, {alpha});"
        for widget in self.comp_widgets:
            widget.setStyleSheet(style)


class SimulatorStats(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.win_chance = "33.3"
        self.tie_chance = "33.3"
        self.lose_chance = "33.3"

        self.setFont(QFont("Roboto", 16))

        self.win_label = QLabel(self.win_chance, self)
        self.tie_label = QLabel(self.tie_chance, self)
        self.lose_label = QLabel(self.lose_chance, self)

        self.setStyleSheet("background-color: #31363b")

        background = QWidget(self)
        layout = QVBoxLayout(background)

        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Win %"))
        label_layout.addWidget(QLabel("Tie %"))
        label_layout.addWidget(QLabel("Lose %"))
        label_layout.addStretch()

        chance_layout = QHBoxLayout()
        chance_layout.addWidget(self.win_label)
        chance_layout.addWidget(self.tie_label)
        chance_layout.addWidget(self.lose_label)
        chance_layout.addStretch()

        layout.addLayout(label_layout)
        layout.addLayout(chance_layout)
        layout.addStretch()

        self.setMinimumSize(1000, 200)


class HoverRegion(QWidget):
    enter_hover = Signal()
    leave_hover = Signal()

    def __init__(self, parent, width, height):
        super().__init__(parent)
        self.background = QWidget(self)
        self.background.setMinimumSize(width, height)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.01);")
        # self.setStyleSheet("background-color: rgba(255, 255, 255, 1);")
        self.setMinimumSize(width, height)

    def enterEvent(self, event):
        self.enter_hover.emit()

    def leaveEvent(self, event):
        self.leave_hover.emit()


app = QApplication(sys.argv)
app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor)
apply_stylesheet(app, theme='dark_teal.xml')
stylesheet = app.styleSheet()
stylesheet = stylesheet.replace("""QTabBar::tab {
  color: #ffffff;
  border: 0px;
}""", """QTabBar::tab {
  border: 0px;
}""") + "QTabBar{ text-transform: none; }"
app.setStyleSheet(stylesheet)
mainWindow = SBBTracker()
mainWindow.show()

sys.exit(app.exec())
