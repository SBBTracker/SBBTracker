import concurrent
import hashlib
import json
import logging
import operator
import time
import random
from collections import defaultdict
from queue import Queue
from statistics import mean, median

from PySide6.QtCore import QSize, QThread, Signal
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSplitter, \
    QStackedLayout, \
    QVBoxLayout, QWidget
from sbbbattlesim import SBBBSCrocException, from_state, simulate

from sbbtracker import paths, rearrange, settings
from sbbtracker.utils import asset_utils
from sbbtracker.utils.sbb_logic_utils import round_to_xp
from sbbtracker.windows.board_comps import BoardComp
from sbbtracker.windows.constants import default_bg_color_rgb
from sbbtracker.windows.overlays import HoverRegion, SimStatWidget

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
                    self.error_simulation.emit("Captain Croc not supported", round_number)
                except concurrent.futures.TimeoutError:
                    self.error_simulation.emit("Simulation timed out!", round_number)
                except Exception:
                    logging.exception("Error in simulation!")
                    with open(paths.sbbtracker_folder.joinpath("error_board.json"), "w") as file:
                        json.dump(from_stated, file, default=lambda o: o.__dict__)
                    self.error_simulation.emit("Error in simulation!", round_number)

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
                self.error_simulation.emit("Couldn't get player id (try reattaching)", round_number)
            time.sleep(1)


