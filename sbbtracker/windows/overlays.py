import operator

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout, QHBoxLayout,
    QLabel,
    QLayout, QMainWindow,
    QPushButton, QSizePolicy, QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from sbbtracker import settings
from sbbtracker.utils import asset_utils, sbb_logic_utils
from sbbtracker.utils.sbb_logic_utils import round_to_xp
from sbbtracker.windows.board_comps import BoardComp
from sbbtracker.windows.constants import default_bg_color, default_bg_color_rgb


def portrait_location(resolution: (int, int)):
    x, y = resolution
    return 0.346 * y - 126


def get_hover_size(resolution: (int, int)):
    x, y = resolution
    width = 0.0773 * y + 0.687
    return width, width * 17 / 21


hover_size = (84, 68)
p1_loc = (38, 247)
hover_distance = 15
base_size = (1920, 1080)


def move_point_by_scale(x, y, scale):
    monitor_at_point = QGuiApplication.screenAt(QPoint(x, y))
    primary = QGuiApplication.primaryScreen()
    new_x, new_y = x * scale, y * scale
    if primary != monitor_at_point and primary and monitor_at_point:
        dimensions = monitor_at_point.size()
        if not (0 < x < dimensions.width()):
            if x < 0:
                new_x = x + dimensions.width()
            elif x > dimensions.width():
                new_x = x - dimensions.width()
            scaled_x = new_x * scale
            new_x = x - scaled_x
        if not (0 < y < dimensions.height()):
            if y < 0:
                new_y = y + dimensions.height()
            elif y > dimensions.height():
                new_y = y - dimensions.height()
            scaled_y = new_y * scale
            new_y = y - scaled_y

    return new_x, new_y


class OverlayBoardComp(BoardComp):
    def __init__(self):
        super().__init__()
        self.xps = []
        self.healths = []

    def update_history(self, xp, health):
        if len(self.xps) == 3:
            self.xps.pop(0)
            self.healths.pop(0)
        if xp == "6.0" or xp not in self.xps:
            self.xps.append(xp)
            self.healths.append(health)

    def get_image_location(self, position: int):
        if 7 <= position <= 9:
            x = (161 * (position - 7))
            y = 440
        else:
            x, y = super().get_image_location(position)
        return x, y

    def draw_hero(self, painter: QPainter):
        pass

    def draw_history(self, painter: QPainter):
        border = QRect(18, 40, 265, 390)
        painter.drawRoundedRect(border, 25, 25)
        for i in reversed(range(0, len(self.xps))):
            self.draw_xp(painter, (30, 50 + 130*(len(self.xps) - 1 - i)), self.xps[i])
            self.draw_health(painter, (140, 45 + 130*(len(self.healths)-1-i)), self.healths[i])

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.scale(self.scale, self.scale)
        self.draw_history(painter)


