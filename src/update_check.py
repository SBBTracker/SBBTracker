import time

import requests
import json
from version import __version__
from packaging import version as vs


def run(window):
    update_available = False
    while not update_available:
        r = requests.get("https://api.github.com/repos/SBBTracker/SBBTracker/releases/latest")
        response = json.loads(r.text)
        tag = response["tag_name"]
        current_version = __version__.replace("v", "")
        update_available = vs.parse(tag) > vs.parse(current_version)
        if update_available:
            window.write_event_value("GITHUB-UPDATE", "https://github.com/SBBTracker/SBBTracker/releases/latest")
        time.sleep(3600)  # Check for updates every hour