class SimulationManager(QThread):
    # Maybe have good errors?
    # end_simulation = Signal(str, str, str, str, str)
    # error_simulation = Signal(str)

    def __init__(self, analysis_queue, simulated_stats, results_board):
        super(SimulationManager, self).__init__()
        self.analysis_queue = analysis_queue

        # initialize simulation queue and results
        self.simulated_stats = simulated_stats
        self.results_board = results_board
        self.queue = Queue()

        self.simulation = SimulationThread(self.queue)
        self.simulation.end_simulation.connect(self.update_chances)
        self.simulation.error_simulation.connect(self.sim_error)
        self.simulation.start()

    def sim_error(self, *args, **kwargs):
        self.active_conditions.remove(self.active_condition)

    def update_chances(self, win, tie, loss, win_dmg, loss_dmg):
        self.active_condition.update_reward(win, tie, loss, win_dmg, loss_dmg)
        self.sim_is_done = True

    def eliminate(self):
        mean_win = median([cond.win for cond in self.active_conditions])
        to_remove = []
        for active_condition in self.active_conditions:
            if active_condition.win < mean_win:
                to_remove.append(active_condition)

        for active_condition in to_remove:
            self.active_conditions.remove(active_condition)

    def best_board(self):
        max_win = max(cond.win for cond in self.active_conditions)
        return next(cond for cond in self.active_conditions if cond.win == max_win)

    def stop_condition(self):
        if len(self.active_conditions) == 1:
            return True
        elif len(set(cond.win for cond in self.active_conditions)) == 1:
            self.all_boards_equal = True
            return True
        else:
            return False

    # This should move into the simulator to include supports and treasures
    @staticmethod
    def moves(slot):
        # given a slot, what are the nearest neighbors
        slot_dests = {
            0: (1, 4),
            1: (0, 2, 4, 5),
            2: (1, 3, 5, 6),
            3: (2, 6),
            4: (0, 1, 5),
            5: (1, 2, 4, 6),
            6: (2, 3, 5),
        }[int(slot)]

        print(f"looking to move character in {slot=}")

        return [
            (slot, slot_dest)
            for slot_dest in slot_dests
        ]

    @staticmethod
    def random_slot(board, last_moved_to):
        characters = [
            int(character.slot) for character in board["player"]
            if character.zone == "Character"
            and character.slot != last_moved_to
        ]
        return random.choice(characters)

    @staticmethod
    def hash(board):
        # sort and dump to json
        data = json.dumps(
            dict(
                sorted(
                    (
                        (
                            k,
                            list(
                                map(
                                    lambda x: json.loads(
                                        str(x)),
                                        sorted(v, key=lambda x: (x.slot, x.zone)
                                    )
                                )
                            )
                        )
                        for k, v in board.items()
                    )
                )
            )
        )
        return hashlib.md5(data.encode("utf-8")).hexdigest()


    def run(self):
        num_simulations = 1000 # settings.get(settings.number_threads, 3)
        num_threads = settings.get(settings.number_threads, 3)
        self.all_boards_equal = False
        while True:
            board = self.analysis_queue.get()
            print(board["player"])
            print(list(map(type, board["player"])))
            playerid = "player"
            # search for one local maxima
            current_board = None
            self.simulated_boards = []
            best_boards = []
            for _ in range(3):
                if current_board is None:
                    print("starting search from player board state")
                    current_board = ActiveCondition(board)
                else:
                    print("starting search from random board state")
                    current_board = ActiveCondition(
                        rearrange.randomize_board(board)
                    )
                board_hash = self.hash(current_board.board)
                print(f"{board_hash=}")
                # self.active_condition will concurrently be update with its results
                self.active_condition = current_board
                self.sim_is_done = False
                print(f"running {num_simulations} simulations")
                self.queue.put(
                    # TODO: if ambrosia, error/warn
                    (
                        self.active_condition.board,
                        playerid,
                        num_simulations,
                        num_threads,
                        0
                    )
                )
                while not self.sim_is_done:
                    time.sleep(1)

                self.results_board.composition = current_board.board["player"]
                self.results_board.update()
                self.simulated_stats.update_chances(
                    *current_board.chances(),
                )
                print(f"Initial result was:\n  {self.active_condition.chances()}")
                self.simulated_boards.append(board_hash)
                # if all options get worse/stay the same, break
                best_boards.append(self.active_condition)
                last_res = self.active_condition.win

                last_moved_to = None
                for _ in range(7):
                    random_restart = True
                    while True:
                        if random_restart is True:
                            # start at a random slot
                            moves = self.moves(
                                self.random_slot(current_board.board, last_moved_to)
                            )
                            random_restart = False
                        else:
                            # keep climbing the hill if we just made a positive step
                            moves = self.moves(last_moved_to)
                        step_results = []
                        for move in moves:
                            new_board = rearrange.make_swap(
                                current_board.board, *move
                            )

                            # should make this an @cachedproperty of ActiveConditon
                            board_hash = self.hash(new_board)
                            print(f"{board_hash=}")
                            if board_hash in self.simulated_boards:
                                continue
                            self.active_condition = ActiveCondition(new_board)
                            self.active_condition.move = move
                            # self.active_condition will concurrently be update with its results
                            step_results.append(self.active_condition)
                            self.sim_is_done = False
                            print(f"running {num_simulations} simulations")
                            self.queue.put(
                                # TODO: if ambrosia, error/warn
                                (
                                    self.active_condition.board,
                                    playerid,
                                    num_simulations,
                                    num_threads,
                                    0
                                )
                            )
                            while not self.sim_is_done:
                                time.sleep(1)

                            self.simulated_boards.append(board_hash)

                        if not step_results:
                            print("all neighbors previously simulated")
                            break

                        max_res = max(map(lambda condition: condition.win, step_results))
                        best_step = next(
                            condition
                            for condition in step_results
                            if condition.win == max_res
                        )
                        # if all options get worse/stay the same, do a random restart
                        if max_res <= last_res:
                            print("No step yields better result")
                            best_boards.append(current_board)
                            break
                        print(f"best result was: {best_step.move=}\n  {best_step.chances()}")
                        current_board = best_step
                        last_moved_to = best_step.move[-1]
                        last_res = max_res

                        self.results_board.composition = current_board.board["player"]
                        self.results_board.update()
                        self.simulated_stats.update_chances(
                            *current_board.chances(),
                        )

            best_result = max(map(lambda condition: condition.win, best_boards))
            best_board = next(
                condition
                for condition in best_boards
                if condition.win == best_result
            )
            # move is (from, to)
            self.results_board.composition = best_board.board["player"]
            self.results_board.update()
            self.simulated_stats.update_chances(
                *best_board.chances(),
            )
            print("SIMULATION DONE")