class OverlayWindow(QMainWindow):
    simluation_update = Signal(str, str, str, str, str)

    def __init__(self, main_window):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setWindowTitle("SBBTrackerOverlay")

        main_widget = QWidget()
        main_widget.setObjectName("overlay")
        main_widget.setStyleSheet("QWidget#overlay {background-color: rgba(0, 0, 0, 0);}")

        self.show_comps = settings.get(settings.enable_comps)
        self.main_window = main_window
        self.stream_overlay = None
        self.visible = True
        self.scale_factor = 1
        self.sbb_rect = QRect(0, 0, 1920, 1080)
        self.dpi_scale = 1
        self.hover_regions = [
            HoverRegion(main_widget, *map(operator.mul, hover_size, (self.scale_factor, self.scale_factor))) for _ in
            range(0, 8)]
        self.simulation_stats = SimulatorStats(main_widget)
        self.simulation_stats.setVisible(settings.get(settings.enable_sim))
        self.turn_display = TurnDisplay(main_widget)
        self.turn_display.setVisible(False)

        self.show_hide = True

        self.comps = [OverlayBoardComp() for _ in range(0, 8)]
        self.comp_widgets = [QFrame(main_widget) for _ in range(0, 8)]
        self.places = list(range(0, 8))
        self.new_places = list(range(0, 8))
        self.base_comp_size = QSize(1020, 650)
        for index in range(len(self.comps)):
            comp = self.comps[index]
            widget = self.comp_widgets[index]

            comp.setParent(widget)
            widget.setVisible(False)
            widget.move(round(self.size().width() / 2 - 100), 0)
        self.set_transparency()
        self.update_comp_scaling()

        self.show_button = QPushButton("Show Tracker", main_widget)
        self.show_button.clicked.connect(self.show_hide_main_window)
        self.show_button.move(40, 40)
        self.show_button.resize(self.show_button.sizeHint().width(), self.show_button.sizeHint().height())
        self.show_button.setVisible(settings.get(settings.show_tracker_button))

        self.setCentralWidget(main_widget)

        self.disable_hovers()

    def show_hide_main_window(self):
        if self.show_hide:
            self.main_window.setWindowState(Qt.WindowState.WindowActive)
            self.show_button.setText("Hide Tracker")
        else:
            self.main_window.showMinimized()
            self.show_button.setText("Show Tracker")
        self.show_hide = not self.show_hide

    def visible_in_bg(self, visible):
        if settings.get(settings.hide_overlay_in_bg) and settings.get(settings.enable_overlay):
            self.visible = visible
            self.setVisible(visible)

    def set_comps_enabled(self, state: bool):
        self.show_comps = state
        if state:
            self.enable_hovers()
        else:
            self.disable_hovers()

    def disable_hovers(self):
        for hover in self.hover_regions:
            hover.setVisible(False)

    def enable_hovers(self):
        if self.show_comps:
            for hover in self.hover_regions:
                hover.setVisible(True)

    def show_hide_comp(self, index, show_or_hide: bool):
        widget = self.comp_widgets[self.places[index]]
        widget.setVisible(show_or_hide)
        if self.stream_overlay:
            streamer_widget = self.stream_overlay.comp_widgets[self.places[index]]
            streamer_widget.setVisible(show_or_hide)

    def update_round(self, round_num):
        self.turn_display.update_label(f"Turn {round_num} ({round_to_xp(round_num)})")
        if self.stream_overlay:
            self.stream_overlay.update_round(round_num)

    def update_player(self, index, health, xp, round_num, place):
        self.comps[index].current_round = round_num
        self.comps[index].update_history(xp, health)
        self.new_places[int(place) - 1] = index
        if self.stream_overlay:
            self.stream_overlay.update_player(index, health, xp, round_num, place)

    def update_comp(self, index, player, round_number):
        comp = self.comps[index]
        comp.composition = player
        comp.last_seen = round_number
        self.update()

    def update_comp_scaling(self):
        for i in range(len(self.comps)):
            comp = self.comps[i]
            widget = self.comp_widgets[i]
            comp.scale = settings.get(settings.overlay_comps_scaling) / 100
            comp.setFixedSize(self.base_comp_size * comp.scale)
            widget.setFixedSize(self.base_comp_size * comp.scale)
            widget.updateGeometry()

    def update_placements(self):
        self.places = self.new_places.copy()
        self.new_places = list(range(0, 8))
        for widget in self.comp_widgets:
            #  fixes bug where hovering over the hero at the end of combat gets the overlay stuck
            widget.setVisible(False)

    def set_rect(self, left, top, right, bottom, dpi):
        self.dpi_scale = 1 / round(dpi / 96 - .24)  # round .75 and up to nearest int
        if settings.get(settings.disable_scaling):
            # Windows 8 scaling is different and I don't want to deal with it
            self.dpi_scale = 1
        left_edge = left
        top_edge = top
        right_edge = right - left
        bottom_edge = bottom - top
        if self.dpi_scale != 1:
            left_edge, top_edge = move_point_by_scale(left, top, self.dpi_scale)
            right_edge *= self.dpi_scale
            bottom_edge *= self.dpi_scale

        self.sbb_rect = QRect(left_edge, top_edge, right_edge, bottom_edge)
        sbb_is_visible = QGuiApplication.screenAt(self.sbb_rect.topLeft()) is not None or QGuiApplication.screenAt(
            self.sbb_rect.bottomRight()) is not None
        if sbb_is_visible:
            self.setFixedSize(self.sbb_rect.size())
            self.setGeometry(QGuiApplication.screens()[0].geometry())
            self.move(left_edge, top_edge)
            self.scale_factor = self.sbb_rect.size().height() / base_size[1]
            self.update_hovers()
            for widget in self.comp_widgets:
                widget.move(QPoint(round(self.size().width() / 2 - 100), 0) * self.dpi_scale)

            sim_pos = QPoint(*settings.get(settings.simulator_position, (self.sbb_rect.top() / 2 - 100, 0)))
            if not self.centralWidget().geometry().contains(sim_pos):
                sim_pos = QPoint(0, 0)
            self.simulation_stats.move(sim_pos * self.dpi_scale)
            turn_pos = QPoint(*settings.get(settings.turn_indicator_position, (self.sbb_rect.top() - 300, 0)))
            if not self.centralWidget().geometry().contains(turn_pos):
                turn_pos = QPoint(0, 0)
            self.turn_display.move(turn_pos * self.dpi_scale)
            self.turn_display.label.setFont(QFont("Roboto", int(settings.get(settings.turn_display_font_size))))
            self.turn_display.update()
            if settings.get(settings.streaming_mode) and self.stream_overlay is not None:
                self.stream_overlay.set_rect(left, top, right, bottom, dpi)

    def update_hovers(self):
        true_scale = self.scale_factor
        for i in range(len(self.hover_regions)):
            hover = self.hover_regions[i]
            loc = QPoint(38 * true_scale,
                         portrait_location((self.sbb_rect.size() / self.dpi_scale).toTuple()) * self.dpi_scale +
                         hover_distance * i * true_scale +
                         hover_size[1] * true_scale * i)
            hover.move(loc)
            new_size = QSize(*get_hover_size(self.sbb_rect.size().toTuple()))
            hover.resize(new_size)
            hover.background.setFixedSize(new_size)
            hover.enter_hover.connect(lambda y=i: self.show_hide_comp(y, True))
            hover.leave_hover.connect(lambda y=i: self.show_hide_comp(y, False))
        self.update()

    def set_transparency(self):
        alpha = (100 - settings.get(settings.boardcomp_transparency, 0)) / 100
        style = f"background-color: rgba({default_bg_color_rgb}, {alpha});"
        for widget in self.comp_widgets:
            widget.setStyleSheet(style)

        alpha = (100 - settings.get(settings.simulator_transparency, 0)) / 100
        style = f"background-color: rgba({default_bg_color_rgb}, {alpha}); font-size: 17px"
        self.simulation_stats.setStyleSheet(style)

    def toggle_transparency(self):
        if settings.get(settings.streaming_mode):
            self.setWindowFlags(self.windowFlags() | Qt.SubWindow)
        else:
            self.setWindowFlags(Qt.SubWindow)


