import json
import subprocess
import time
from os.path import expanduser
from pathlib import Path
from urllib.request import urlretrieve

import requests
from packaging import version as vs

from version import __version__


def check_updates():
    update_available = False
    while not update_available:
        r = requests.get("https://api.github.com/repos/SBBTracker/SBBTracker/releases/latest")
        try:
            response = json.loads(r.text)
            tag = response["tag_name"]
            current_version = __version__.replace("v", "")
            update_available = vs.parse(tag) > vs.parse(current_version)
            if update_available:
                return response["body"]
        except:
            print("Couldn't parse github update")
        time.sleep(3600)  # Check for updates every hour


def self_update(progress_handler):
    release_request = requests.get("https://api.github.com/repos/SBBTracker/SBBTracker/releases/latest")
    response = json.loads(release_request.text)
    download_url = None
    for asset in response["assets"]:
        if asset["name"] == "SBBTracker_installer.exe":
            download_url = asset["browser_download_url"]
            break

    if download_url:
        destination = Path(expanduser('~/Downloads')).joinpath("SBBTracker_installer.exe")
        download = urlretrieve(download_url, destination, progress_handler)
        subprocess.Popen(f'{destination} /SILENT /RESTARTAPPLICATIONS')