class BoardAnalysis(QWidget):
    def __init__(self, size, player_ids):
        super().__init__()
        self.player_ids = player_ids
        self.layout = QVBoxLayout(self)

        self.last_brawl = QSplitter(Qt.Horizontal)
        # Submit analysis button
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        submit_button = QPushButton("Submit")
        submit_button.clicked.connect(self.run_simulations)
        btn_layout.addWidget(submit_button)
        self.last_brawl.addWidget(btn_widget)
        # Submit analysis tab
        self.player_board = BoardComp(scale=0.5)
        self.opponent_board = BoardComp(scale=0.5)
        self.last_brawl.addWidget(self.player_board)
        self.last_brawl.addWidget(self.opponent_board)

        # Simulation results tab
        self.sim_results = QWidget()
        self.simulated_stats = BoardAnalysisSimulationResults(self.sim_results)
        self.results_board = BoardComp(scale=0.5)

        # Put it all together
        self.layout.addWidget(self.last_brawl)
        self.layout.addWidget(self.sim_results)
        self.layout.addWidget(self.results_board)

        self.analysis_queue = Queue()
        self.simulation_manager = SimulationManager(
            self.analysis_queue, self.simulated_stats, self.results_board,
        )
        self.simulation_manager.start()


    def set_color_palette(self, palette):
        self.user_palette = palette
        self.update_graph()

    def update_comp(self, player, round_number, player_id):
        # The person playing is player_ids[0]
        if player_id == self.player_ids[0]:
            comp = self.player_board
        else:
            comp = self.opponent_board
        comp.composition = player
        comp.last_seen = round_number
        self.update()

    def run_simulations(self):
        board = {
            "player": self.player_board.composition,
            "opponent": self.opponent_board.composition,
        }
        self.analysis_queue.put(
            board
        )
        # clear board results:
        self.simulated_stats.reset_chances()

class ActiveCondition:
    def __init__(self, board):
        # win, tie, loss, win_dmg, loss_dmg
        self.board = board

    def update_reward(self, win, tie, loss, win_dmg, loss_dmg):
        self.win = win / 100
        self.tie = tie / 100
        self.loss = loss / 100
        self.win_dmg = win_dmg
        self.loss_dmg = loss_dmg

    def chances(self):
        return (
            f"{self.win*100:.2f}%",
            f"{self.tie*100:.2f}%",
            f"{self.loss*100:.2f}%",
            f"{self.win_dmg:.2f}",
            f"{self.loss_dmg:.2f}",
        )

class BoardAnalysisOverlay(QWidget):
    simluation_update = Signal(str, str, str, str, str)

    def __init__(self, parent):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setWindowTitle("SBBTrackerOverlay")

        self.simulated_board = QSplitter(Qt.Horizontal)
        # Submit analysis tab
        self.player_board = BoardComp(scale=0.5)
        self.opponent_board = BoardComp(scale=0.5)
        self.simulated_board.addWidget(self.player_board)
        self.simulated_board.addWidget(self.opponent_board)
        self.main_frame = QFrame()
        self.main_frame.move(300, 700)
        self.layout = QHBoxLayout(self.main_frame)
        self.layout.addWidget(self.simulated_board)
        self.msg = QLabel("all boards equal")
        self.layout.addWidget(self.simulated_board)
        self.layout.addWidget(self.msg)
        self.msg.setVisible(False)

        self.visible = True
        self.scale_factor = 1
        self.dpi_scale = 1
        self.hover_region = HoverRegion(
            parent, *map(
                operator.mul, (400, 80), (self.scale_factor, self.scale_factor)
            )
        )
        self.base_comp_size = QSize(550, 325)
        self.disable_hover()
        self.update_comp_scaling()
        self.enable_hover()

        self.hover_region.move(420, 85)
        size = QSize(210, 80)
        self.hover_region.resize(size)
        self.hover_region.background.setFixedSize(size)
        self.hover_region.enter_hover.connect(lambda: self.show_hide_comp(True))
        self.hover_region.leave_hover.connect(lambda: self.show_hide_comp(False))

    def visible_in_bg(self, visible):
        self.visible = visible
        self.setVisible(visible)

    def disable_hover(self):
        self.hover_region.setVisible(False)

    def enable_hover(self):
        self.hover_region.setVisible(True)

    def show_hide_comp(self, show_or_hide: bool):
        self.main_frame.setVisible(show_or_hide)

    def update_round(self, round_num):
        self.turn_display.update_label(f"Turn {round_num} ({round_to_xp(round_num)})")
        if self.stream_overlay:
            self.stream_overlay.update_round(round_num)

    def update_comps(self, player_board, opponent_board):
        self.simulated_board.setVisible(True)
        self.msg.setVisible(False)
        self.player_board.composition = player_board
        self.player_board.last_seen = 0
        self.player_board.current_round = 0
        self.opponent_board.composition = opponent_board
        self.opponent_board.last_seen = 0
        self.opponent_board.current_round = 0
        self.update()

    def update_comp_scaling(self):
        self.player_board.setFixedSize(self.base_comp_size) # * comp.scale)
        self.opponent_board.setFixedSize(self.base_comp_size) # * comp.scale)
        self.player_board.updateGeometry()
        self.opponent_board.updateGeometry()

    def set_transparency(self):
        alpha = (100 - settings.get(settings.boardcomp_transparency, 0)) / 100
        style = f"background-color: rgba({default_bg_color_rgb}, {alpha});"
        self.hover_region.setStyleSheet(style)

    def toggle_transparency(self):
        if settings.get(settings.streaming_mode):
            self.setWindowFlags(self.windowFlags() | Qt.SubWindow)
        else:
            self.setWindowFlags(Qt.SubWindow)

    def show_error(self):
        self.simulated_board.setVisible(False)
        self.msg.setVisible(True)
        self.update()