class StreamerOverlayWindow(OverlayWindow):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowFlags(self.windowFlags() &
                            ~Qt.WindowStaysOnTopHint & ~Qt.SubWindow
                            | Qt.WindowStaysOnBottomHint)
        self.centralWidget().setStyleSheet(
            f"QWidget#overlay {{background-color: {settings.get(settings.stream_overlay_color)} ;}}")
        self.show_button.hide()
        self.setFixedSize(*settings.get(settings.streamer_overlay_size))
        self.disable_hovers()

    def set_transparency(self):
        alpha = 1
        style = f"background-color: rgba({default_bg_color_rgb}, {alpha});"
        for widget in self.comp_widgets:
            widget.setStyleSheet(style)

        alpha = 1
        style = f"background-color: rgba({default_bg_color_rgb}, {alpha}); font-size: 17px"
        self.simulation_stats.setStyleSheet(style)

    def set_rect(self, left, top, right, bottom, dpi):
        super().set_rect(left, top, right, bottom, dpi)
        settings.set_(settings.streamer_overlay_size, self.sbb_rect.size().toTuple())


class SimStatWidget(QFrame):
    def __init__(self, parent, title: QLabel, value: QLabel):
        super().__init__(parent)
        self.title = title
        self.value = value

        layout = QVBoxLayout(self)
        layout.addWidget(title, alignment=Qt.AlignHCenter)
        layout.addWidget(value, alignment=Qt.AlignHCenter)
        layout.setSpacing(20)
        title.setAttribute(Qt.WA_TranslucentBackground)
        title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        value.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(80)
        self.setStyleSheet("background-color: rgba(0,0,0,0%);")


