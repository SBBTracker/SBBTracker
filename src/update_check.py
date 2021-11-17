import json
import time

import requests
from packaging import version as vs

from version import __version__


def run():
    update_available = False
    while not update_available:
        r = requests.get("https://api.github.com/repos/SBBTracker/SBBTracker/releases/latest")
        response = json.loads(r.text)
        tag = response["tag_name"]
        current_version = __version__.replace("v", "")
        update_available = vs.parse(tag) > vs.parse(current_version)
        if update_available:
            break
        time.sleep(3600)  # Check for updates every hour
