import logging
import multiprocessing
import sys

import matplotlib

from sbbtracker.windows.constants import default_bg_color
from sbbtracker.windows.main_windows import SBBTracker

matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

import seaborn as sns
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox, QSplashScreen,
)
from qt_material import apply_stylesheet


from sbbtracker import stats, settings, paths
from sbbtracker.utils import asset_utils


logging.basicConfig(filename=paths.sbbtracker_folder.joinpath("sbbtracker.log"), filemode="w",
                    format='%(name)s - %(levelname)s - %(message)s', level=logging.WARNING)
logging.getLogger().addHandler(logging.StreamHandler())

DEBUG = False

sns.set_style("darkgrid", {"axes.facecolor": default_bg_color})

plt.rcParams.update({'text.color': "white",
                     'xtick.color': 'white',
                     'ytick.color': 'white',
                     'figure.facecolor': default_bg_color,
                     'axes.labelcolor': "white"})


def main():
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    pixmap = QPixmap(asset_utils.get_asset("icon.png"))
    splash = QSplashScreen(pixmap)
    splash.show()

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

    stats.backup_stats()

    # TODO: uncomment this when the updater doesn't require input

    #     if settings.silent_updates not in settings:
    #         reply = QMessageBox.question(None, "Enable silent updates?",
    #                                      f"""Would you like to enable silent updates?
    # This will allow the application to update automatically
    # when you open it (if there's an update).
    #
    # You can change this setting at any time at:
    # settings > Updates > Enable silent updates
    # """)
    #         settings.set(settings.silent_updates, reply == QMessageBox.Yes)
    #         settings.save()

    if settings.get(settings.prompt_data_collection) and not settings.get(settings.upload_data):
        settings.set_(settings.prompt_data_collection, False)
        reply = QMessageBox.question(None, "Opt-in to data collection?",
                                     """Would you like to opt into to data collection?
This enables you to upload your matches to sbbtracker.com
and contribute to the community dataset.

Things that are currently collected:
* Your steam name (this is not shared)
* Board states
* Placement
* Hero, Health, and XP
* Net MMR

This may include more game-related information as we improve
our ability to collect it.

This info may be shared as part of the public dataset.

For a full privacy policy, please visit sbbtracker.com/privacy.

You may change your selection at any time at Settings > Data > Upload Matches""")
        settings.set_(settings.upload_data, reply == QMessageBox.Yes)
        settings.save()

    main_window = SBBTracker()
    main_window.show()
    splash.finish(main_window)
    if settings.get(settings.show_patch_notes, False):
        main_window.show_patch_notes()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