class MovableWidget(QWidget):
    def __init__(self, parent, setting: settings.Setting):
        super().__init__(parent)
        self.setting = setting

    def set_setting(self, setting):
        self.setting = setting

    def mousePressEvent(self, event):
        self._mousePressed = True
        self._mousePos = event.globalPosition().toPoint()
        self._windowPos = self.pos()

    def mouseMoveEvent(self, event):
        if self._mousePressed and (Qt.LeftButton & event.buttons()):
            self.move(self._windowPos +
                      (event.globalPosition().toPoint() - self._mousePos))

    def mouseReleaseEvent(self, event):
        if self.setting:
            settings.set_(self.setting, self.pos().toTuple())


class SimulatorStats(MovableWidget):
    def __init__(self, parent):
        super().__init__(parent, settings.simulator_position)
        self.parent = parent

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

    def update_chances(self, win, tie, loss, win_dmg, loss_dmg, round_num):
        self.win_dmg = str(win_dmg)
        self.win = str(win) + "%"
        self.loss = str(loss) + "%"
        self.tie = str(tie) + "%"
        self.loss_dmg = str(loss_dmg)
        if self.displayable:
            self.update_labels()
        self.displayable = False

    def show_error(self, msg: str, round_num):
        self.error_msg.setText(msg)
        self.layout.setCurrentIndex(1)

    def update_labels(self):
        self.win_dmg_label.setText(self.win_dmg)
        self.win_label.setText(self.win)
        self.loss_label.setText(self.loss)
        self.tie_label.setText(self.tie)
        self.loss_dmg_label.setText(self.loss_dmg)
        self.displayable = True


class TurnDisplay(MovableWidget):
    def __init__(self, parent):
        super().__init__(parent, settings.turn_indicator_position)
        layout = QHBoxLayout(self)
        frame = QFrame(self)
        frame_layout = QHBoxLayout(frame)
        self.label = QLabel("Turn 0 (0.0)", frame)
        frame.setStyleSheet(f"QFrame {{ background-color: {default_bg_color}}};")
        self.label.setFont(QFont("Roboto", int(settings.get(settings.turn_display_font_size))))
        layout.addWidget(frame)
        frame_layout.addWidget(self.label, Qt.AlignVCenter)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSizeConstraint(QLayout.SetMinimumSize)
        frame_layout.setSizeConstraint(QLayout.SetMinimumSize)

    def update_label(self, text):
        self.label.setText(text)


class HoverRegion(QWidget):
    enter_hover = Signal()
    leave_hover = Signal()

    def __init__(self, parent, width, height):
        super().__init__(parent)
        self.background = QWidget(self)
        self.background.setMinimumSize(width, height)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.01);")
        self.setMinimumSize(width, height)

    def enterEvent(self, event):
        self.enter_hover.emit()

    def leaveEvent(self, event):
        self.leave_hover.emit()


class StreamableMatchDisplay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint)
        self.setWindowTitle("SBBTracker Scores")
        self.scores = settings.get(settings.streamable_scores)
        self.label = QLabel("Scores:")
        self.label.setStyleSheet("QLabel { font-size: 50px; background-color: #00FFFF;}")
        self.setCentralWidget(self.label)
        self.update_label()

    def add_score(self, score):
        self.scores.append(score)
        settings.set_(settings.streamable_scores, self.scores)
        self.update_label()

    def update_label(self):
        display_text = "Scores: "
        max_scores = settings.get(settings.streamable_score_max_len)
        for i in range(0, len(self.scores)):
            score = self.scores[i]
            display_text += f"{score} "
            if (i + 1) % max_scores == 0 and i != 0:
                display_text += '\n               '

        self.label.setText(display_text)

    def reset(self):
        self.scores = []
        settings.set_(settings.streamable_scores, [])
        self.update_label()

    def mousePressEvent(self, event):
        self._mousePressed = True
        self._mousePos = event.globalPosition().toPoint()
        self._windowPos = self.pos()

    def mouseMoveEvent(self, event):
        if self._mousePressed and (Qt.LeftButton & event.buttons()):
            self.move(self._windowPos +
                      (event.globalPosition().toPoint() - self._mousePos))