import json
import logging
import os
import subprocess
import platform
import time
from os.path import expanduser
from pathlib import Path
from urllib.request import urlretrieve

import requests
from packaging import version as vs

from version import __version__

os_name = platform.system()


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
            logging.error("Couldn't parse github update")
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
        download_folder = Path('/tmp') if os_name == "Linux" else Path(os.environ["LOCALAPPDATA"]).joinpath("Temp")
        destination = download_folder.joinpath("SBBTracker_installer.exe")
        try:
            download = urlretrieve(download_url, destination, progress_handler)
            subprocess.Popen(f'{destination} /SILENT /RESTARTAPPLICATIONS')
        except Exception as e:
            logging.error(e)
    else:
        logging.warning("Couldn't find the .exe to download from the release page")


