import concurrent.futures
import calendar
import concurrent.futures
import datetime
import json
import logging
import os
import sys
import threading
import time
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path
from queue import Queue
from statistics import mean

import matplotlib
import numpy as np
import pandas as pd
import requests

from sbbtracker import graphs, paths, settings, stats, updater, version
from sbbtracker.languages import tr
from sbbtracker.utils.qt_utils import open_url
from sbbtracker.utils.sbb_logic_utils import round_to_xp
from sbbtracker.windows.constants import default_bg_color, primary_color
from sbbtracker.windows.overlays import BoardComp, OverlayWindow, StreamableMatchDisplay, StreamerOverlayWindow
from sbbtracker.windows.settings_window import SettingsWindow
from sbbtracker.windows.shop_display import ShopDisplay
from sbbtracker.windows.simulation_widget import BoardAnalysis, SimulationThread

matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

from PySide6.QtCore import QSize, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon, \
    QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication,
    QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from sbbtracker.utils import asset_utils
from sbbtracker.parsers import log_parser

from sbbbattlesim import from_state, simulate
from sbbbattlesim.exceptions import SBBBSCrocException
from sbbtracker.utils.sbb_window_utils import SBBWindowCheckThread

round_font = QFont("Roboto", 18)

patch_notes_file = paths.sbbtracker_folder.joinpath("patch_notes.txt")


def update_table(table: QTableWidget, data: list[list]):
    for row in range(len(data)):
        for column in range(len(data[0])):
            datum = (data[row][column])
            table.setItem(row, column, QTableWidgetItem(str(datum)))


all_matches = tr("All Matches")
latest_patch = tr("Latest Patch") + " (68.9)"
prev_patch = tr("Previous Patch") + " (67.5)"
today_ = tr("Today")
yesterday = tr("Yesterday")
last_7 = tr("Last 7 days")
last_30 = tr("Last 30 days")
this_month = tr("This month")
last_month = tr("Last month")

default_dates = [all_matches, latest_patch, prev_patch, today_, yesterday, last_7, last_30, this_month, last_month]


