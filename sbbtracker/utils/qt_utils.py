from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from sbbtracker.languages import tr


def open_url(parent, url_string: str):
    url = QUrl(url_string)
    if not QDesktopServices.openUrl(url):
        QMessageBox.warning(parent, tr('Open Url'), tr('Could not open url'))