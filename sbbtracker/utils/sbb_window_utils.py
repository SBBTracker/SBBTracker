import time

from PySide6.QtCore import QThread, Signal

try:
    from win32gui import GetForegroundWindow, GetClientRect, FindWindow, ClientToScreen
    from win32api import MonitorFromPoint
    from ctypes import windll
except:
    pass
from sbbtracker.paths import os_name


def get_sbb_window():
    return FindWindow("UnityWndClass", "Storybook Brawl")


def get_overlay_window():
    return FindWindow(None, "SBBTrackerOverlay")


def get_tracker_window():
    return FindWindow(None, "SBBTracker")


def get_settings_window():
    return FindWindow(None, "SBBTracker Settings")


def sbb_is_visible():
    current_window = GetForegroundWindow()
    sbb_window = get_sbb_window()
    return (current_window == sbb_window) or (current_window == get_overlay_window()) and sbb_window != 0


def get_sbb_rect():
    window = get_sbb_window()
    scale = get_sbb_scale()
    if window != 0:
        try:
            rect = GetClientRect(get_sbb_window())
            (left, top) = ClientToScreen(window, (rect[0], rect[1]))
            (right, bottom) = ClientToScreen(window, (rect[2], rect[3]))
            return left, top, right, bottom, scale
        except:
            pass
    else:
        return -1, -1, -1, -1, scale


def get_sbb_scale():
    window = get_sbb_window()
    user32 = windll.user32
    if hasattr(user32, 'GetDpiForWindow'):
        return user32.GetDpiForWindow(window) if window != 0 else 96
    else:
        return 96


class SBBWindowCheckThread(QThread):
    changed_foreground = Signal(bool)
    changed_rect = Signal(int, int, int, int, int)

    def __init__(self):
        super(SBBWindowCheckThread, self).__init__()

    def run(self):
        if "Windows" == os_name:
            prev_visible = sbb_is_visible
            prev_rect = get_sbb_rect()
            self.changed_rect.emit(*prev_rect)
            self.changed_foreground.emit(prev_visible)  # find out on startup whether to show the overlay or not
            while True:
                visible = sbb_is_visible()
                current_rect = get_sbb_rect()

                if visible != prev_visible:
                    self.changed_foreground.emit(visible)

                if current_rect != prev_rect and current_rect != (-1, -1, -1, -1, 96):
                    self.changed_rect.emit(*current_rect)
                prev_visible = visible
                prev_rect = current_rect
                time.sleep(0.5)