class BoardAnalysisSimulationResults(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.sim_is_done = True
        self.parent = parent
        self.move(420, 85)

        self.layout = QStackedLayout(self)
        background = QFrame(self)
        self.layout.addWidget(background)

        self.win_dmg_label = QLabel("-", background)
        self.win_label = QLabel("-", background)
        self.tie_label = QLabel("-", background)
        self.loss_label = QLabel("-", background)
        self.loss_dmg_label = QLabel("-", background)

        self.win_dmg = "-"
        self.win = "-"
        self.loss = "-"
        self.tie = "-"
        self.loss_dmg = "-"
        self.displayable = False

        label_layout = QGridLayout(background)

        win_dmg_title = QLabel("DMG")
        win_percent_title = QLabel("WIN")
        win_dmg_title.setStyleSheet("QLabel { color : #9FD4A3 }")
        win_percent_title.setStyleSheet("QLabel { color : #9FD4A3 }")

        loss_dmg_title = QLabel("DMG")
        loss_percent_title = QLabel("LOSS")
        loss_dmg_title.setStyleSheet("QLabel { color : #e3365c }")
        loss_percent_title.setStyleSheet("QLabel { color : #e3365c }")

        tie_title = QLabel("TIE")

        self.error_widget = QFrame(self)
        error_layout = QVBoxLayout(self.error_widget)
        self.error_msg = QLabel("Error in simulation!")
        error_layout.addWidget(self.error_msg, alignment=Qt.AlignCenter)
        error_layout.setContentsMargins(0, 0, 0, 0)
        self.error_msg.setStyleSheet(
            "QLabel#sim-error { text-align: center; font-size: 20px; background-color: rgba(0,0,0,0%); }")
        self.error_msg.setObjectName("sim-error")
        self.error_msg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        label_layout.addWidget(SimStatWidget(self, win_dmg_title, self.win_dmg_label), 0, 0)
        label_layout.addWidget(SimStatWidget(self, win_percent_title, self.win_label), 0, 1)
        label_layout.addWidget(SimStatWidget(self, tie_title, self.tie_label), 0, 2)
        label_layout.addWidget(SimStatWidget(self, loss_percent_title, self.loss_label), 0, 3)
        label_layout.addWidget(SimStatWidget(self, loss_dmg_title, self.loss_dmg_label), 0, 4)

        self.layout.addWidget(self.error_widget)
        self.error_widget.setMinimumSize(background.minimumSize())

        label_layout.setSpacing(0)
        label_layout.setRowStretch(0, 1)
        label_layout.setRowStretch(1, 1)
        label_layout.setContentsMargins(0, 0, 0, 0)

    def reset_chances(self):
        self.win_dmg = "-"
        self.win = "-"
        self.tie = "-"
        self.loss = "-"
        self.loss_dmg = "-"
        self.win_dmg_label.setText(self.win_dmg)
        self.win_label.setText(self.win)
        self.loss_label.setText(self.loss)
        self.tie_label.setText(self.tie)
        self.loss_dmg_label.setText(self.loss_dmg)
        self.displayable = False
        self.layout.setCurrentIndex(0)

    def update_chances(self, win, tie, loss, win_dmg, loss_dmg):
        self.win_dmg = win_dmg
        self.win = win
        self.loss = loss
        self.tie = tie
        self.loss_dmg = loss_dmg
        self.update_labels()
        self.displayable = False

    def show_error(self, msg: str):
        self.error_msg.setText(msg)
        self.layout.setCurrentIndex(1)

    def update_labels(self):
        self.win_dmg_label.setText(self.win_dmg)
        self.win_label.setText(self.win)
        self.loss_label.setText(self.loss)
        self.tie_label.setText(self.tie)
        self.loss_dmg_label.setText(self.loss_dmg)
        self.displayable = True

    def sim_end(self, *args):
        self.sim_is_done = True