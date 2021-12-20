import time

from PySide6.QtCore import QThread, Signal
from win32gui import GetWindowText, GetForegroundWindow, IsWindowVisible, FindWindow


def get_sbb_window():
    return FindWindow(None, "Storybook Brawl")


def get_overlay_window():
    return FindWindow(None, "SBBTrackerOverlay")


def get_tracker_window():
    return FindWindow(None, "SBBTracker")


def get_settings_window():
    return FindWindow(None, "SBBTracker Settings")


class SBBWindowCheckThread(QThread):
    changed_foreground = Signal(bool)

    def __init__(self):
        super(SBBWindowCheckThread, self).__init__()

    def run(self):
        prev_visible = False
        while True:
            current_window = GetForegroundWindow()
            visible = (current_window == get_sbb_window()) or (current_window == get_overlay_window()) or \
                      (current_window == get_tracker_window()) or (current_window == get_settings_window())
            if visible != prev_visible:
                self.changed_foreground.emit(visible)
            prev_visible = visible
            time.sleep(0.5)