def get_date_range(key):
    today = date.today()
    _, days_this_month = calendar.monthrange(today.year, today.month)
    first_day_this_month = today.replace(day=1)
    last_day_this_month = today.replace(day=days_this_month)
    last_day_prev_month = first_day_this_month - datetime.timedelta(days=1)
    first_day_prev_month = last_day_prev_month.replace(day=1)

    if key == all_matches:
        return "1970-01-01", today.isoformat()
    elif key == latest_patch:
        return "2022-03-02", today.isoformat()
    elif key == prev_patch:
        return "2022-02-14", "2022-03-02"
    elif key == today_:
        return today.isoformat(), today.isoformat()
    elif key == yesterday:
        return (today - datetime.timedelta(1)).isoformat(), (today - datetime.timedelta(1)).isoformat()
    elif key == last_7:
        return (today - datetime.timedelta(days=7)).isoformat(), today.isoformat()
    elif key == last_30:
        return (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif key == this_month:
        return first_day_this_month.isoformat(), last_day_this_month.isoformat()
    elif key == last_month:
        return first_day_prev_month.isoformat(), last_day_prev_month.isoformat()


api_url = "https://9n2ntsouxb.execute-api.us-east-1.amazonaws.com/prod/api/v1/game"
api_id = settings.get(settings.api_key)
if not api_id:
    api_id = settings.set_(settings.api_key, str(uuid.uuid4()))


def upload_data(payload):
    try:
        resp = requests.post(api_url, data=json.dumps(payload))
        print(resp.content)
    except:
        logging.exception("Unable to post data!")


class SimulationThread(QThread):
    end_simulation = Signal(float, float, float, float, float, int)
    error_simulation = Signal(str, int)

    def __init__(self, comp_queue):
        super(SimulationThread, self).__init__()
        self.comp_queue = comp_queue

    def run(self):
        while True:
            board, playerid, num_simulations, num_threads, round_number = self.comp_queue.get()
            simulation_stats = None

            if playerid is None:
                playerid = settings.get(settings.player_id)
            simulator_board = asset_utils.replace_template_ids(board)
            from_stated = from_state(simulator_board)

            if all([from_stated[player_id]['level'] != 0 for player_id in from_stated]):
                try:
                    simulation_stats = simulate(simulator_board, t=num_threads, k=int(num_simulations / num_threads),
                                                timeout=60)
                except SBBBSCrocException:
                    self.error_simulation.emit(tr("Captain Croc not supported"), round_number)
                except concurrent.futures.TimeoutError:
                    self.error_simulation.emit(tr("Simulation timed out!"), round_number)
                except Exception:
                    logging.exception("Error in simulation!")
                    with open(paths.sbbtracker_folder.joinpath("error_board.json"), "w") as file:
                        json.dump(from_stated, file, default=lambda o: o.__dict__)
                    self.error_simulation.emit(tr("Error in simulation!"), round_number)

                logging.debug(from_stated)

                # TODO: do math on changes in XP
                if simulation_stats:
                    results = simulation_stats.results
                    aggregated_results = defaultdict(list)
                    for result in results:
                        aggregated_results[result.win_id].append(result.damage)

                    keys = set(aggregated_results.keys()) - {playerid, None}
                    win_damages = aggregated_results.get(playerid, [])
                    tie_damages = aggregated_results.get(None, [])
                    loss_damages = [] if not keys else aggregated_results[keys.pop()]

                    win_percent = round(len(win_damages) / len(results) * 100, 2)
                    tie_percent = round(len(tie_damages) / len(results) * 100, 2)
                    loss_percent = round(len(loss_damages) / len(results) * 100, 2)
                    # win_10th_percentile, win_90th_percentile = (0, 0) if (len(win_damages) == 0) \
                    #     else np.percentile(win_damages, [10, 90])
                    # loss_10th_percentile, loss_90th_percentile = (0, 0) if (len(loss_damages) == 0) \
                    #     else np.percentile(loss_damages, [10, 90])

                    win_dmg= round(mean(win_damages), 1) if win_percent > 0 else 0
                    loss_dmg = round(mean(loss_damages), 1) if loss_percent > 0 else 0

                    self.end_simulation.emit(win_percent, tie_percent, loss_percent, win_dmg, loss_dmg, round_number)
            else:
                self.error_simulation.emit(tr("Couldn't get player id (try reattaching)"), round_number)
            time.sleep(1)


class LogThread(QThread):
    round_update = Signal(int)
    player_update = Signal(object, int)
    comp_update = Signal(object, int)
    stats_update = Signal(str, object, str, object)
    player_info_update = Signal(graphs.LivePlayerStates)
    health_update = Signal(object)
    new_game = Signal(bool)
    update_card = Signal(object)
    end_combat = Signal(bool)
    hero_discover = Signal(list)

    def run(self):
        queue = Queue()
        threading.Thread(target=log_parser.run,
                         args=(
                             queue,),
                         daemon=True).start()
        round_number = 0
        current_player = None
        counter = 0
        states = graphs.LivePlayerStates()
        matchmaking = False
        after_first_combat = False
        session_id = None
        build_id = None
        match_data = {}
        combats = []
        while True:
            update = queue.get()
            job = update.job
            state = update.state
            if job == log_parser.JOB_MATCHMAKING:
                matchmaking = True
            elif job == log_parser.JOB_NEWGAME and state.session_id != session_id:
                states.clear()
                match_data.clear()
                current_player = None
                round_number = 0
                self.new_game.emit(matchmaking)
                self.round_update.emit(0)
                matchmaking = False
                after_first_combat = False
                session_id = state.session_id
                build_id = state.build_id
                combats.clear()
                match_data.clear()
            elif job == log_parser.JOB_HERODISCOVER:
                if round_number < 1:
                    self.hero_discover.emit(state.choices)
            elif job == log_parser.JOB_INITCURRENTPLAYER:
                if not after_first_combat:
                    current_player = state
                    settings.get(settings.player_id, state.playerid)
                    # only save the first time
                self.player_update.emit(state, round_number)
            elif job == log_parser.JOB_ROUNDINFO:
                round_number = state.round_num
                self.round_update.emit(round_number)
            elif job == log_parser.JOB_PLAYERINFO:
                self.player_update.emit(state, round_number)
                xp = f"{state.level}.{state.experience}"
                states.update_player(state.playerid, round_number, state.health, xp,
                                     asset_utils.get_card_name(state.heroid), state.heroid)
                counter += 1
                if counter == 8:
                    self.player_info_update.emit(states)
                    if after_first_combat:
                        self.end_combat.emit(False)
                if not after_first_combat:
                    after_first_combat = True
            elif job == log_parser.JOB_BOARDINFO:
                self.comp_update.emit(state, round_number)

                combat = from_state(state)
                combat["round"] = round_number
                combats.append(combat)
            elif job == log_parser.JOB_ENDCOMBAT:
                counter = 0
            elif job == log_parser.JOB_ENDGAME:
                self.end_combat.emit(True)
                if state and current_player and session_id and build_id:
                    match_data["tracker-id"] = api_id
                    match_data["tracker-version"] = version.__version__
                    match_data["player-id"] = current_player.playerid
                    match_data["display-name"] = current_player.displayname
                    match_data["match-id"] = session_id
                    match_data["build-id"] = build_id
                    match_data["combat-info"] = combats
                    match_data["placement"] = state.place
                    match_data["players"] = states.json_friendly()
                    self.stats_update.emit(asset_utils.get_card_name(current_player.heroid), state, session_id, match_data)
            elif job == log_parser.JOB_HEALTHUPDATE:
                self.health_update.emit(state)
            elif job == log_parser.JOB_CARDUPDATE:
                self.update_card.emit(state)


class SBBTracker(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SBBTracker")
        self.comps = [BoardComp(self) for _ in range(0, 8)]
        self.round_indicator = QLabel(tr("Waiting for match to start..."))
        self.round_indicator.setFont(round_font)
        self.player_stats = stats.PlayerStats()
        self.player_ids = []
        self.most_recent_combat = None
        self.in_matchmaking = False
        self.sim_results = {}
        self.shop_display = ShopDisplay()
        if settings.get(settings.show_id_window):
            self.shop_display.show()

        self.overlay = OverlayWindow(self)
        self.streamer_overlay = StreamerOverlayWindow(self)
        self.overlay.stream_overlay = self.streamer_overlay
        settings.get(settings.enable_overlay)
        self.show_overlay()
        if settings.get(settings.streaming_mode):
            self.streamer_overlay.set_transparency()
            self.streamer_overlay.show()
        self.streamable_scores = StreamableMatchDisplay()
        self.show_scores()

        self.comp_tabs = QTabWidget(self)
        for index in range(len(self.comps)):
            self.comp_tabs.addTab(self.comps[index], f"Player{index}")

        self.reset_button = QPushButton(tr("Reattach to Storybook Brawl"))
        self.reset_button.setMaximumWidth(self.reset_button.fontMetrics().boundingRect("Reattach to Storybook Brawl")
                                          .width() * 2)
        self.reset_button.clicked.connect(self.reattach_to_log)
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
        self.board_analysis = BoardAnalysis(size=self.size(), player_ids=self.player_ids)
        self.hero_selection = HeroSelection(self)

        main_tabs = QTabWidget()
        main_tabs.addTab(comps_widget, tr("Board Comps"))
        main_tabs.addTab(self.hero_selection, tr("Hero Selection"))
        main_tabs.addTab(self.live_graphs, tr("Live Graphs"))
        main_tabs.addTab(self.match_history, tr("Match History"))
        main_tabs.addTab(self.stats_graph, tr("Stats Graphs"))
        main_tabs.addTab(self.board_analysis, "Simulator")

        self.main_tabs = main_tabs

        toolbar = QToolBar(self)
        toolbar.setMinimumHeight(40)
        toolbar.setStyleSheet("QToolBar {border-bottom: none; border-top: none;}")
        discord_action = QAction(QPixmap(asset_utils.get_asset("icons/discord.png")), "&"+tr("Join our Discord"), self)
        # toolbar.insertAction(toolbar.minimize, discord_action)
        toolbar.addAction(discord_action)
        discord_action.triggered.connect(self.open_discord)

        bug_action = QAction(QPixmap(asset_utils.get_asset("icons/bug_report.png")), "&"+tr("Report a bug"), self)
        toolbar.insertAction(discord_action, bug_action)
        bug_action.triggered.connect(self.open_issues)

        self.settings_window = SettingsWindow(self)
        settings_action = QAction(QPixmap(asset_utils.get_asset("icons/settings.png")), "&"+tr("Settings"), self)
        toolbar.insertAction(bug_action, settings_action)
        settings_action.triggered.connect(self.settings_window.show)

        self.export_comp_action = QAction(QPixmap(asset_utils.get_asset("icons/file-export.png")),
                                          "&"+tr("Export last combat"), self)
        toolbar.insertAction(bug_action, self.export_comp_action)
        self.export_comp_action.triggered.connect(self.export_last_comp)
        self.export_comp_action.setVisible(settings.get(settings.export_comp_button))

        patch_notes_action = QAction(QPixmap(asset_utils.get_asset("icons/information.png")), "&"+tr("Patch Notes"), self)
        toolbar.insertAction(self.export_comp_action, patch_notes_action)
        patch_notes_action.triggered.connect(self.show_patch_notes)

        main_tabs.setCornerWidget(toolbar)

        self.update_banner = QToolBar(self)
        self.update_banner.setMinimumHeight(40)
        self.update_banner.setStyleSheet(
            f"QToolBar {{border-bottom: none; border-top: none; background: {primary_color};}}")
        update_text = QLabel(tr("    An update is available! Would you like to install?    "))
        update_text.setStyleSheet(f"QLabel {{ color : {default_bg_color}; }}")
        self.update_banner.addWidget(update_text)

        yes_update = QAction("&"+tr("Yes"), self)
        yes_update.triggered.connect(self.install_update)
        no_update = QAction("&"+tr("Remind me later"), self)
        no_update.triggered.connect(self.update_banner.hide)
        self.update_banner.addAction(yes_update)
        self.update_banner.addAction(no_update)
        self.update_banner.hide()

        self.setWindowIcon(QIcon(asset_utils.get_asset("icon.png")))

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.update_banner)
        main_layout.addWidget(main_tabs)

        self.setCentralWidget(main_widget)
        self.setMinimumSize(QSize(1200, 820))
        self.setBaseSize(QSize(1400, 900))
        self.github_updates = updater.UpdateCheckThread()
        self.github_updates.github_update.connect(self.handle_update)

        self.log_updates = LogThread()
        self.log_updates.comp_update.connect(self.update_comp)
        self.log_updates.player_update.connect(self.update_player)
        self.log_updates.round_update.connect(self.update_round_num)
        self.log_updates.stats_update.connect(self.update_stats)
        self.log_updates.player_info_update.connect(self.live_graphs.update_graph)
        self.log_updates.player_info_update.connect(self.overlay.update_placements)
        self.log_updates.player_info_update.connect(self.streamer_overlay.update_placements)
        self.log_updates.new_game.connect(self.new_game)
        self.log_updates.health_update.connect(self.update_health)
        self.log_updates.end_combat.connect(self.end_combat)
        self.log_updates.update_card.connect(self.shop_display.update_card)
        self.log_updates.hero_discover.connect(self.update_hero_discover)

        self.board_queue = Queue()
        self.simulation = SimulationThread(self.board_queue)
        self.simulation.end_simulation.connect(self.overlay.simulation_stats.update_chances)
        self.simulation.end_simulation.connect(self.streamer_overlay.simulation_stats.update_chances)
        self.simulation.end_simulation.connect(self.end_simulation)
        self.simulation.error_simulation.connect(self.overlay.simulation_stats.show_error)
        self.simulation.error_simulation.connect(self.streamer_overlay.simulation_stats.show_error)
        self.simulation.error_simulation.connect(self.simulation_error)

        self.sbb_watcher_thread = SBBWindowCheckThread()
        self.sbb_watcher_thread.changed_foreground.connect(self.overlay.visible_in_bg)
        self.sbb_watcher_thread.changed_rect.connect(self.overlay.set_rect)

        self.resize(1300, 800)

        self.sbb_watcher_thread.start()
        self.log_updates.start()
        self.github_updates.start()
        self.simulation.start()

    def get_player_index(self, player_id: str):
        if player_id not in self.player_ids:
            self.player_ids.append(player_id)
        return self.player_ids.index(player_id)

    def new_game(self, matchmaking):
        self.in_matchmaking = matchmaking
        self.player_ids.clear()
        self.sim_results.clear()
        self.shop_display.clear()
        self.overlay.enable_hovers()
        self.overlay.hide_hero_rates()
        self.overlay.turn_display.setVisible(settings.get(settings.enable_turn_display))
        self.streamer_overlay.turn_display.setVisible(settings.get(settings.enable_turn_display))
        for index in range(0, 8):
            self.comp_tabs.tabBar().setTabTextColor(index, "white")
            comp = self.comps[index]
            comp.composition = None
            comp.player = None
            comp.current_round = 0
            comp.last_seen = None

        for overlay in [self.overlay, self.streamer_overlay]:
            overlay.comp_widget.reset()
            overlay.simulation_stats.reset_chances()

    def end_combat(self, end_of_game):
        self.overlay.simulation_stats.update_labels()
        self.streamer_overlay.simulation_stats.update_labels()
        if end_of_game:
            self.overlay.hide_hero_rates()
            self.overlay.disable_hovers()
            self.overlay.turn_display.setVisible(False)

    def get_comp(self, index: int):
        return self.comps[index]

    def update_round_num(self, round_number):
        self.round_indicator.setText(f"Turn {round_number} ({round_to_xp(round_number)})")
        self.round_indicator.update()
        self.overlay.update_round(round_number)
        self.overlay.hide_hero_rates()

    def update_player(self, player, round_number):
        index = self.get_player_index(player.playerid)
        real_hero_name = asset_utils.get_card_name(player.heroid)
        title = f"{real_hero_name}"
        if player.health <= 0:
            self.comp_tabs.tabBar().setTabTextColor(index, "red")
            title += tr(" *DEAD*")
        self.comp_tabs.tabBar().setTabText(index, title)
        comp = self.get_comp(index)
        comp.player = player
        comp.current_round = round_number
        self.overlay.update_player(index, player.health, f"{player.level}.{player.experience}", round_number, player.place)
        self.update()

    def update_comp(self, state, round_number):
        for player_id in state:
            board = state[player_id]
            index = self.get_player_index(player_id)
            comp = self.get_comp(index)

            player = comp.player
            board_player = None
            for char in board:
                if char.zone == "Hero":
                    board_player = char
                    break
            if player and board_player:
                board_player.level = player.level
            elif board_player:
                board_player.level = 0
            comp.composition = board
            comp.last_seen = round_number
            self.board_analysis.update_comp(board, round_number, player_id)
            self.overlay.update_comp(index, board, round_number)
            self.streamer_overlay.update_comp(index, board, round_number)
            self.update()

        self.overlay.simulation_stats.reset_chances()
        self.streamer_overlay.simulation_stats.reset_chances()
        self.most_recent_combat = state
        if settings.get(settings.enable_sim):
            if self.board_queue.qsize() == 0:
                self.board_queue.put((state, self.player_ids[0], settings.get(settings.number_simulations, 1000),
                                      settings.get(settings.number_threads, 3), round_number))

    def update_stats(self, starting_hero: str, player, session_id: str, match_data):
        if settings.get(settings.upload_data) and self.in_matchmaking and session_id not in self.player_stats.df['SessionId'].values:
            # upload only matchmade games
            for round_num in self.sim_results:
                index = round_num - 1
                if "combat-info" in match_data and index < len(match_data["combat-info"]):
                    match_data["combat-info"][index]["sim-results"] = self.sim_results[round_num]
            upload_data(match_data)
        if settings.get(settings.save_stats, True) and (
                not settings.get(settings.matchmaking_only) or self.in_matchmaking):
            place = player.place if int(player.health) <= 0 else "1"
            self.player_stats.update_stats(starting_hero, asset_utils.get_card_name(player.heroid),
                                           place, player.mmr, session_id)
            if match_data:
                self.player_stats.save_match_info(match_data, session_id)
            self.match_history.update_history_table()
            self.match_history.update_stats_table()
            if settings.get(settings.streamable_score_list):
                self.streamable_scores.add_score(place)

    def update_health(self, player):
        index = self.get_player_index(player.playerid)
        new_place = int(player.place)
        places = self.overlay.places
        places.remove(index)
        places.insert(new_place - 1, index)

    def end_simulation(self, win, tie, loss, win_dmg, loss_dmg, round_num):
        self.sim_results[round_num] = {"win-percent": win, "tie-percent": tie, "loss-percent": loss, "win-dmg": win_dmg, "loss-dmg": loss_dmg}

    def simulation_error(self, error, round_num):
        self.sim_results[round_num] = {"error": error}

    def show_overlay(self):
        if settings.get(settings.enable_overlay):
            self.overlay.show()
        else:
            self.overlay.hide()

    def show_scores(self):
        if settings.get(settings.streamable_score_list):
            self.streamable_scores.show()
        else:
            self.streamable_scores.hide()

    def update_hero_discover(self, hero_ids):
        self.hero_selection.update_heroes(hero_ids, self.player_stats, self.overlay)
        self.main_tabs.setCurrentIndex(1)

    def export_last_comp(self):
        if self.most_recent_combat:
            with open(paths.sbbtracker_folder.joinpath("last_combat.json"), "w") as file:
                json.dump(from_state(asset_utils.replace_template_ids(self.most_recent_combat)),
                          file, default=lambda o: o.__dict__)

    def open_discord(self):
        open_url(self, 'https://discord.com/invite/2AJctfj239')

    def open_github_release(self):
        open_url(self, "https://github.com/SBBTracker/SBBTracker/releases/latest")

    def open_issues(self):
        open_url(self, "https://github.com/SBBTracker/SBBTracker/issues")

    def show_patch_notes(self):
        try:
            with open(patch_notes_file, "r") as file:
                patch_notes = file.read()
                QMessageBox.information(self, "Patch Notes", patch_notes)
                settings.set_(settings.show_patch_notes, False)
        except Exception:
            logging.exception("Couldn't read patch notes file!")

    def handle_update(self, update_avail, patch_notes):
        if update_avail:
            self.update_banner.show()
            try:
                with open(patch_notes_file, "w") as file:
                    file.write(patch_notes)
            except Exception:
                logging.exception("Couldn't write patch notes!")

    def install_update(self):
        if paths.os_name == "Windows":
            dialog = QDialog(self)
            dialog.setWindowTitle(tr("Updater"))
            dialog_layout = QVBoxLayout(dialog)
            self.download_progress = QProgressBar(dialog)
            dialog_layout.addWidget(QLabel(tr("Downloading update...")))
            dialog_layout.addWidget(self.download_progress)
            dialog.show()
            dialog.update()
            logging.info("Starting download...")
            updater.self_update(self.handle_progress)
            settings.set_(settings.show_patch_notes, True)
            self.close()
            sys.exit(0)
        else:
            self.open_github_release()

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
        if filepath:
            self.player_stats.export(Path(filepath))

    def delete_stats(self, window):
        reply = QMessageBox.question(window, tr("Delete all Stats"), tr("Do you want to delete *ALL* saved stats?"))
        if reply == QMessageBox.Yes:
            self.player_stats.delete()
            self.match_history.update_history_table()

    def reattach_to_log(self):
        try:
            os.remove(log_parser.offsetfile)
        except Exception as e:
            logging.warning(str(e))
        self.update()

    def closeEvent(self, *args, **kwargs):
        super(QMainWindow, self).closeEvent(*args, **kwargs)
        self.github_updates.terminate()
        self.log_updates.terminate()
        self.simulation.terminate()
        self.sbb_watcher_thread.terminate()
        self.player_stats.save()
        self.overlay.close()
        self.streamer_overlay.close()
        self.streamable_scores.close()
        settings.save()


class MatchHistory(QWidget):
    def __init__(self, parent, player_stats: stats.PlayerStats):
        super().__init__()
        self.parent = parent
        self.player_stats = player_stats
        self.match_history_table = QTableWidget(stats.stats_per_page, 4)
        self.page = 1
        self.display_starting_hero = 0
        self.filter_ = settings.get(settings.filter_)
        if self.filter_ not in default_dates:
            self.filter_ = tr("All Matches")
            settings.set_(settings.filter_, self.filter_)
        self.match_history_table.setHorizontalHeaderLabels([tr("Starting Hero"), tr("Ending Hero"), tr("Place"),
                                                            tr("+/- MMR")])
        self.match_history_table.setColumnWidth(0, 140)
        self.match_history_table.setColumnWidth(1, 140)
        self.match_history_table.setColumnWidth(2, 80)
        self.match_history_table.setColumnWidth(3, 85)
        self.match_history_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.match_history_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.match_history_table.setContextMenuPolicy(Qt.CustomContextMenu)

        def history_menu(position):
            menu = QMenu()
            delete_action = menu.addAction(tr("Delete"))
            action = menu.exec(self.match_history_table.mapToGlobal(position))
            if action == delete_action:
                self.player_stats.delete_entry(self.match_history_table.itemAt(position).row() +
                                               (self.page - 1) * stats.stats_per_page, reverse=True)
                self.update_history_table()

        self.match_history_table.customContextMenuRequested.connect(history_menu)

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
        self.stats_table = QTableWidget(asset_utils.get_num_heroes() + 1, 6)
        self.stats_table.setHorizontalHeaderLabels([tr(heading) for heading in stats.headings])
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
        hero_types = [tr("Starting Heroes"), tr("Ending Heroes")]
        self.toggle_hero.activated.connect(self.toggle_heroes)
        self.toggle_hero.addItems(hero_types)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(default_dates)
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
        start, end = get_date_range(self.filter_)
        hero_stats = self.player_stats.filter(start, end, self.sort_col, self.sort_asc)
        chosen_stats = hero_stats[self.display_starting_hero]
        update_table(self.stats_table, chosen_stats)

    def toggle_heroes(self, index: int):
        self.display_starting_hero = index
        self.update_stats_table()

    def filter_stats(self):
        self.filter_ = self.filter_combo.currentText()
        settings.set_(settings.filter_, self.filter_)
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
        self.user_palette = settings.get(settings.live_palette)
        self.states = None

        self.health_canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.xp_canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.health_ax = self.health_canvas.figure.subplots()
        self.xp_ax = self.xp_canvas.figure.subplots()

        graphs_tabs = QTabWidget(self)
        graphs_tabs.addTab(self.health_canvas, tr("Health Graph"))
        graphs_tabs.addTab(self.xp_canvas, tr("XP Graph"))
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

        self.mmr_range = QComboBox()
        self.mmr_range.setMaximumWidth(200)
        self.mmr_range.addItems(["25", "50", "100"])
        self.mmr_range.activated.connect(self.update_mmr_range)
        self.range_label = QLabel(tr("# Matches"))

        self.range = 25

        self.layout = QVBoxLayout(self)
        combo_layout = QHBoxLayout(self)
        combo_layout.addWidget(self.graph_selection, alignment=Qt.AlignLeft)
        combo_layout.addWidget(self.range_label, alignment=Qt.AlignRight)
        combo_layout.addWidget(self.mmr_range, alignment=Qt.AlignLeft)
        combo_layout.addStretch()
        self.layout.addLayout(combo_layout)
        self.layout.addWidget(self.canvas)

        self.update_graph()

    def update_graph(self):
        self.selection = self.graph_selection.currentText()
        self.ax.cla()
        self.mmr_range.setVisible(self.selection == graphs.mmr_change)
        self.range_label.setVisible(self.selection == graphs.mmr_change)
        self.figure = graphs.stats_graph(self.player_stats.df, self.selection, self.ax, self.range)
        self.canvas.draw()

    def update_mmr_range(self):
        self.range = int(self.mmr_range.currentText())
        self.update_graph()


class HeroSelection(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.heroes = [HeroStatsWidget(self) for _ in range(0, 4)]
        layout = QHBoxLayout(self)
        for widget in self.heroes:
            layout.addWidget(widget)

    def update_heroes(self, hero_ids, player_stats: stats.PlayerStats, overlay):
        hero_names = []
        for i in range(0, 4):
            hero_id = hero_ids[i]
            hero_name = asset_utils.get_card_name(hero_id)
            hero_names.append(hero_name)
            placement, matches, histogram = player_stats.get_stats_for_hero(*get_date_range(latest_patch), hero_name)
            self.heroes[i].update_hero(placement, matches, histogram, hero_id)
            overlay.update_hero_rates(i, placement, matches)
        overlay.update_data_url(hero_names)


class HeroStatsWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        font = QFont("Roboto", 20)
        self.placement = QLabel("Avg Placement: " + "0.00")
        self.placement.setFont(font)
        self.num_matches = QLabel("Matches: " + "0")
        self.num_matches.setFont(font)
        self.hero_label = QLabel()
        self.hero_label.setFont(font)
        self.hero_name_label = QLabel()
        self.hero_name_label.setFont(font)
        self.histogram = HistogramWidget(self)
        self.histogram.setFixedSize(300, 250)

        layout = QVBoxLayout(self)
        layout.addWidget(self.hero_name_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.hero_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.placement, alignment=Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(self.num_matches, alignment=Qt.AlignCenter | Qt.AlignTop)
        layout.addWidget(self.histogram, alignment=Qt.AlignCenter | Qt.AlignTop)
        layout.addStretch()

    def update_hero(self, placement, matches, histogram, hero_id):
        hero_name = asset_utils.get_card_name(hero_id)
        pixmap = QPixmap(asset_utils.get_card_path(hero_id, False))
        self.hero_label.setPixmap(pixmap)
        self.hero_name_label.setText(hero_name)
        self.placement.setText(tr("Avg Place") + ": " + str(placement))
        self.num_matches.setText(tr("# Matches") + ": " + str(matches))
        self.histogram.draw_hist(histogram)


class HistogramWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.figure = None
        self.canvas = FigureCanvasQTAgg(plt.Figure(figsize=(13.5, 18)))
        self.ax = self.canvas.figure.subplots()
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def draw_hist(self, series):
        self.ax.cla()
        self.ax.bar(np.arange(1,9), series[0], width=1)
        self.ax.set_xticks(np.arange(1,9))
        self.ax.set_title(tr("Placements"))
        self.canvas.draw()
