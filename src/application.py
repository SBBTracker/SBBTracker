import datetime
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

matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from PySide6 import QtGui
from PySide6.QtCore import QObject, QPoint, QRect, QSettings, QSize, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QIntValidator, \
    QPainter, QPainterPath, \
    QPen, \
    QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication,
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QErrorMessage, QFileDialog, QFrame, QGraphicsDropShadowEffect,
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

if not stats.sbbtracker_folder.exists():
    stats.sbbtracker_folder.mkdir()
logging.basicConfig(filename=stats.sbbtracker_folder.joinpath("sbbtracker.log"), filemode="w",
                    format='%(name)s - %(levelname)s - %(message)s')

art_dim = (161, 204)
att_loc = (26, 181)
health_loc = (137, 181)
xp_loc = (137, 40)

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
        with open(settings_file, "r") as json_file:
            return json.load(json_file)
    else:
        return {}


settings = load_settings()


def save_settings():
    with open(settings_file, "w") as json_file:
        json.dump(settings, json_file)


today = date.today()
default_dates = {
    "All Matches": ("1970-01-01", today.strftime("%Y-%m-%d")),
    "Latest Patch (64.2)": ("2021-11-08", today.strftime("%Y-%m-%d")),
    "Previous Patch (63.4)": ("2021-10-18", "2021-11-08"),
    "Today": (today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
    "Last 7 days": ((today - datetime.timedelta(days=7)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
    "Last 30 days": ((today - datetime.timedelta(days=30)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
}


class LogSignals(QObject):
    round_update = Signal(int)
    player_update = Signal(object, int)
    comp_update = Signal(str, object, int)
    stats_update = Signal(str, object)
    player_info_update = Signal(graphs.LivePlayerStates)
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
        states = graphs.LivePlayerStates()
        while True:
            update = queue.get()
            job = update.job
            state = update.state
            if job == log_parser.JOB_NEWGAME:
                states.clear()
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
                xp = float(f"{state.level}.{int(state.experience) * 333333333}")
                states.update_player(state.playerid, round_number, state.health, xp,
                                     asset_utils.get_card_art_name(state.heroid, state.heroname))
            elif job == log_parser.JOB_BOARDINFO:
                for player_id in state:
                    self.signals.comp_update.emit(player_id, state[player_id], round_number)
            elif job == log_parser.JOB_ENDCOMBAT:
                self.signals.player_info_update.emit(states)
            elif job == log_parser.JOB_ENDGAME:
                if state and current_player:
                    self.signals.stats_update.emit(asset_utils.get_card_art_name(current_player.heroid,
                                                                                 current_player.heroname), state)


class UpdateCheckSignals(QObject):
    github_update = Signal(str)


class UpdateCheckThread(QThread):
    def __init__(self, *args, **kwargs):
        super(UpdateCheckThread, self).__init__()
        self.args = args
        self.kwargs = kwargs
        self.signals = UpdateCheckSignals()

    def run(self):
        release_notes = updater.check_updates()
        # wait for an update
        self.signals.github_update.emit(release_notes)


class DraggableTitleBar(QToolBar):

    def __init__(self, window: QMainWindow, parent):
        super(DraggableTitleBar, self).__init__()
        self.parent = parent
        self._window = window
        self._mousePressed = False
        self.setMaximumHeight(40)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        titlebar_icon = QLabel()
        titlebar_icon.setPixmap(QPixmap("../assets/icon.png").scaled(QSize(20, 20), mode=Qt.SmoothTransformation))
        self.addWidget(QLabel("  "))
        self.addWidget(titlebar_icon)
        self.title = QLabel("  SBBTracker")
        self.title.setFont(QFont("Roboto", 12))
        self.addWidget(self.title)
        self.addWidget(spacer)
        self.minimize = QAction("&🗕", self)
        self.addAction(self.minimize)
        self.minimize.triggered.connect(self.parent.showMinimized)
        self.widgetForAction(self.minimize).setToolTip("")

        self.maximize = QAction("&🗖", self)
        self.addAction(self.maximize)
        self.widgetForAction(self.maximize).setToolTip("")
        self.maximize.triggered.connect(self.btn_max_clicked)

        self.close = QAction("&🗙", self)
        self.addAction(self.close)
        self.close.triggered.connect(self.parent.close)
        self.setObjectName("close-button")
        close_widget = self.widgetForAction(self.close)
        close_widget.setStyleSheet("QToolButton:hover { background-color: red; border-right: 10px solid red; "
                                   "border-left: 10px solid red;}")
        close_widget.setToolTip("")

    def resizeEvent(self, QResizeEvent):
        super(DraggableTitleBar, self).resizeEvent(QResizeEvent)

    def mousePressEvent(self, event):
        self._mousePressed = True
        self._mousePos = event.globalPosition().toPoint()
        self._windowPos = self._window.pos()

    def mouseMoveEvent(self, event):
        if self._mousePressed and (Qt.LeftButton & event.buttons()):
            self._window.setWindowState(Qt.WindowNoState)
            self._window.move(self._windowPos +
                              (event.globalPosition().toPoint() - self._mousePos))

    def btn_close_clicked(self):
        self.parent.close()

    def btn_max_clicked(self):
        if self._window.isMaximized():
            self._window.setWindowState(Qt.WindowNoState)
        else:
            self._window.setWindowState(Qt.WindowMaximized)

    def btn_min_clicked(self):
        self.parent.showMinimized()


class FramelessWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        # self.setWindowFlags(Qt.FramelessWindowHint)
        self.titleBar = DraggableTitleBar(self, self)


class SettingsWindow(FramelessWindow):
    def __init__(self, main_window):
        super().__init__()
        self.hide()
        self.main_window = main_window
        main_widget = QFrame()
        main_layout = QVBoxLayout(main_widget)
        general_settings = QWidget()
        settings_tabs = QTabWidget()
        settings_tabs.addTab(general_settings, "General")

        general_layout = QVBoxLayout(general_settings)

        export_button = QPushButton("Export Stats")
        export_button.clicked.connect(main_window.export_csv)
        delete_button = QPushButton("Delete Stats")
        delete_button.clicked.connect(lambda: main_window.delete_stats(self))

        # scaling_layout = QHBoxLayout()
        # scaling_layout.addWidget(QLabel("UI Scaling Factor"))
        # self.scale_slider = QSlider(Qt.Horizontal)
        # self.scale_editor = QLineEdit()
        # saved_scaling = settings.get("scaling", 100)
        # self.scale_slider.setValue(saved_scaling)
        # self.scale_slider.setMaximum(200)
        # self.scale_slider.setMinimum(50)
        # self.scale_slider.valueChanged.connect(lambda val: self.scale_editor.setText(str(val)))
        # self.scale_editor.setValidator(QIntValidator(0, 200))
        # self.scale_editor.setText(str(saved_scaling))
        # self.scale_editor.textEdited.connect(lambda text: self.scale_slider.setValue(int(text)) if text != '' else None)
        # scaling_layout.addWidget(self.scale_slider)
        # scaling_layout.addWidget(self.scale_editor)

        save_stats_widget = QWidget()
        save_stats_layout = QHBoxLayout(save_stats_widget)
        save_stats_checkbox = QCheckBox()
        save_stats_checkbox.setChecked(settings.get("save-stats", True))
        save_stats_layout.addWidget(QLabel("Save match results"), alignment=Qt.AlignLeft)
        save_stats_layout.addWidget(save_stats_checkbox, Qt.AlignLeft)
        save_stats_layout.addStretch()
        save_stats_checkbox.stateChanged.connect(main_window.toggle_saving)

        general_layout.addWidget(export_button, alignment=Qt.AlignTop)
        general_layout.addWidget(delete_button, alignment=Qt.AlignTop)
        general_layout.addWidget(save_stats_widget, alignment=Qt.AlignTop)
        # general_layout.addLayout(scaling_layout)
        general_layout.addStretch()

        save_close_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)
        close_button = QPushButton("Cancel")
        close_button.clicked.connect(self.hide)
        save_close_layout.addStretch()
        save_close_layout.addWidget(save_button)
        save_close_layout.addWidget(close_button)

        # main_layout.addWidget(self.titleBar)
        main_layout.addWidget(settings_tabs)
        main_layout.addLayout(save_close_layout)

        self.setCentralWidget(main_widget)
        self.setFixedSize(600, 600)

    def save(self):
        # scaling = self.scale_slider.value()
        # settings["scaling"] = scaling
        settings["save-stats"] = self.main_window.save_stats
        save_settings()
        self.hide()


class SBBTracker(FramelessWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SBBTracker")
        self.first_comp = BoardComp()
        self.ids_to_comps = {index: BoardComp() for index in range(0, 8)}
        self.round_indicator = QLabel("Waiting for match to start...")
        self.round_indicator.setFont(round_font)
        self.player_stats = stats.PlayerStats()
        self.player_ids = []
        self.save_stats = settings.get("save-stats", True)

        self.comp_tabs = QTabWidget()
        for index in self.ids_to_comps:
            self.comp_tabs.addTab(self.ids_to_comps[index], f"Player{index}")

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
        discord_action = QAction(QPixmap("../assets/icons/discord.png"), "&Join our Discord", self)
        # toolbar.insertAction(toolbar.minimize, discord_action)
        toolbar.addAction(discord_action)
        discord_action.triggered.connect(self.open_discord)

        bug_action = QAction(QPixmap("../assets/icons/bug_report.png"), "&Report a bug", self)
        toolbar.insertAction(discord_action, bug_action)
        bug_action.triggered.connect(self.open_issues)

        self.settings_window = SettingsWindow(self)
        settings_action = QAction(QPixmap("../assets/icons/settings.png"), "&Settings", self)
        toolbar.insertAction(bug_action, settings_action)
        settings_action.triggered.connect(self.settings_window.show)

        main_tabs.setCornerWidget(toolbar)

        self.setWindowIcon(QIcon("../assets/icon.png"))

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # main_layout.addWidget(toolbar)
        main_layout.addWidget(main_tabs)

        self.setCentralWidget(main_widget)
        self.setMinimumSize(QSize(1200, 800))
        self.setBaseSize(QSize(1400, 900))
        self.github_updates = UpdateCheckThread()
        self.github_updates.signals.github_update.connect(self.github_update_popup)

        self.log_updates = LogThread()
        self.log_updates.signals.comp_update.connect(self.update_comp)
        self.log_updates.signals.player_update.connect(self.update_player)
        self.log_updates.signals.round_update.connect(self.update_round_num)
        self.log_updates.signals.stats_update.connect(self.update_stats)
        self.log_updates.signals.player_info_update.connect(self.live_graphs.update_graph)
        self.log_updates.signals.new_game.connect(self.new_game)

        self.resize(1300, 800)

        self.log_updates.start()
        self.github_updates.start()

    def get_player_index(self, player_id: str):
        if player_id not in self.player_ids:
            self.player_ids.append(player_id)
        return self.player_ids.index(player_id)

    def new_game(self):
        self.player_ids.clear()
        for index in range(0, 8):
            self.comp_tabs.tabBar().setTabTextColor(index, "white")
        for comp in self.ids_to_comps.values():
            comp.composition = None
            comp.player = None
            comp.current_round = 0
            comp.last_seen = None

    def get_comp(self, index: int):
        return self.ids_to_comps[index]

    def update_round_num(self, round_number):
        self.round_indicator.setText(f"Turn {round_number} ({round_to_xp(round_number)})")
        self.round_indicator.update()

    def update_player(self, player, round_number):
        index = self.get_player_index(player.playerid)
        real_hero_name = asset_utils.get_card_art_name(player.heroid, player.heroname)
        title = f"{real_hero_name}"
        if player.health <= 0:
            self.comp_tabs.tabBar().setTabTextColor(index, "red")
            title += " *DEAD"
        self.comp_tabs.tabBar().setTabText(index, title)
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
        if self.save_stats:
            place = player.place if int(player.health) <= 0 else "1"
            self.player_stats.update_stats(starting_hero, asset_utils.get_card_art_name(player.heroid, player.heroname),
                                           place, player.mmr)
            self.match_history.update_history_table()
            self.match_history.update_stats_table()

    def toggle_saving(self):
        self.save_stats = not self.save_stats

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
        reply = QMessageBox.question(self, "New update available!",
                                     f"""New version available!
 
 Changes:
 
 {update_notes}
 
 Would you like to automatically download and install?""")
        if reply == QMessageBox.Yes:
            # self.open_github_release()
            self.install_update()

    def install_update(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Updater")
        dialog_layout = QVBoxLayout(dialog)
        self.download_progress = QProgressBar(dialog)
        dialog_layout.addWidget(QLabel("Downloading update..."))
        dialog_layout.addWidget(self.download_progress)
        dialog.show()
        dialog.update()
        updater.self_update(self.handle_progress)
        self.close()
        sys.exit(0)

    def handle_progress(self, blocknum, blocksize, totalsize):

        read_data = blocknum * blocksize

        if totalsize > 0:
            download_percentage = read_data * 100 / totalsize

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
        save_settings()


class BoardComp(QWidget):
    def __init__(self):
        super().__init__()
        self.composition = None
        self.golden_overlay = QPixmap("../assets/golden_overlay.png")
        self.border = QPixmap("../assets/neutral_border.png")
        self.last_seen = None
        self.current_round = 0
        self.player = None
        self.number_display_font = QFont("Impact", 25, weight=QFont.ExtraBold)

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
                painter.drawPixmap(QPoint(*att_circle_center), QPixmap("../assets/attack_orb.png"))
                path = QPainterPath()
                path.addText(QPoint(*att_text_center), self.number_display_font, attack)
                painter.setPen(QPen(QColor("black"), 1))
                painter.setBrush(QBrush("white"))
                painter.drawPath(path)
        if health:
            if slot < 7 or slot == 11:
                painter.drawPixmap(QPoint(*health_circle_center), QPixmap("../assets/health_orb.png"))
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
        painter.drawPixmap(QPoint(*xp_orb_center), QPixmap("../assets/xp_orb.png"))
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
        self.filter = settings.get("filter", "All Matches")
        self.match_history_table.setHorizontalHeaderLabels(["Starting Hero", "Ending Hero", "Place", "+/- MMR"])
        self.match_history_table.setColumnWidth(0, 140)
        self.match_history_table.setColumnWidth(1, 140)
        self.match_history_table.setColumnWidth(2, 80)
        self.match_history_table.setColumnWidth(3, 85)
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
        self.stats_table.setStyleSheet("""
QTabBar::tab:left,
QTabBar::tab:right{
  padding: 1px 0;
  width: 30px;
}""")

        self.stats_table.horizontalHeader().sectionClicked.connect(self.sort_stats)

        filter_widget = QWidget()
        self.toggle_hero = QComboBox()
        hero_types = ["Starting Heroes", "Ending Heroes"]
        self.toggle_hero.activated.connect(self.toggle_heroes)
        self.toggle_hero.addItems(hero_types)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(default_dates.keys())
        index = self.filter_combo.findText(self.filter)
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
        self.page_indicator.setText(f'Page {self.page} of {max(1,self.player_stats.get_num_pages())}')

    def update_stats_table(self):
        start, end = default_dates[self.filter]
        hero_stats = self.player_stats.filter(start, end, self.sort_col, self.sort_asc)
        chosen_stats = hero_stats[self.display_starting_hero]
        update_table(self.stats_table, chosen_stats)

    def toggle_heroes(self, index: int):
        self.display_starting_hero = index
        self.update_stats_table()

    def filter_stats(self):
        self.filter = self.filter_combo.currentText()
        settings["filter"] = self.filter
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

        self.health_canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.xp_canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.health_ax = self.health_canvas.figure.subplots()
        self.xp_ax = self.xp_canvas.figure.subplots()

        graphs_tabs = QTabWidget(self)
        graphs_tabs.addTab(self.health_canvas, "Health Graph")
        graphs_tabs.addTab(self.xp_canvas, "XP Graph")
        self.layout.addWidget(graphs_tabs)

    def update_graph(self, states: graphs.LivePlayerStates):
        self.xp_ax.cla()
        graphs.xp_graph(states, self.xp_ax)
        self.xp_canvas.draw()

        self.health_ax.cla()
        graphs.live_health_graph(states, self.health_ax)
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
